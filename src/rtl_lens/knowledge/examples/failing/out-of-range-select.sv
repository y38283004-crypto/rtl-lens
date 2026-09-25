module out_of_range_select(
  input logic [7:0] data_i,
  output logic bit_o,
  output logic [1:0] slice_o
);
  assign bit_o = data_i[8];
  assign slice_o = data_i[9:8];
endmodule
