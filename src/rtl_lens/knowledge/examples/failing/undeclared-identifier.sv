module undeclared_identifier(input logic data_i, output logic data_o);
  assign data_o = data_i & missing_enable;
endmodule
