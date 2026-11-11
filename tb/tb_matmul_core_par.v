// matmul_core_par（列平行）獨立 testbench：直接下列命令，逐階段（A、AAB 的 B、X'、COMMIT）與 TB 內的整數參考比對。
// 兩輪：小幅值（不飽和）與大幅值（觸發飽和路徑）。
`timescale 1ns/1ps
module tb_matmul_core_par;
    localparam N = 8, W = 16, F = 13, NN = 64;
    localparam integer CA = 14109, CB = -19558, CC = 8321;

    reg clk = 0, rst_n = 0;
    always #5 clk = ~clk;

    reg cmd_valid = 0;
    reg [1:0] cmd_op = 0;
    reg [2:0] cmd_i = 0, cmd_j = 0;
    wire cmd_ready;
    reg ld_we = 0;
    reg [5:0] ld_addr = 0;
    reg signed [W-1:0] ld_data = 0;
    reg [5:0] rd_addr = 0;
    wire signed [W-1:0] rd_data;

    matmul_core_par #(.N(N), .W(W), .F(F)) dut (
        .clk(clk), .rst_n(rst_n),
        .cmd_valid(cmd_valid), .cmd_op(cmd_op), .cmd_i(cmd_i), .cmd_j(cmd_j), .cmd_ready(cmd_ready),
        .ld_we(ld_we), .ld_addr(ld_addr), .ld_data(ld_data),
        .rd_addr(rd_addr), .rd_data(rd_data)
    );

    // 參考：加 0.5 LSB、右移 13、飽和
    function signed [W-1:0] rs(input signed [63:0] v);
        reg signed [63:0] t;
        begin
            t = (v + 64'sd4096) >>> 13;
            if (t > 32767) rs = 16'sh7FFF;
            else if (t < -32768) rs = 16'sh8000;
            else rs = t[W-1:0];
        end
    endfunction

    reg rxn_sel = 0;
    integer rx [0:NN-1];
    integer ra [0:NN-1];
    integer raa [0:NN-1];
    integer rb [0:NN-1];
    integer rxn [0:NN-1];
    integer errors = 0, seed = 11;
    integer i, j, k, n, round, amp;
    reg signed [63:0] acc64;

    task issue(input [1:0] op, input [2:0] ii, input [2:0] jj);
        begin
            @(negedge clk);
            while (!cmd_ready) @(negedge clk);
            cmd_valid = 1; cmd_op = op; cmd_i = ii; cmd_j = jj;
            @(negedge clk);
            cmd_valid = 0;
        end
    endtask

    task wait_idle;
        begin
            @(negedge clk);
            while (!cmd_ready) @(negedge clk);
        end
    endtask

    task check_flat(input [127:0] name, input integer which);
        // which: 0 = A 陣列（ma_f），1 = B 陣列（mb_f）
        integer m;
        reg signed [W-1:0] got;
        integer expv;
        begin
            for (m = 0; m < NN; m = m + 1) begin
                got = (which == 0) ? dut.ma_f[m*W +: W] : dut.mb_f[m*W +: W];
                expv = (which == 0) ? (rxn_sel ? rxn[m] : ra[m]) : rb[m];
                if (got !== expv[W-1:0]) begin
                    errors = errors + 1;
                    if (errors < 10) $display("FAIL %0s[%0d]：got=%0d expect=%0d", name, m, got, expv);
                end
            end
        end
    endtask
    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1;

        for (round = 0; round < 2; round = round + 1) begin
            amp = (round == 0) ? 2400 : 16000;   // 0.3 與約 1.95（Q3.13）
            for (n = 0; n < NN; n = n + 1) rx[n] = ($random(seed) % (amp + 1));

            // 載入 X
            for (n = 0; n < NN; n = n + 1) begin
                @(negedge clk);
                ld_we = 1; ld_addr = n; ld_data = rx[n];
            end
            @(negedge clk); ld_we = 0;

            // 參考計算
            for (i = 0; i < N; i = i + 1) for (j = 0; j < N; j = j + 1) begin
                acc64 = 0;
                for (k = 0; k < N; k = k + 1) acc64 = acc64 + rx[i*N+k] * rx[j*N+k];
                ra[i*N+j] = rs(acc64);
            end
            for (i = 0; i < N; i = i + 1) for (j = 0; j < N; j = j + 1) begin
                acc64 = 0;
                for (k = 0; k < N; k = k + 1) acc64 = acc64 + ra[i*N+k] * ra[j*N+k];
                raa[i*N+j] = rs(acc64);
            end
            for (n = 0; n < NN; n = n + 1)
                rb[n] = rs((64'sd0 + CB * ra[n] + CC * raa[n]) <<< 1);
            for (i = 0; i < N; i = i + 1) for (j = 0; j < N; j = j + 1) begin
                acc64 = 0;
                for (k = 0; k < N; k = k + 1) acc64 = acc64 + rb[i*N+k] * rx[k*N+j];
                acc64 = acc64 + ((CA * rx[i*N+j]) <<< 1);
                rxn[i*N+j] = rs(acc64);
            end

            // 階段 1：OP_A（整列）
            rxn_sel = 0;
            for (i = 0; i < N; i = i + 1) issue(2'd0, i, 3'd0);
            wait_idle;
            check_flat("A", 0);

            // 階段 2：OP_AAB（B 寫入 B 陣列）
            for (i = 0; i < N; i = i + 1) issue(2'd1, i, 3'd0);
            wait_idle;
            check_flat("B", 1);

            // 階段 3：OP_X（新 X 寫入 A 陣列）
            for (i = 0; i < N; i = i + 1) issue(2'd2, i, 3'd0);
            wait_idle;
            rxn_sel = 1;
            check_flat("Xnew", 0);

            // 階段 4：COMMIT，用讀出埠檢查 X 陣列
            issue(2'd3, 0, 0);
            wait_idle;
            for (n = 0; n < NN; n = n + 1) begin
                rd_addr = n;
                #1;
                if (rd_data !== rxn[n][W-1:0]) begin
                    errors = errors + 1;
                    if (errors < 10) $display("FAIL X[%0d]：got=%0d expect=%0d", n, rd_data, rxn[n]);
                end
            end
        end

        if (errors == 0) $display("PASS tb_matmul_core_par");
        else             $display("FAIL tb_matmul_core_par：%0d 個錯誤", errors);
        $finish;
    end
endmodule
