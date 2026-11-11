# 報告暫存器到暫存器（內部）最差路徑與 I/O 路徑。
# 為什麼要另外做：ns_top 的讀出埠是非同步讀取（rd_addr -> rd_data 為純組合路徑），再加上 I/O 延遲 = 週期 x 20% x 2，
# ORFS 回報的 WNS 通常是這條 I/O 路徑，不能代表內部資料路徑（MAC、記憶體讀取多工器）的速度。
# 用法：RESULTS=<results 目錄> openroad -exit flow/reg2reg.tcl
set platform $::env(HOME)/OpenROAD-flow-scripts/flow/platforms/nangate45
read_liberty $platform/lib/NangateOpenCellLibrary_typical.lib
read_db $::env(RESULTS)/6_final.odb
read_sdc $::env(RESULTS)/6_final.sdc
source $platform/setRC.tcl
read_spef $::env(RESULTS)/6_final.spef
puts "=== REG2REG ==="
report_checks -path_delay max -from [all_registers -clock_pins] -to [all_registers -data_pins] -digits 3 -fields {fanout}
puts "=== REG2REG_END ==="
puts "=== IO ==="
report_checks -path_delay max -from [all_inputs] -to [all_outputs] -digits 3
puts "=== IO_END ==="
