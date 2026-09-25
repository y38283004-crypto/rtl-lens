module configurable_block #(parameter int WIDTH = 1) (
  input logic [WIDTH-1:0] data_i,
  output logic [WIDTH-1:0] data_o
);
  assign data_o = data_i;
endmodule

module deprecated_defparam(input logic [1:0] data_i, output logic [1:0] data_o);
  configurable_block configured (.data_i(data_i), .data_o(data_o));
  defparam configured.WIDTH = 2;
endmodule
