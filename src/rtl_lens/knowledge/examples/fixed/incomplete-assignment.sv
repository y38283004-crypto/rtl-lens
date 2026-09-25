module incomplete_assignment(input logic enable, input logic data_i, output logic data_o);
  always_comb begin
    data_o = 1'b0;
    if (enable) data_o = data_i;
  end
endmodule
