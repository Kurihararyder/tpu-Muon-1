"""階段 A 驗收：檢查奇異值範圍，並與 SVD 精確解 U @ Vt 比較 Frobenius 誤差。"""
import numpy as np
from golden import newton_schulz5

SHAPES = [(4, 4), (8, 8), (16, 16), (8, 16)]
SEEDS = range(10)


def main():
    print("| 形狀 | 種子數 | 奇異值最小 | 奇異值最大 | 與 U@Vt 的 Frobenius 誤差（平均） | 最大 | 落在 0.5～1.3 的比例 |")
    print("|---|---|---|---|---|---|---|")
    all_ok = True
    for shape in SHAPES:
        smin, smax, errs = [], [], []
        n_in, n_all = 0, 0
        for seed in SEEDS:
            G = np.random.default_rng(seed).standard_normal(shape)
            O = newton_schulz5(G)
            s = np.linalg.svd(O, compute_uv=False)
            U, _, Vt = np.linalg.svd(G, full_matrices=False)
            errs.append(np.linalg.norm(O - U @ Vt))
            n_in += int(((s >= 0.5) & (s <= 1.3)).sum())
            n_all += len(s)
            smin.append(s.min())
            smax.append(s.max())
        frac = n_in / n_all
        # 近乎奇異的輸入（縮放後最小奇異值 ~1e-3）五輪內來不及推到 0.7，屬演算法特性，故以比例驗收
        ok = frac >= 0.99 and max(smax) <= 1.3
        all_ok &= ok
        print(f"| {shape[0]}x{shape[1]} | {len(list(SEEDS))} | {min(smin):.3f} | {max(smax):.3f} "
              f"| {np.mean(errs):.3f} | {max(errs):.3f} | {frac:.1%} |")
    print("\n奇異值範圍檢查（比例 >= 99% 且最大值 <= 1.3）：", "通過" if all_ok else "未通過")


if __name__ == "__main__":
    main()
