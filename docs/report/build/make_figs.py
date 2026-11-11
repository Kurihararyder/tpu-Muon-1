"""產生實驗報告與簡報用的圖表（matplotlib）。資料來自 flow/summary.json 與階段 B 的評估結果。
色盤：dataviz 參考色盤前三個類別色（藍、橘、青綠），中性灰作為對照。"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, NullFormatter
from matplotlib import font_manager as fm

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "report" / "figs"
fm.fontManager.addfont("/mnt/c/Windows/Fonts/msjh.ttc")
fm.fontManager.addfont("/mnt/c/Windows/Fonts/msjhbd.ttc")
plt.rcParams.update({"font.family": "Microsoft JhengHei", "axes.unicode_minus": False, "font.size": 12,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#8a8984",
                     "axes.labelcolor": "#52514e", "xtick.color": "#52514e", "ytick.color": "#52514e",
                     "text.color": "#0b0b0b", "figure.facecolor": "white", "axes.facecolor": "white",
                     "grid.color": "#e6e5e1", "grid.linewidth": 0.8})
BLUE, ORANGE, AQUA, YELLOW, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#b9b8b2"
S = {r["variant"]: r for r in json.load(open(ROOT / "flow" / "summary.json"))}


def save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


# ---- 圖 1：數值格式誤差（階段 B，20 組隨機 8x8，四捨五入）
def fig_format():
    fmts = ["FP32", "Q3.13（選定）", "Q4.12", "FP16", "Q8.8", "bf16", "Q2.14"]
    mean = [1.92e-7, 4.61e-4, 7.15e-4, 2.44e-3, 1.05e-2, 1.84e-2, 1.86]
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    cols = [GRAY, BLUE, GRAY, GRAY, GRAY, GRAY, ORANGE]
    y = range(len(fmts))[::-1]
    ax.barh(list(y), mean, color=cols, height=0.62)
    ax.set_xscale("log")
    ax.set_yticks(list(y)); ax.set_yticklabels(fmts)
    for yy, v, f in zip(y, mean, fmts):
        lab = f"{v:.1e}" + ("  （範圍 ±2，B 矩陣飽和而失效）" if f == "Q2.14" else "")
        ax.text(v * 1.25, yy, lab, va="center", fontsize=11)
    ax.set_xlim(1e-8, 2e2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"1e{int(round(__import__('math').log10(v)))}"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("平均絕對誤差（對 float64 黃金模型，越低越好，對數軸）")
    ax.grid(axis="x"); ax.set_axisbelow(True)
    save(fig, "fig_format.png")


# ---- 圖 2：時脈掃描（內部 slack 與功耗）
def fig_clock():
    ser = [("base", 10), ("clk6p0", 6), ("clk5p0", 5), ("clk4p0", 4), ("clk3p0", 3), ("clk2p5", 2.5), ("clk2p0", 2),
           ("clk1p8", 1.8), ("clk1p6", 1.6)]
    par = [("par", 10), ("par_clk2p0", 2), ("par_clk1p8", 1.8), ("par_clk1p6", 1.6)]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2))
    for data, col, lab in ((ser, BLUE, "序列式"), (par, ORANGE, "列平行")):
        p = [x[1] for x in data]
        a.plot(p, [S[v]["r2r_slack_ns"] for v, _ in data], "-o", color=col, lw=2, ms=6, mfc=col, mec="white")
        b.plot([1000 / x for x in p], [S[v]["power_mw"] for v, _ in data], "-o", color=col, lw=2, ms=6, mec="white")
    a.axhline(0, color="#52514e", lw=1)
    a.set_xscale("log"); a.invert_xaxis()
    a.set_xticks([10, 5, 3, 2, 1.6]); a.set_xticklabels(["10", "5", "3", "2", "1.6"])
    a.xaxis.set_minor_formatter(NullFormatter())
    a.set_xlabel("時脈目標週期 (ns)"); a.set_ylabel("內部路徑 slack (ns)")
    a.text(2.1, -0.75, "零線以下：時序不達標", fontsize=10, color="#52514e", ha="left", va="center")
    a.set_ylim(-1.1, 8.6)
    a.text(2.9, 5.2, "序列式", color=BLUE, fontsize=12, fontweight="bold")
    a.text(7.0, 7.3, "列平行", color=ORANGE, fontsize=12, fontweight="bold")
    a.grid(); a.set_axisbelow(True)
    b.set_xlabel("時脈頻率 (MHz)"); b.set_ylabel("總功耗 (mW，預設活動率估算)")
    b.text(250, 12, "序列式", color=BLUE, fontsize=12, fontweight="bold")
    b.text(250, 46, "列平行", color=ORANGE, fontsize=12, fontweight="bold")
    b.grid(); b.set_axisbelow(True)
    fig.tight_layout()
    save(fig, "fig_clock.png")


# ---- 圖 3：位寬比較（面積與誤差）
def fig_width():
    ws = ["12 位元\nQ3.9", "16 位元\nQ3.13", "24 位元\nQ3.19"]
    area = [S["w12"]["synth_area_um2"], S["base"]["synth_area_um2"], S["w24"]["synth_area_um2"]]
    err = [5.17e-3, 4.17e-4, 4.73e-5]
    fig, (a, b) = plt.subplots(1, 2, figsize=(10.5, 4.2))
    cols = [GRAY, BLUE, GRAY]
    a.bar(ws, area, color=cols, width=0.55)
    for i, v in enumerate(area):
        a.text(i, v + 900, f"{v/1000:.1f}k µm²\n（{v/area[1]:.2f}×）", ha="center", fontsize=11)
    a.set_ylim(0, 72000); a.set_ylabel("合成面積 (µm²)"); a.grid(axis="y"); a.set_axisbelow(True)
    b.bar(ws, err, color=cols, width=0.55)
    b.set_yscale("log")
    for i, v in enumerate(err):
        b.text(i, v * 1.3, f"{v:.1e}", ha="center", fontsize=11)
    b.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"1e{int(round(__import__('math').log10(v)))}"))
    b.yaxis.set_minor_formatter(NullFormatter())
    b.set_ylim(1e-5, 4e-2); b.set_ylabel("平均絕對誤差（越低越好，對數軸）"); b.grid(axis="y"); b.set_axisbelow(True)
    fig.tight_layout()
    save(fig, "fig_width.png")


# ---- 圖 4：架構比較（各自最快達標時脈；序列式 1.8 ns、列平行 2.0 ns）
def fig_arch():
    s, p = S["clk1p8"], S["par_clk2p0"]
    lat = (8527 * 1.8 / 1000, 1527 * 2.0 / 1000)
    area = (s["stdcell_area_um2"], p["stdcell_area_um2"])
    thr = (1000 / lat[0], 1000 / lat[1])
    tpa = (thr[0] / (area[0] / 1e6), thr[1] / (area[1] / 1e6))
    items = [("延遲 (µs／次)\n越低越好", lat, "{:.2f}"), ("面積 (µm²)\n越低越好", area, "{:,.0f}"),
             ("吞吐量／面積\n(次／ms／mm²) 越高越好", tpa, "{:,.0f}")]
    fig, axs = plt.subplots(1, 3, figsize=(11, 4.0))
    for ax, (title, v, fmt) in zip(axs, items):
        ax.bar(["序列式\n@1.8 ns", "列平行\n@2.0 ns"], v, color=[BLUE, ORANGE], width=0.55)
        for i, x in enumerate(v):
            ax.text(i, x * 1.02, fmt.format(x), ha="center", fontsize=11)
        ax.set_ylim(0, max(v) * 1.18); ax.set_title(title, fontsize=12, color="#52514e")
        ax.grid(axis="y"); ax.set_axisbelow(True)
    fig.tight_layout()
    save(fig, "fig_arch.png")


# ---- 圖 5：合成面積分布（序列式 vs 列平行）
def fig_breakdown():
    cats = ["MUX2（讀取多工器）", "正反器", "全加器／半加器（MAC）", "其他組合邏輯"]
    ser = [15910, 14580, 2858, 6797]
    par = [15814, 16835, 12861, 15932]
    cols = [BLUE, ORANGE, AQUA, YELLOW]
    fig, ax = plt.subplots(figsize=(10.5, 3.3))
    for row, (name, vals) in enumerate((("列平行\n61.4k µm²", par), ("序列式\n40.1k µm²", ser))):
        left = 0
        for v, c, cat in zip(vals, cols, cats):
            ax.barh(row, v - 160, left=left + 80, color=c, height=0.6)   # 段間留白 2px 感
            ax.text(left + v / 2, row, f"{v/1000:.1f}k", ha="center", va="center", fontsize=11,
                    color="white" if c in (BLUE, ORANGE, AQUA) else "#0b0b0b", fontweight="bold")
            left += v
    ax.set_yticks([0, 1]); ax.set_yticklabels(["列平行\n61.4k µm²", "序列式\n40.1k µm²"])
    ax.set_xlabel("合成面積 (µm²)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in cols]
    ax.legend(handles, cats, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.22), frameon=False, fontsize=11)
    ax.set_xlim(0, 64000); ax.grid(axis="x"); ax.set_axisbelow(True)
    save(fig, "fig_breakdown.png")


for f in (fig_format, fig_clock, fig_width, fig_arch, fig_breakdown):
    f()
