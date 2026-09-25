module ascending_range(input logic [7:0] data_i, output logic [7:0] data_o);
  logic [7:0] aligned_bus;

  assign aligned_bus = data_i;
  assign data_o = aligned_bus;
endmodule
