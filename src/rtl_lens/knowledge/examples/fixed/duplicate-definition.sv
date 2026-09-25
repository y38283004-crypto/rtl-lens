module duplicate_definition_a(input logic data_i, output logic data_o);
  assign data_o = data_i;
endmodule

module duplicate_definition_b(input logic data_i, output logic data_o);
  assign data_o = ~data_i;
endmodule
