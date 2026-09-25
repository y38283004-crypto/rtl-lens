module always_comb_order(input logic a, input logic b, output logic y);
  logic intermediate;

  always_comb begin
    y = a & intermediate;
    intermediate = b;
  end
endmodule
