/*
 * ping_servo_uno.ino
 * Ping STS3215 servo via Waveshare Bus Servo Adapter (A) in UART-Servo mode.
 * Target: Arduino Uno (ATmega328P)
 *
 * Wiring (board in UART-Servo mode):
 *   Arduino Pin 1 (TX) → Board TX
 *   Arduino Pin 0 (RX) → Board RX
 *   Arduino GND        → Board GND
 *   12V supply         → Board barrel jack
 *
 * NOTE: Disconnect pins 0 and 1 before uploading. Reconnect after.
 * NOTE: Serial Monitor will not work while pins 0/1 are connected — Serial
 *       is used for servo communication at 1Mbps. Read LED for result.
 *
 * LED (pin 13):
 *   Fast blink (10x)  = Servo responded — communication working
 *   Slow blink        = No response from servo
 */

#include <SCServo.h>

SMS_STS sc;

#define TEST_ID  1   // Factory default servo ID
#define LED_PIN  13

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(1000000);
  sc.pSerial = &Serial;
  delay(1000);
}

void loop() {
  int id = sc.Ping(TEST_ID);

  if (id != -1) {
    // Success — fast blink
    for (int i = 0; i < 10; i++) {
      digitalWrite(LED_PIN, HIGH); delay(50);
      digitalWrite(LED_PIN, LOW);  delay(50);
    }
  } else {
    // No response — slow blink
    digitalWrite(LED_PIN, HIGH); delay(500);
    digitalWrite(LED_PIN, LOW);  delay(500);
  }
}
