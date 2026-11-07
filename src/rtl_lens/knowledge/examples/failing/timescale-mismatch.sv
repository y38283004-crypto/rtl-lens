module untimed_child(input logic data_i, output logic data_o);
  assign data_o = data_i;
endmodule

`timescale 1ns/1ps
module timescale_mismatch(input logic data_i, output logic data_o);
  untimed_child child (.data_i(data_i), .data_o(data_o));
endmodule
