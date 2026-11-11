// ns_ctrl 獨立 testbench：以隨機忙碌延遲的假核心驗證命令序列（op、i、j 的順序與總數）、
// done 的行為（start 後清除、完成後保持），並連跑兩次。
`timescale 1ns/1ps
module tb_ns_ctrl;
    parameter ROWMODE = 0;
    localparam N = 8, STEPS = 5, IW = 3;

    reg clk = 0, rst_n = 0;
    always #5 clk = ~clk;

    reg start = 0;
    wire core_ready;
    wire cmd_valid, busy, done;
    wire [1:0] cmd_op;
    wire [IW-1:0] cmd_i, cmd_j;

    ns_ctrl #(.N(N), .STEPS(STEPS), .ROWMODE(ROWMODE)) dut (
        .clk(clk), .rst_n(rst_n), .start(start), .core_ready(core_ready),
        .cmd_valid(cmd_valid), .cmd_op(cmd_op), .cmd_i(cmd_i), .cmd_j(cmd_j),
        .busy(busy), .done(done)
    );

    // 假核心：接受命令後忙 1～5 個週期（COMMIT 不忙，與真實核心一致）
    reg [3:0] busy_cnt = 0;
    assign core_ready = (busy_cnt == 0);
    integer seed = 5;
    always @(posedge clk) begin
        if (busy_cnt != 0) busy_cnt <= busy_cnt - 1'b1;
        else if (cmd_valid && cmd_op != 2'd3) busy_cnt <= 1 + ({$random(seed)} % 5);
    end

    // 期望序列
    reg [1:0] eop [0:1023];
    reg [IW-1:0] ei [0:1023], ej [0:1023];
    integer ne = 0;
    integer it, i, j;

    task build;
        begin
            ne = 0;
            for (it = 0; it < STEPS; it = it + 1) begin
                if (ROWMODE) begin   // 列模式：每階段 N 個命令，j 固定 0
                    for (i = 0; i < N; i = i + 1) begin eop[ne] = 2'd0; ei[ne] = i; ej[ne] = 0; ne = ne + 1; end
                    for (i = 0; i < N; i = i + 1) begin eop[ne] = 2'd1; ei[ne] = i; ej[ne] = 0; ne = ne + 1; end
                    for (i = 0; i < N; i = i + 1) begin eop[ne] = 2'd2; ei[ne] = i; ej[ne] = 0; ne = ne + 1; end
                end else begin
                for (i = 0; i < N; i = i + 1) for (j = i; j < N; j = j + 1) begin
                    eop[ne] = 2'd0; ei[ne] = i; ej[ne] = j; ne = ne + 1; end
                for (i = 0; i < N; i = i + 1) for (j = i; j < N; j = j + 1) begin
                    eop[ne] = 2'd1; ei[ne] = i; ej[ne] = j; ne = ne + 1; end
                for (i = 0; i < N; i = i + 1) for (j = 0; j < N; j = j + 1) begin
                    eop[ne] = 2'd2; ei[ne] = i; ej[ne] = j; ne = ne + 1; end
                end
                eop[ne] = 2'd3; ei[ne] = 0; ej[ne] = 0; ne = ne + 1;
            end
        end
    endtask

    integer errors = 0, nf = 0, run;

    // 每次握手都檢查
    always @(posedge clk) begin
        if (rst_n && cmd_valid && core_ready) begin
            if (nf >= ne) begin
                errors = errors + 1;
                $display("FAIL：多餘的命令 #%0d", nf);
            end else begin
                if (cmd_op !== eop[nf] || (cmd_op != 2'd3 && (cmd_i !== ei[nf] || cmd_j !== ej[nf]))) begin
                    errors = errors + 1;
                    if (errors < 10)
                        $display("FAIL：命令 #%0d op=%0d i=%0d j=%0d，期望 op=%0d i=%0d j=%0d",
                                 nf, cmd_op, cmd_i, cmd_j, eop[nf], ei[nf], ej[nf]);
                end
            end
            nf = nf + 1;
        end
    end

    integer timeout;
    initial begin
        build;
        $display("期望命令總數 = %0d", ne);
        repeat (3) @(negedge clk);
        rst_n = 1;
        repeat (2) @(negedge clk);
        if (done !== 1'b0 || busy !== 1'b0) begin errors = errors + 1; $display("FAIL：重置後 done/busy 不為 0"); end

        for (run = 0; run < 2; run = run + 1) begin
            nf = 0;
            @(negedge clk); start = 1;
            @(negedge clk); start = 0;
            timeout = 0;
            while (!done && timeout < 200000) begin @(negedge clk); timeout = timeout + 1; end
            if (!done) begin errors = errors + 1; $display("FAIL：逾時，done 未拉高"); end
            if (nf !== ne) begin errors = errors + 1; $display("FAIL：run %0d 命令數 %0d，期望 %0d", run, nf, ne); end
            repeat (5) @(negedge clk);
            if (done !== 1'b1 || busy !== 1'b0) begin errors = errors + 1; $display("FAIL：done 未保持"); end
        end

        if (errors == 0) $display("PASS tb_ns_ctrl");
        else             $display("FAIL tb_ns_ctrl：%0d 個錯誤", errors);
        $finish;
    end
endmodule
