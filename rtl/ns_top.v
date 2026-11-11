// ns_top：Muon 核心（五次 Newton-Schulz 正交化）頂層（可合成）
//
// 介面（記憶體式，避免 N*N*W 位元的寬匯流排佔用大量腳位）：
//   載入：每個週期可寫入一個元素（ld_we、ld_addr = i*N+j、ld_data = 原始梯度 G，Q4.12）。
//         載入的資料先經 norm_scale 乘上 scale 變成 X0（Q3.13）。載入期間 scale 須保持穩定。
//   啟動：載入完成後拉高 start 一個週期（可與最後一筆載入同一週期，也可之後）。
//   完成：done 拉高；之後用 rd_addr 讀出 rd_data（Q3.13，非同步讀取）。
//   done 在 start 之後立即遮蔽為 0，直到本次運算完成。
//
// 第一版限制：方陣 N x N；scale = 1/(||G||_F + eps) 由外部預先算好（見 docs/rtl_design.md）。
module ns_top #(
    parameter N     = 8,
    parameter W     = 16,
    parameter F     = 13,
    parameter GW    = 16,     // 輸入 G 的位寬
    parameter GF    = 12,     // 輸入 G 的小數位寬
    parameter SW    = 20,     // scale 位寬（無號）
    parameter SF    = 16,     // scale 小數位寬
    parameter STEPS = 5,
    parameter ARCH  = 0,      // 0：序列式（單一 MAC）；1：列平行（N 條 MAC，一次算一整列）
    parameter CW    = 16,     // 係數位寬（Q4.CF，CW = CF + 4）
    parameter CF    = 12,     // 係數小數位寬；須 F >= CF
    parameter ACCW  = 32,     // 累加器位寬；須 >= 2F + 6（8x8）
    parameter signed [CW-1:0] COEF_A =  16'sd14109,   // round(3.4445 * 2^CF)
    parameter signed [CW-1:0] COEF_B = -16'sd19558,   // round(-4.7750 * 2^CF)
    parameter signed [CW-1:0] COEF_C =  16'sd8321     // round(2.0315 * 2^CF)
) (
    input  wire                      clk,
    input  wire                      rst_n,
    input  wire                      start,
    input  wire [SW-1:0]             scale,
    input  wire                      ld_we,
    input  wire [$clog2(N*N)-1:0]    ld_addr,
    input  wire [GW-1:0]             ld_data,   // 不宣告 signed：Yosys 會把 signed 寫進網表，OpenSTA 無法解析
    input  wire [$clog2(N*N)-1:0]    rd_addr,
    output wire [W-1:0]              rd_data,
    output wire                      busy,
    output wire                      done
);
    localparam AW = $clog2(N*N);
    localparam IW = $clog2(N);

    // 載入路徑：G -> norm_scale -> X 陣列
    wire              s_valid;
    wire [AW-1:0]     s_addr;
    wire signed [W-1:0] s_data;

    norm_scale #(.W(W), .GW(GW), .GF(GF), .SW(SW), .SF(SF), .F(F), .AW(AW)) u_scale (
        .clk(clk), .rst_n(rst_n),
        .in_valid(ld_we), .in_addr(ld_addr), .in_data(ld_data), .scale(scale),
        .out_valid(s_valid), .out_addr(s_addr), .out_data(s_data)
    );

    // start 延遲一個週期：讓最後一筆載入（經 norm_scale 一級暫存）先寫入 X 陣列
    reg start_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) start_q <= 1'b0;
        else        start_q <= start;
    end

    // 頂層輸出不宣告 signed（見埠宣告的說明）；核心端為有號，這裡以內部線轉接（須先宣告再使用）
    wire signed [W-1:0] rd_data_s;

    wire              cmd_valid, cmd_ready, ctrl_busy, ctrl_done;
    wire [1:0]        cmd_op;
    wire [IW-1:0]     cmd_i, cmd_j;

    ns_ctrl #(.N(N), .STEPS(STEPS), .ROWMODE(ARCH)) u_ctrl (
        .clk(clk), .rst_n(rst_n), .start(start_q), .core_ready(cmd_ready),
        .cmd_valid(cmd_valid), .cmd_op(cmd_op), .cmd_i(cmd_i), .cmd_j(cmd_j),
        .busy(ctrl_busy), .done(ctrl_done)
    );

    // 依 ARCH 選擇核心；兩者介面相同、輸出逐位元一致
    generate
        if (ARCH == 0) begin : g_serial
            matmul_core #(.N(N), .W(W), .F(F), .CW(CW), .CF(CF), .ACCW(ACCW),
                          .COEF_A(COEF_A), .COEF_B(COEF_B), .COEF_C(COEF_C)) u_core (
                .clk(clk), .rst_n(rst_n),
                .cmd_valid(cmd_valid), .cmd_op(cmd_op), .cmd_i(cmd_i), .cmd_j(cmd_j),
                .cmd_ready(cmd_ready),
                .ld_we(s_valid), .ld_addr(s_addr), .ld_data(s_data),
                .rd_addr(rd_addr), .rd_data(rd_data_s)
            );
        end else begin : g_par
            matmul_core_par #(.N(N), .W(W), .F(F), .CW(CW), .CF(CF), .ACCW(ACCW),
                              .COEF_A(COEF_A), .COEF_B(COEF_B), .COEF_C(COEF_C)) u_core (
                .clk(clk), .rst_n(rst_n),
                .cmd_valid(cmd_valid), .cmd_op(cmd_op), .cmd_i(cmd_i), .cmd_j(cmd_j),
                .cmd_ready(cmd_ready),
                .ld_we(s_valid), .ld_addr(s_addr), .ld_data(s_data),
                .rd_addr(rd_addr), .rd_data(rd_data_s)
            );
        end
    endgenerate

    assign rd_data = rd_data_s;

    assign busy = ctrl_busy | start_q;
    assign done = ctrl_done & ~start & ~start_q;
endmodule
