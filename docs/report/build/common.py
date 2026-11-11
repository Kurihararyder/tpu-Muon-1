"""報告與簡報共用的資料與常數。數字全部由專案內的結果檔讀取，不手打。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIGS = ROOT / "docs" / "report" / "figs"
FONT = "Microsoft JhengHei"
S = {r["variant"]: r for r in json.load(open(ROOT / "flow" / "summary.json"))}


def sim_cases():
    """sim/build/compare.log 的案例表 -> [(名稱, 一致?, 最大誤差, 平均誤差, 奇異值範圍)]"""
    rows = []
    for l in (ROOT / "sim" / "build" / "compare.log").read_text(encoding="utf-8").splitlines():
        if l.startswith("| ") and not l.startswith("| 案例") and not l.startswith("|---"):
            c = [x.strip() for x in l.strip("|").split("|")]
            rows.append((c[0], c[1], c[2], c[3], c[4].replace(" ← 未通過", "")))
    return rows


def arch_numbers():
    s, p = S["clk1p8"], S["par_clk2p0"]
    lat = (8527 * 1.8 / 1000, 1527 * 2.0 / 1000)
    thr = (1000 / lat[0], 1000 / lat[1])
    tpa = (thr[0] / (s["stdcell_area_um2"] / 1e6), thr[1] / (p["stdcell_area_um2"] / 1e6))
    return dict(lat=lat, thr=thr, tpa=tpa, area=(s["stdcell_area_um2"], p["stdcell_area_um2"]))
