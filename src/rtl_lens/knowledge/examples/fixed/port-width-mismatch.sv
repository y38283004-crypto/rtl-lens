module width_port_child(
  input logic [7:0] data_i,
  output logic [7:0] data_o
);
  assign data_o = data_i;
endmodule

module port_width_mismatch(
  input logic [7:0] data_i,
  output logic [7:0] data_o
);
  width_port_child child (
    .data_i(data_i),
    .data_o(data_o)
  );
endmodule
