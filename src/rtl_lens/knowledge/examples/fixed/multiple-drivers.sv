module multiple_drivers(input logic clk, input logic [7:0] data_i, output logic [15:0] data_o);
  always @(posedge clk) begin
    data_o[7:0] <= data_i;
    data_o[15:8] <= data_i;
  end
endmodule
