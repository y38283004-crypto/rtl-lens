module multiple_drivers(input logic clk, input logic [7:0] data_i, output logic [15:0] data_o);
  always @(posedge clk) data_o[7:0] <= data_i;
  always @(negedge clk) data_o[15:8] <= data_i;
endmodule
