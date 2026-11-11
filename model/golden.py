"""Muon 最佳化器核心運算的 Python 黃金模型：五次 Newton-Schulz 正交化。

此檔為整個專案的數值基準，RTL 的輸出都與它比對。
"""
import numpy as np

A_COEF, B_COEF, C_COEF = 3.4445, -4.7750, 2.0315


def newton_schulz5(G, steps=5, eps=1e-7):
    """輸入梯度矩陣 G，回傳近似正交矩陣（奇異值約 0.7～1.2）。"""
    X = G.astype(np.float64)
    X = X / (np.linalg.norm(X) + eps)  # Frobenius norm 縮放，奇異值 <= 1
    transposed = X.shape[0] > X.shape[1]
    if transposed:
        X = X.T
    for _ in range(steps):
        A = X @ X.T
        B = B_COEF * A + C_COEF * (A @ A)
        X = A_COEF * X + B @ X
    if transposed:
        X = X.T
    return X


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    G = rng.standard_normal((8, 8))
    O = newton_schulz5(G)
    print("輸出奇異值：", np.linalg.svd(O, compute_uv=False))  # 預期約 0.7 ~ 1.2
