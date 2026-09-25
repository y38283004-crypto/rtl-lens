module incomplete_assignment(input logic enable, input logic data_i, output logic data_o);
  always_comb if (enable) data_o = data_i;
endmodule
