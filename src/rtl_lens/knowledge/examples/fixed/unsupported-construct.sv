module unsupported_construct;
  typedef struct packed {
    logic [7:0] payload;
  } transaction_t;

  transaction_t pending;
endmodule
