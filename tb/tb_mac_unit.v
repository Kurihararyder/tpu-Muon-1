// mac_unit 獨立 testbench：隨機長度的乘加序列，與 TB 內的整數參考結果比對；並檢查 en=0 時保持。
`timescale 1ns/1ps
module tb_mac_unit;
    localparam OPW = 16, ACCW = 32, SHL = 1;

    reg clk = 0, rst_n = 0;
    always #5 clk = ~clk;

    reg en = 0, clr = 0, sh = 0;
    reg signed [OPW-1:0] a = 0, b = 0;
    wire signed [ACCW-1:0] acc;

    mac_unit #(.OPW(OPW), .ACCW(ACCW), .SHL(SHL)) dut (
        .clk(clk), .rst_n(rst_n), .en(en), .clr(clr), .sh(sh), .a(a), .b(b), .acc(acc)
    );

    integer errors = 0, trial, len, t, seed;
    reg signed [63:0] expect_acc, term;
    reg signed [OPW-1:0] ra, rb;
    reg rsh;

    initial begin
        seed = 1;
        repeat (3) @(negedge clk);
        rst_n = 1;
        @(negedge clk);

        for (trial = 0; trial < 500; trial = trial + 1) begin
            len = 1 + ({$random(seed)} % 12);
            expect_acc = 0;
            for (t = 0; t < len; t = t + 1) begin
                // 偶爾放入極端值（最大／最小）
                case ({$random(seed)} % 8)
                    0: begin ra = 16'sh7FFF; rb = 16'sh7FFF; end
                    1: begin ra = 16'sh8000; rb = 16'sh8000; end
                    2: begin ra = 16'sh8000; rb = 16'sh7FFF; end
                    default: begin ra = $random(seed); rb = $random(seed); end
                endcase
                rsh = (({$random(seed)} % 4) == 0);
                @(negedge clk);
                en = 1; clr = (t == 0); sh = rsh; a = ra; b = rb;
                term = $signed(ra) * $signed(rb);
                if (rsh) term = term <<< SHL;
                expect_acc = (t == 0) ? term : (expect_acc + term);
            end
            @(negedge clk);
            en = 0; clr = 0; sh = 0;
            // 最後一筆於上一個負緣給入：t+1 週期累加完成，這個負緣之後即可讀
            @(negedge clk);
            if (acc !== expect_acc[ACCW-1:0]) begin
                errors = errors + 1;
                $display("FAIL trial %0d: acc=%0d expect=%0d", trial, acc, $signed(expect_acc[ACCW-1:0]));
            end
            // en=0 時須保持：再等數個週期
            repeat (3) @(negedge clk);
            if (acc !== expect_acc[ACCW-1:0]) begin
                errors = errors + 1;
                $display("FAIL trial %0d: acc 未保持", trial);
            end
        end

        if (errors == 0) $display("PASS tb_mac_unit");
        else             $display("FAIL tb_mac_unit：%0d 個錯誤", errors);
        $finish;
    end
endmodule
