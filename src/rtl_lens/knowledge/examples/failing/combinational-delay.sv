module combinational_delay(input logic a, input logic b, output logic y);
  always_comb begin
    #1 y = a & b;
  end
endmodule
