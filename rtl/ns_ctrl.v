// ns_ctrl：Newton-Schulz 控制 FSM（可合成）
//   對 matmul_core 依序下達命令：每輪 = A（上三角含對角）→ AAB（上三角含對角）→ X（全部）→ COMMIT，
//   共 STEPS 輪。下一個命令只在核心回到 IDLE（cmd_ready=1）時送出，因此前一個命令的結果
//   一定已寫入，不需另外的相依性檢查。
//   ROWMODE=1 時三個階段都只走列（i = 0..N-1，j = 0），每個命令代表整列。
//   done 為準位訊號：start 後清除，全部完成後拉高並保持到下一次 start。
module ns_ctrl #(
    parameter N       = 8,
    parameter STEPS   = 5,
    parameter ROWMODE = 0      // 0：逐元素下命令（序列核心）；1：逐列下命令（列平行核心，j 固定為 0）
) (
    input  wire                    clk,
    input  wire                    rst_n,
    input  wire                    start,
    input  wire                    core_ready,
    output wire                    cmd_valid,
    output wire [1:0]              cmd_op,
    output wire [$clog2(N)-1:0]    cmd_i,
    output wire [$clog2(N)-1:0]    cmd_j,
    output wire                    busy,
    output reg                     done
);
    localparam IW  = $clog2(N);
    localparam ITW = $clog2(STEPS + 1);

    localparam [2:0] C_IDLE = 3'd0, C_A = 3'd1, C_AB = 3'd2, C_X = 3'd3,
                     C_COMMIT = 3'd4, C_WAIT = 3'd5;

    reg [2:0]    st;
    reg [IW-1:0] i, j;
    reg [ITW-1:0] it;

    assign cmd_valid = (st == C_A) || (st == C_AB) || (st == C_X) || (st == C_COMMIT);
    assign cmd_op    = (st == C_A)  ? 2'd0 :
                       (st == C_AB) ? 2'd1 :
                       (st == C_X)  ? 2'd2 : 2'd3;
    assign cmd_i     = i;
    assign cmd_j     = j;
    assign busy      = (st != C_IDLE);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st   <= C_IDLE;
            i    <= {IW{1'b0}};
            j    <= {IW{1'b0}};
            it   <= {ITW{1'b0}};
            done <= 1'b0;
        end else begin
            case (st)
                C_IDLE: begin
                    if (start) begin
                        st   <= C_A;
                        i    <= {IW{1'b0}};
                        j    <= {IW{1'b0}};
                        it   <= {ITW{1'b0}};
                        done <= 1'b0;
                    end
                end
                // 上三角（j 從 i 開始）：A、AB 兩個階段共用同一種走法；ROWMODE 時只走列
                C_A, C_AB: begin
                    if (core_ready) begin
                        if (ROWMODE != 0) begin
                            if (i == N - 1) begin
                                st <= (st == C_A) ? C_AB : C_X;
                                i  <= {IW{1'b0}};
                            end else begin
                                i <= i + 1'b1;
                            end
                        end else if (j == N - 1) begin
                            if (i == N - 1) begin
                                st <= (st == C_A) ? C_AB : C_X;
                                i  <= {IW{1'b0}};
                                j  <= {IW{1'b0}};
                            end else begin
                                i <= i + 1'b1;
                                j <= i + 1'b1;
                            end
                        end else begin
                            j <= j + 1'b1;
                        end
                    end
                end
                C_X: begin
                    if (core_ready) begin
                        if (ROWMODE != 0 || j == N - 1) begin
                            j <= {IW{1'b0}};
                            if (i == N - 1) begin
                                i  <= {IW{1'b0}};
                                st <= C_COMMIT;
                            end else begin
                                i <= i + 1'b1;
                            end
                        end else begin
                            j <= j + 1'b1;
                        end
                    end
                end
                C_COMMIT: begin
                    if (core_ready) begin
                        if (it == STEPS - 1) begin
                            st <= C_WAIT;
                        end else begin
                            it <= it + 1'b1;
                            st <= C_A;
                            i  <= {IW{1'b0}};
                            j  <= {IW{1'b0}};
                        end
                    end
                end
                C_WAIT: begin
                    if (core_ready) begin
                        done <= 1'b1;
                        st   <= C_IDLE;
                    end
                end
                default: st <= C_IDLE;
            endcase
        end
    end
endmodule
