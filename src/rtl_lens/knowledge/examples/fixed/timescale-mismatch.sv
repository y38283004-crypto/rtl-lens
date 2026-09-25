`timescale 1ns/1ps
module timed_child(input logic data_i, output logic data_o);
  assign #1 data_o = data_i;
endmodule

module timescale_mismatch(input logic data_i, output logic data_o);
  timed_child child (.data_i(data_i), .data_o(data_o));
endmodule
