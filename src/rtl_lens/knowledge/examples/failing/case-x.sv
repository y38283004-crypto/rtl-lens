module case_x(input logic [1:0] selector, output logic matched);
  always_comb begin
    matched = 1'b0;
    casex (selector)
      2'b0x: matched = 1'b1;
      default: matched = 1'b0;
    endcase
  end
endmodule
