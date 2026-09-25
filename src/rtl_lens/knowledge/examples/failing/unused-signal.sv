module unused_signal(input logic a, input logic b, output logic y);
  logic unused_value;
  assign unused_value = b;
  assign y = a;
endmodule
