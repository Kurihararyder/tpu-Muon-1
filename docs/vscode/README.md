# VS Code 專案畫面

這些畫面是**專案完成後**，於 2026-11-11 以 VS Code（Remote-WSL，Ubuntu-22.04）開啟 `~/muon_chip` 所擷取，內容為專案裡真實存在的檔案與真實的模擬輸出。
**它們不是開發過程中逐步拍攝的照片**，也不能當作開發歷程的證明。

| 檔案 | 畫面內容 |
|---|---|
| 01_ns_top.png | rtl/ns_top.v（頂層）與專案檔案總管 |
| 02_matmul_core.png | rtl/matmul_core.v（序列式核心） |
| 03_matmul_core_par.png | rtl/matmul_core_par.v（列平行核心） |
| 04_tb_ns_top.png | tb/tb_ns_top.v（系統 testbench） |
| 05_sim_log.png | sim/build/tb_ns_top.log：20 組全部「位元一致」、PASS（`bash sim/run.sh` 的輸出） |
| 06_compare_log.png | sim/build/compare.log：與位元精確模型及 float64 的比對表 |
| 07_fixed_model.png | model/fixed_model.py（位元精確整數模型） |
| 08_waveform.png | docs/waveform_zoom_aab.png（由 VCD 重繪的單一元素波形） |
| 09_layout.png | docs/layout/base_placement.png（OpenROAD 佈局圖） |
| 10_flow_config.png | flow/config.mk（ORFS 設定） |
| 11_ppa_table.png | docs/ppa_table.md（PPA 報告） |
| 12_readme.png | README.md |
