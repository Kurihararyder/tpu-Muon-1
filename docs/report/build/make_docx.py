"""產生實驗報告（Word）：docs/report/Muon晶片_實驗報告.docx"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from common import FIGS, FONT, ROOT, S, arch_numbers, sim_cases

OUT = ROOT / "docs" / "report" / "Muon晶片_實驗報告.docx"
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.left_margin = sec.right_margin = Cm(2.2)
sec.top_margin = sec.bottom_margin = Cm(2.2)


def set_font(style_or_run, size=None, bold=None, color=None):
    f = style_or_run.font
    f.name = FONT
    if size: f.size = Pt(size)
    if bold is not None: f.bold = bold
    if color: f.color.rgb = RGBColor.from_string(color)
    el = style_or_run.element if hasattr(style_or_run, "element") else style_or_run._element
    rpr = el.get_or_add_rPr() if hasattr(el, "get_or_add_rPr") else el.rPr
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts"); rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), FONT)


for name, size, color in (("Normal", 11, None), ("Heading 1", 17, "1F4E8C"), ("Heading 2", 13.5, "1F4E8C"),
                          ("Heading 3", 12, "333333"), ("Title", 26, "1F4E8C")):
    st = doc.styles[name]
    set_font(st, size, bold=name != "Normal", color=color)
doc.styles["Normal"].paragraph_format.line_spacing = 1.35
doc.styles["Normal"].paragraph_format.space_after = Pt(6)


def P(text, bold=False, size=None, align=None, color=None, italic=False, after=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    set_font(r, size, bold, color)
    r.italic = italic
    if align: p.alignment = align
    if after is not None: p.paragraph_format.space_after = Pt(after)
    return p


def B(text, bold_lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_lead:
        r = p.add_run(bold_lead); set_font(r, bold=True)
    r = p.add_run(text); set_font(r)
    p.paragraph_format.space_after = Pt(3)
    return p


def H(text, lvl=1):
    h = doc.add_heading(text, level=lvl)
    for r in h.runs: set_font(r)
    return h


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def T(header, rows, widths=None, size=9.5, bold_rows=()):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]; c.text = ""
        r = c.paragraphs[0].add_run(h); set_font(r, size, True, "FFFFFF")
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        shade(c, "1F4E8C")
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v)); set_font(r, size, ri in bold_rows)
            cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i else WD_ALIGN_PARAGRAPH.LEFT
            if ri % 2: shade(cells[i], "F2F5FA")
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths): row.cells[i].width = Cm(w)
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(1); p.paragraph_format.line_spacing = 1.1
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


fig_no = [0]
tab_no = [0]


def FIG(path, caption, width=15.5):
    doc.add_picture(str(path), width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    fig_no[0] += 1
    P(f"圖 {fig_no[0]}　{caption}", size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER, color="52514E", after=10)


def CAP(text):
    tab_no[0] += 1
    P(f"表 {tab_no[0]}　{text}", size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER, color="52514E", after=3)


# 頁尾頁碼
fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
for tag, txt in (("begin", None), (None, "PAGE"), ("end", None)):
    r = fp.add_run(); set_font(r, 9)
    if tag:
        e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), tag); r._r.append(e)
    else:
        e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt; r._r.append(e)

# ================= 封面 =================
for _ in range(5): P("")
P("Muon 晶片", bold=True, size=34, align=WD_ALIGN_PARAGRAPH.CENTER, color="1F4E8C", after=4)
P("Newton-Schulz 正交化硬體實作與開源流程評估", bold=True, size=20, align=WD_ALIGN_PARAGRAPH.CENTER, after=30)
P("實　驗　報　告", size=18, align=WD_ALIGN_PARAGRAPH.CENTER, after=60)
for l in ("指導教授：劉志俊 老師", "靜宜大學 資訊工程學系／晶片設計學士學位學程", "報告人：＿＿＿＿＿＿＿＿（請自行填寫姓名與學號）",
          "報告日期：2026 年 11 月 11 日"):
    P(l, size=13, align=WD_ALIGN_PARAGRAPH.CENTER, after=8)
doc.add_page_break()

# ================= 摘要 =================
H("摘要")
a = arch_numbers()
P("Muon 最佳化器以五次 Newton-Schulz 迭代把梯度（動量）矩陣推向近似正交，整個運算只有矩陣乘法與加法，適合以硬體實作。"
  "本實驗把這個核心運算做成可合成的 Verilog 電路，並在筆電上以開源 EDA 工具（Icarus Verilog、Yosys、OpenROAD，經由 OpenROAD-flow-scripts）"
  "完成功能驗證、合成與佈局繞線的初步評估，製程庫為 Nangate45。")
P("主要成果：")
B("以 Python 黃金模型與數值格式評估，選定資料格式 Q3.13（16 位元定點）、係數 Q4.12、累加器 32 位元；平均誤差約 4.6e-4。", "數值格式：")
B("實作序列式（單一 MAC）與列平行（8 條 MAC）兩種架構，輸出彼此逐位元一致，也與 Python 位元精確整數模型逐位元一致（20 組測試向量、1,280 個輸出元素）。", "RTL 與驗證：")
B("序列式合成面積約 40,140 µm²，內部資料路徑可達 1.8 ns（約 555 MHz）；一次 8x8 運算 8,527 個週期。", "合成與佈局繞線：")
B(f"列平行版以約 {a['area'][1]/a['area'][0]:.2f} 倍面積換得約 {a['thr'][1]/a['thr'][0]:.1f} 倍吞吐量，吞吐量／面積約 {a['tpa'][1]/a['tpa'][0]:.1f} 倍；"
  "位寬比較顯示 16 位元是精度與面積的合理折衷。", "比較實驗：")
P("注意：Nangate45 為開源製程庫，數字只能做相對比較，不能直接當成實驗室製程的結果；功耗為預設活動率估算，不是由模擬波形反標。", italic=True, size=10, color="52514E")

# ================= 1 緒論 =================
H("1　背景與目標")
P("本專案源自指導教授的投影片「Muon 渺子矩陣正交化最佳化器」，其「未來工作」提到「Muon 晶片」。"
  "目標是把 Muon 的核心運算做成硬體，先在筆電以開源流程完成功能驗證與合成、佈局繞線的初步評估，之後再搬到實驗室的商用工具（VCS、Design Compiler、PrimeTime、IC Compiler II）重跑。")
P("實驗流程分為五個階段：")
T(["階段", "內容", "主要產出"],
  [["A", "Python 黃金模型", "golden.py、eval_golden.py"],
   ["B", "數值格式評估", "format_eval.py、docs/format_study.md"],
   ["C", "RTL 設計（Verilog）", "rtl/ 五個模組＋列平行核心、各模組 testbench"],
   ["D", "模擬驗證", "sim/run.sh、測試向量、波形"],
   ["E", "合成與佈局繞線、PPA 比較", "flow/、docs/ppa_table.md、版面圖"]],
  widths=[1.8, 6.0, 8.0])

# ================= 2 演算法 =================
H("2　演算法與黃金模型（階段 A）")
P("輸入梯度矩陣 G，輸出近似正交矩陣（奇異值被推到約 0.7～1.2）。係數 a = 3.4445、b = −4.7750、c = 2.0315。")
for l in ("X = G / (‖G‖F + eps)，使奇異值不大於 1", "重複 5 次：A = X·Xᵀ；B = b·A + c·A·A；X = a·X + B·X",
          "輸出 X"):
    B(l)
P("每輪三次矩陣乘法，沒有 SVD。縮放步驟需要平方和與開根號，是硬體上較麻煩的部分；第一版由外部預先算好縮放值再輸入，並已在文件註明。")
P("黃金模型 model/golden.py 以 float64 實作。以 4x4、8x8、16x16、8x16 各 10 組隨機種子檢查：")
T(["形狀", "輸出奇異值最小", "最大", "與 U·Vᵀ 的 Frobenius 誤差（平均）", "落在 0.5～1.3 的比例"],
  [["4x4", "0.682", "1.134", "0.396", "100%"], ["8x8", "0.682", "1.134", "0.511", "100%"],
   ["16x16", "0.249", "1.168", "0.774", "99.4%"], ["8x16", "0.682", "1.134", "0.541", "100%"]],
  widths=[2.2, 3.2, 2.2, 5.2, 3.6])
CAP("黃金模型的奇異值範圍（每組形狀 10 個隨機種子）")
P("輸出奇異值並非全部落在 0.7～1.2：16x16 的種子 7 輸入矩陣近乎奇異（縮放後最小奇異值約 0.0005），五輪只能推到 0.25，這是 Newton-Schulz 五輪的演算法特性，不是程式錯誤。"
  "因此驗收準則改為「至少 99% 的奇異值落在 0.5～1.3 且最大值不超過 1.3」（此準則為本實驗自訂）。"
  "與 U·Vᵀ 的誤差 0.4～0.8 是因為演算法只把奇異值推到 1 附近、不會精確收斂到 1，所以後續一律以黃金模型作為比較基準，而不是 U·Vᵀ。")

# ================= 3 格式 =================
H("3　數值格式評估（階段 B）")
H("3.1　假設與方法", 2)
P("使用者未指定時採用的預設假設（非老師指定）：矩陣 8x8、資料 16 位元定點。評估 FP32、bf16、FP16 三種浮點，以及 Q4.12、Q8.8、Q2.14 三種 16 位元定點，另外加入 Q3.13 作為附加候選。"
  "浮點在每次乘法與加法後量化；定點則以寬累加器累加，每個矩陣運算結果寫回儲存格式時量化一次（含飽和）。係數 a、b、c 為常數暫存器，定點一律用 Q4.12。"
  "測試資料為 20 組標準常態隨機矩陣、5 組病態矩陣（條件數 1e1～1e5）、零矩陣與單位矩陣。")
H("3.2　中間值範圍", 2)
T(["變數", "最大絕對值", "所需整數位（含符號）"],
  [["X", "0.895", "1"], ["A = X·Xᵀ", "1.383", "2"], ["A·A", "1.948", "2"], ["B = bA + cA²", "2.737", "3"],
   ["B·X", "2.440", "3"], ["X 新值", "0.939", "1"]], widths=[5, 4, 5])
CAP("各中間值的最大範圍（float64，25 組輸入、5 輪）")
P("B 需要 3 個整數位（範圍 ±4）。這不只是實測：B 的元素絕對值不會超過其譜範數，也就是 p(λ) = −4.775λ + 2.0315λ² 在 λ = σ² 上的值；只要奇異值 σ ≤ 1.2，p 的最小值約 −2.81，與實測 2.737 吻合，離 ±4 還有約 1.4 倍餘裕。"
  "因此 Q2.14（範圍 ±2）必然在 B 飽和，實測確實整個發散。")
FIG(FIGS / "fig_format.png", "各數值格式對 float64 黃金模型的平均絕對誤差（20 組隨機 8x8，四捨五入）", 14.5)
H("3.3　選定格式", 2)
P("選定：資料 Q3.13（16 位元）、四捨五入、累加器 32 位元（Q6.26，乘積不捨入）、係數 Q4.12。理由：")
B("3 個整數位剛好涵蓋最大值 2.74 並留有餘裕；Q4.12 多出的整數位用不到，等於少一位小數精度。")
B("同為 16 位元，Q3.13 的平均誤差約為 Q4.12 的 0.65 倍，病態矩陣最大誤差約 0.46 倍；隨機矩陣最大誤差兩者相近（6.1e-3 對 4.6e-3），差異在雜訊內。")
B("四捨五入優於截斷（截斷有負偏差，最大誤差約 2～3 倍），硬體成本只多一個常數加法。")
B("精度優於 bf16 約 40 倍、優於 FP16 約 5 倍，而且乘加單元是純整數，面積與時序都較浮點小。")
B("32 位元累加器、乘積不捨入，讓 RTL 與 Python 位元精確模型可以逐位元一致。24 位元累加器精度相當，列為位寬比較的後續選項。")
P("Q3.13 不在原先指定的候選清單內，是依範圍分析加入的附加候選；RTL 以參數化設計，要改回 Q4.12 只需把 F 設為 12。", italic=True, size=10, color="52514E")

# ================= 4 RTL =================
H("4　RTL 設計（階段 C）")
H("4.1　模組與介面", 2)
T(["模組", "功能"],
  [["mac_unit", "兩級管線乘加單元；clr 以乘積取代累加器，sh 讓係數乘積左移以對齊小數點"],
   ["norm_scale", "X0 = G × scale，四捨五入並飽和；scale = 1/(‖G‖F+eps) 由外部預先算好"],
   ["matmul_core", "序列式核心：單一 MAC、X／A／B 三個暫存器陣列，逐元素執行 OP_A／OP_AAB／OP_X／OP_COMMIT"],
   ["matmul_core_par", "列平行核心：8 條 MAC，一個命令算完一整列；數值運算與序列式完全相同"],
   ["ns_ctrl", "FSM：五輪 ×（A → AAB → X → COMMIT）；ROWMODE 參數切換逐元素或逐列命令"],
   ["ns_top", "頂層；ARCH 參數選架構；記憶體式載入埠與讀出埠"]], widths=[3.4, 12.6], size=10)
CAP("RTL 模組一覽")
P("介面採記憶體式（每週期載入一個元素、以位址讀出一個元素），避免 N·N·W = 1,024 位元的寬匯流排佔用大量腳位，對佈局繞線較友善。"
  "輸入 G 為 Q4.12，輸出為 Q3.13。")
H("4.2　運算流程與對稱性", 2)
B("A = X·Xᵀ 與 A·A 都是對稱矩陣，序列版只算上三角（含對角）並鏡射寫入，由 64 個元素降為 36 個；鏡射值與直接計算逐位元相同（乘積相同、加總順序相同）。")
B("B = b·A + c·A·A 的兩次係數乘法併入 A·A 的元素計算內，共用同一個 MAC，不另設乘法器。")
B("新的 X 先寫入 A 陣列（避免原地覆寫尚要使用的 X），每輪結束時以單一週期平行複製回 X 陣列。")
B("係數 Q4.12 乘資料 Q3.13 的小數位為 25 位，左移 1 位對齊累加器的 26 位。")
H("4.3　週期數", 2)
P("序列式每個元素的命令週期為 OP_A 11、OP_AAB 15、OP_X 12；一輪 = 36×11 + 36×15 + 64×12 + 1 = 1,705，五輪為 8,525，模擬實測 8,527。"
  "列平行版每個命令處理一整列，週期數相同，一輪 = 8×(11+15+12) + 1 = 305，五輪 1,527（模擬實測）。")

# ================= 5 驗證 =================
H("5　模擬驗證（階段 D）")
H("5.1　驗證方法", 2)
B("位元精確整數模型 model/fixed_model.py：與 RTL 一一對應，全部使用 int64 整數運算。它與階段 B 的浮點實作定點模型 200 組輸入完全一致。")
B("各模組獨立 testbench（Icarus Verilog）：mac_unit（500 組隨機序列）、norm_scale（5,000 筆含飽和）、ns_ctrl（685 個命令的順序，連跑兩次）、matmul_core 與 matmul_core_par（逐階段與整數參考比對，含小幅值與觸發飽和的大幅值兩輪）。")
B("系統 testbench：Python 產生 20 組測試向量，tb_ns_top 以 $readmemh 讀入、驅動 ns_top、與位元精確模型逐位元比對，並交替測試 start 與最後一筆載入同週期、以及載入後數週期兩種時機。")
B("變異測試：故意改壞 RTL（係數差 1 LSB、少加捨入常數、拿掉鏡射寫入、移位錯誤、累加改相減、少算對角、不飽和、lane 位址錯誤等），各 testbench 都能抓到。")
B("一鍵執行：bash sim/run.sh（可加 --variant w12|w24、--arch par、--vcd N）。")
H("5.2　結果", 2)
rows = [[n, e, mx, mn, sv] for n, e, mx, mn, sv in sim_cases()]
T(["案例", "與位元精確模型", "對 float64 最大誤差", "平均誤差", "輸出奇異值範圍"], rows, widths=[3.6, 3.0, 3.6, 2.8, 3.4], size=9)
CAP("20 組系統測試向量（序列式；列平行版、12 位元與 24 位元變體結果同樣逐位元一致）")
P("20 組、1,280 個輸出元素全部與位元精確模型逐位元一致。與 float64 的誤差：隨機矩陣最大約 1e-3～2e-3；病態矩陣因輸入奇異值極小、五輪來不及推到 1，誤差較大（條件數 1e5 時最大 5.7e-2），這是演算法與 16 位元格式的特性，RTL 與模型仍然一致。"
  "全零矩陣輸出全為 0（沒有除以零問題）。rank1 與 all_ones 的輸出奇異值上限只有 0.696，因為只有一個非零奇異值時它從 1 出發，係數多項式 3.4445−4.7750+2.0315 = 0.701，是 Muon 係數的設計行為，float64 黃金模型同樣如此。")
FIG(ROOT / "docs" / "waveform_overview.png", "ns_top 整段運算總覽：載入、五輪 A→AAB→X、done（由 VCD 重繪）", 15.5)
FIG(ROOT / "docs" / "waveform_zoom_aab.png", "單一 OP_AAB 元素的逐週期行為：AA 內積、量化、B1（b·A）、B2（c·AA）、寫回（由 VCD 重繪）", 15.5)
P("說明：本環境（WSL2＋WSLg）無法擷取 GTKWave 視窗，所以波形圖由 model/plot_vcd.py 讀同一個 VCD 重繪，內容與 GTKWave 看到的相同；docs/ns_top.gtkw 可在 GTKWave 載入同樣的訊號清單。圖內標籤為英文（環境沒有中文字型）。",
  size=10, italic=True, color="52514E")

# ================= 6 PPA =================
H("6　合成與佈局繞線（階段 E）")
H("6.1　設定", 2)
T(["項目", "設定"],
  [["工具", "Yosys 0.69+154、OpenROAD 26Q3-2754-g9928beba28、ORFS"],
   ["平台", "Nangate45（FreePDK45，typical 角落），單一時脈 clk"],
   ["佈局參數", "CORE_UTILIZATION = 40、PLACE_DENSITY = 0.60（核心面積 99,710 µm²，實際使用率 40.6%）"],
   ["SDC", "時脈週期可變；輸入／輸出延遲為週期的 20%"],
   ["流程", "完整 ORFS：合成 → floorplan → 佈局 → CTS → 繞線 → 填充 → 報表"]], widths=[3.0, 13.0])
CAP("ORFS 實驗設定")
H("6.2　基準設計結果（序列式、10 ns）", 2)
b = S["base"]
T(["指標", "數值"],
  [["合成面積／元件數", f"{b['synth_area_um2']:,.0f} µm²／{b['synth_cells']:,} 個（正反器 {b['flops']:,}）"],
   ["佈局後元件面積", f"{b['stdcell_area_um2']:,.0f} µm²"],
   ["內部路徑 slack", f"{b['r2r_slack_ns']:.2f} ns（10 ns 時脈）"],
   ["總功耗", f"{b['power_mw']:.2f} mW（預設活動率估算）"],
   ["收斂", "細部繞線 DRC 0、天線違規 0、setup／hold 無違規（hold slack +0.063 ns）、時脈偏移 0.027 ns"]],
  widths=[4.2, 11.8])
CAP("基準設計（序列式）在 10 ns 下的結果")
FIG(ROOT / "docs" / "layout" / "base_placement.png", "序列式設計的佈局（OpenROAD 內建繪圖輸出）", 9.5)
P("版面圖是 OpenROAD 內建繪圖的輸出，不是 KLayout 截圖；GDS／DEF 在 flow/work/results/nangate45/muon_ns/ 內，可用 KLayout 或 OpenROAD GUI 檢視。", size=10, italic=True, color="52514E")
H("6.3　I/O 路徑不能代表內部速度", 2)
P("ORFS 預設回報的 WNS 是 rd_addr → rd_data 的非同步讀出組合路徑，再加上 I/O 延遲（週期的 20% 乘 2），例如 10 ns 時 I/O 路徑 slack 為 +4.98 ns，內部路徑為 +8.09 ns，所以 ORFS 的「fmax 199 MHz」只是 I/O 約束的產物。"
  "為此另寫 flow/reg2reg.tcl，對每個變體的最終佈局重新分析暫存器到暫存器的內部路徑；報告中的內部 slack 與最高時脈都來自這個分析。")
H("6.4　時脈目標掃描", 2)
rows = []
for v, per in (("base", 10), ("clk5p0", 5), ("clk3p0", 3), ("clk2p0", 2), ("clk1p8", 1.8), ("clk1p6", 1.6)):
    r = S[v]
    rows.append([f"{per:g}", f"{r['stdcell_area_um2']:,.0f}", f"{r['r2r_slack_ns']:.3f}", f"{r['io_slack_ns']:.3f}",
                 "達標" if r["r2r_slack_ns"] >= 0 else "未達標", f"{r['power_mw']:.2f}"])
T(["時脈週期 (ns)", "佈局後面積 (µm²)", "內部 slack (ns)", "I/O slack (ns)", "內部時序", "功耗 (mW)"], rows,
  widths=[2.6, 3.2, 2.8, 2.8, 2.4, 2.2], size=9.5)
CAP("序列式設計的時脈掃描")
B("內部資料路徑在 1.8 ns（約 555 MHz）仍達標（slack +0.026 ns），1.6 ns 開始不達標（−0.111 ns）；關鍵路徑一貫是 MAC：運算元暫存器 → 乘法器 → 累加器。")
B("面積幾乎不隨時脈變化（合成面積固定 40,140 µm²；最緊的 1.6 ns 多了約 1.7% 的時序修復緩衝器）。")
B("功耗大致隨頻率線性成長（7.3 mW → 37.4 mW），漏電約 0.71 mW 不變。一次運算的能量幾乎不隨頻率變：10 ns 時約 0.62 µJ，1.8 ns 時約 0.57 µJ。")
FIG(FIGS / "fig_clock.png", "時脈掃描：內部路徑 slack（左）與總功耗（右）。列平行版只掃了 10、2、1.8、1.6 ns 四點", 16.0)

# ================= 7 位寬 =================
H("7　位寬比較")
w12, w16, w24 = S["w12"], S["base"], S["w24"]
T(["位寬", "資料格式", "合成面積", "相對 16 位元", "正反器", "功耗 @10 ns", "2 ns 內部 slack", "平均誤差", "最大誤差"],
  [["12", "Q3.9", f"{w12['synth_area_um2']:,.0f}", f"{w12['synth_area_um2']/w16['synth_area_um2']:.2f}×", f"{w12['flops']:,}", f"{w12['power_mw']:.2f} mW", f"{S['w12_clk2p0']['r2r_slack_ns']:+.3f}", "5.17e-3", "2.32e-2"],
   ["16", "Q3.13", f"{w16['synth_area_um2']:,.0f}", "1.00×", f"{w16['flops']:,}", f"{w16['power_mw']:.2f} mW", f"{S['clk2p0']['r2r_slack_ns']:+.3f}", "4.17e-4", "2.16e-3"],
   ["24", "Q3.19", f"{w24['synth_area_um2']:,.0f}", f"{w24['synth_area_um2']/w16['synth_area_um2']:.2f}×", f"{w24['flops']:,}", f"{w24['power_mw']:.2f} mW", f"{S['w24_clk2p0']['r2r_slack_ns']:+.3f}", "4.73e-5", "4.45e-4"]],
  widths=[1.2, 1.8, 2.0, 1.9, 1.4, 2.0, 2.2, 1.8, 1.8], size=8.5)
CAP("位寬比較（面積單位 µm²；誤差為 8 組隨機矩陣對 float64 的絕對誤差）")
FIG(FIGS / "fig_width.png", "位寬對面積與精度的影響", 15.0)
B("面積與位寬大致成線性（0.77× / 1× / 1.49×，位寬比為 0.75× / 1× / 1.5×），因為面積由「每個元素一個 W 位元暫存器＋讀取多工器」主導，乘法器（隨位寬平方成長）占比很小。")
B("位寬越大，乘法器與加法鏈越長，2 ns 時內部 slack 由 +0.296 ns（12 位元）降到 +0.034 ns（24 位元）。")
B("16 位元是合理的折衷：12 位元省 23% 面積，但誤差約為 10 倍（病態矩陣最大誤差 0.34）；24 位元多 49% 面積，誤差雖更小，但 16 位元的誤差（平均 4e-4）已遠小於演算法本身與 U·Vᵀ 的差距（0.4～0.8），沒有實質好處。")
P("三個位寬的 RTL 都經 sim/run.sh --variant 驗證，與各自的位元精確模型逐位元一致。", size=10, italic=True, color="52514E")

# ================= 8 架構 =================
H("8　架構比較：序列式 vs 列平行")
P("列平行版（ARCH = 1）有 8 條 MAC，每個命令處理整列的 8 個元素（lane j 負責第 j 個元素），所有 lane 在同一個週期處理同一個 k。"
  "數值運算與序列版完全相同，輸出逐位元一致。因為整列直接算，不再利用 A 的對稱性鏡射，但整體仍快很多。")
a = arch_numbers()
sB, pB = S["clk1p8"], S["par_clk2p0"]
T(["", "序列式 @1.8 ns", "列平行 @2.0 ns", "倍率"],
  [["週期／次", "8,527", "1,527", "5.58× 少"],
   ["延遲", f"{a['lat'][0]:.2f} µs", f"{a['lat'][1]:.2f} µs", f"{a['lat'][0]/a['lat'][1]:.1f}× 快"],
   ["吞吐量", f"{a['thr'][0]:.1f} 次／ms", f"{a['thr'][1]:.1f} 次／ms", f"{a['thr'][1]/a['thr'][0]:.1f}×"],
   ["佈局後面積", f"{a['area'][0]:,.0f} µm²", f"{a['area'][1]:,.0f} µm²", f"{a['area'][1]/a['area'][0]:.2f}×"],
   ["正反器", f"{sB['flops']:,}", f"{pB['flops']:,}", "—"],
   ["功耗", f"{sB['power_mw']:.2f} mW", f"{pB['power_mw']:.2f} mW", "—"],
   ["吞吐量／面積（次／ms／mm²）", f"{a['tpa'][0]:,.0f}", f"{a['tpa'][1]:,.0f}", f"{a['tpa'][1]/a['tpa'][0]:.1f}×"]],
  widths=[5.2, 3.8, 3.8, 3.2], bold_rows=(6,))
CAP("各自在最快、時序仍達標的時脈下比較（序列式 1.8 ns、列平行 2.0 ns）")
FIG(FIGS / "fig_arch.png", "兩種架構的延遲、面積與吞吐量／面積", 15.5)
FIG(FIGS / "fig_breakdown.png", "合成面積分布：多出來的面積幾乎全是額外的 MAC", 15.0)
B("用約 1.5 倍面積換約 5 倍吞吐量，吞吐量／面積約 3.3 倍（固定 10 ns 時為 3.7 倍）。列平行版最高時脈較低（2.0 ns 達標，1.8 ns slack −0.014 ns），因為 8 條 MAC 共用的運算元與控制訊號扇出變大。")
B("多出的面積幾乎全是 7 條額外 MAC：合成後 MUX2 數量與面積不變（約 8,500 個、15.9k µm²），正反器多 442 個（約 +2.3k µm²），全加器／半加器多約 +10k µm²，其餘組合邏輯多約 +9k µm²；每條額外 MAC 約 3k µm²。")
B("每次運算的能量約降為 1/4.7（10 ns：0.620 → 0.132 µJ），因為完成同樣工作的週期少很多；但功耗是預設活動率估算，兩種架構的實際切換活動不同，這個比值只能當趨勢。")
B("暫存器陣列與讀取多工器的絕對面積幾乎不變（約 30k → 32k µm²），但占比從序列版的約 76% 降到列平行版的約 53%；平行化之後若還要縮面積，仍要處理陣列。")
B("列平行版 10 ns 下 DRC 0、天線 0、hold slack +0.069 ns、setup 無違規。")

# ================= 9 結論 =================
H("9　結論與後續工作")
P("本實驗完成了 Muon 核心運算從演算法、數值格式、RTL、模擬驗證到開源流程合成與佈局繞線的完整評估：")
B("Q3.13（16 位元）定點格式在精度與成本上最合適，且 RTL 與位元精確模型逐位元一致。")
B("面積由暫存器陣列與讀取多工器主導，MAC 本身占比很小，所以平行化很划算：列平行版以約 1.5 倍面積換約 5 倍吞吐量。")
B("內部資料路徑可達約 500～555 MHz（Nangate45 typical 角落）。")
P("後續工作：")
B("縮減暫存器陣列：A、B 只存對稱矩陣的一半、B 與 A 共用、改用 SRAM 巨集。")
B("評估中間架構（例如 2／4 條 lane）與真正的脈動陣列。")
B("補上縮放步驟（平方和與開根號），並支援 rows > cols 的轉置情況。")
B("為讀出埠加輸出暫存器，消除 I/O 組合路徑；以模擬波形反標做功耗分析。")
B("搬到實驗室的 VCS、Design Compiler、PrimeTime、IC Compiler II 以實驗室製程重跑；RTL、testbench、測試向量與黃金模型可直接沿用，SDC 需換成實驗室的製程庫與約束。")

H("10　限制與誠實聲明")
for l in ("資料格式 Q3.13 不在原先候選清單內，是依範圍分析加入的；使用者未指定時採用的 8x8、16 位元定點是假設，非老師指定。",
          "Nangate45 的數字只能做相對比較，不能直接當成實驗室製程的結果；只使用 typical 一個角落，沒有多角落與 OCV。",
          "功耗為 OpenROAD 預設活動率估算，不是由模擬波形反標；能量比值僅為趨勢。",
          "波形圖由 VCD 重繪、版面圖為 OpenROAD 內建繪圖輸出，兩者都不是 GTKWave 或 KLayout 截圖。",
          "只支援方陣；scale 由外部提供（範圍 0～16）；累加器溢位時環繞而非飽和（8x8 實測最大值 2.74，Q6.26 餘裕充足，矩陣放大或輸入分布不同時須重新檢查）。",
          "架構比較只做了序列式與 8 條 lane 的列平行，沒有中間點與脈動陣列。",
          "ORFS 的最佳化帶有隨機性，個位數百分比的差異不應過度解讀。"):
    B(l)

H("附錄 A　重現方式與檔案")
for c in ("bash sim/run.sh                       # 產生向量、編譯、模擬、比對",
          "bash sim/run.sh --arch par            # 列平行架構",
          "bash sim/run.sh --variant w12         # 位寬變體（w12／w24）",
          "bash sim/run_unit.sh                  # 各模組獨立 testbench 與 lint",
          "CLOCK_PERIOD=10 flow/run_flow.sh base # ORFS 完整流程",
          "flow/run_experiments.sh               # 時脈掃描、位寬與架構比較",
          "python3 flow/summarize.py             # 彙整 PPA 表"):
    p = doc.add_paragraph(); r = p.add_run(c); r.font.name = "Consolas"; r.font.size = Pt(9.5)
    p.paragraph_format.space_after = Pt(1)
P("")
T(["路徑", "內容"],
  [["model/", "黃金模型、格式評估、位元精確整數模型、向量產生與比對、波形繪製"],
   ["rtl/", "mac_unit、norm_scale、matmul_core、matmul_core_par、ns_ctrl、ns_top"],
   ["tb/、sim/", "各模組 testbench、系統 testbench、run.sh、run_unit.sh"],
   ["flow/", "ORFS 設定、執行與彙整腳本、流程輸出（work/）"],
   ["docs/", "format_study.md、rtl_design.md、sim_report.md、ppa_table.md、波形圖、版面圖"]], widths=[3.2, 12.8])

doc.add_page_break()
H("附錄 B　VS Code 專案畫面")
P("下列畫面是專案完成後，以 VS Code（Remote-WSL，Ubuntu-22.04）開啟專案所擷取，檔案內容與模擬輸出皆為專案中真實存在的資料。"
  "這些畫面不是開發過程中逐步拍攝的照片。", size=10.5, italic=True, color="52514E")
SHOTS = [("01_ns_top.png", "頂層 rtl/ns_top.v 與專案檔案總管"), ("02_matmul_core.png", "序列式核心 rtl/matmul_core.v"),
         ("03_matmul_core_par.png", "列平行核心 rtl/matmul_core_par.v"), ("04_tb_ns_top.png", "系統 testbench tb/tb_ns_top.v"),
         ("05_sim_log.png", "sim/run.sh 的模擬輸出：20 組全部位元一致、PASS"), ("06_compare_log.png", "與位元精確模型及 float64 的比對表"),
         ("07_fixed_model.png", "位元精確整數模型 model/fixed_model.py"), ("08_waveform.png", "單一 OP_AAB 元素的波形（由 VCD 重繪）"),
         ("09_layout.png", "OpenROAD 佈局圖"), ("10_flow_config.png", "ORFS 設定 flow/config.mk"),
         ("11_ppa_table.png", "PPA 報告 docs/ppa_table.md"), ("12_readme.png", "README.md")]
for i, (f, cap) in enumerate(SHOTS):
    doc.add_picture(str(ROOT / "docs" / "vscode" / f), width=Cm(15.0))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    P(f"圖 B{i+1}　{cap}", size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER, color="52514E", after=8)

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print("saved", OUT)
