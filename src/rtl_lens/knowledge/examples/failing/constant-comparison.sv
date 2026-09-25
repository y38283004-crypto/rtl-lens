module constant_comparison(input logic flag, output logic impossible);
  assign impossible = flag > 1'b1;
endmodule
