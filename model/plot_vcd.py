"""把 sim/ns_top.vcd 畫成波形圖（matplotlib），輸出到 docs/。

此腳本是 GTKWave 截圖的替代品：本環境（WSLg）無法擷取 GTKWave 視窗，所以用 VCD 內容重繪。
圖上的資料與 GTKWave 開啟同一個 VCD 看到的完全相同；docs/ns_top.gtkw 可在 GTKWave 載入同樣的訊號清單。
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
T = "tb_ns_top."
SIGNALS = {
    "clk": T + "clk", "start": T + "start", "ld_we": T + "ld_we", "busy": T + "busy", "done": T + "done",
    "c_st": T + "dut.u_ctrl.st", "cmd_valid": T + "dut.u_ctrl.cmd_valid", "cmd_op": T + "dut.u_ctrl.cmd_op",
    "i": T + "dut.u_ctrl.i", "j": T + "dut.u_ctrl.j", "it": T + "dut.u_ctrl.it",
    "ready": T + "dut.u_core.cmd_ready", "k_st": T + "dut.u_core.st", "k": T + "dut.u_core.k",
    "mac_en": T + "dut.u_core.mac_en", "mac_clr": T + "dut.u_core.mac_clr",
    "acc": T + "dut.u_core.acc", "aa_q": T + "dut.u_core.aa_q",
}
CTRL_ST = {0: "IDLE", 1: "A", 2: "AAB", 3: "X", 4: "COMMIT", 5: "WAIT"}
CORE_ST = {0: "IDLE", 1: "DOT", 2: "XA", 3: "B1", 4: "B2", 5: "DRAIN", 6: "WB"}
OPS = {0: "A", 1: "AAB", 2: "X", 3: "COMMIT"}


def parse_vcd(path, wanted):
    """回傳 {別名: [(時間 ns, 值或 None), ...]}。"""
    scope, ids, want_full = [], {}, {v: k for k, v in wanted.items()}
    traces = {k: [] for k in wanted}
    unit = 1e-3
    in_defs = True
    t = 0.0
    with open(path, "r", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if in_defs:
                if line.startswith("$timescale"):
                    txt = line + " " + (next(f).strip() if "$end" not in line else "")
                    unit = 1e-3 if "ps" in txt else 1.0
                elif line.startswith("$scope"):
                    scope.append(line.split()[2])
                elif line.startswith("$upscope"):
                    scope.pop()
                elif line.startswith("$var"):
                    p = line.split()
                    full = ".".join(scope) + "." + p[4]
                    if full in want_full:
                        ids.setdefault(p[3], []).append(want_full[full])
                elif line.startswith("$enddefinitions"):
                    in_defs = False
                continue
            if not line:
                continue
            if line[0] == "#":
                t = int(line[1:]) * unit
            elif line[0] == "b":
                val, ident = line[1:].split()
                for name in ids.get(ident, []):
                    traces[name].append((t, int(val, 2) if set(val) <= {"0", "1"} else None))
            elif line[0] in "01xz" and line[1:] in ids:
                for name in ids[line[1:]]:
                    traces[name].append((t, int(line[0]) if line[0] in "01" else None))
    return traces


def value_at(tr, t):
    v = None
    for tt, vv in tr:
        if tt > t:
            break
        v = vv
    return v


def segments(tr, t0, t1):
    """把 [t0,t1] 內的變化切成 (起, 迄, 值)。"""
    pts = [(t0, value_at(tr, t0))] + [(t, v) for t, v in tr if t0 < t <= t1]
    return [(pts[n][0], pts[n + 1][0] if n + 1 < len(pts) else t1, pts[n][1]) for n in range(len(pts))]


def to_signed(v, w):
    return None if v is None else (v - (1 << w) if v >= 1 << (w - 1) else v)


def draw(traces, t0, t1, rows, title, out, width=14):
    fig, axes = plt.subplots(len(rows), 1, figsize=(width, 0.55 * len(rows) + 1.2), sharex=True)
    fig.suptitle(title, fontsize=12)
    palette = ["#cfe8ff", "#ffe3b3", "#d6f5d6", "#f5d0e6", "#e0e0e0", "#fff2a8", "#d9d2f7"]
    for ax, (label, key, kind, fmt) in zip(axes, rows):
        segs = segments(traces[key], t0, t1)
        if kind == "bit":
            xs, ys = [], []
            for a, b, v in segs:
                xs += [a, b]
                ys += [0 if v is None else v] * 2
            ax.plot(xs, ys, drawstyle="steps-post", color="#1f4e8c", lw=1.2)
            ax.set_ylim(-0.3, 1.3)
            ax.set_yticks([])
        else:
            for a, b, v in segs:
                txt = "x" if v is None else fmt(v)
                col = palette[(v or 0) % len(palette)] if kind == "enum" else "#eef3f8"
                ax.add_patch(plt.Rectangle((a, 0.1), max(b - a, 0), 0.8, fc=col, ec="#555555", lw=0.7))
                if (b - a) > (t1 - t0) / 90:
                    ax.text((a + b) / 2, 0.5, txt, ha="center", va="center", fontsize=7)
            ax.set_ylim(0, 1)
            ax.set_yticks([])
        ax.set_ylabel(label, rotation=0, ha="right", va="center", fontsize=8)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
    axes[-1].set_xlim(t0, t1)
    axes[-1].set_xlabel("time (ns)")
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK TC", "Noto Sans CJK JP", "WenQuanYi Zen Hei", "DejaVu Sans"]
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print("wrote", out)


def first_time(tr, pred, after=0.0):
    for t, v in tr:
        if t >= after and v is not None and pred(v):
            return t
    raise RuntimeError("找不到事件")


def main(vcd=ROOT / "sim" / "ns_top.vcd"):
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK TC", "Noto Sans CJK JP", "WenQuanYi Zen Hei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    tr = parse_vcd(vcd, SIGNALS)
    t_start = first_time(tr["start"], lambda v: v == 1)
    t_done = first_time(tr["done"], lambda v: v == 1, t_start + 20)
    hex_ = lambda v: f"{v:x}"
    dec = lambda v: str(v)

    # 圖 1：整段運算總覽（五輪）
    rows = [("clk", "clk", "bit", None), ("ld_we", "ld_we", "bit", None), ("start", "start", "bit", None),
            ("busy", "busy", "bit", None), ("done", "done", "bit", None),
            ("ctrl phase", "c_st", "enum", lambda v: CTRL_ST.get(v, str(v))), ("iteration", "it", "enum", dec)]
    t0 = first_time(tr["ld_we"], lambda v: v == 1) - 20
    tr["clk"] = [(t, v) for t, v in tr["clk"]]
    rows_ov = rows[1:]
    draw(tr, t0, t_done + 300, rows_ov, "ns_top overview: load -> 5 Newton-Schulz iterations -> done (case 2, random_0)",
         ROOT / "docs" / "waveform_overview.png")

    detail = [("clk", "clk", "bit", None), ("ctrl phase", "c_st", "enum", lambda v: CTRL_ST.get(v, str(v))),
              ("cmd_valid", "cmd_valid", "bit", None), ("cmd_ready", "ready", "bit", None),
              ("cmd_op", "cmd_op", "enum", lambda v: OPS.get(v, str(v))),
              ("i", "i", "enum", dec), ("j", "j", "enum", dec),
              ("core state", "k_st", "enum", lambda v: CORE_ST.get(v, str(v))), ("k", "k", "enum", dec),
              ("mac_en", "mac_en", "bit", None), ("mac_clr", "mac_clr", "bit", None),
              ("acc (Q6.26)", "acc", "bus", lambda v: str(to_signed(v, 32))),
              ("aa_q (Q3.13)", "aa_q", "bus", lambda v: str(to_signed(v, 16)))]

    # 圖 2：第一個 OP_A 元素（含 start 起頭）
    t_a = first_time(tr["c_st"], lambda v: v == 1, t_start)
    draw(tr, t_a - 25, t_a + 135, detail, "One OP_A element, cycle by cycle: A[0][0] = sum_k X[0][k]*X[0][k]",
         ROOT / "docs" / "waveform_zoom_opa.png")

    # 圖 3：第一個 OP_AAB 元素（含 B1／B2 兩次係數乘法）
    t_ab = first_time(tr["c_st"], lambda v: v == 2, t_a)
    draw(tr, t_ab - 15, t_ab + 175, detail, "One OP_AAB element: AA dot product -> quantize -> B1 (b*A) -> B2 (c*AA) -> write B",
         ROOT / "docs" / "waveform_zoom_aab.png")


if __name__ == "__main__":
    sys.exit(main())
