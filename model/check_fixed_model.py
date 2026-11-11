"""交叉驗證：整數模型（fixed_model.py）必須與浮點實作的定點模型（format_eval.ns_fix）位元一致，
並量測整條 RTL 路徑（含 Q4.12 輸入量化與 scale 量化）對 float64 黃金模型的誤差。"""
import numpy as np

from golden import newton_schulz5
from fixed_model import (COEF_A, COEF_B, COEF_C, F, ns_int, norm_scale, quantize_g, run_from_float,
                         scale_int)
from format_eval import FORMATS, ns_fix


def main():
    q313 = next(f for f in FORMATS if f.name.startswith("Q3.13"))
    print(f"係數：a={COEF_A} b={COEF_B} c={COEF_C}")

    rng = np.random.default_rng(7)
    n_ok, n_all = 0, 0
    # (1) 位元一致性：同一個 X0 餵給兩個模型
    for _ in range(200):
        G = rng.standard_normal((8, 8)) * rng.choice([0.1, 1, 10])
        x0 = norm_scale(quantize_g(G), scale_int(G))
        out_i, ovf = ns_int(x0)
        out_f, st = ns_fix(None, q313, "round", 32, x0=x0 / 2 ** F)
        n_all += 1
        n_ok += int(np.array_equal(out_i, np.rint(out_f * 2 ** F).astype(np.int64)) and ovf == 0 and st.acc_sat == 0)
    print(f"整數模型 vs 浮點實作定點模型：{n_ok}/{n_all} 組位元一致")
    assert n_ok == n_all

    # (2) 整條路徑對 float64 黃金模型的誤差
    errs_max, errs_mean = [], []
    for seed in range(20):
        G = np.random.default_rng(seed).standard_normal((8, 8))
        out, _, _ = run_from_float(G)
        d = np.abs(out / 2 ** F - newton_schulz5(G))
        errs_max.append(d.max())
        errs_mean.append(d.mean())
    print(f"整條 RTL 路徑（20 組隨機 8x8）對 float64：最大絕對誤差 {max(errs_max):.2e}，"
          f"平均絕對誤差 {np.mean(errs_mean):.2e}")
    print("（階段 B 的純 Q3.13 評估：最大 6.10e-03，平均 4.61e-04）")


if __name__ == "__main__":
    main()
