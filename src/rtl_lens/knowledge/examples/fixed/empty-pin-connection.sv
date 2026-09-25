module empty_pin_child(
  input logic enable,
  input logic data_i,
  output logic data_o,
  inout wire data_bidir
);
  assign data_o = enable & data_i & data_bidir;
endmodule

module empty_pin_connection(
  input logic enable,
  input logic data_i,
  output logic data_o,
  inout wire data_bidir
);
  empty_pin_child child (
    .enable(enable),
    .data_i(data_i),
    .data_o(data_o),
    .data_bidir(data_bidir)
  );
endmodule
