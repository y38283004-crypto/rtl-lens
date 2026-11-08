module demo_top(input logic [7:0] sample_i, output logic [3:0] nibble_o);
  width_stage stage (.sample_i(sample_i), .nibble_o(nibble_o));
endmodule

module width_stage(input logic [7:0] sample_i, output logic [3:0] nibble_o);
  assign nibble_o = sample_i[3:0];
endmodule
