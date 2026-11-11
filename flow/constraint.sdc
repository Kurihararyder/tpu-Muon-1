# 時脈約束：預設 10 ns（100 MHz）；以環境變數 CLOCK_PERIOD（ns）覆寫。
# 輸入／輸出延遲取週期的 20%（10 ns 時為 2 ns）。
if { [info exists ::env(CLOCK_PERIOD)] } {
  set clk_period $::env(CLOCK_PERIOD)
} else {
  set clk_period 10.0
}
create_clock -name clk -period $clk_period [get_ports clk]
set_input_delay  [expr {$clk_period * 0.2}] -clock clk [all_inputs -no_clocks]
set_output_delay [expr {$clk_period * 0.2}] -clock clk [all_outputs]
