module signedness_mismatch(
  input logic signed [7:0] signed_value,
  input logic [7:0] unsigned_value,
  output logic [7:0] converted,
  output logic is_less,
  output logic is_negative
);
  assign converted = signed_value;
  assign is_less = signed_value < unsigned_value;
  assign is_negative = unsigned_value < 0;
endmodule
