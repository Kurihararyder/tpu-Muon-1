#!/usr/bin/env bash
# 平行執行 PPA 比較實驗（時脈掃描 + 位寬比較）。base 另外以 `CLOCK_PERIOD=10 flow/run_flow.sh base` 執行。
# 變體名稱：par*（列平行架構 ARCH=1，不同時脈）；clk2p0～clk6p0（Q3.13、不同時脈目標，單位 ns）；w12／w24（10 ns，不同資料位寬）
set -u
here=$(cd "$(dirname "$0")" && pwd)
export NUM_CORES=4
# Yosys 的 chparam 無法解析負數，所以負係數 b 以 CW 位元的二補數位元型樣傳入
#   w12：CW=13，-2445 -> 8192-2445 = 5747；w24：CW=22，-1251738 -> 4194304-1251738 = 2942566
W12="W 12 F 9 CW 13 CF 9 ACCW 24 COEF_A 1764 COEF_B 5747 COEF_C 1040"
W24="W 24 F 19 CW 22 CF 18 ACCW 44 COEF_A 902955 COEF_B 2942566 COEF_C 532546"
run() {  # run <variant> <period> [params]；環境變數 ONLY="w12 w24" 可只跑指定變體
    local v=$1 p=$2 params=${3:-}
    [ -z "${ONLY:-}" ] || [[ " $ONLY " == *" $v "* ]] || return 0
    ( start=$(date +%s)
      CLOCK_PERIOD=$p TOP_PARAMS="$params" "$here/run_flow.sh" "$v" > "$here/$v.log" 2>&1
      echo "$v 結束（碼 $?），耗時 $(( $(date +%s) - start )) 秒" >> "$here/experiments.status" ) &
}
: >> "$here/experiments.status"
run clk6p0 6.0
run clk5p0 5.0
run clk4p0 4.0
run clk3p0 3.0
run clk2p5 2.5
run clk2p0 2.0
run clk1p8 1.8
run clk1p6 1.6
run par 10.0 "ARCH 1"
run par_clk2p0 2.0 "ARCH 1"
run par_clk1p8 1.8 "ARCH 1"
run par_clk1p6 1.6 "ARCH 1"
run w12 10.0 "$W12"
run w12_clk2p0 2.0 "$W12"
run w24_clk2p0 2.0 "$W24"
run w24 10.0 "$W24"
wait
echo "全部完成" >> "$here/experiments.status"
