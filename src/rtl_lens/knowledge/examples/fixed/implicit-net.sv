`default_nettype none
module implicit_net(input logic data_i, input logic enable, output logic data_o);
  assign data_o = data_i & enable;
endmodule
`default_nettype wire
