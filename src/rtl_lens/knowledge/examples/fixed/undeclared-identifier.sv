module undeclared_identifier(
  input logic data_i,
  input logic enable,
  output logic data_o
);
  assign data_o = data_i & enable;
endmodule
