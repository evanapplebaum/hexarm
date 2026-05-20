# Servo Communication Debug Log

**Hardware:** FEETECH STS3215 × 12, Waveshare Bus Servo Adapter (A) × 2, Raspberry Pi Zero 2W  
**Duration:** ~3 days  
**Resolution date:** 2026-05-19  
**Root cause:** Incorrect UART wiring convention (crossed instead of straight-through)

---

## Problem Statement

After assembling the hexarm hardware stack, no serial communication could be established with any STS3215 servo from any host device. Servos powered on (red LED lit), but returned zero bytes in response to ping packets, and showed no physical response to broadcast torque commands.

---

## System Architecture

```
Host (Mac / Arduino / Pi)
        ↓  full-duplex UART (TX + RX)
Waveshare Bus Servo Adapter (A)
        ↓  half-duplex TTL serial bus
STS3215 servo(s) — daisy-chained, each with unique ID
```

The Waveshare board handles half-duplex direction switching internally. The host sees a normal full-duplex UART interface; the board drives the servo bus in one direction at a time.

---

## Debugging Chronology

### Phase 1 — Mac via USB (USB-Servo mode)

**Setup:** Mac → USB-C → Waveshare board (USB-Servo mode) → JST → STS3215  
**Tools:** `ping_one.py` (scservo_sdk), `raw_ping.py` (pure pyserial), `baud_scan.py`

**What was tried:**
- `ping_one.py` with scservo_sdk → "There is no status packet" for all IDs
- Official Waveshare `sms_sts/ping.py` example → same result
- `raw_ping.py` bypassing SDK entirely → "No bytes received"
- All supported baud rates: 9600 / 19200 / 38400 / 57600 / 115200 / 250000 / 500000 / 1000000
- IDs 1–20 at every baud rate
- Broadcast torque enable (ID 0xFE) → no physical stiffening at any baud
- Both `/dev/tty.*` and `/dev/cu.*` port prefixes on macOS

**What was ruled out:**
- Echo fix: added `ser.read()` after writes thinking board echoed TX bytes back — it doesn't. The board handles half-duplex in hardware with no echo. Fix reverted; protocol_packet_handler.py left stock.
- Wrong SDK class: `sms_sts` is correct for STS3215 (not `scscl`)
- tty vs cu: no difference in outcome

**Suspected causes (all wrong):**
- Mac USB CDC driver silently dropping writes
- Board data line not passing signal to servo bus
- Servo bricked or in fault state

---

### Phase 2 — Arduino via UART (direct to servo)

**Setup:** Arduino → 1kΩ resistor half-duplex bus → STS3215 directly  
**Result:** No response

**Note:** Arduino Uno at 16MHz cannot accurately generate 1Mbps baud — the hardware UART's divisor doesn't divide evenly to 1,000,000. This makes the Arduino test inconclusive. Communication failure here is expected and does not confirm or deny servo health.

---

### Phase 3 — Raspberry Pi Zero 2W via UART (UART-Servo mode)

**Setup:** Pi GPIO UART → Waveshare board (UART-Servo mode) → JST → STS3215

#### Pi setup required:

1. **OS:** Ubuntu 24.04 Server (fresh flash via Raspberry Pi Imager)
2. **SSH:** Configured WiFi credentials in Raspberry Pi Imager; accessed via `ssh ekapi@eka-pi02w.local`
3. **Free the PL011 hardware UART from Bluetooth:**
   ```bash
   echo "dtoverlay=disable-bt" | sudo tee -a /boot/firmware/config.txt
   echo "enable_uart=1" | sudo tee -a /boot/firmware/config.txt
   sudo reboot
   ```
   After reboot: `/dev/ttyAMA0` appears on GPIO 14 (TX) and GPIO 15 (RX)
4. **Add user to dialout group** (for UART access without sudo):
   ```bash
   sudo usermod -a -G dialout ekapi
   sudo reboot
   ```
5. **Python environment:**
   ```bash
   sudo apt install python3.12-venv -y
   cd ~/hexarm
   python3 -m venv .venv
   source .venv/bin/activate
   pip install pyserial
   ```

#### First wiring attempt (WRONG):

Wired Pi TX → Board RX, Pi RX → Board TX (standard UART crossing convention).

**Result:** No bytes received. Identical to all previous tests.

Tested two different Waveshare boards and two different STS3215 servos — all with the same result. At this point, hardware failure was strongly suspected.

#### Root cause discovered:

A Waveshare documentation search revealed the correct wiring for the Bus Servo Adapter (A) in UART-Servo mode:

> **"the connection must be RX-RX, TX-TX"**

The board labels its UART pins **from the host's perspective** — the pin labeled TX is where the host's TX wire connects, not where the board transmits. This is the **opposite of the standard UART labeling convention**, where a device's TX pin is where it transmits and the host must connect its RX.

#### Corrected wiring:

| Pi GPIO | Board Pin |
|---------|-----------|
| GPIO 14 (TX) | TX |
| GPIO 15 (RX) | RX |
| GND | GND |

#### Result after rewiring:

```
$ python3 baud_scan.py --port /dev/ttyAMA0

--- Baud: 1000000 ---
  *** GOT RESPONSE from ID 1: FC
  Done (no responses at 1000000)

Scan complete.
```

**Servo confirmed alive at 1Mbps, ID=1 (factory defaults intact).**

---

## Root Cause Analysis

**The Waveshare Bus Servo Adapter (A) uses non-standard UART pin labeling.**

On a typical UART device:
- The device's **TX** pin is where it **transmits** → host connects its **RX** here
- The device's **RX** pin is where it **receives** → host connects its **TX** here
- Result: wires are crossed (TX↔RX)

On the Waveshare Bus Servo Adapter (A):
- The **TX** pin means "connect the host's TX here"
- The **RX** pin means "connect the host's RX here"
- Result: wires are straight-through (TX↔TX, RX↔RX)

This convention is used on some boards where the designer labeled the connector from the system integrator's perspective rather than the device's perspective. It is not documented prominently on the Waveshare wiki.

**Every other aspect of the setup was correct.** The SDK, baud rate, packet format, servo IDs, board power, servo power, and OS configuration were all fine. Three days of debugging were caused by two wires being swapped.

---

## Lessons Learned

1. **Verify pin labeling convention before assuming standard UART crossing.** When using third-party adapter boards, always check whether UART pins are labeled from the device's or the host's perspective.

2. **Broadcast commands are a strong diagnostic tool.** Broadcast torque enable (ID 0xFE) requires no ID knowledge and no response — if servos don't physically stiffen, the data line isn't reaching them.

3. **Isolate the hardware path systematically.** Testing across multiple hosts (Mac, Arduino, Pi) and multiple interfaces (USB, UART) helped rule out software and driver issues — but the common failure point (the wiring convention) affected all of them equally.

4. **Arduino is unreliable for 1Mbps UART.** At 16MHz, the hardware UART cannot accurately generate 1Mbps. Do not use Arduino results as ground truth for high-baud servo communication.

5. **`raw_ping.py` is the right first diagnostic.** Bypassing the SDK removes one entire layer of potential failure. Always start with the most direct hardware test.

---

## Working Configuration Reference

```
Pi Zero 2W (Ubuntu 24.04)
  GPIO 14 (TX) ────────────────── TX  ┐
  GPIO 15 (RX) ────────────────── RX  │  Waveshare Bus Servo Adapter (A)
  GND          ────────────────── GND ┘  (switch: UART-Servo)
                                          │
                                       JST connector
                                          │
                                       STS3215 servo
                                       (ID=1, 1Mbps, factory defaults)

UART device: /dev/ttyAMA0
Baud rate:   1,000,000
```
