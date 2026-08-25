/*
Ping() to test a servo on the bus is ready.
*/

// the UART used to control servos.
#define A_TX  1
#define A_RX  2

#include <SCServo.h>

SCSCL sc;

int TEST_ID = 3;

int LEDpin = 13;
void setup()
{
  pinMode(LEDpin,OUTPUT);
  digitalWrite(LEDpin, HIGH);
  Serial.begin(115200);
  Serial1.begin(1000000, SERIAL_8N1, S_RXD, S_TXD);
  sc.pSerial = &Serial1;
  delay(1000);
}

void loop()
{
  int ID = sc.Ping(TEST_ID);
  if(ID!=-1){
    digitalWrite(LEDpin, LOW);
    Serial.print("Servo ID:");
    Serial.println(ID, DEC);
    delay(100);
  }else{
    Serial.println("Ping servo ID error!");
    digitalWrite(LEDpin, HIGH);
    delay(2000);
  }
}