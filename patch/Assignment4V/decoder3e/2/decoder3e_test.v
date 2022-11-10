

module decoder3e_test
(
  a,
  ena,
  y
);

  input [2:0] a;
  input ena;
  output [7:0] y;
  reg [7:0] y;

  always @(a or ena) begin
    if(~ena) y = 8'd0; 
    else case(a)
      3'b000: y <= 'b00000001;
      3'b001: y <= 'b00000010;
      3'b010: y <= 'b00000100;
      3'b011: y <= 'b00001000;
      3'b100: y <= 'b00010000;
      3'b101: y <= 'b00100000;
      3'b110: y <= 'b01000000;
      3'b111: y <= 'b10000000;
    endcase
  end


endmodule

