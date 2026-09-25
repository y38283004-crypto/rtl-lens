module width_mismatch;
  logic [7:0] wide_value;
  logic [3:0] narrow_value;

  assign narrow_value = wide_value;
endmodule
