module duplicated_unit(input logic data_i, output logic data_o);
  assign data_o = data_i;
endmodule

module duplicated_unit(input logic data_i, output logic data_o);
  assign data_o = ~data_i;
endmodule
