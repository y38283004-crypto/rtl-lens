module assignment_to_input(
  input logic data_i,
  input logic force_low,
  output logic data_o
);
  always_comb begin
    if (force_low) data_i = 1'b0;
    data_o = data_i;
  end
endmodule
