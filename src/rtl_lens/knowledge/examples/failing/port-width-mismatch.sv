module width_port_child(
  input logic [7:0] data_i,
  output logic [7:0] data_o
);
  assign data_o = data_i;
endmodule

module port_width_mismatch(
  input logic [3:0] narrow_input,
  output logic [3:0] narrow_output
);
  width_port_child child (
    .data_i(narrow_input),
    .data_o(narrow_output)
  );
endmodule
