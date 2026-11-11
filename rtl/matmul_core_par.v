// matmul_core_par：列平行矩陣乘法核心（可合成）。介面與 matmul_core 相同，命令改為「以列為單位」。
//   * N 條 MAC（lane），lane j 負責該列的第 j 個元素；每個週期所有 lane 同時處理同一個 k。
//   * 命令（cmd_i 為列號，cmd_j 不使用）：
//       OP_A     ：A[i][j]  = Q( sum_k X[i][k]*X[j][k] )，j = 0..N-1（整列，不用鏡射）
//       OP_AAB   ：AA[i][j] = Q( sum_k A[i][k]*A[j][k] )，再 B[i][j] = Q( b*A[i][j] + c*AA[i][j] )
//       OP_X     ：X'[i][j] = Q( sum_k B[i][k]*X[k][j] + a*X[i][j] )，寫入 A 陣列
//       OP_COMMIT：X <= A 陣列
//   * 數值運算與 matmul_core 完全相同（同樣的乘積、同樣的捨入與飽和），因此輸出逐位元一致。
//   * 每個命令的週期數與序列版的「單一元素」相同（11／15／12），但一次完成一整列。
module matmul_core_par #(
    parameter N    = 8,
    parameter W    = 16,
    parameter F    = 13,
    parameter CW   = 16,
    parameter CF   = 12,
    parameter ACCW = 32,
    parameter signed [CW-1:0] COEF_A =  16'sd14109,
    parameter signed [CW-1:0] COEF_B = -16'sd19558,
    parameter signed [CW-1:0] COEF_C =  16'sd8321
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         cmd_valid,
    input  wire [1:0]                   cmd_op,
    input  wire [$clog2(N)-1:0]         cmd_i,
    input  wire [$clog2(N)-1:0]         cmd_j,      // 不使用（保持與序列版相同的介面）
    output wire                         cmd_ready,
    input  wire                         ld_we,
    input  wire [$clog2(N*N)-1:0]       ld_addr,
    input  wire signed [W-1:0]          ld_data,
    input  wire [$clog2(N*N)-1:0]       rd_addr,
    output wire signed [W-1:0]          rd_data
);
    localparam IW   = $clog2(N);
    localparam AW   = $clog2(N*N);
    localparam NN   = N * N;
    localparam KW   = IW + 1;
    localparam ACCF = 2 * F;
    localparam SHL  = F - CF;
    localparam OPW  = (W > CW) ? W : CW;

    localparam [1:0] OP_A = 2'd0, OP_AAB = 2'd1, OP_X = 2'd2, OP_COMMIT = 2'd3;
    localparam [2:0] ST_IDLE = 3'd0, ST_DOT = 3'd1, ST_XA = 3'd2, ST_B1 = 3'd3,
                     ST_B2 = 3'd4, ST_DRAIN = 3'd5, ST_WB = 3'd6;

    reg [2:0]    st;
    reg [1:0]    op_r;
    reg [IW-1:0] i_r;
    reg [KW-1:0] k;
    reg          bph;

    assign cmd_ready = (st == ST_IDLE);
    wire commit = (st == ST_IDLE) && cmd_valid && (cmd_op == OP_COMMIT);

    wire [NN*W-1:0] mx_f, ma_f, mb_f;

    // 所有 lane 共用的運算元（列 i 的第 k 個元素）
    wire [AW-1:0] a_ik = i_r * N + k;
    wire signed [W-1:0] mx_ik = mx_f[a_ik*W +: W];
    wire signed [W-1:0] ma_ik = ma_f[a_ik*W +: W];
    wire signed [W-1:0] mb_ik = mb_f[a_ik*W +: W];

    assign rd_data = mx_f[rd_addr*W +: W];

    reg signed [OPW-1:0] op1;
    reg                  mac_en, mac_clr, mac_sh;

    always @* begin
        op1 = {OPW{1'b0}};
        mac_en  = 1'b0;
        mac_clr = 1'b0;
        mac_sh  = 1'b0;
        case (st)
            ST_DOT: begin
                mac_en  = 1'b1;
                mac_clr = (k == 0);
                case (op_r)
                    OP_A:    op1 = mx_ik;
                    OP_AAB:  op1 = ma_ik;
                    default: op1 = mb_ik;
                endcase
            end
            ST_XA: begin mac_en = 1'b1; mac_sh = 1'b1; op1 = COEF_A; end
            ST_B1: begin mac_en = 1'b1; mac_clr = 1'b1; mac_sh = 1'b1; op1 = COEF_B; end
            ST_B2: begin mac_en = 1'b1; mac_sh = 1'b1; op1 = COEF_C; end
            default: ;
        endcase
    end

    // ------------------------------------------------------------ 控制 FSM（與序列版相同）
    wire wb = (st == ST_WB);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st   <= ST_IDLE;
            op_r <= 2'd0;
            i_r  <= {IW{1'b0}};
            k    <= {KW{1'b0}};
            bph  <= 1'b0;
        end else begin
            case (st)
                ST_IDLE: begin
                    if (cmd_valid && cmd_op != OP_COMMIT) begin
                        op_r <= cmd_op;
                        i_r  <= cmd_i;
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
                        bph <= 1'b1;
                        st  <= ST_B1;
                    end else begin
                        bph <= 1'b0;
                        st  <= ST_IDLE;
                    end
                end
                default: st <= ST_IDLE;
            endcase
        end
    end

    // ------------------------------------------------------------ N 條 MAC lane
    localparam signed [ACCW:0] SMAX =  (1 <<< (W - 1)) - 1;
    localparam signed [ACCW:0] SMIN = -(1 <<< (W - 1));

    wire [N*W-1:0] q_f;       // 各 lane 的量化結果（lane j 為第 j 個元素）

    genvar l;
    generate
        for (l = 0; l < N; l = l + 1) begin : g_lane
            wire [AW-1:0] a_lk = l * N + k;       // X[l][k] / A[l][k]
            wire [AW-1:0] a_kl = k * N + l;       // X[k][l]
            wire [AW-1:0] a_il = i_r * N + l;     // X[i][l] / A[i][l]
            wire signed [W-1:0] mx_lk = mx_f[a_lk*W +: W];
            wire signed [W-1:0] ma_lk = ma_f[a_lk*W +: W];
            wire signed [W-1:0] mx_kl = mx_f[a_kl*W +: W];
            wire signed [W-1:0] mx_il = mx_f[a_il*W +: W];
            wire signed [W-1:0] ma_il = ma_f[a_il*W +: W];
            reg  signed [W-1:0] aa_q;             // 這個 lane 量化後的 AA[i][l]

            reg signed [OPW-1:0] op2;
            always @* begin
                op2 = {OPW{1'b0}};
                case (st)
                    ST_DOT: begin
                        case (op_r)
                            OP_A:    op2 = mx_lk;
                            OP_AAB:  op2 = ma_lk;
                            default: op2 = mx_kl;
                        endcase
                    end
                    ST_XA: op2 = mx_il;
                    ST_B1: op2 = ma_il;
                    ST_B2: op2 = aa_q;
                    default: ;
                endcase
            end

            wire signed [ACCW-1:0] acc;
            mac_unit #(.OPW(OPW), .ACCW(ACCW), .SHL(SHL)) u_mac (
                .clk(clk), .rst_n(rst_n),
                .en(mac_en), .clr(mac_clr), .sh(mac_sh),
                .a(op1), .b(op2), .acc(acc)
            );

            wire signed [ACCW:0] acc_rnd = $signed({acc[ACCW-1], acc}) + (1 <<< (ACCF - F - 1));
            wire signed [ACCW:0] acc_shr = acc_rnd >>> (ACCF - F);
            wire signed [W-1:0]  q = (acc_shr > SMAX) ? SMAX[W-1:0] :
                                     (acc_shr < SMIN) ? SMIN[W-1:0] : acc_shr[W-1:0];
            assign q_f[l*W +: W] = q;

            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) aa_q <= {W{1'b0}};
                else if (wb && op_r == OP_AAB && !bph) aa_q <= q;
            end
        end
    endgenerate

    // ------------------------------------------------------------ 暫存器陣列的寫入（整列同時寫）
    wire ma_we = wb && (op_r == OP_A || op_r == OP_X);
    wire mb_we = wb && (op_r == OP_AAB) && bph;

    genvar g;
    generate
        for (g = 0; g < NN; g = g + 1) begin : g_mem
            localparam ROW = g / N;
            localparam COL = g % N;
            reg [W-1:0] mx_r, ma_r, mb_r;

            always @(posedge clk) begin
                if (commit)
                    mx_r <= ma_r;
                else if (ld_we && (ld_addr == g))
                    mx_r <= ld_data;

                if (ma_we && (i_r == ROW)) ma_r <= q_f[COL*W +: W];
                if (mb_we && (i_r == ROW)) mb_r <= q_f[COL*W +: W];
            end

            assign mx_f[g*W +: W] = mx_r;
            assign ma_f[g*W +: W] = ma_r;
            assign mb_f[g*W +: W] = mb_r;
        end
    endgenerate
endmodule
