module assignment_to_input(
  input logic data_i,
  input logic force_low,
  output logic data_o
);
  logic selected_data;

  always_comb begin
    selected_data = data_i;
    if (force_low) selected_data = 1'b0;
    data_o = selected_data;
  end
endmodule
