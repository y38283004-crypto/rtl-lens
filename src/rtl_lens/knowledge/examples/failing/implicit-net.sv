module implicit_net(input logic data_i, output logic data_o);
  assign enable_typo = data_i;
  assign data_o = enable_typo;
endmodule
