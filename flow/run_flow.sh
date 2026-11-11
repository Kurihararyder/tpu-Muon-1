#!/usr/bin/env bash
# 用 ORFS（Yosys + OpenROAD，nangate45）跑完整流程：合成 -> 佈局 -> CTS -> 繞線 -> 報表。
# 用法：flow/run_flow.sh <variant> [make 目標，預設 finish]
# 環境變數：
#   CLOCK_PERIOD  時脈週期 ns（預設 10.0）
#   TOP_PARAMS    頂層參數，例："W 12 F 9 CF 9 CW 13 ACCW 24 ..."（預設為 Q3.13 設計）
#   CORE_UTILIZATION、PLACE_DENSITY 可覆寫
# 輸出：flow/work/{logs,reports,results,objects}/nangate45/muon_ns/<variant>/
set -eu
variant=${1:?請指定 variant 名稱}
target=${2:-finish}
here=$(cd "$(dirname "$0")" && pwd)
source "$HOME/OpenROAD-flow-scripts/env.sh" > /dev/null
cd "$FLOW_HOME"
make DESIGN_CONFIG="$here/config.mk" WORK_HOME="$here/work" FLOW_VARIANT="$variant" \
     NUM_CORES="${NUM_CORES:-8}" VERILOG_TOP_PARAMS="${TOP_PARAMS:-}" "$target"
