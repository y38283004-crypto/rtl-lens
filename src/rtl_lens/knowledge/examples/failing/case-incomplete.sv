module case_incomplete(input logic [1:0] sel, output logic y);
  always_comb case (sel)
    2'b00: y = 1'b0;
    2'b01: y = 1'b1;
  endcase
endmodule
