module blocking_and_nonblocking(
  input logic clk,
  input logic load,
  input logic data_i,
  output logic data_o
);
  always_ff @(posedge clk) begin
    if (load) data_o <= data_i;
  end
endmodule
