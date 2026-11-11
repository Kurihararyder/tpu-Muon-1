#!/usr/bin/env bash
# 一個指令完成：產生測試向量 -> 編譯 -> 模擬 ns_top -> 與 Python 模型比對。
# 用法：bash sim/run.sh [--variant base|w12|w24] [--arch serial|par] [--vcd <組別編號>]
#   --arch par   列平行核心（matmul_core_par）；預設 serial（單一 MAC）
#   --vcd 2   把第 2 組（random_0）的波形存成 sim/ns_top.vcd
#   --variant 位寬變體（階段 E 的位寬比較用）：base = Q3.13（預設）、w12 = Q3.9、w24 = Q3.19
set -eu
cd "$(dirname "$0")/.."
mkdir -p sim/build

VCDARG=""; VARIANT=base; ARCH=0; ASFX=""
while [ $# -gt 0 ]; do
    case "$1" in
        --vcd) VCDARG="+VCDCASE=${2:?請指定組別編號}"; shift 2 ;;
        --variant) VARIANT=${2:?請指定 base|w12|w24}; shift 2 ;;
        --arch) case "${2:?請指定 serial|par}" in serial) ARCH=0; ASFX="" ;; par) ARCH=1; ASFX="_par" ;; *) echo "未知架構"; exit 2 ;; esac; shift 2 ;;
        *) echo "未知參數 $1"; exit 2 ;;
    esac
done

# 各變體的參數：W F CF（係數 Q4.CF，CW = CF+4）ACCW，與 model/fixed_model.py 的 Cfg 對應
case "$VARIANT" in
    base) W=16; F=13; CF=12; ACCW=32; CA=14109;  CB=-19558;    CC=8321;   SFX="" ;;
    w12)  W=12; F=9;  CF=9;  ACCW=24; CA=1764;   CB=-2445;     CC=1040;   SFX="_w12" ;;
    w24)  W=24; F=19; CF=18; ACCW=44; CA=902955; CB=-1251738;  CC=532546; SFX="_w24" ;;
    *) echo "未知變體 $VARIANT"; exit 2 ;;
esac
CW=$((CF + 4))
OUT=sim/out_rtl${SFX}${ASFX}.hex

PY=${PYTHON:-python3}

echo "[1/4] 產生測試向量（變體 $VARIANT：W=$W F=$F CF=$CF ACCW=$ACCW）"
(cd model && $PY gen_vectors.py --w $W --f $F --cf $CF --accw $ACCW --suffix "$SFX")

NCASES=$(wc -l < data/vec_names${SFX}.txt)

echo "[2/4] 編譯 RTL 與 testbench"
iverilog -g2012 -Wall -Wno-timescale \
    -Ptb_ns_top.NCASES=$NCASES -Ptb_ns_top.ARCH=$ARCH -Ptb_ns_top.W=$W -Ptb_ns_top.F=$F -Ptb_ns_top.CF=$CF -Ptb_ns_top.CW=$CW \
    -Ptb_ns_top.ACCW=$ACCW -Ptb_ns_top.COEF_A=$CA -Ptb_ns_top.COEF_B=$CB -Ptb_ns_top.COEF_C=$CC \
    -o sim/build/tb_ns_top${SFX}${ASFX}.vvp tb/tb_ns_top.v rtl/ns_top.v rtl/ns_ctrl.v rtl/matmul_core.v \
    rtl/matmul_core_par.v rtl/mac_unit.v rtl/norm_scale.v

echo "[3/4] 模擬"
vvp -n sim/build/tb_ns_top${SFX}${ASFX}.vvp $VCDARG +VIN=data/vec_in${SFX}.hex +VEXP=data/vec_exp${SFX}.hex +OUT=$OUT \
    | tee sim/build/tb_ns_top${SFX}${ASFX}.log | grep -aE "^(case|共比對|PASS|FAIL)"
grep -aq "^PASS tb_ns_top" sim/build/tb_ns_top${SFX}${ASFX}.log

echo "[4/4] 與 Python 模型比對"
(cd model && $PY compare_rtl.py --w $W --f $F --suffix "$SFX" --out ../$OUT) | tee sim/build/compare${SFX}${ASFX}.log
