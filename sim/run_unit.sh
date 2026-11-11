#!/usr/bin/env bash
# 執行各模組的獨立 testbench（Icarus Verilog），並對 RTL 做 Verilator lint。
set -u
cd "$(dirname "$0")/.."
mkdir -p sim/build
fail=0

run_tb() {  # run_tb <tb 名稱> <rtl 檔...>；環境變數 TBP 可附加 iverilog 參數（例如 -Ptb_ns_ctrl.ROWMODE=1）
    local tb=$1; shift
    iverilog -g2012 -Wall ${TBP:-} -o "sim/build/$tb.vvp" "tb/$tb.v" "$@" || { echo "FAIL $tb（編譯失敗）"; fail=1; return; }
    local out
    out=$(vvp -n "sim/build/$tb.vvp")
    echo "$out" | grep -E "PASS|FAIL|期望命令總數"
    echo "$out" | grep -q "^PASS" || fail=1
}

run_tb tb_mac_unit     rtl/mac_unit.v
run_tb tb_norm_scale   rtl/norm_scale.v
run_tb tb_ns_ctrl      rtl/ns_ctrl.v
run_tb tb_matmul_core  rtl/matmul_core.v rtl/mac_unit.v
TBP=-Ptb_ns_ctrl.ROWMODE=1 run_tb tb_ns_ctrl rtl/ns_ctrl.v   # 列模式
run_tb tb_matmul_core_par rtl/matmul_core_par.v rtl/mac_unit.v

if verilator --lint-only -Wall -Wno-DECLFILENAME -Wno-WIDTH -Irtl --top-module ns_top \
        rtl/ns_top.v rtl/ns_ctrl.v rtl/matmul_core.v rtl/matmul_core_par.v rtl/mac_unit.v rtl/norm_scale.v; then
    echo "PASS verilator lint"
else
    echo "FAIL verilator lint"; fail=1
fi

[ $fail -eq 0 ] && echo "== 全部通過 ==" || echo "== 有失敗項目 =="
exit $fail
