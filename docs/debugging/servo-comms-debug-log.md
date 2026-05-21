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

---

## Phase 4 — Intermittent Response Failures (2026-05-20)

**Symptom:** After basic communication was established (Phase 3), pinging a servo produced inconsistent byte counts: always 0/6 or 5/6, **never 1–4**. Running `raw_ping.py` manually ~100 times showed a loose pattern of 2–3 failures followed by a success.

---

### Data Collection

Wrote `ping_stress.py` — a stress-test script that pings a servo N times and logs every result (timestamp, byte count, hex bytes) to CSV. Two modes: `--mode reopen` (re-opens serial port each ping) and `--mode keepopen` (port stays open).

Results at 1Mbps over ~100 pings each:

| Mode | OK (6/6) | MISS (0/6) | PARTIAL (5/6) |
|---|---|---|---|
| reopen | ~14% | ~10% | ~76% |
| keepopen | ~30% | ~30% | ~40% |

Key observations:
- **PARTIAL was always exactly 5/6** — the missing byte was always the first one (0xFF)
- **Never 1, 2, 3, or 4 bytes** across hundreds of attempts
- keepopen mode had more MISSes (0/6) than reopen

---

### Hypothesis Generation

The "never 1–4" pattern is a strong constraint. If the cause were:
- Timing / return delay → you'd get partial responses cut off anywhere in the packet
- Loose wire → random byte counts, possible mid-packet dropout
- VMIN=0 read() race → 0 bytes only (not 5)

The only consistent explanation for 0/5/6 with nothing in between: **only the first byte is vulnerable, and all subsequent bytes arrive as an indivisible block.**

---

### Root Cause: UART Framing Error

At the TX→RX bus turnaround on a half-duplex bus, the servo's line driver must pull the bus line back to idle-high before sending the response. This takes a finite time determined by the RC time constant: **τ = R_driver × C_bus**, where R is the driver's output impedance and C is the total parasitic capacitance of the wiring, connectors, and pins.

During this rise time, the PL011 UART sees the line sitting low. It interprets the falling edge (TX→idle→response) as a start bit. It then clocks in 8 "data" bits while the line is still charging — garbage data. At the end of the byte, when it checks the stop bit (expected high), it may find the line low → **framing error**.

The Linux tty layer, running under its default `IGNPAR` configuration, **silently discards** framing-errored bytes. No signal is sent to userspace. The discarded byte is gone.

Because only the **first byte of the response** is at the turnaround boundary, and all remaining bytes are transmitted contiguously (no gap between them), only the first byte is ever affected. This perfectly explains the 0/5/6 distribution.

The 0/6 case: occasionally the framing error hits the **outgoing ping packet's** first byte instead, corrupting the command. The servo rejects the malformed packet and sends no response.

**Why retry works:** After the first transmission, the line driver's gate capacitances are partially charged and the driver re-enables faster on the next attempt. This is an RC capacitance effect — the driver is "warm" — not a thermal effect. On a DIY setup with hand-soldered headers and longer-than-spec wire runs, parasitic capacitance is higher than on a proper PCB, making this effect more pronounced.

**What doesn't help:**
- **Return delay (reg 7):** adds silence *before* the response, but the framing transient is locked to byte 1 of the response regardless of how long the bus was silent before it
- **Baud rate reduction (250kbps tested):** the RC time constant is set by hardware capacitance, not by bit timing; a slower baud rate doesn't shrink the transient

---

### VMIN/VTIME Discovery

A separate issue: pyserial sets `VMIN=0 VTIME=0` on `serial.Serial()` open, and these terminal settings **persist after `close()`**. With `VMIN=0`, a `read(n)` call returns immediately with 0 bytes if nothing has arrived yet — it doesn't block. This caused `raw_ping.py` run-to-run inconsistency that was mistaken for a hardware issue.

**Fix:** After opening the port, call `termios.tcsetattr()` to set `VMIN=n` (where n = expected response length). This makes `read(n)` block until n bytes are available, eliminating the race condition.

```python
def set_vmin(ser, vmin, vtime=0):
    fd = ser.fileno()
    attrs = termios.tcgetattr(fd)
    attrs[6][termios.VMIN]  = vmin
    attrs[6][termios.VTIME] = vtime
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
```

---

### Fix Implemented

**1. Resync parser** (added to `scservo_sdk/port_handler.py:readPort()` and `control/raw_ping.py:parse_response()`):

- Read `length+1` bytes (one extra to absorb the potential dropped first byte)
- Search for `FF FF` header → clean case, return `buf[i:i+length]`
- If not found, search for lone `FF` → the first 0xFF was dropped; prepend a synthetic 0xFF to reconstruct the original packet
- Validate with checksum: `~(ID + LEN + ERR) & 0xFF`

```python
# Clean case
for i in range(len(buf) - 1):
    if buf[i] == 0xFF and buf[i + 1] == 0xFF:
        return bytes(buf[i:i + length])

# Lone FF — first 0xFF dropped, reconstruct
for i in range(len(buf)):
    if buf[i] == 0xFF:
        return bytes(bytearray([0xFF]) + buf[i:i + length - 1])
```

**2. Retry on empty response** (`raw_ping.py`, MAX_RETRIES=2):

```python
for attempt in range(1, MAX_RETRIES + 2):
    ser.reset_input_buffer()
    ser.write(pkt)
    raw = ser.read(PING_RESPONSE_LEN)
    if raw:
        break
```

**Result:** Near-100% reliable communication after fix. Occasional 0/6 (cold start) resolves on first retry.

---

### Servo ID Assignment (2026-05-20)

All 12 STS3215 servos assigned unique IDs using `setup_servo.py` with the `--force` flag (broadcast write, no ACK):

```bash
# For each servo (one at a time, factory default ID=1):
python3 software/control/setup_servo.py --new-id <X> --return-delay 100 --force
python3 software/control/raw_ping.py --id <X>   # verify
```

| Arm | Servo | ID | Joint |
|---|---|---|---|
| Leader | Base | 1 | — |
| Leader | — | 2 | — |
| Leader | — | 3 | — |
| Leader | — | 4 | — |
| Leader | — | 5 | — |
| Leader | Tip | 6 | — |
| Follower | Base | 7 | — |
| Follower | — | 8 | — |
| Follower | — | 9 | — |
| Follower | — | 10 | — |
| Follower | — | 11 | — |
| Follower | Tip | 12 | — |

Return delay set to 100 units (200µs) for all servos.

**Critical note about `--force` mode:** `--force` uses broadcast ID (0xFE) and skips ACK checking. Baud rate writes via `--force` write to SRAM — the EPROM only reloads on power cycle. Always specify `--baud <current_servo_baud>` when communicating at a non-default baud rate, e.g.:
```bash
python3 setup_servo.py --current-id 9 --new-baud 1000000 --force --baud 250000
```

---

### Additional Files

- `software/control/baud_scan.py` — scans all baud rates × IDs 1–20; useful when servo baud rate is unknown
- `software/control/ping_stress.py` — stress-test script; CSV output; `--mode reopen` or `--mode keepopen`
- **Note:** test CSV files (`reopen.csv`, `keepopen.csv`, `ping_stress_keepopen.csv`) were committed to the repo — add these to `.gitignore`

---

### Lessons Learned (Phase 4)

1. **The byte count distribution is a strong diagnostic signal.** "Never 1–4 bytes" immediately rules out timing and loose-wire hypotheses and points to a per-byte mechanism at a fixed boundary.

2. **VMIN=0 is a silent foot-gun.** pyserial's default terminal settings cause `read()` to be non-blocking. Set VMIN explicitly after opening the port on any Pi UART project.

3. **Resync parsers beat return delay tuning.** Return delay cannot fix a framing error because the transient is physically welded to byte 1. A software resync parser handles it transparently without any hardware changes.

4. **RC warm-up explains retry success.** The line driver charges faster on retry because the parasitic capacitance is already partially charged. This is more pronounced on DIY wiring than a production PCB.

5. **port_handler.py is modified — do not replace with stock version.** The resync parser lives in `readPort()`. Replacing it with the upstream SDK would re-introduce the framing error.
