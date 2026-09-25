module implicit_net(input logic data_i, output logic data_o);
  assign data_o = data_i & enable_typo;
endmodule
