module signedness_mismatch(
  input logic signed [7:0] signed_value,
  input logic [7:0] unsigned_value,
  output logic [7:0] converted,
  output logic is_less,
  output logic is_negative
);
  assign converted = $unsigned(signed_value);
  assign is_less = signed_value < $signed(unsigned_value);
  assign is_negative = $signed(unsigned_value) < 0;
endmodule
