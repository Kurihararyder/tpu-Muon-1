"""產生簡報（PowerPoint，16:9）：docs/report/Muon晶片_簡報.pptx
文字方塊以 PIL 量測實際字寬，超出方塊就印出警告（沒有 PowerPoint 可預覽時的替代檢查）。"""
from PIL import ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from common import FIGS, FONT, ROOT, S, arch_numbers

OUT = ROOT / "docs" / "report" / "Muon晶片_簡報.pptx"
INK, MUTED, BLUE, ORANGE, AQUA, LIGHT, LINE = "0B0B0B", "52514E", "2A78D6", "EB6834", "1BAF7A", "F2F5FA", "D9DEE7"
NAVY = "1F4E8C"
_fr = ImageFont.truetype("/mnt/c/Windows/Fonts/msjh.ttc", 100, index=0)
_fb = ImageFont.truetype("/mnt/c/Windows/Fonts/msjhbd.ttc", 100, index=0)
warnings = []

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def rgb(h): return RGBColor.from_string(h)


def text_height(paras, width_in):
    """估算段落排版後的高度（吋）。paras: [(text, size_pt, bold)]"""
    total = 0.0
    for text, size, bold in paras:
        f = _fb if bold else _fr
        w_pt = width_in * 72
        lines, cur = 1, 0.0
        for ch in text:
            cw = f.getlength(ch) * size / 100
            if cur + cw > w_pt:
                lines += 1; cur = cw
            else:
                cur += cw
        total += lines * size * 1.3 / 72 + size * 0.35 / 72
    return total


def tb(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, align=PP_ALIGN.LEFT, tag=""):
    """paras: [(text, size, bold, color)]；超出方塊時印警告。"""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05); tf.margin_top = tf.margin_bottom = Inches(0.03)
    for i, (t, size, bold, color) in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(size * 0.35)
        r = p.add_run(); r.text = t
        r.font.size = Pt(size); r.font.bold = bold; r.font.name = FONT; r.font.color.rgb = rgb(color)
        rPr = r._r.get_or_add_rPr()
        from pptx.oxml.ns import qn
        from lxml import etree
        for tagname in ("a:ea", "a:cs"):
            e = etree.SubElement(rPr, qn(tagname)); e.set("typeface", FONT)
    need = text_height([(t, s, b) for t, s, b, _ in paras], w - 0.1)
    if need > h + 0.02:
        warnings.append(f"[第 {len(prs.slides)} 張 {tag or paras[0][0][:12]}] 文字需 {need:.2f} 吋，方塊只有 {h:.2f} 吋")
    return box


def rect(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = rgb(fill)
    if line: s.line.color.rgb = rgb(line); s.line.width = Pt(1)
    else: s.line.fill.background()
    s.shadow.inherit = False
    return s


def title(slide, text, sub=None):
    rect(slide, 0, 0, 0.18, 7.5, BLUE)
    tb(slide, 0.55, 0.35, 12.2, 0.75, [(text, 30, True, NAVY)], anchor=MSO_ANCHOR.MIDDLE, tag="標題")
    if sub:
        tb(slide, 0.55, 1.05, 12.2, 0.45, [(sub, 16, False, MUTED)], tag="副標")


def footer(slide, n):
    tb(slide, 0.55, 7.05, 9, 0.3, [("Muon 晶片：Newton-Schulz 正交化硬體實作　｜　靜宜大學 劉志俊 老師", 10, False, MUTED)], tag="頁尾")
    tb(slide, 12.0, 7.05, 0.8, 0.3, [(str(n), 10, False, MUTED)], align=PP_ALIGN.RIGHT, tag="頁碼")


def bullets(slide, x, y, w, h, items, size=18, gap_color=INK):
    paras = []
    for it in items:
        lead, rest = it if isinstance(it, tuple) else (None, it)
        paras.append(("•  " + (lead + "：" if lead else "") + rest, size, False, gap_color))
    return tb(slide, x, y, w, h, paras, tag="條列")


def card(slide, x, y, w, h, big, label, color=BLUE):
    rect(slide, x, y, w, h, LIGHT)
    rect(slide, x, y, 0.08, h, color)
    tb(slide, x + 0.2, y + 0.1, w - 0.3, h * 0.55, [(big, 28, True, color)], anchor=MSO_ANCHOR.MIDDLE, tag="卡片數字")
    tb(slide, x + 0.2, y + h * 0.58, w - 0.3, h * 0.4, [(label, 13, False, MUTED)], tag="卡片說明")


def pic(slide, path, x, y, w=None, h=None):
    kw = {}
    if w: kw["width"] = Inches(w)
    if h: kw["height"] = Inches(h)
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), **kw)


def table(slide, x, y, w, rows, colw, size=13, rowh=0.42, header=True):
    shp = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(rowh * len(rows)))
    t = shp.table
    for i, cw in enumerate(colw): t.columns[i].width = Inches(cw)
    for ri, row in enumerate(rows):
        t.rows[ri].height = Inches(rowh)
        for ci, val in enumerate(row):
            c = t.cell(ri, ci); c.text = ""
            c.margin_left = c.margin_right = Inches(0.08); c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = c.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER
            r = p.add_run(); r.text = str(val); r.font.size = Pt(size); r.font.name = FONT
            hdr = header and ri == 0
            r.font.bold = hdr; r.font.color.rgb = rgb("FFFFFF" if hdr else INK)
            c.fill.solid(); c.fill.fore_color.rgb = rgb(NAVY if hdr else ("FFFFFF" if ri % 2 else LIGHT))
            need = text_height([(str(val), size, hdr)], colw[ci] - 0.16)
            if need > rowh + 0.02:
                warnings.append(f"[第 {len(prs.slides)} 張 表格 {val!s:.12}] 需 {need:.2f} 吋 > 列高 {rowh}")
    return shp


def new(n, ttl, sub=None):
    s = prs.slides.add_slide(BLANK)
    title(s, ttl, sub); footer(s, n)
    return s


a = arch_numbers()
b = S["base"]

# ---- 1 封面
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, 13.333, 7.5, NAVY)
rect(s, 0.8, 3.55, 1.6, 0.06, ORANGE)
tb(s, 0.8, 1.55, 11.5, 1.2, [("Muon 晶片", 54, True, "FFFFFF")], tag="封面標題")
tb(s, 0.8, 2.7, 11.8, 0.8, [("Newton-Schulz 正交化的硬體實作與開源流程評估", 26, False, "FFFFFF")], tag="封面副標")
tb(s, 0.8, 3.85, 11.5, 1.9, [("指導教授：劉志俊 老師", 18, False, "DCE6F5"),
                             ("靜宜大學 資訊工程學系／晶片設計學士學位學程", 18, False, "DCE6F5"),
                             ("報告人：＿＿＿＿＿＿＿＿　　2026 年 11 月", 18, False, "DCE6F5")], tag="封面資訊")

# ---- 2 目標與流程
s = new(2, "目標：把 Muon 的核心運算做成晶片", "Muon 最佳化器的核心 = 五次 Newton-Schulz 正交化迭代：只有矩陣乘法與加法，沒有 SVD")
bullets(s, 0.55, 1.75, 12.2, 1.9, [
    ("來源", "老師的投影片「Muon 渺子矩陣正交化最佳化器」，最後一頁「未來工作」提到「Muon 晶片」"),
    ("做法", "先在筆電用開源 EDA 工具完成功能驗證與合成、佈局繞線的初步評估"),
    ("之後", "搬到實驗室的 VCS／Design Compiler／PrimeTime／IC Compiler II 重跑")], size=18)
stages = [("A", "Python\n黃金模型"), ("B", "數值格式\n評估"), ("C", "RTL 設計\nVerilog"), ("D", "模擬驗證\n逐位元比對"), ("E", "合成與佈局繞線\nPPA 比較")]
x0, w, gap = 0.55, 2.28, 0.2
for i, (k, t) in enumerate(stages):
    x = x0 + i * (w + gap)
    rect(s, x, 4.1, w, 1.9, LIGHT)
    rect(s, x, 4.1, w, 0.08, BLUE if i < 4 else ORANGE)
    tb(s, x + 0.1, 4.3, w - 0.2, 0.6, [("階段 " + k, 20, True, NAVY)], tag="階段")
    tb(s, x + 0.1, 4.95, w - 0.2, 0.95, [(l, 15, False, INK) for l in t.split("\n")], tag="階段說明")
tb(s, 0.55, 6.25, 12.2, 0.6, [("注意：Nangate45 是開源製程庫，數字只能做相對比較，不能直接當成實驗室製程的結果", 14, False, MUTED)], tag="提醒")

# ---- 3 演算法
s = new(3, "演算法：每輪三次矩陣乘法", "a = 3.4445　b = −4.7750　c = 2.0315　　X = G / (‖G‖F + eps)，之後重複 5 次")
rect(s, 0.55, 1.8, 5.6, 2.4, LIGHT)
tb(s, 0.8, 1.9, 5.2, 2.2, [("A = X · Xᵀ", 24, True, NAVY), ("B = b·A + c·A·A", 24, True, NAVY), ("X = a·X + B·X", 24, True, NAVY),
                           ("A 是對稱矩陣，只需算一半", 15, False, MUTED)], anchor=MSO_ANCHOR.MIDDLE, tag="公式")
bullets(s, 0.55, 4.45, 5.7, 2.4, [("硬體友善", "只有乘加，沒有 SVD"),
                                   ("麻煩處", "縮放需要平方和與開根號；第一版由外部算好縮放值輸入")], size=16)
tb(s, 6.6, 1.75, 6.2, 0.4, [("黃金模型（float64）：輸出奇異值範圍", 16, True, NAVY)], tag="表標題")
table(s, 6.6, 2.2, 6.2, [["形狀", "奇異值最小", "最大", "落在 0.5～1.3"],
                          ["4x4", "0.682", "1.134", "100%"], ["8x8", "0.682", "1.134", "100%"],
                          ["16x16", "0.249", "1.168", "99.4%"], ["8x16", "0.682", "1.134", "100%"]],
      [1.4, 1.7, 1.2, 1.9], size=14, rowh=0.46)
bullets(s, 6.6, 4.7, 6.2, 2.2, [("16x16 的 0.249", "來自近乎奇異的輸入（最小奇異值約 0.0005），五輪推不到 0.7，是演算法特性，不是錯誤")], size=15)

# ---- 4 格式評估
s = new(4, "數值格式評估：Q3.13 最準，Q2.14 失效", "20 組隨機 8x8 + 5 組病態矩陣；每次乘法與加法後量化；FP／定點共 7 種")
pic(s, FIGS / "fig_format.png", 0.55, 1.65, w=7.9)
bullets(s, 8.7, 1.8, 4.2, 5.0, [("B 矩陣最大 2.74", "需要 3 個整數位（±4）；理論上界約 2.81，與實測吻合"),
                                ("Q2.14", "範圍只有 ±2，B 飽和後整個發散"),
                                ("Q3.13", "比 Q4.12 多一位小數，平均誤差 0.65 倍"),
                                ("四捨五入", "最大誤差約為截斷的 1/2～1/3")], size=15)

def callout(slide, y, text, color=BLUE):
    rect(slide, 0.55, y, 8.4, 1.0, LIGHT); rect(slide, 0.55, y, 0.08, 1.0, color)
    tb(slide, 0.8, y + 0.05, 8.0, 0.9, [(text, 16, True, NAVY)], anchor=MSO_ANCHOR.MIDDLE, tag="重點")


callout(prs.slides[3], 5.5, "Q3.13 平均誤差 4.6e-4：比 bf16 準約 40 倍、比 FP16 準約 5 倍，且乘加單元是純整數")

# ---- 5 選定
s = new(5, "選定：資料 Q3.13、係數 Q4.12、32 位元累加器", "選型理由；Q3.13 不在原候選清單內，是依範圍分析加入的附加候選")
cards = [("4.6e-4", "平均誤差（對 float64）", BLUE), ("40×", "比 bf16 準（平均誤差）", BLUE), ("5×", "比 FP16 準", BLUE), ("0.65×", "Q4.12 的平均誤差倍數", AQUA)]
for i, (bg, lb, c) in enumerate(cards):
    card(s, 0.55 + i * 3.1, 1.8, 2.9, 1.45, bg, lb, c)
bullets(s, 0.55, 3.6, 12.2, 3.2, [
    ("整數位", "3 位剛好涵蓋最大值 2.74 並有約 1.4 倍餘裕；Q4.12 多的整數位用不到"),
    ("累加器", "32 位元（Q6.26）、乘積不捨入 → RTL 與 Python 模型可逐位元一致"),
    ("係數", "|b| = 4.775 放不進 Q3.13，另設 Q4.12 常數暫存器"),
    ("彈性", "RTL 參數化，要改回 Q4.12 只需 F = 12")], size=17)

# ---- 6 RTL 架構圖
s = new(6, "RTL 架構：序列式單一 MAC", "ns_top = 載入／縮放 + 控制 FSM + 運算核心；記憶體式介面，避免 1,024 位元寬匯流排")
def block(x, y, w, h, t1, t2, fill=LIGHT, edge=BLUE):
    rect(s, x, y, w, h, fill, edge)
    tb(s, x + 0.08, y + 0.08, w - 0.16, 0.4, [(t1, 15, True, NAVY)], tag=t1)
    if t2: tb(s, x + 0.08, y + 0.5, w - 0.16, h - 0.55, [(t2, 12, False, MUTED)], tag=t1 + "說明")
rect(s, 0.55, 1.7, 12.25, 5.15, "FFFFFF", LINE)
tb(s, 0.7, 1.75, 3, 0.35, [("ns_top", 14, True, MUTED)], tag="ns_top")
block(0.9, 2.3, 2.5, 1.5, "norm_scale", "X0 = G × scale\n四捨五入＋飽和")
block(0.9, 4.2, 2.5, 1.5, "ns_ctrl", "FSM：5 輪 ×\n(A → AAB → X → COMMIT)")
rect(s, 3.9, 2.0, 8.7, 4.65, "FFFFFF", BLUE)
tb(s, 4.05, 2.05, 4, 0.35, [("matmul_core（資料路徑）", 14, True, BLUE)], tag="core")
for i, (nm, d) in enumerate((("X 陣列", "64×16 位元"), ("A 陣列", "兼作新 X 緩衝"), ("B 陣列", "64×16 位元"))):
    block(4.2, 2.55 + i * 1.3, 2.3, 1.1, nm, d, fill="FFFFFF")
block(7.0, 2.55, 2.5, 1.2, "運算元選擇", "64:1 讀取多工器", fill="FFFFFF")
block(7.0, 4.0, 2.5, 1.2, "mac_unit", "16×16 乘加（兩級管線）\n累加器 32 位元", fill="FFFFFF", edge=ORANGE)
block(9.9, 3.3, 2.5, 1.4, "捨入＋飽和", "加 0.5 LSB → 右移 13\n→ 飽和 16 位元", fill="FFFFFF")
for (x1, y1, x2, y2) in ((3.4, 3.05, 4.2, 3.2), (3.4, 4.95, 7.0, 4.95), (6.5, 3.1, 7.0, 3.15), (9.5, 3.15, 9.9, 3.7), (9.5, 4.6, 9.9, 4.3)):
    ln = s.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2)); ln.line.color.rgb = rgb(MUTED); ln.line.width = Pt(1.5)
tb(s, 0.9, 6.0, 2.7, 0.7, [("載入埠／讀出埠", 13, True, NAVY), ("ld_we／ld_addr／ld_data；rd_addr／rd_data", 10, False, MUTED)], tag="埠")

# ---- 7 命令與對稱性
s = new(7, "資料路徑：逐元素命令，利用 A 的對稱性", "一輪 = A（36 元素）→ AAB（36 元素）→ X（64 元素）→ COMMIT")
table(s, 0.55, 1.75, 7.3, [["命令", "運算", "週期"],
                           ["OP_A", "A[i][j] = Σₖ X[i][k]·X[j][k]，鏡射寫 A[j][i]", "11"],
                           ["OP_AAB", "AA 內積 → 量化；B = b·A + c·AA，鏡射寫 B[j][i]", "15"],
                           ["OP_X", "X' = Σₖ B[i][k]·X[k][j] + a·X[i][j]，寫入 A 陣列", "12"],
                           ["OP_COMMIT", "X ← A 陣列（整個陣列平行複製）", "1"]],
      [1.5, 5.0, 0.8], size=13, rowh=0.7)
bullets(s, 0.55, 5.4, 7.3, 1.5, [("A 與 A·A 對稱", "只算上三角 36 個元素，鏡射值與直接計算逐位元相同")], size=15)
card(s, 8.3, 1.75, 4.5, 1.5, "8,527", "週期／次運算（模擬實測；估算 8,525）", BLUE)
card(s, 8.3, 3.5, 4.5, 1.5, "共用 1 個 MAC", "B 的兩次係數乘法併入 AA 的元素計算", ORANGE)
card(s, 8.3, 5.25, 4.5, 1.45, "新 X 先寫入 A 陣列", "避免原地覆寫還要用的 X，輪末再一次複製", AQUA)

# ---- 8 驗證方法與結果
s = new(8, "驗證：RTL 與位元精確模型逐位元一致", "20 組測試向量、1,280 個輸出元素全部一致；列平行版與 12／24 位元變體同樣一致")
card(s, 0.55, 1.75, 3.0, 1.45, "1,280 / 1,280", "輸出元素逐位元一致", BLUE)
card(s, 3.75, 1.75, 3.0, 1.45, "200 / 200", "整數模型 vs 浮點定點模型", AQUA)
card(s, 6.95, 1.75, 3.0, 1.45, "5 個模組", "各有獨立 testbench", BLUE)
card(s, 10.15, 1.75, 2.65, 1.45, "全部抓到", "故意改壞 RTL 的變異測試", ORANGE)
bullets(s, 0.55, 3.55, 12.2, 3.4, [
    ("測試案例", "全零、單位矩陣、8 組隨機、5 組病態（條件數 1e1～1e5）、小幅值、rank-1、對角、全 1、稀疏"),
    ("對 float64 誤差", "隨機矩陣最大約 1e-3～2e-3；病態矩陣（1e5）最大 5.7e-2，屬演算法與格式特性"),
    ("全零矩陣", "輸出全為 0，沒有除以零問題"),
    ("一鍵執行", "bash sim/run.sh　（--arch par、--variant w12|w24、--vcd N）")], size=17)

# ---- 9 波形
s = new(9, "波形：五輪迭代與單一元素的逐週期行為", "圖由 VCD 重繪（環境無法擷取 GTKWave 視窗）；docs/ns_top.gtkw 可在 GTKWave 載入同樣訊號")
pic(s, ROOT / "docs" / "waveform_overview.png", 0.55, 1.7, w=5.9)
pic(s, ROOT / "docs" / "waveform_zoom_aab.png", 6.65, 1.7, w=6.2)
tb(s, 0.55, 3.75, 5.9, 1.0, [("整段運算：載入 → 5 輪 A / AAB / X → done；done 在 start 後立即清除", 14, False, MUTED)], tag="圖說1")
tb(s, 6.65, 5.55, 6.2, 1.2, [("OP_AAB 一個元素：內積 8 個週期 → 量化 aa_q → B1（b·A）→ B2（c·AA）→ 寫回 B", 14, False, MUTED)], tag="圖說2")

# ---- 10 合成與佈局繞線
s = new(10, "合成與佈局繞線：Nangate45、10 ns 基準", "Yosys + OpenROAD（ORFS）完整流程：合成 → 佈局 → CTS → 繞線；核心使用率 40.6%")
card(s, 0.55, 1.75, 2.9, 1.4, f"{b['synth_area_um2']/1000:.1f}k µm²", f"合成面積（{b['synth_cells']:,} 個元件）", BLUE)
card(s, 3.65, 1.75, 2.9, 1.4, f"{b['flops']:,}", "正反器（3 個陣列約 3.1k）", BLUE)
card(s, 0.55, 3.35, 2.9, 1.4, "DRC 0", "細部繞線；天線違規 0", AQUA)
card(s, 3.65, 3.35, 2.9, 1.4, f"{b['power_mw']:.1f} mW", "@100 MHz（預設活動率估算）", ORANGE)
bullets(s, 0.55, 5.0, 6.0, 1.9, [("時序", "setup／hold 皆無違規；hold slack +0.063 ns"),
                                  ("提醒", "ORFS 的 WNS 是讀出埠的 I/O 路徑，不代表內部速度（見下頁）")], size=14)
pic(s, ROOT / "docs" / "layout" / "base_placement.png", 6.95, 1.7, h=5.2)

# ---- 11 時脈掃描
s = new(11, "時脈掃描：內部路徑可達 1.8 ns（約 555 MHz）", "關鍵路徑一貫是 MAC：運算元暫存器 → 乘法器 → 累加器；1.6 ns 開始不達標")
pic(s, FIGS / "fig_clock.png", 0.55, 1.65, w=8.4)
bullets(s, 9.15, 1.8, 3.7, 5.0, [
    ("內部 slack", "1.8 ns 為 +0.026 ns，1.6 ns 為 −0.111 ns"),
    ("面積", "幾乎不變，最緊時多約 1.7% 修復緩衝器"),
    ("功耗", "隨頻率線性成長：7.3 → 37.4 mW"),
    ("能量／次", "幾乎不變，約 0.57～0.62 µJ"),
    ("為何另寫腳本", "ORFS 的 WNS 是 I/O 路徑，flow/reg2reg.tcl 分析內部路徑")], size=13)

callout(prs.slides[10], 5.5, "內部資料路徑在 1.8 ns 仍達標；功耗隨頻率線性成長，每次運算的能量幾乎不變", ORANGE)

# ---- 12 位寬
s = new(12, "位寬比較：16 位元是合理的折衷", "同一份 RTL 以參數改變位寬，三個位寬都與各自的位元精確模型逐位元一致")
pic(s, FIGS / "fig_width.png", 0.55, 1.65, w=8.4)
bullets(s, 9.15, 1.8, 3.7, 5.0, [
    ("12 位元", "省 23% 面積，但誤差約 10 倍（病態矩陣最大 0.34）"),
    ("24 位元", "多 49% 面積；誤差更小但已無實質好處"),
    ("線性", "面積與位寬約成線性：面積由陣列與讀取多工器主導，乘法器占比小"),
    ("速度", "位寬越大越慢：2 ns 時 slack +0.30 → +0.12 → +0.03 ns")], size=13)

callout(prs.slides[11], 5.5, "12 位元誤差約 10 倍、24 位元多 49% 面積 → 16 位元（Q3.13）是合理的折衷")

# ---- 13 架構比較
s = new(13, "架構比較：列平行用 1.5 倍面積換 5 倍吞吐量", "列平行：8 條 MAC 一次算一整列；輸出與序列式逐位元一致；各自在最快達標時脈下比較")
pic(s, FIGS / "fig_arch.png", 0.55, 1.65, w=8.4)
table(s, 9.0, 1.8, 3.85, [["", "序列式", "列平行"],
                          ["週期／次", "8,527", "1,527"],
                          ["時脈", "1.8 ns", "2.0 ns"],
                          ["延遲", f"{a['lat'][0]:.2f} µs", f"{a['lat'][1]:.2f} µs"],
                          ["面積", f"{a['area'][0]/1000:.1f}k", f"{a['area'][1]/1000:.1f}k"],
                          ["吞吐量／面積", f"{a['tpa'][0]:,.0f}", f"{a['tpa'][1]:,.0f}"]],
      [1.45, 1.2, 1.2], size=12, rowh=0.5)
bullets(s, 0.55, 4.8, 8.4, 2.1, [
    ("結果", f"吞吐量約 {a['thr'][1]/a['thr'][0]:.1f} 倍、面積約 {a['area'][1]/a['area'][0]:.2f} 倍 → 吞吐量／面積約 {a['tpa'][1]/a['tpa'][0]:.1f} 倍"),
    ("代價", "最高時脈較低（8 條 MAC 共用訊號扇出變大）：2.0 ns 達標，1.8 ns 差 0.014 ns"),
    ("能量", "每次運算約降為 1/4.7（預設活動率估算，僅為趨勢）")], size=14)

# ---- 14 面積分布
s = new(14, "面積由陣列與讀取多工器主導，MAC 本身很小", "多出來的面積幾乎全是 7 條額外的 MAC，每條約 3k µm²；多工器數量不變")
pic(s, FIGS / "fig_breakdown.png", 0.55, 1.75, w=8.6)
bullets(s, 9.3, 1.85, 3.55, 5.0, [
    ("序列式", "MUX2 + 正反器 = 76%"),
    ("列平行", "占比降到 53%"),
    ("下一步", "縮陣列：A、B 只存一半、B 與 A 共用、改用 SRAM 巨集")], size=14)
tb(s, 0.55, 5.5, 8.6, 1.3, [("合成後單元統計（Yosys）：序列式 MUX2 8,525 個、正反器 3,213 個、FA／HA 765 個；列平行 MUX2 8,505 個、正反器 3,655 個、FA／HA 3,400 個", 14, False, MUTED)], tag="統計")

# ---- 15 結論
s = new(15, "結論、限制與後續", None)
tb(s, 0.55, 1.2, 6.0, 0.45, [("結論", 20, True, NAVY)], tag="結論標題")
bullets(s, 0.55, 1.7, 6.0, 5.0, [
    "Q3.13 定點格式在精度與成本最合適，RTL 與位元精確模型逐位元一致",
    "MAC 占面積很小，平行化划算：約 1.5 倍面積換 5 倍吞吐量",
    "內部資料路徑可達 500～555 MHz（Nangate45 typical）",
    "RTL、testbench、向量、黃金模型可直接搬到實驗室商用工具"], size=15)
tb(s, 6.9, 1.2, 6.0, 0.45, [("限制（如實說明）", 20, True, ORANGE)], tag="限制標題")
bullets(s, 6.9, 1.7, 5.95, 3.2, [
    "Nangate45 只能做相對比較；只有 typical 角落",
    "功耗為預設活動率估算，非波形反標",
    "只支援方陣；scale 由外部提供",
    "只比了 1 條與 8 條 MAC，沒有中間點與脈動陣列"], size=14)
tb(s, 6.9, 4.9, 6.0, 0.45, [("後續工作", 20, True, NAVY)], tag="後續標題")
bullets(s, 6.9, 5.35, 5.95, 1.6, ["縮陣列、2／4 條 lane、脈動陣列", "補平方和與開根號；讀出埠加輸出暫存器"], size=14)

# ---- 附錄：VS Code 專案畫面
VS = ROOT / "docs" / "vscode"
for n, (ttl, items) in enumerate((("附錄：VS Code 專案畫面（1/2）", (("02_matmul_core.png", "序列式核心 matmul_core.v"), ("04_tb_ns_top.png", "系統 testbench tb_ns_top.v"))),
                                  ("附錄：VS Code 專案畫面（2/2）", (("05_sim_log.png", "模擬輸出：20 組全部位元一致、PASS"), ("08_waveform.png", "單一 OP_AAB 元素波形（VCD 重繪）"))))):
    s = new(16 + n, ttl, "專案完成後以 VS Code 開啟檢視的畫面（內容為真實檔案與真實輸出），不是開發過程中逐步拍攝的照片")
    for i, (f, cap) in enumerate(items):
        x = 0.55 + i * 6.2
        pic(s, VS / f, x, 1.75, w=6.0)
        tb(s, x, 5.55, 6.0, 0.5, [(cap, 14, False, MUTED)], tag="擷圖說明")

prs.save(OUT)
print("saved", OUT, "共", len(prs.slides), "張")
print("\n".join(warnings) if warnings else "文字量測：沒有超出方塊的文字")
