"""產生階段 D 的測試向量（寫入 data/；每次執行會覆蓋同名檔案，不會動到其他檔名）。

檔案：
  data/vec_in.hex     每組 65 行：第 1 行 scale（5 位十六進位，Q4.16），其後 64 行 G（4 位十六進位，Q4.12 二補數）
  data/vec_exp.hex    每組 64 行：位元精確整數模型的預期輸出（Q3.13，4 位十六進位）
  data/vec_float.npy  每組 64 個 float64：未量化的 float64 黃金模型輸出（比對誤差用）
  data/vec_names.txt  每組的名稱
"""
import argparse
from pathlib import Path

import numpy as np

from fixed_model import Cfg, ns_int, norm_scale, quantize_g, scale_int
from golden import newton_schulz5

N = 8
DATA = Path(__file__).resolve().parent.parent / "data"


def cases():
    rng = np.random.default_rng(20261111)
    out = [("zeros", np.zeros((N, N))), ("identity", np.eye(N))]
    for s in range(8):
        out.append((f"random_{s}", rng.standard_normal((N, N))))
    for cond in (1e1, 1e2, 1e3, 1e4, 1e5):
        U, _ = np.linalg.qr(rng.standard_normal((N, N)))
        V, _ = np.linalg.qr(rng.standard_normal((N, N)))
        out.append((f"illcond_{cond:.0e}", U @ np.diag(np.logspace(0, -np.log10(cond), N)) @ V.T))
    out.append(("small_scale_0.01", 0.01 * rng.standard_normal((N, N))))
    out.append(("rank1", np.outer(rng.standard_normal(N), rng.standard_normal(N))))
    out.append(("diagonal", np.diag(rng.uniform(0.2, 3.0, N))))
    out.append(("all_ones", np.ones((N, N))))
    out.append(("sparse", np.where(rng.random((N, N)) < 0.15, rng.standard_normal((N, N)), 0.0)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--w", type=int, default=16)
    ap.add_argument("--f", type=int, default=13)
    ap.add_argument("--cf", type=int, default=12)
    ap.add_argument("--accw", type=int, default=32)
    ap.add_argument("--suffix", default="", help="輸出檔名尾碼（預設格式為空字串）")
    a = ap.parse_args()
    cfg = Cfg(W=a.w, F=a.f, CF=a.cf, ACCW=a.accw)
    sfx, hd = a.suffix, (a.w + 3) // 4
    DATA.mkdir(exist_ok=True)
    names, vin, vexp, vfloat = [], [], [], []
    for name, G in cases():
        g, s = quantize_g(G, cfg), scale_int(G, cfg)
        out, ovf = ns_int(norm_scale(g, s, cfg), 5, cfg)
        assert ovf == 0, f"{name}：累加器溢位"
        names.append(name)
        vin.append(f"{s:05x}")
        vin += [f"{int(v) & 0xFFFF:04x}" for v in g.reshape(-1)]
        vexp += [f"{int(v) & ((1 << a.w) - 1):0{hd}x}" for v in out.reshape(-1)]
        vfloat.append(newton_schulz5(G).reshape(-1))
    (DATA / f"vec_in{sfx}.hex").write_text("\n".join(vin) + "\n")
    (DATA / f"vec_exp{sfx}.hex").write_text("\n".join(vexp) + "\n")
    (DATA / f"vec_names{sfx}.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    np.save(DATA / f"vec_float{sfx}.npy", np.array(vfloat))
    print(f"已產生 {len(names)} 組測試向量於 {DATA}")


if __name__ == "__main__":
    main()
