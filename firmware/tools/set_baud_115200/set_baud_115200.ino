/*
 * set_baud_115200.ino
 * -------------------
 * One-shot utility: changes ST3215 servo baud rate from 1 Mbps (factory default)
 * to 115200 bps, stored in EEPROM.
 *
 * Wiring (half-duplex resistor bus):
 *   Servo DATA  ──┬── Arduino RX (pin 0)
 *                 └── 1kΩ ── Arduino TX (pin 1)
 *   Servo GND   ── Arduino GND (common ground with 12V supply)
 *   Servo VIN   ── 6–12.6V supply (NOT Arduino 5V)
 *
 * Usage:
 *   1. Upload this sketch (disconnect servo DATA line during upload to avoid
 *      contention on pins 0/1 — the bootloader uses them)
 *   2. Reconnect servo DATA, apply 12V supply, let sketch run (~500ms)
 *   3. Power-cycle the servo — baud rate change takes effect on reboot
 *   4. Replace this sketch with your actual firmware (at 115200)
 *
 * NOTE: Arduino Uno has one hardware UART. At 1 Mbps the USB-serial bridge
 * cannot relay to the PC, so Serial Monitor is useless here. Run-and-done.
 *
 * Protocol: SCS (Feetech Serial Control Servo), half-duplex TTL UART
 * Target:   ST3215, default ID = 1
 */

// ── Register addresses (EEPROM region) ───────────────────────────────────────
#define REG_BAUD_RATE   0x06   // Baud rate setting register
#define REG_LOCK        0x37   // EEPROM lock (0 = unlocked, 1 = locked)

// ── Baud rate register values ─────────────────────────────────────────────────
#define BAUD_1M         0      // 1,000,000 bps  (factory default)
#define BAUD_115200     4      // 115,200 bps

// ── Target servo ─────────────────────────────────────────────────────────────
#define SERVO_ID        1      // Factory default ID for all ST3215s

// ── SCS instruction codes ────────────────────────────────────────────────────
#define INSTR_WRITE     0x03

// ── Timing ───────────────────────────────────────────────────────────────────
#define ECHO_DRAIN_MS    5     // Wait for our own echo bytes to arrive on RX
#define EEPROM_WRITE_MS  10    // EEPROM write settle time

// ─────────────────────────────────────────────────────────────────────────────

/*
 * calcChecksum()
 * SCS checksum = ~(ID + LEN + INSTR + ADDR + DATA) truncated to 8 bits.
 * Arithmetic overflow on uint8_t is intentional — only the low byte matters.
 */
uint8_t calcChecksum(uint8_t id, uint8_t len, uint8_t instr,
                     uint8_t addr, uint8_t value) {
  return ~((uint8_t)(id + len + instr + addr + value));
}

/*
 * writeByte()
 * Sends a single-register WRITE packet over the half-duplex bus.
 *
 * SCS packet layout:
 *   [0xFF] [0xFF] [ID] [LEN] [INSTR] [ADDR] [VALUE] [CHECKSUM]
 *
 *   LEN = number of bytes after the LEN field, up to and including CHECKSUM
 *       = INSTR(1) + ADDR(1) + VALUE(1) + CHECKSUM(1) = 4 for a 1-byte write
 *
 * Echo draining:
 *   TX and RX share the same data wire (via 1kΩ). Every byte we transmit
 *   appears on RX too. We flush them after each packet so they don't corrupt
 *   a future read (e.g., reading the servo's status response).
 */
void writeByte(uint8_t id, uint8_t addr, uint8_t value) {
  const uint8_t len      = 4;
  uint8_t       checksum = calcChecksum(id, len, INSTR_WRITE, addr, value);

  uint8_t packet[8] = {
    0xFF, 0xFF,   // Start-of-packet marker
    id,           // Servo ID
    len,          // Bytes remaining (after LEN field)
    INSTR_WRITE,  // 0x03 = write register
    addr,         // Target register address
    value,        // Data to write
    checksum      // ~(ID+LEN+INSTR+ADDR+VALUE) & 0xFF
  };

  Serial.write(packet, sizeof(packet));
  Serial.flush();                      // Wait until last byte leaves TX

  delay(ECHO_DRAIN_MS);                // Give echo bytes time to arrive
  while (Serial.available()) Serial.read();  // Discard them
}

// ─────────────────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(1000000);  // Must match servo's CURRENT baud rate
  delay(100);             // Wait for servo to finish power-on init

  // 1. Unlock EEPROM (required before writing any EEPROM-region register)
  writeByte(SERVO_ID, REG_LOCK, 0x00);
  delay(EEPROM_WRITE_MS);

  // 2. Write new baud rate (takes effect after power cycle)
  writeByte(SERVO_ID, REG_BAUD_RATE, BAUD_115200);
  delay(EEPROM_WRITE_MS);

  // 3. Re-lock EEPROM
  writeByte(SERVO_ID, REG_LOCK, 0x01);

  // Done — power-cycle the servo to apply the new baud rate.
}

void loop() {}
