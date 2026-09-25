module case_overlap(input logic [1:0] sel, output logic y);
  always_comb case (sel)
    2'b01, 2'b11: y = 1'b1;
    default: y = 1'b0;
  endcase
endmodule
