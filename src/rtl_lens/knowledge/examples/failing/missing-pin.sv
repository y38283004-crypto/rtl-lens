module missing_pin_child(
  input logic enable,
  input logic data_i,
  output logic data_o,
  inout wire data_bidir
);
  assign data_o = enable & data_i & data_bidir;
endmodule

module missing_pin(input logic enable);
  missing_pin_child child (
    .enable(enable)
  );
endmodule
