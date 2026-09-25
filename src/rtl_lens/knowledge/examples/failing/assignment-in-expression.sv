module assignment_in_expression(
  input logic choose_a,
  input logic data_a,
  input logic data_b,
  output logic y
);
  logic selected;

  assign y = (selected = choose_a) ? data_a : data_b;
endmodule
