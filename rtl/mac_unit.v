// mac_unit：兩級管線的乘加單元（可合成）
//   第 1 級：鎖存運算元與控制訊號
//   第 2 級：乘法並累加（clr=1 時以乘積取代累加器內容）
// 延遲：在第 t 個週期給入運算元，累加結果於第 t+2 個週期可由 acc 讀到。
// sh=1 時乘積左移 SHL 位，用來把「係數 x 資料」的小數點對齊到「資料 x 資料」。
module mac_unit #(
    parameter OPW  = 16,   // 運算元位寬（有號）
    parameter ACCW = 32,   // 累加器位寬（有號）；超出範圍時環繞（二補數），不做飽和
    parameter SHL  = 1     // sh=1 時的乘積左移位數
) (
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire                   en,     // 本週期給入的運算元有效
    input  wire                   clr,    // 1：acc <= 乘積；0：acc <= acc + 乘積
    input  wire                   sh,     // 1：乘積左移 SHL 位
    input  wire signed [OPW-1:0]  a,
    input  wire signed [OPW-1:0]  b,
    output reg  signed [ACCW-1:0] acc
);
    reg signed [OPW-1:0] a_r, b_r;
    reg                  en_r, clr_r, sh_r;

    wire signed [2*OPW-1:0] prod    = a_r * b_r;
    wire signed [ACCW-1:0]  prod_ext = prod;
    wire signed [ACCW-1:0]  prod_al  = sh_r ? (prod_ext <<< SHL) : prod_ext;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            en_r  <= 1'b0;
            clr_r <= 1'b0;
            sh_r  <= 1'b0;
            acc   <= {ACCW{1'b0}};
        end else begin
            en_r  <= en;
            clr_r <= clr;
            sh_r  <= sh;
            if (en_r) acc <= clr_r ? prod_al : (acc + prod_al);
        end
    end

    // 運算元暫存器不需重置（en_r=0 時不會被使用）
    always @(posedge clk) begin
        a_r <= a;
        b_r <= b;
    end
endmodule
