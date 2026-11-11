// norm_scale 獨立 testbench：隨機與邊界輸入，和 TB 內的 64 位元整數參考結果比對（含飽和）。
`timescale 1ns/1ps
module tb_norm_scale;
    localparam W = 16, GF = 12, SW = 20, SF = 16, F = 13, AW = 6;

    reg clk = 0, rst_n = 0;
    always #5 clk = ~clk;

    reg              in_valid = 0;
    reg  [AW-1:0]    in_addr  = 0;
    reg  signed [W-1:0] in_data = 0;
    reg  [SW-1:0]    scale = 0;
    wire             out_valid;
    wire [AW-1:0]    out_addr;
    wire signed [W-1:0] out_data;

    norm_scale #(.W(W), .GF(GF), .SW(SW), .SF(SF), .F(F), .AW(AW)) dut (
        .clk(clk), .rst_n(rst_n), .in_valid(in_valid), .in_addr(in_addr), .in_data(in_data),
        .scale(scale), .out_valid(out_valid), .out_addr(out_addr), .out_data(out_data)
    );

    function signed [W-1:0] ref_scale(input signed [W-1:0] g, input [SW-1:0] s);
        reg signed [63:0] p, r;
        begin
            p = $signed(g) * $signed({1'b0, s});
            r = (p + (64'sd1 <<< (GF + SF - F - 1))) >>> (GF + SF - F);
            if (r > 32767) ref_scale = 16'sh7FFF;
            else if (r < -32768) ref_scale = 16'sh8000;
            else ref_scale = r[W-1:0];
        end
    endfunction

    integer errors = 0, n, seed;
    reg signed [W-1:0] exp_d;
    reg [AW-1:0] exp_a;
    reg exp_v;
    reg signed [W-1:0] g;
    reg [SW-1:0] s;

    initial begin
        seed = 3;
        repeat (3) @(negedge clk);
        rst_n = 1;

        for (n = 0; n < 5000; n = n + 1) begin
            // 輸入：一般隨機、邊界、零
            case (n % 10)
                0: begin g = 16'sh7FFF; s = {SW{1'b1}}; end
                1: begin g = 16'sh8000; s = {SW{1'b1}}; end
                2: begin g = 16'sd0;    s = $random(seed); end
                3: begin g = $random(seed); s = 0; end
                4: begin g = 16'sh8000; s = 20'd1; end
                default: begin g = $random(seed); s = $random(seed) >> (({$random(seed)} % 12)); end
            endcase
            @(negedge clk);
            in_valid = ({$random(seed)} % 4) != 0;   // 部分週期無效
            in_addr  = $random(seed);
            in_data  = g;
            scale    = s;
            exp_v = in_valid;
            exp_a = in_addr;
            exp_d = ref_scale(g, s);
            @(negedge clk);   // 一級暫存後輸出
            in_valid = 0;
            if (out_valid !== exp_v || out_addr !== exp_a || out_data !== exp_d) begin
                errors = errors + 1;
                if (errors < 10)
                    $display("FAIL n=%0d g=%0d s=%0d: out=%0d expect=%0d (valid %b/%b addr %0d/%0d)",
                             n, g, s, out_data, exp_d, out_valid, exp_v, out_addr, exp_a);
            end
        end

        if (errors == 0) $display("PASS tb_norm_scale");
        else             $display("FAIL tb_norm_scale：%0d 個錯誤", errors);
        $finish;
    end
endmodule
