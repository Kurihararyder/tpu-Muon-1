"""階段 B：數值格式評估（浮點 FP32／bf16／FP16 與 16 位元定點 Q4.12／Q8.8／Q2.14）。

量化規則（盡量貼近之後的 RTL 資料路徑）：
  * 浮點：每次乘法與加法之後都量化（模擬各自格式的運算單元）。
  * 定點：資料以 W 位元（F 位小數）儲存；乘積先截到累加器的小數位寬 accf 再累加，
    累加器為 acc_bits 位元；每個矩陣運算的結果寫回儲存格式時才做一次量化（含飽和）。
  * 係數 a、b、c 為常數暫存器：定點一律用 Q4.12（16 位元）表示；浮點則用該格式本身表示。
  * 縮放 X = G / ||G|| 假設由外部先算好，輸入到資料路徑時先量化成儲存格式。
輸出：docs/format_results.md（表格），供 docs/format_study.md 引用。
"""
import sys
from pathlib import Path

import numpy as np

from golden import A_COEF, B_COEF, C_COEF, newton_schulz5

COEF_F = 12  # 定點係數的小數位寬（Q4.12）


# ---------------------------------------------------------------- 量化函式
def qgrid(x, f, mode):
    """量化到 2^-f 的格點。round：四捨五入（偏向正無窮，等同加 0.5 再捨去）；trunc：位元截斷（floor）。"""
    s = 2.0 ** f
    if mode == "round":
        return np.floor(x * s + 0.5) / s
    return np.floor(x * s) / s


class Stats:
    def __init__(self):
        self.sat = 0          # 儲存格式飽和次數
        self.acc_sat = 0      # 累加器飽和次數
        self.acc_max = 0.0    # 累加器內最大絕對值


def qfix(x, w, f, mode, st):
    v = qgrid(x, f, mode)
    hi = (2.0 ** (w - 1) - 1) / 2.0 ** f
    lo = -(2.0 ** (w - 1)) / 2.0 ** f
    st.sat += int(((v > hi) | (v < lo)).sum())
    return np.clip(v, lo, hi)


def qfloat(x, mbits, emin, emax, mode):
    """通用浮點量化：mbits 尾數位數（不含隱藏位）、emin／emax 為最小／最大指數；含次正規數與飽和。"""
    x = np.asarray(x, dtype=np.float64)
    _, e = np.frexp(x)
    e_eff = np.maximum(e, emin + 1)
    ulp = 2.0 ** (e_eff - 1 - mbits)
    q = x / ulp
    q = np.rint(q) if mode == "round" else np.trunc(q)
    out = q * ulp
    mx = (2.0 - 2.0 ** -mbits) * 2.0 ** emax
    return np.clip(out, -mx, mx)


# ---------------------------------------------------------------- 格式定義
class Fmt:
    def __init__(self, name, kind, **kw):
        self.name, self.kind = name, kind
        self.__dict__.update(kw)

    def accf(self, acc_bits):
        """累加器小數位寬：保留儲存整數位 + 3 位保護位（8 項相加）；最多保留完整乘積的 2F 位。"""
        int_bits = self.w - self.f
        return min(2 * self.f, acc_bits - (int_bits + 3))


FORMATS = [
    Fmt("FP32", "float", mbits=23, emin=-126, emax=127),
    Fmt("bf16", "float", mbits=7, emin=-126, emax=127),
    Fmt("FP16", "float", mbits=10, emin=-14, emax=15),
    Fmt("Q4.12", "fix", w=16, f=12),
    Fmt("Q8.8", "fix", w=16, f=8),
    Fmt("Q2.14", "fix", w=16, f=14),
    Fmt("Q3.13（附加）", "fix", w=16, f=13),
]


# ---------------------------------------------------------------- 浮點資料路徑
def ns_float(G, fmt, mode, steps=5, eps=1e-7):
    q = lambda v: qfloat(v, fmt.mbits, fmt.emin, fmt.emax, mode)

    def mm(P, Q):
        acc = np.zeros((P.shape[0], Q.shape[1]))
        for k in range(P.shape[1]):
            acc = q(acc + q(P[:, k:k + 1] * Q[k:k + 1, :]))
        return acc

    a, b, c = q(A_COEF), q(B_COEF), q(C_COEF)
    X = q(G / (np.linalg.norm(G) + eps))
    tr = X.shape[0] > X.shape[1]
    if tr:
        X = X.T
    for _ in range(steps):
        A = mm(X, X.T)
        AA = mm(A, A)
        B = q(q(b * A) + q(c * AA))
        X = q(q(a * X) + mm(B, X))
    return X.T if tr else X


# ---------------------------------------------------------------- 定點資料路徑
def ns_fix(G, fmt, mode, acc_bits=32, steps=5, eps=1e-7, x0=None):
    st = Stats()
    w, f = fmt.w, fmt.f
    accf = fmt.accf(acc_bits)
    acc_int = acc_bits - accf
    acc_hi = 2.0 ** (acc_int - 1)  # 累加器可表示的絕對值上限（不含）
    cq = lambda v: qgrid(v, COEF_F, "round")
    a, b, c = cq(A_COEF), cq(B_COEF), cq(C_COEF)

    def pacc(p):  # 乘積截到累加器小數位寬
        return qgrid(p, accf, mode)

    def finish(s):  # 累加結果：檢查累加器範圍，再寫回儲存格式
        st.acc_max = max(st.acc_max, float(np.abs(s).max()))
        over = np.abs(s) >= acc_hi
        st.acc_sat += int(over.sum())
        s = np.clip(s, -acc_hi, acc_hi - 2.0 ** -accf)
        return qfix(s, w, f, mode, st)

    def mmsum(P, Q):  # 矩陣乘積在累加器內的和（尚未寫回）
        return pacc(P[:, :, None] * Q[None, :, :]).sum(axis=1)

    # x0：直接指定已量化的 X0（供與 RTL 位元精確模型交叉驗證用）；未指定時由 G 縮放後量化
    X = qfix(G / (np.linalg.norm(G) + eps), w, f, mode, st) if x0 is None else np.asarray(x0, dtype=np.float64)
    tr = X.shape[0] > X.shape[1]
    if tr:
        X = X.T
    for _ in range(steps):
        A = finish(mmsum(X, X.T))
        AA = finish(mmsum(A, A))
        B = finish(pacc(b * A) + pacc(c * AA))
        X = finish(mmsum(B, X) + pacc(a * X))
    return (X.T if tr else X), st


def run(G, fmt, mode, acc_bits=32):
    if fmt.kind == "float":
        return ns_float(G, fmt, mode), None
    return ns_fix(G, fmt, mode, acc_bits)


# ---------------------------------------------------------------- 測試資料
def make_cases(n=8):
    rng = np.random.default_rng(2026)
    rand = [rng.standard_normal((n, n)) for _ in range(20)]
    ill = []
    for cond in (1e1, 1e2, 1e3, 1e4, 1e5):
        U, _ = np.linalg.qr(rng.standard_normal((n, n)))
        V, _ = np.linalg.qr(rng.standard_normal((n, n)))
        ill.append(U @ np.diag(np.logspace(0, -np.log10(cond), n)) @ V.T)
    return rand, ill


def range_analysis(cases, steps=5):
    """用 float64 追蹤各中間值的最大絕對值，決定所需整數位數。"""
    mx = dict(X=0, A=0, AA=0, B=0, BX=0, Xnew=0)
    for G in cases:
        X = G / (np.linalg.norm(G) + 1e-7)
        for _ in range(steps):
            A = X @ X.T
            AA = A @ A
            B = B_COEF * A + C_COEF * AA
            BX = B @ X
            Xn = A_COEF * X + BX
            for k, v in zip(mx, (X, A, AA, B, BX, Xn)):
                mx[k] = max(mx[k], float(np.abs(v).max()))
            X = Xn
    return mx


def evaluate(cases, fmt, mode, acc_bits=32):
    errs_max, errs_mean, smin, smax, sat, accsat, accmax = [], [], [], [], 0, 0, 0.0
    for G in cases:
        ref = newton_schulz5(G)
        out, st = run(G, fmt, mode, acc_bits)
        d = np.abs(out - ref)
        errs_max.append(d.max())
        errs_mean.append(d.mean())
        s = np.linalg.svd(out, compute_uv=False)
        smin.append(s.min())
        smax.append(s.max())
        if st:
            sat += st.sat
            accsat += st.acc_sat
            accmax = max(accmax, st.acc_max)
    return dict(max=max(errs_max), mean=float(np.mean(errs_mean)), smin=min(smin), smax=max(smax),
                sat=sat, accsat=accsat, accmax=accmax)


def row(fmt, mode, r):
    sat = "—" if fmt.kind == "float" else f"{r['sat']}"
    return (f"| {fmt.name} | {'四捨五入' if mode == 'round' else '截斷'} | {r['max']:.2e} | {r['mean']:.2e} "
            f"| {r['smin']:.3f}～{r['smax']:.3f} | {sat} |")


def main():
    rand, ill = make_cases()
    out = []
    P = lambda s="": (out.append(s), print(s))

    # 零矩陣與單位矩陣（檢查除以零與基本行為）
    P("## 特殊輸入檢查\n")
    P("| 格式 | 零矩陣輸出最大絕對值 | 單位矩陣誤差（對黃金模型最大絕對差） |")
    P("|---|---|---|")
    Z, I = np.zeros((8, 8)), np.eye(8)
    for fmt in FORMATS:
        oz, _ = run(Z, fmt, "round")
        oi, _ = run(I, fmt, "round")
        P(f"| {fmt.name} | {np.abs(oz).max():.1e} | {np.abs(oi - newton_schulz5(I)).max():.2e} |")

    P("\n## 各中間值最大範圍（float64，20 組隨機 + 5 組病態矩陣，8x8，5 輪）\n")
    mx = range_analysis(rand + ill)
    P("| 變數 | 最大絕對值 | 所需整數位（含符號） |")
    P("|---|---|---|")
    for k, v in mx.items():
        P(f"| {k} | {v:.3f} | {int(np.floor(np.log2(max(v, 1e-9)))) + 2 if v >= 1 else 1} |")

    P("\n## 隨機矩陣（20 組 8x8）：各格式對 float64 黃金模型的誤差\n")
    P("| 格式 | 取捨 | 最大絕對誤差 | 平均絕對誤差 | 輸出奇異值範圍 | 儲存飽和次數 |")
    P("|---|---|---|---|---|---|")
    for fmt in FORMATS:
        for mode in ("round", "trunc"):
            P(row(fmt, mode, evaluate(rand, fmt, mode)))

    P("\n## 病態矩陣（5 組，條件數 1e1～1e5）\n")
    P("| 格式 | 取捨 | 最大絕對誤差 | 平均絕對誤差 | 輸出奇異值範圍 | 儲存飽和次數 |")
    P("|---|---|---|---|---|---|")
    for fmt in FORMATS:
        for mode in ("round", "trunc"):
            P(row(fmt, mode, evaluate(ill, fmt, mode)))

    P("\n## 累加器位寬（定點、四捨五入、隨機 + 病態矩陣）\n")
    P("| 格式 | 累加器位元 | 累加器小數位 | 累加器最大絕對值 | 累加器飽和 | 最大絕對誤差 | 平均絕對誤差 |")
    P("|---|---|---|---|---|---|---|")
    for fmt in FORMATS:
        if fmt.kind != "fix":
            continue
        for ab in (24, 32):
            r = evaluate(rand + ill, fmt, "round", ab)
            P(f"| {fmt.name} | {ab} | {fmt.accf(ab)} | {r['accmax']:.3f} | {r['accsat']} "
              f"| {r['max']:.2e} | {r['mean']:.2e} |")

    Path(__file__).resolve().parent.parent.joinpath("docs", "format_results.md").write_text(
        "# 數值格式評估結果（由 model/format_eval.py 自動產生）\n\n" + "\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
