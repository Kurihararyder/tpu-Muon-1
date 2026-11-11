"""比對 RTL 輸出（sim/out_rtl.hex）：
  1. 與位元精確整數模型（data/vec_exp.hex）必須逐位元一致；
  2. 與 float64 黃金模型（data/vec_float.npy）比較，報告最大／平均絕對誤差與輸出奇異值範圍。
全零矩陣輸出必須為 0。回傳碼 0 = 通過。"""
import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
N = 8
# 對 float64 黃金模型的絕對誤差上限：一般矩陣 0.02，病態矩陣放寬（階段 B：條件數 1e5 時約 0.05）
TOL_NORMAL, TOL_ILL = 0.02, 0.10


def read_hex(path, w):
    v = np.array([int(x, 16) for x in Path(path).read_text().split()], dtype=np.int64)
    return np.where(v >= 1 << (w - 1), v - (1 << w), v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=int, default=16)
    ap.add_argument("--f", type=int, default=13)
    ap.add_argument("--suffix", default="")
    ap.add_argument("--out", default=str(ROOT / "sim" / "out_rtl.hex"))
    a = ap.parse_args()
    F = a.f
    rtl = read_hex(a.out, a.w).reshape(-1, N * N)
    exp = read_hex(ROOT / "data" / f"vec_exp{a.suffix}.hex", a.w).reshape(-1, N * N)
    ref = np.load(ROOT / "data" / f"vec_float{a.suffix}.npy")
    names = (ROOT / "data" / f"vec_names{a.suffix}.txt").read_text(encoding="utf-8").split()
    assert rtl.shape == exp.shape == ref.shape, (rtl.shape, exp.shape, ref.shape)

    print("| 案例 | 與位元精確模型 | 對 float64 最大誤差 | 對 float64 平均誤差 | 輸出奇異值範圍 |")
    print("|---|---|---|---|---|")
    ok = True
    for n, name in enumerate(names):
        exact = np.array_equal(rtl[n], exp[n])
        out = rtl[n].reshape(N, N) / 2 ** F
        d = np.abs(out - ref[n].reshape(N, N))
        sv = np.linalg.svd(out, compute_uv=False)
        tol = TOL_ILL if name.startswith(("illcond", "rank1", "diagonal", "all_ones", "sparse")) else TOL_NORMAL
        # 只有 W >= 16 的格式才強制對 float64 的誤差上限；較窄的位寬（例如 12 位元）以位元一致為通過條件，誤差僅列出
        good = exact and (a.w < 16 or d.max() <= tol)
        if name == "zeros":
            good = good and not rtl[n].any()
        ok &= good
        print(f"| {name} | {'一致' if exact else '**不一致**'} | {d.max():.2e} | {d.mean():.2e} "
              f"| {sv.min():.3f}～{sv.max():.3f} |{'' if good else ' ← 未通過'}")
    print("\n比對結果：", "全部通過" if ok else "有未通過項目")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
