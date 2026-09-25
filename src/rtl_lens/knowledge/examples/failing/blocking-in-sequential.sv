module blocking_in_sequential(input logic clk, input logic data_i, output logic data_o);
  always_ff @(posedge clk) data_o = data_i;
endmodule
