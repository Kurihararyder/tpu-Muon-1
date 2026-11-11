// matmul_core：序列式矩陣乘法核心（資料路徑，可合成）
//   * 單一 MAC 重複使用（面積最小）；逐元素執行命令，每個元素內部自己數 k。
//   * 內含三個暫存器陣列：X（目前的 X）、A（A 矩陣，之後兼作新 X 的緩衝）、B。
//   * 命令（cmd_op）：
//       OP_A     ：A[i][j] = Q( sum_k X[i][k]*X[j][k] )，同時寫 A[j][i]（A 對稱）
//       OP_AAB   ：AA = Q( sum_k A[i][k]*A[j][k] )（A 對稱，故 A·A 以列內積計算），
//                  再算 B[i][j] = Q( b*A[i][j] + c*AA )，同時寫 B[j][i]
//       OP_X     ：X'[i][j] = Q( sum_k B[i][k]*X[k][j] + a*X[i][j] )，寫入 A 陣列
//       OP_COMMIT：X <= A 陣列（單一週期，整個陣列平行複製）
//     Q() = 加 0.5 LSB、捨去低位、飽和到 W 位元。累加器小數位 = 2F（乘積不捨入）。
//   * 載入埠（ld_*）寫入 X 陣列；讀出埠（rd_*）非同步讀取 X 陣列。
//   * cmd_ready=1 時（IDLE）才接受命令；cmd_valid && cmd_ready 為一次握手。
//   * 僅支援方陣 N x N。係數 COEF_* 為 Q(CW-CF).CF 的常數；改 CF 時須同步改這三個常數。
module matmul_core #(
    parameter N    = 8,
    parameter W    = 16,    // 資料位寬
    parameter F    = 13,    // 資料小數位寬（Q3.13）
    parameter CW   = 16,    // 係數位寬
    parameter CF   = 12,    // 係數小數位寬（Q4.12）
    parameter ACCW = 32,    // 累加器位寬
    parameter signed [CW-1:0] COEF_A =  16'sd14109,   // round(3.4445 * 2^12)
    parameter signed [CW-1:0] COEF_B = -16'sd19558,   // round(-4.7750 * 2^12)
    parameter signed [CW-1:0] COEF_C =  16'sd8321     // round(2.0315 * 2^12)
) (
    input  wire                         clk,
    input  wire                         rst_n,
    // 命令介面
    input  wire                         cmd_valid,
    input  wire [1:0]                   cmd_op,
    input  wire [$clog2(N)-1:0]         cmd_i,
    input  wire [$clog2(N)-1:0]         cmd_j,
    output wire                         cmd_ready,
    // X 陣列載入埠
    input  wire                         ld_we,
    input  wire [$clog2(N*N)-1:0]       ld_addr,
    input  wire signed [W-1:0]          ld_data,
    // X 陣列讀出埠（非同步）
    input  wire [$clog2(N*N)-1:0]       rd_addr,
    output wire signed [W-1:0]          rd_data
);
    localparam IW   = $clog2(N);
    localparam AW   = $clog2(N*N);
    localparam NN   = N * N;
    localparam KW   = IW + 1;
    localparam ACCF = 2 * F;            // 累加器小數位寬
    localparam SHL  = F - CF;           // 係數乘積的對齊位移（須 >= 0）
    localparam OPW  = (W > CW) ? W : CW;

    localparam [1:0] OP_A = 2'd0, OP_AAB = 2'd1, OP_X = 2'd2, OP_COMMIT = 2'd3;
    localparam [2:0] ST_IDLE = 3'd0, ST_DOT = 3'd1, ST_XA = 3'd2, ST_B1 = 3'd3,
                     ST_B2 = 3'd4, ST_DRAIN = 3'd5, ST_WB = 3'd6;

    // ------------------------------------------------------------ 狀態與計數器
    reg [2:0]          st;
    reg [1:0]          op_r;
    reg [IW-1:0]       i_r, j_r;
    reg [KW-1:0]       k;
    reg                bph;      // OP_AAB：0 = 正在算 AA，1 = 正在算 B
    reg signed [W-1:0] aa_q;     // 量化後的 AA[i][j]

    assign cmd_ready = (st == ST_IDLE);
    wire commit = (st == ST_IDLE) && cmd_valid && (cmd_op == OP_COMMIT);

    // ------------------------------------------------------------ 暫存器陣列（攤平成向量）
    wire [NN*W-1:0] mx_f, ma_f, mb_f;

    wire [AW-1:0] a_ik = i_r * N + k;
    wire [AW-1:0] a_jk = j_r * N + k;
    wire [AW-1:0] a_kj = k * N + j_r;
    wire [AW-1:0] a_ij = i_r * N + j_r;
    wire [AW-1:0] a_ji = j_r * N + i_r;

    wire signed [W-1:0] mx_ik = mx_f[a_ik*W +: W];
    wire signed [W-1:0] mx_jk = mx_f[a_jk*W +: W];
    wire signed [W-1:0] mx_kj = mx_f[a_kj*W +: W];
    wire signed [W-1:0] mx_ij = mx_f[a_ij*W +: W];
    wire signed [W-1:0] ma_ik = ma_f[a_ik*W +: W];
    wire signed [W-1:0] ma_jk = ma_f[a_jk*W +: W];
    wire signed [W-1:0] ma_ij = ma_f[a_ij*W +: W];
    wire signed [W-1:0] mb_ik = mb_f[a_ik*W +: W];

    assign rd_data = mx_f[rd_addr*W +: W];

    // ------------------------------------------------------------ 運算元選擇與 MAC
    reg signed [OPW-1:0] op1, op2;
    reg                  mac_en, mac_clr, mac_sh;

    always @* begin
        op1 = {OPW{1'b0}};
        op2 = {OPW{1'b0}};
        mac_en  = 1'b0;
        mac_clr = 1'b0;
        mac_sh  = 1'b0;
        case (st)
            ST_DOT: begin
                mac_en  = 1'b1;
                mac_clr = (k == 0);
                case (op_r)
                    OP_A:    begin op1 = mx_ik; op2 = mx_jk; end
                    OP_AAB:  begin op1 = ma_ik; op2 = ma_jk; end
                    default: begin op1 = mb_ik; op2 = mx_kj; end   // OP_X
                endcase
            end
            ST_XA: begin           // a * X[i][j]
                mac_en = 1'b1;
                mac_sh = 1'b1;
                op1 = COEF_A;
                op2 = mx_ij;
            end
            ST_B1: begin           // b * A[i][j]
                mac_en  = 1'b1;
                mac_clr = 1'b1;
                mac_sh  = 1'b1;
                op1 = COEF_B;
                op2 = ma_ij;
            end
            ST_B2: begin           // c * AA[i][j]
                mac_en = 1'b1;
                mac_sh = 1'b1;
                op1 = COEF_C;
                op2 = aa_q;
            end
            default: ;
        endcase
    end

    wire signed [ACCW-1:0] acc;

    mac_unit #(.OPW(OPW), .ACCW(ACCW), .SHL(SHL)) u_mac (
        .clk(clk), .rst_n(rst_n),
        .en(mac_en), .clr(mac_clr), .sh(mac_sh),
        .a(op1), .b(op2), .acc(acc)
    );

    // ------------------------------------------------------------ 捨入與飽和
    localparam signed [ACCW:0] SMAX =  (1 <<< (W - 1)) - 1;
    localparam signed [ACCW:0] SMIN = -(1 <<< (W - 1));

    wire signed [ACCW:0] acc_rnd = $signed({acc[ACCW-1], acc}) + (1 <<< (ACCF - F - 1));
    wire signed [ACCW:0] acc_shr = acc_rnd >>> (ACCF - F);
    wire signed [W-1:0]  q = (acc_shr > SMAX) ? SMAX[W-1:0] :
                             (acc_shr < SMIN) ? SMIN[W-1:0] : acc_shr[W-1:0];

    // ------------------------------------------------------------ 控制 FSM
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st   <= ST_IDLE;
            op_r <= 2'd0;
            i_r  <= {IW{1'b0}};
            j_r  <= {IW{1'b0}};
            k    <= {KW{1'b0}};
            bph  <= 1'b0;
            aa_q <= {W{1'b0}};
        end else begin
            case (st)
                ST_IDLE: begin
                    if (cmd_valid && cmd_op != OP_COMMIT) begin
                        op_r <= cmd_op;
                        i_r  <= cmd_i;
                        j_r  <= cmd_j;
                        k    <= {KW{1'b0}};
                        bph  <= 1'b0;
                        st   <= ST_DOT;
                    end
                end
                ST_DOT: begin
                    if (k == N - 1) begin
                        k  <= {KW{1'b0}};
                        st <= (op_r == OP_X) ? ST_XA : ST_DRAIN;
                    end else begin
                        k <= k + 1'b1;
                    end
                end
                ST_XA:    st <= ST_DRAIN;
                ST_B1:    st <= ST_B2;
                ST_B2:    st <= ST_DRAIN;
                ST_DRAIN: st <= ST_WB;
                ST_WB: begin
                    if (op_r == OP_AAB && !bph) begin
                        aa_q <= q;
                        bph  <= 1'b1;
                        st   <= ST_B1;
                    end else begin
                        bph <= 1'b0;
                        st  <= ST_IDLE;
                    end
                end
                default: st <= ST_IDLE;
            endcase
        end
    end

    // ------------------------------------------------------------ 暫存器陣列的寫入
    wire wb      = (st == ST_WB);
    wire ma_we0  = wb && (op_r == OP_A || op_r == OP_X);
    wire ma_we1  = wb && (op_r == OP_A);
    wire mb_we   = wb && (op_r == OP_AAB) && bph;

    genvar g;
    generate
        for (g = 0; g < NN; g = g + 1) begin : g_mem
            reg [W-1:0] mx_r, ma_r, mb_r;

            always @(posedge clk) begin
                if (commit)
                    mx_r <= ma_r;
                else if (ld_we && (ld_addr == g))
                    mx_r <= ld_data;

                if ((ma_we0 && (a_ij == g)) || (ma_we1 && (a_ji == g)))
                    ma_r <= q;

                if (mb_we && ((a_ij == g) || (a_ji == g)))
                    mb_r <= q;
            end

            assign mx_f[g*W +: W] = mx_r;
            assign ma_f[g*W +: W] = ma_r;
            assign mb_f[g*W +: W] = mb_r;
        end
    endgenerate
endmodule
