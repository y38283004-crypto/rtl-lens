module top;
`ifdef RTL_LENS_NARROW
  logic [3:0] value;
`else
  logic [7:0] value;
`endif
  assign value = 8'hff;
endmodule
