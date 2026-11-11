// ns_top 系統 testbench：讀入 data/vec_in.hex，逐組載入、啟動、等待 done、讀出，
// 與 data/vec_exp.hex（位元精確模型）逐位元比對，並把 RTL 輸出寫入 sim/out_rtl.hex 供 Python 再比對。
// 交替測試兩種 start 時機：與最後一筆載入同週期、以及載入結束後數個週期。
// plusargs：+VCDCASE=<n> 只傾印第 n 組的波形到 sim/ns_top.vcd（預設不傾印）
`timescale 1ns/1ps
module tb_ns_top;
    parameter NCASES = 18;
    parameter ARCH = 0;
    parameter W = 16, F = 13, GW = 16, CW = 16, CF = 12, ACCW = 32;
    parameter signed [CW-1:0] COEF_A = 16'sd14109, COEF_B = -16'sd19558, COEF_C = 16'sd8321;
    localparam N = 8, NN = 64, SW = 20;

    reg clk = 0, rst_n = 0;
    always #5 clk = ~clk;     // 100 MHz

    reg start = 0;
    reg [SW-1:0] scale = 0;
    reg ld_we = 0;
    reg [5:0] ld_addr = 0;
    reg [GW-1:0] ld_data = 0;
    reg [5:0] rd_addr = 0;
    wire [W-1:0] rd_data;
    wire busy, done;

    ns_top #(.N(N), .W(W), .F(F), .GW(GW), .ARCH(ARCH), .CW(CW), .CF(CF), .ACCW(ACCW),
            .COEF_A(COEF_A), .COEF_B(COEF_B), .COEF_C(COEF_C)) dut (
        .clk(clk), .rst_n(rst_n), .start(start), .scale(scale),
        .ld_we(ld_we), .ld_addr(ld_addr), .ld_data(ld_data),
        .rd_addr(rd_addr), .rd_data(rd_data), .busy(busy), .done(done)
    );

    reg [SW-1:0] vin  [0:NCASES*(NN+1)-1];
    reg [W-1:0]  vexp [0:NCASES*NN-1];

    integer c, n, errors = 0, case_errors, cycles, timeout, fout, vcdcase;
    integer total_cycles = 0, ncheck = 0;
    reg [W-1:0] got;
    reg [1023:0] f_vin, f_vexp, f_out;

    initial begin
        if (!$value$plusargs("VIN=%s", f_vin))   f_vin  = "data/vec_in.hex";
        if (!$value$plusargs("VEXP=%s", f_vexp)) f_vexp = "data/vec_exp.hex";
        if (!$value$plusargs("OUT=%s", f_out))   f_out  = "sim/out_rtl.hex";
        $readmemh(f_vin, vin);
        $readmemh(f_vexp, vexp);
        fout = $fopen(f_out, "w");
        if (!$value$plusargs("VCDCASE=%d", vcdcase)) vcdcase = -1;
        if (vcdcase >= 0) begin
            $dumpfile("sim/ns_top.vcd");
            $dumpvars(0, tb_ns_top);
            $dumpoff;
        end

        repeat (4) @(negedge clk);
        rst_n = 1;
        repeat (2) @(negedge clk);

        for (c = 0; c < NCASES; c = c + 1) begin
            case_errors = 0;
            if (c == vcdcase) $dumpon;

            // 載入：每個週期一個元素
            scale = vin[c*(NN+1)];
            for (n = 0; n < NN; n = n + 1) begin
                @(negedge clk);
                ld_we = 1; ld_addr = n; ld_data = vin[c*(NN+1) + 1 + n][GW-1:0];
                // 偶數組：最後一筆載入的同一週期就拉 start
                if (n == NN-1 && (c % 2 == 0)) start = 1;
            end
            @(negedge clk);
            ld_we = 0;
            if (c % 2 == 0) begin
                start = 0;
            end else begin
                repeat (3) @(negedge clk);   // 奇數組：載入結束後數個週期才 start
                start = 1;
                @(negedge clk);
                start = 0;
            end

            // start 之後 done 必須立即為 0（上一組的 done 不能殘留）
            cycles = 0; timeout = 0;
            if (done !== 1'b0) begin
                errors = errors + 1; case_errors = case_errors + 1;
                $display("FAIL case %0d：start 後 done 未清除", c);
            end
            while (!done && timeout < 50000) begin
                @(negedge clk); cycles = cycles + 1; timeout = timeout + 1;
                if (cycles == 3 && !busy) begin
                    errors = errors + 1; case_errors = case_errors + 1;
                    $display("FAIL case %0d：運算期間 busy 為 0", c);
                end
            end
            if (!done) begin
                errors = errors + 1; case_errors = case_errors + 1;
                $display("FAIL case %0d：逾時", c);
            end
            total_cycles = total_cycles + cycles;
            if (c == vcdcase) begin repeat (3) @(negedge clk); $dumpoff; end

            // 讀出並比對
            for (n = 0; n < NN; n = n + 1) begin
                rd_addr = n; #1;
                got = rd_data;
                $fdisplay(fout, "%h", got);
                ncheck = ncheck + 1;
                if (got !== vexp[c*NN + n]) begin
                    errors = errors + 1; case_errors = case_errors + 1;
                    if (case_errors < 6)
                        $display("FAIL case %0d [%0d]：RTL=%h 預期=%h", c, n, got, vexp[c*NN+n]);
                end
            end
            if (case_errors == 0) $display("case %2d：位元一致，約 %0d 個週期（start 到 done）", c, cycles);
            else                  $display("case %2d：不一致，約 %0d 個週期（start 到 done）", c, cycles);
            repeat (2) @(negedge clk);
        end

        $fclose(fout);
        $display("共比對 %0d 個輸出元素，平均 %0d 週期／組", ncheck, total_cycles / NCASES);
        if (errors == 0) $display("PASS tb_ns_top");
        else             $display("FAIL tb_ns_top：%0d 個錯誤", errors);
        $finish;
    end
endmodule
