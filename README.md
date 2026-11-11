# Muon 晶片專案：Newton-Schulz 正交化硬體實作

指導教授：劉志俊老師（靜宜大學資訊工程學系／晶片設計學士學位學程）。
把 Muon 最佳化器的核心運算（五次 Newton-Schulz 迭代）做成硬體：Python 黃金模型 → 數值格式評估 → Verilog RTL → 模擬驗證 → 開源流程（Yosys + OpenROAD，經由 ORFS）合成與佈局繞線。

## 結果摘要

| 項目 | 結果 |
|---|---|
| 設計 | 8x8、五輪；資料 Q3.13（16 位元）、係數 Q4.12、累加器 32 位元。兩種架構：序列式單一 MAC（`ARCH=0`，基準）與列平行 8 條 MAC（`ARCH=1`） |
| 功能驗證 | 20 組測試向量（含全零、單位矩陣、病態矩陣）、1280 個輸出元素與位元精確模型**逐位元一致** |
| 精度 | 對 float64 黃金模型：隨機 8x8 平均誤差約 4e-4、最大約 2e-3 |
| 延遲 | 序列式 8,527 個週期／次運算；列平行 1,527 個週期 |
| 面積（nangate45） | 合成後約 40,140 µm²（19,331 個元件，3,213 個正反器） |
| 時脈 | 序列式內部路徑在 1.8 ns（約 555 MHz）仍達標，1.6 ns 不達標；列平行在 2.0 ns（500 MHz）達標 |
| 架構比較 | 列平行用約 1.52 倍面積換 5.0 倍吞吐量，吞吐量／面積約 3.3 倍（各自在最快達標時脈下） |
| 功耗 | 7.3 mW @100 MHz、37.4 mW @556 MHz（預設活動率估算） |
| 版圖 | DRC 0、天線 0、hold／setup 無違規 |

Nangate45 的數字只能做相對比較，不能直接當成實驗室製程的結果。

## 如何執行

環境：WSL2 Ubuntu 22.04；Icarus Verilog、Verilator、GTKWave、KLayout、Python 3 + numpy + matplotlib；ORFS 在 `~/OpenROAD-flow-scripts`（`source ~/OpenROAD-flow-scripts/env.sh` 會設好 Yosys 與 OpenROAD）。

```bash
bash sim/run.sh                  # 產生向量 -> 編譯 -> 模擬 -> 與模型比對（一個指令）
bash sim/run.sh --vcd 2          # 同上，並把第 2 組的波形存成 sim/ns_top.vcd
bash sim/run.sh --variant w12    # 位寬變體（w12／w24），供 PPA 比較
bash sim/run.sh --arch par       # 列平行架構（可與 --variant 併用）
bash sim/run_unit.sh             # 各模組獨立 testbench + Verilator lint
python3 model/plot_vcd.py        # 由 VCD 重繪波形圖到 docs/
```

```bash
python3 model/golden.py                 # 黃金模型
python3 model/eval_golden.py            # 階段 A：奇異值範圍與對 SVD 解的誤差
python3 model/format_eval.py            # 階段 B：數值格式評估（輸出 docs/format_results.md）
python3 model/check_fixed_model.py      # 位元精確整數模型與格式評估模型的交叉驗證
```

```bash
CLOCK_PERIOD=10 flow/run_flow.sh base   # ORFS 完整流程（約 5～10 分鐘），輸出在 flow/work/
flow/run_experiments.sh                 # 時脈掃描與位寬比較（平行執行）
python3 flow/summarize.py               # 彙整 PPA 表（flow/summary_table.md）
```

## 目錄

```
muon_chip/
├── model/   golden.py（黃金模型）、format_eval.py（格式評估）、fixed_model.py（位元精確整數模型）、
│            gen_vectors.py／compare_rtl.py（測試向量與比對）、plot_vcd.py（波形圖）
├── rtl/     mac_unit.v、norm_scale.v、matmul_core.v（序列）、matmul_core_par.v（列平行）、ns_ctrl.v、ns_top.v
├── tb/      各模組 testbench 與 tb_ns_top.v（系統）
├── sim/     run.sh（一鍵）、run_unit.sh；輸出與波形（VCD）
├── data/    測試向量（由 gen_vectors.py 產生）
├── flow/    ORFS 設定（config.mk、constraint.sdc）、執行與彙整腳本、work/（流程輸出）
└── docs/    各階段報告、波形圖、版面圖
```

## 設計說明

- 演算法：`X = G/‖G‖F`，之後五輪 `A = XXᵀ`、`B = bA + cA²`、`X = aX + BX`（a=3.4445、b=−4.7750、c=2.0315）。
- 序列版：單一 MAC 逐元素計算；列平行版（`ARCH=1`）：8 條 MAC 一次算一整列，輸出與序列版逐位元一致。序列版內：A 與 A·A 對稱，只算上三角再鏡射寫入；B 的兩次係數乘法併入 A·A 的元素計算內，共用同一個 MAC。
- 介面為記憶體式（載入埠／讀出埠），不使用 1024 位元的寬匯流排。
- 縮放值 `scale = 1/(‖G‖F + eps)` 由外部預先算好輸入，`norm_scale` 只做乘法、四捨五入與飽和。
- 詳見 [docs/rtl_design.md](docs/rtl_design.md)。

## 文件

| 文件 | 內容 |
|---|---|
| [docs/format_study.md](docs/format_study.md) | 數值格式評估與 RTL 預設格式的選擇理由 |
| [docs/rtl_design.md](docs/rtl_design.md) | RTL 模組、參數、介面、週期數 |
| [docs/sim_report.md](docs/sim_report.md) | 系統模擬結果與波形 |
| [docs/ppa_table.md](docs/ppa_table.md) | 合成、佈局繞線、PPA 比較與版面圖 |

## 假設與已知限制

- 使用者未指定時採用的假設：8x8、16 位元定點（非老師指定）。資料格式 Q3.13 不在原先候選清單內，是依範圍分析加入的，RTL 可用參數改回 Q4.12（`F=12`）。
- 只支援方陣；`scale` 由外部提供（範圍 0～16）；累加器溢位時環繞。
- 波形圖由 `model/plot_vcd.py` 重繪（環境無法擷取 GTKWave 視窗），不是 GTKWave 截圖；`docs/ns_top.gtkw` 可在 GTKWave 載入相同訊號。圖內標籤為英文（環境沒有中文字型）。
- 版面圖是 OpenROAD 內建繪圖的輸出，不是 KLayout 截圖。
- 架構比較只做了序列式 vs 8 lane 列平行，沒有中間點與脈動陣列；功耗為預設活動率估算（能量比值僅為趨勢）；只有 typical 角落。
- 讀出埠為非同步組合讀取，會形成 I/O 組合路徑，ORFS 預設回報的 WNS 因此不代表內部速度（詳見 docs/ppa_table.md 3.2）。
- 搬到實驗室商用工具（VCS／Design Compiler／PrimeTime／IC Compiler II）時：RTL、testbench、測試向量、黃金模型可直接沿用，SDC 需改用實驗室製程庫與約束；`rtl/` 內沒有工具專屬語法。
