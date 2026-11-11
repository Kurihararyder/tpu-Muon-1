// norm_scale：逐元素縮放 X0 = G * scale（可合成）
//   第一版：scale = 1 / (||G||_F + eps) 由外部（主機）預先算好後輸入，本模組只做乘法、
//   四捨五入與飽和；平方和與開根號留待後續版本。
//   in_data ：原始梯度元素，GW 位元有號，小數 GF 位（預設 Q4.12）
//   scale   ：縮放值，SW 位元無號，小數 SF 位（預設 Q4.16，範圍 0～16）
//   out_data：縮放後元素，W 位元有號，小數 F 位（預設 Q3.13），飽和處理
// 一級暫存：out_valid／out_addr 與 in_valid／in_addr 相隔 1 個週期。
module norm_scale #(
    parameter W  = 16,    // 輸出位寬
    parameter GW = 16,    // 輸入位寬
    parameter GF = 12,
    parameter SW = 20,
    parameter SF = 16,
    parameter F  = 13,
    parameter AW = 6
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  in_valid,
    input  wire [AW-1:0]         in_addr,
    input  wire signed [GW-1:0]  in_data,
    input  wire [SW-1:0]         scale,
    output reg                   out_valid,
    output reg  [AW-1:0]         out_addr,
    output reg  signed [W-1:0]   out_data
);
    localparam PW  = GW + SW + 1;     // 乘積位寬
    localparam SHR = GF + SF - F;    // 乘積右移位數（須大於 0）

    wire signed [PW-1:0] prod = in_data * $signed({1'b0, scale});
    wire signed [PW-1:0] rnd  = prod + (1 <<< (SHR - 1));   // 加 0.5 LSB
    wire signed [PW-1:0] shr  = rnd >>> SHR;

    localparam signed [PW-1:0] SMAX =  (1 <<< (W - 1)) - 1;
    localparam signed [PW-1:0] SMIN = -(1 <<< (W - 1));

    wire signed [W-1:0] sat = (shr > SMAX) ? SMAX[W-1:0] :
                              (shr < SMIN) ? SMIN[W-1:0] : shr[W-1:0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out_valid <= 1'b0;
            out_addr  <= {AW{1'b0}};
            out_data  <= {W{1'b0}};
        end else begin
            out_valid <= in_valid;
            out_addr  <= in_addr;
            out_data  <= sat;
        end
    end
endmodule
