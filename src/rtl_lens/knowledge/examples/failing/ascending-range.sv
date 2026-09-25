module ascending_range(input logic [7:0] data_i, output logic [7:0] data_o);
  logic [0:7] reversed_bus;

  assign reversed_bus = data_i;
  assign data_o = reversed_bus;
endmodule
