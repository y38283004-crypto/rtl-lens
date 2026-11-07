module unused_signal(input logic a, input logic b, output logic y);
  logic discarded_value;
  assign discarded_value = b;
  assign y = a;
endmodule
