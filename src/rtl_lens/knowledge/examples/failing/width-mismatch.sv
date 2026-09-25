module width_mismatch;
  logic [7:0] wide_source;
  logic [3:0] narrow_source;
  logic [3:0] truncated_value;
  logic [7:0] expanded_value;
  logic [3:0] constant_value;

  assign truncated_value = wide_source;
  assign expanded_value = narrow_source;
  assign constant_value = 8'hff;
endmodule
