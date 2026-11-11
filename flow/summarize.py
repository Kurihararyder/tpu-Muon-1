"""從 ORFS 的輸出擷取 PPA 指標，產生 docs/ppa_table.md 與 flow/summary.json。
用法：python3 flow/summarize.py [變體...]（預設：base clk6p0 clk5p0 clk4p0 w12 w24，存在的才列）
數據來源：flow/work/logs/nangate45/muon_ns/<variant>/{1_synth,6_report}.json 與 reports/.../synth_stat.txt
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
DOCS = HERE.parent / "docs"
DEFAULT = ["base", "clk6p0", "clk5p0", "clk4p0", "clk3p0", "clk2p5", "clk2p0", "clk1p8", "clk1p6", "w12", "w24", "w12_clk2p0", "w24_clk2p0", "par", "par_clk2p0", "par_clk1p8", "par_clk1p6"]
INFO = {  # 變體：(說明, 資料格式, 時脈目標 ns)
    "base": ("基準", "Q3.13 / 16 位元", 10.0),
    "clk6p0": ("時脈 6 ns", "Q3.13 / 16 位元", 6.0),
    "clk5p0": ("時脈 5 ns", "Q3.13 / 16 位元", 5.0),
    "clk4p0": ("時脈 4 ns", "Q3.13 / 16 位元", 4.0),
    "clk3p0": ("時脈 3 ns", "Q3.13 / 16 位元", 3.0),
    "clk2p5": ("時脈 2.5 ns", "Q3.13 / 16 位元", 2.5),
    "clk2p0": ("時脈 2 ns", "Q3.13 / 16 位元", 2.0),
    "clk1p8": ("時脈 1.8 ns", "Q3.13 / 16 位元", 1.8),
    "clk1p6": ("時脈 1.6 ns", "Q3.13 / 16 位元", 1.6),
    "w12": ("位寬 12", "Q3.9 / 12 位元", 10.0),
    "w24": ("位寬 24", "Q3.19 / 24 位元", 10.0),
    "par": ("平行 8 lane", "Q3.13 / 16 位元", 10.0),
    "par_clk2p0": ("平行 8 lane、時脈 2 ns", "Q3.13 / 16 位元", 2.0),
    "par_clk1p8": ("平行 8 lane、時脈 1.8 ns", "Q3.13 / 16 位元", 1.8),
    "par_clk1p6": ("平行 8 lane、時脈 1.6 ns", "Q3.13 / 16 位元", 1.6),
    "w12_clk2p0": ("位寬 12、時脈 2 ns", "Q3.9 / 12 位元", 2.0),
    "w24_clk2p0": ("位寬 24、時脈 2 ns", "Q3.19 / 24 位元", 2.0),
}


def paths(v):
    """用 reg2reg.tcl 重新分析最終佈局：回傳 (暫存器到暫存器 slack, 起點, 終點, I/O slack)。結果快取在 reports 內。"""
    res = WORK / "results" / "nangate45" / "muon_ns" / v
    rpt = WORK / "reports" / "nangate45" / "muon_ns" / v / "reg2reg.rpt"
    if not rpt.exists():
        out = subprocess.run([os.path.expanduser("~/.local/bin/openroad"), "-exit", str(HERE / "reg2reg.tcl")],
                             env={**os.environ, "RESULTS": str(res)}, capture_output=True, text=True).stdout
        rpt.write_text(out)
    txt = rpt.read_text()
    r2r = txt.split("=== REG2REG ===")[1].split("=== REG2REG_END ===")[0]
    io = txt.split("=== IO ===")[1].split("=== IO_END ===")[0]
    sl = lambda t: float(re.search(r"(-?[\d.]+)\s+slack", t).group(1))
    sp = re.search(r"Startpoint: (\S+)", r2r).group(1)
    ep = re.search(r"Endpoint: (\S+)", r2r).group(1)
    return sl(r2r), sp, ep, sl(io)


def load(v):
    logs = WORK / "logs" / "nangate45" / "muon_ns" / v
    rep = WORK / "reports" / "nangate45" / "muon_ns" / v
    if not (logs / "6_report.json").exists():
        return None
    fin = json.load(open(logs / "6_report.json"))
    syn = json.load(open(logs / "1_synth.json"))
    stat = (rep / "synth_stat.txt").read_text()
    cells = int(re.search(r"^\s*(\d+)\s+[\d.]+\s+cells", stat, re.M).group(1)) if re.search(
        r"^\s*(\d+)\s+[\d.]+\s+cells", stat, re.M) else None
    g = lambda d, k: d.get(k)
    period = INFO[v][2]
    ws = g(fin, "finish__timing__setup__ws")
    r2r, sp, ep, io = paths(v)
    return {
        "r2r_slack_ns": r2r, "r2r_start": sp, "r2r_end": ep, "io_slack_ns": io,
        "r2r_fmax_mhz": 1000.0 / (period - r2r) if r2r >= 0 else None,   # 時序未達標（slack < 0）時不列
        "variant": v, "period_ns": period,
        "synth_area_um2": g(syn, "synth__design__instance__area__stdcell") or g(syn, "synth__design__instance__area"),
        "synth_cells": g(syn, "synth__design__instance__count__stdcell") or g(syn, "synth__design__instance__count"),
        "stdcell_area_um2": g(fin, "finish__design__instance__area__stdcell"),
        "flops": g(fin, "finish__design__instance__count__class:sequential_cell"),
        "core_area_um2": g(fin, "finish__design__core__area"),
        "utilization": g(fin, "finish__design__instance__utilization"),
        "wns_ns": ws, "tns_ns": g(fin, "finish__timing__setup__tns"),
        "hold_ws_ns": g(fin, "finish__timing__hold__ws"),
        "fmax_mhz": (1.0 / (period - ws) * 1000.0) if ws is not None and period - ws > 0 else None,
        "power_mw": (g(fin, "finish__power__total") or 0) * 1000.0,
        "power_internal_mw": (g(fin, "finish__power__internal__total") or 0) * 1000.0,
        "power_switching_mw": (g(fin, "finish__power__switching__total") or 0) * 1000.0,
        "power_leakage_mw": (g(fin, "finish__power__leakage__total") or 0) * 1000.0,
    }


def main():
    variants = sys.argv[1:] or DEFAULT
    rows = [r for r in (load(v) for v in variants) if r]
    json.dump(rows, open(HERE / "summary.json", "w"), indent=1)
    f = lambda x, p=1: "—" if x is None else f"{x:,.{p}f}"
    lines = ["| 變體 | 資料格式 | 時脈目標 (ns) | 合成面積 (µm²) | 佈局後元件面積 (µm²) | 正反器數 | 核心面積 (µm²) "
             "| 內部（暫存器到暫存器）slack (ns) | 內部最高時脈 (MHz) | I/O 路徑 slack (ns) | 總功耗 (mW) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {INFO[r['variant']][0]} | {INFO[r['variant']][1]} | {r['period_ns']:g} | {f(r['synth_area_um2'])} "
                     f"| {f(r['stdcell_area_um2'])} | {f(r['flops'], 0)} | {f(r['core_area_um2'], 0)} "
                     f"| {f(r['r2r_slack_ns'], 3)} | {f(r['r2r_fmax_mhz'], 0)} | {f(r['io_slack_ns'], 3)} | {f(r['power_mw'], 2)} |")
    print("\n".join(lines))
    (HERE / "summary_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 架構比較表：序列式（單一 MAC，8,527 週期）vs 列平行（8 條 MAC，1,527 週期），相同時脈下比較
    cyc = {"serial": 8527, "par": 1527}
    by = {r["variant"]: r for r in rows}
    pairs = [("base", "par", 10.0), ("clk2p0", "par_clk2p0", 2.0), ("clk1p8", "par_clk1p8", 1.8), ("clk1p6", "par_clk1p6", 1.6)]
    al = ["| 時脈目標 (ns) | 架構 | 週期／次 | 內部 slack (ns) | 面積 (µm²) | 正反器 | 功耗 (mW) | 延遲 (µs／次) | 能量 (µJ／次) | 吞吐量 (次／ms) | 吞吐量／面積 (次／ms／mm²) |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for sv, pv, per in pairs:
        for name, v in (("序列式", sv), ("列平行", pv)):
            if v not in by:
                continue
            r = by[v]
            c = cyc["par" if v.startswith("par") else "serial"]
            lat = c * per / 1000.0                      # µs
            en = r["power_mw"] * lat / 1000.0           # µJ
            thr = 1000.0 / lat                          # 次/ms
            note = "" if r["r2r_slack_ns"] >= 0 else "（未達標）"
            al.append(f"| {per:g} | {name} | {c:,} | {f(r['r2r_slack_ns'], 3)}{note} | {f(r['stdcell_area_um2'], 0)} | {f(r['flops'], 0)} "
                      f"| {f(r['power_mw'], 2)} | {f(lat, 2)} | {f(en, 3)} | {f(thr, 1)} | {f(thr / (r['stdcell_area_um2'] / 1e6), 0)} |")
    (HERE / "summary_arch.md").write_text("\n".join(al) + "\n", encoding="utf-8")
    print()
    print("\n".join(al))


if __name__ == "__main__":
    main()
