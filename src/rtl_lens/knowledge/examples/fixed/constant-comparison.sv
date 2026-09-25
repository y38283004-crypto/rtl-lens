module constant_comparison(input logic flag, output logic asserted);
  assign asserted = flag == 1'b1;
endmodule
