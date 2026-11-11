"""RTL 的位元精確整數模型（預設：Q3.13 資料、Q4.12 係數、32 位元累加器）。

與 rtl/ 的資料路徑一一對應：
  norm_scale：X0 = Q( g * s )，g 為 Q?.GF 整數，s 為無號 Q?.SF 整數，輸出 W 位元、小數 F 位
  matmul_core：A、AA、B、X' 各自以「整數累加 -> 加 0.5 LSB -> 右移 F 位 -> 飽和」寫回
全部使用 numpy int64 做精確整數運算（算術右移等同 floor），沒有任何浮點。
位寬可由 Cfg 改變（階段 E 的位寬比較實驗用）：係數固定為 Q4.CF（CW = CF + 4）。
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Cfg:
    W: int = 16       # 資料位寬
    F: int = 13       # 資料小數位寬
    CF: int = 12      # 係數小數位寬（係數位寬 CW = CF + 4）
    ACCW: int = 32    # 累加器位寬
    GW: int = 16      # 輸入 G 位寬
    GF: int = 12      # 輸入 G 小數位寬
    SW: int = 20      # scale 位寬（無號）
    SF: int = 16      # scale 小數位寬

    @property
    def CW(self):
        return self.CF + 4

    @property
    def coefs(self):
        return tuple(int(np.floor(v * 2 ** self.CF + 0.5)) for v in (3.4445, -4.7750, 2.0315))


DEFAULT = Cfg()
# 預設格式的模組層級別名（供舊腳本使用）
W, F, CF, GF, SW, SF, ACCW = DEFAULT.W, DEFAULT.F, DEFAULT.CF, DEFAULT.GF, DEFAULT.SW, DEFAULT.SF, DEFAULT.ACCW
COEF_A, COEF_B, COEF_C = DEFAULT.coefs


def sat(v, width=16):
    return np.clip(v, -(1 << (width - 1)), (1 << (width - 1)) - 1)


def rnd_sat(acc, sh, width):
    """加 0.5 LSB、算術右移、飽和（與 RTL 的 q 完全相同）。"""
    return sat((acc + (1 << (sh - 1))) >> sh, width)


def quantize_g(G, cfg=DEFAULT):
    """主機端：把浮點 G 量化成 Q?.GF 整數（四捨五入、飽和在 GW 位元內）。"""
    return sat(np.floor(np.asarray(G, dtype=np.float64) * 2 ** cfg.GF + 0.5).astype(np.int64), cfg.GW)


def scale_int(G, cfg=DEFAULT, eps=1e-7):
    """主機端：scale = 1 / (||G||_F + eps)，量化成無號整數（飽和在 SW 位元內）。"""
    s = 1.0 / (np.linalg.norm(G) + eps)
    return int(np.clip(np.floor(s * 2 ** cfg.SF + 0.5), 0, (1 << cfg.SW) - 1))


def norm_scale(g_int, s_int, cfg=DEFAULT):
    """norm_scale 模組的整數模型。"""
    return rnd_sat(np.asarray(g_int, dtype=np.int64) * int(s_int), cfg.GF + cfg.SF - cfg.F, cfg.W)


def ns_int(x0, steps=5, cfg=DEFAULT):
    """matmul_core + ns_ctrl 的整數模型；x0 為資料格式的整數矩陣。回傳 (輸出, 累加器溢位次數)。"""
    ca, cb, cc = cfg.coefs
    shl = cfg.F - cfg.CF
    X = np.asarray(x0, dtype=np.int64)
    lim = 1 << (cfg.ACCW - 1)
    ovf = 0

    def chk(acc):
        nonlocal ovf
        ovf += int(((acc >= lim) | (acc < -lim)).sum())
        return acc

    def q(acc):
        return rnd_sat(acc, cfg.F, cfg.W)   # 累加器小數 2F -> 儲存小數 F，右移 F 位

    for _ in range(steps):
        A = q(chk(X @ X.T))
        AA = q(chk(A @ A.T))                    # A 對稱，故 A@A == A@A.T（RTL 以列內積計算）
        B = q(chk(((cb * A) << shl) + ((cc * AA) << shl)))
        X = q(chk(B @ X + ((ca * X) << shl)))
    return X, ovf


def run_from_float(G, steps=5, cfg=DEFAULT):
    """端到端：浮點 G -> 整數 G + scale -> norm_scale -> ns_int。回傳 (輸出整數, g_int, s_int)。"""
    g, s = quantize_g(G, cfg), scale_int(G, cfg)
    out, _ = ns_int(norm_scale(g, s, cfg), steps, cfg)
    return out, g, s


if __name__ == "__main__":
    print("係數整數（Q4.12）：a =", COEF_A, " b =", COEF_B, " c =", COEF_C)
    for c in (Cfg(W=12, F=9, CF=9, ACCW=24), Cfg(W=24, F=19, CF=18, ACCW=44)):
        print(f"W={c.W} F={c.F} CF={c.CF} CW={c.CW} ACCW={c.ACCW} 係數 =", c.coefs)
