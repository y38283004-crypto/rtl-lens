module case_overlap(input logic [1:0] sel, output logic y);
  always_comb casez (sel)
    2'b?1: y = 1'b1;
    2'b1?: y = 1'b0;
    default: y = 1'b0;
  endcase
endmodule
