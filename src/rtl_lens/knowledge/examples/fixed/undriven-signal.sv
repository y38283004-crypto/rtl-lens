module undriven_signal(output logic y);
  logic driven_value;
  assign driven_value = 1'b0;
  assign y = driven_value;
endmodule
