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
- **Note:** test CSV files (`reopen.csv`, `keepopen.csv`, `ping_stress_keepopen.csv`) had been committed to the repo despite a `.gitignore` rule that didn't actually match their path (`software/control/*.csv` instead of `software/low-lvl-setup/*.csv`) — the pattern was corrected; the already-tracked files are still pending removal

---

### Lessons Learned (Phase 4)

1. **The byte count distribution is a strong diagnostic signal.** "Never 1–4 bytes" immediately rules out timing and loose-wire hypotheses and points to a per-byte mechanism at a fixed boundary.

2. **VMIN=0 is a silent foot-gun.** pyserial's default terminal settings cause `read()` to be non-blocking. Set VMIN explicitly after opening the port on any Pi UART project.

3. **Resync parsers beat return delay tuning.** Return delay cannot fix a framing error because the transient is physically welded to byte 1. A software resync parser handles it transparently without any hardware changes.

4. **RC warm-up explains retry success.** The line driver charges faster on retry because the parasitic capacitance is already partially charged. This is more pronounced on DIY wiring than a production PCB.

5. **port_handler.py is modified — do not replace with stock version.** The resync parser lives in `readPort()`. Replacing it with the upstream SDK would re-introduce the framing error.

> **2026-05-25 update — lesson #5 above is wrong.** Phase 5 below revealed the framing-error narrative was misdiagnosed. The resync logic in `port_handler.readPort()` was reverted to the SDK original. Reasoning preserved here for context; refer to Phase 5 for the corrected understanding.

---

## Phase 5 — SDK Path Regression and the Real Root Cause (2026-05-25)

**Symptom:** With the Phase 4 fixes in place, `raw_ping.py` worked but every SDK-based script (`ping_one.py`, `calibrate.py`, `setup_servo.py`) failed with `COMM_RX_TIMEOUT` or `COMM_RX_CORRUPT`. The bug was sticky — survived reboots, survived re-seating connectors, survived `port_handler.py` edits.

This phase reframed Phase 4 entirely. The framing-error theory turned out to be wrong. Two separate problems were stacked, and one was masking the other.

---

### Step 1 — Refactor for sharing (`_serial_utils.py`)

To stop duplicating the same setup boilerplate across `ping_one.py`, `setup_servo.py`, `calibrate.py`, the code was consolidated into `software/control/_serial_utils.py`:

- `set_vmin(ser, vmin=1)` — termios fix from Phase 4
- `open_sdk_port(port, baud)` → `(port_handler, st)` — handles PortHandler boilerplate plus VMIN
- `ping_with_retry(st, id)` / `read_pos_with_retry(st, id)` / `write_byte_with_retry(st, id, addr, val)` — wrap SDK calls with a small retry budget

Also fixed: `port_handler.setupPort()` was opening pyserial with `timeout=0`, which sets `O_NONBLOCK` on the fd and **overrides any VMIN setting at the kernel level**. Changed to `timeout=0.1`, which makes pyserial use a `select()`-based timeout and lets VMIN actually take effect.

**Result:** No change. SDK path still failed.

---

### Step 2 — Diagnostic script (`sdk_diag.py`)

Built a diagnostic comparing four ping patterns against the same servo back-to-back:

| Variant | Description |
|---|---|
| A. RAW | Verbatim `raw_ping.py` — VMIN=6, single `ser.read(6)` |
| B. VMIN1 | Same as A but VMIN=1 |
| C. LOOP | VMIN=1 + `ser.read(1)` × 6 (the SDK's read pattern) |
| D. SDK | Full PortHandler + `sms_sts.ping()` stack |

First run results were unexpected: **every variant returned 0 bytes**, including A (which had worked manually moments before).

```
A. RAW   (VMIN=6, read(6)): 0/5
B. VMIN1 (VMIN=1, read(6)): 0/5
C. LOOP  (VMIN=1, read(1) x 6): 0/5
D. SDK   (PortHandler.ping): 0/5
```

This was the moment the framing-error theory started falling apart — if RC turnaround were the issue, raw_ping wouldn't have been intermittently working all session.

---

### Step 3 — Triage: power cycle, reseat, reboot, loopback

Suspecting hardware fault:

1. Power-cycled Waveshare board → no change
2. Reseated JST-PH and Dupont connectors → no change
3. Rebooted Pi → no change
4. **Bypassed Waveshare entirely**: jumpered Pi GPIO 14 (TX) directly to GPIO 15 (RX) with a Dupont wire and wrote three bytes, expected to see them echo back:

   ```python
   ser = serial.Serial('/dev/ttyAMA0', 1000000, timeout=0.1)
   ser.write(b'\xAA\xBB\xCC')
   time.sleep(0.05)
   print(ser.read(10).hex())   # Got: '' (empty)
   ```

The Pi couldn't echo its own bytes through its own UART. That eliminated the Waveshare, the servo, and the bus wiring as suspects. The problem had to be on the Pi side.

---

### Step 4 — The actual root cause

Running:

```bash
sudo dmesg | grep -iE "uart|serial|tty(AMA|S)"
```

revealed:

```
Kernel command line: ... console=ttyAMA0,115200 ...
[    1.871269] 3f201000.serial: ttyAMA0 ... is a PL011 rev2
[    1.873146] printk: legacy console [ttyAMA0] enabled
[   12.968559] systemd[1]: Expecting device dev-ttyAMA0.device - /dev/ttyAMA0...
```

And:

```bash
stty -F /dev/ttyAMA0 -a | head -1
# speed 115200 baud; rows 24; columns 80; ...
```

`stty` reported the port speed as **115200**, even though every Python script in the project was setting it to 1,000,000. The PL011 was being held at 115200 because **a kernel serial console + `serial-getty@ttyAMA0.service` were running on `/dev/ttyAMA0`**.

A getty/console on the same UART:

- **Consumes incoming bytes** before pyserial's `read()` can see them
- **Writes login prompt characters out the TX line** between reads, putting noise on the servo bus
- **Holds the port at its console baud (115200)** at the kernel level — Python's `setBaudRate(1000000)` had been silently fighting this the whole time

This single setting alone explained **every confusing symptom of Phase 4**:
- The "5/6, never 1–4" distribution → getty was occasionally swallowing the leading 0xFF
- The "retry works because the bus is warm" effect → coincidence; gettys are non-deterministic about which bytes they grab
- The bus randomly going silent → getty fully active, eating everything
- The loopback failure → getty consumed the test bytes before pyserial read them

---

### Step 5 — The fix

Two changes on the Pi:

1. **Remove the serial console** from the kernel command line. Edit `/boot/firmware/cmdline.txt` and delete `console=serial0,115200 ` (note: `serial0` is a symlink to `ttyAMA0` here because `disable-bt` routed PL011 to GPIO). The remaining `console=tty1` is fine — it's the virtual console for HDMI/log output, unrelated to the GPIO UART.

2. **Disable serial-getty:**
   ```bash
   sudo systemctl disable --now serial-getty@ttyAMA0.service
   sudo systemctl disable --now serial-getty@serial0.service
   sudo reboot
   ```

Verify after reboot:

```bash
cat /proc/cmdline | grep -o "console=[^ ]*"
# Should output:  console=tty1  (only)

stty -F /dev/ttyAMA0 -a | head -1
# Should NOT be locked to 115200 anymore
```

Easier alternative for the future: `sudo raspi-config` → Interface Options → Serial Port → login shell **NO**, hardware **YES**.

---

### Step 6 — Re-running `sdk_diag.py`

After the reboot, the diagnostic told a completely different story:

```
A. RAW   (VMIN=6, read(6)): 5/5    dt = 0.4ms
B. VMIN1 (VMIN=1, read(6)): 5/5    dt = 0.4ms
C. LOOP  (VMIN=1, read(1)x6 loop): 5/5    dt = 603ms   ← see below
D. SDK   (PortHandler.ping): 0/5   result = COMM_RX_CORRUPT, dt = 1208ms
```

**Three things to extract:**

1. **All read patterns worked cleanly.** Every variant returned a 6/6 response (`FF FF 02 02 00 FB`). Importantly, **no 5/6 cases appeared** — strong evidence that the "framing error at RC turnaround" theory of Phase 4 was misdiagnosis. The "missing first byte" pattern was getty interference all along.

2. **The read(1)-loop (variant C) was 1500× slower than the single-read variants.** That's because the patched `port_handler.readPort()` was set to read `length+1` bytes (`target = 7`) to "absorb a dropped leading byte." For a clean 6-byte response, there is no 7th byte — so the loop burned the full 600ms deadline waiting for it.

3. **The SDK variant (D) took exactly 2× the loop time (1208ms) and returned -7 (COMM_RX_CORRUPT).** That's the signature of `ping()` doing **two** transactions: the PING (succeeds, ~600ms) plus a follow-up READ of the model-number register at address 3 (corrupts, ~600ms).

---

### Step 7 — The SDK byte-stealing bug

Tracing the second transaction inside `ping()`:

1. Servo response: `FF FF 02 04 00 09 00 CHK` (8 bytes — 2-byte model number)
2. SDK calls `port_handler.readPort(6)` (initial `wait_length - rx_length = 6 - 0`)
3. Custom `readPort` sets `target = 7` and reads 7 bytes from the kernel: `[FF FF 02 04 00 09 00]`
4. Resync finds `FF FF` at offset 0, returns `buf[0:length] = buf[0:6]` — **the 7th byte (`00`) is silently dropped on the floor**
5. SDK's `rxPacket` extends `rxpacket` to 6 bytes, sees `rxpacket[PKT_LENGTH] = 0x04`, recalculates `wait_length = 4 + 3 + 1 = 8`, loops back to `readPort(2)`
6. Kernel buffer only has 1 byte left (the `CHK`) — the other needed byte (`00`) was consumed by step 3 and then thrown away
7. After another 600ms wait, `rxpacket` has 7 bytes, `wait_length = 8`, `isPacketTimeout` fires → `COMM_RX_CORRUPT`

**The "read length+1 to absorb a dropped byte" pattern is broken for any multi-transaction SDK call.** It works for single-shot reads (`ReadPos`, the first half of `ping()`), but `ping()` itself does two reads back-to-back and the stolen byte was the data the second read needed.

---

### Step 8 — Fix

Reverted `port_handler.readPort()` to the original SDK implementation:

```python
def readPort(self, length):
    if sys.version_info > (3, 0):
        return self.ser.read(length)
    else:
        return [ord(ch) for ch in self.ser.read(length)]
```

With the getty gone, framing errors at the bus turnaround are no longer observed. If they ever reappear (different hardware, longer cabling), the right place to handle them is at the SDK-call level — via the existing `ping_with_retry` / `read_pos_with_retry` / `write_byte_with_retry` wrappers in `_serial_utils.py` — not by stealing bytes in `readPort`.

Re-running `sdk_diag.py`:

```
A. RAW   (VMIN=6, read(6)): 5/5    dt = 0.4ms
B. VMIN1 (VMIN=1, read(6)): 5/5    dt = 0.4ms
C. LOOP  (VMIN=1, read(1)x6 loop): 5/5    dt = 603ms   ← (the diag still has +1 target;
                                                          not relevant — the SDK no longer uses this pattern)
D. SDK   (PortHandler.ping): 5/5   result = COMM_SUCCESS, model = 777, dt = 1ms
```

Variant D went from 1208ms / corrupt to **1ms / success**. End-to-end test on `calibrate.py`:

```
Opening /dev/ttyAMA0 at 1000000 baud...
Servo ID to calibrate (1–12): 2
  ✓ Servo 2 online (model 777)
  ID  2  |  Live: 3567  |  >MIN=----  |   MAX=----  |   MID=----
  ✓ MIN = 3567
  ✓ MAX = 797
  ✓ MID = 2402
  Saved → ../config/limits.json
```

STS3215 reported model number **777** in `ping()`. Calibration writes recorded successfully.

---

### Lessons Learned (Phase 5)

1. **`stty -F /dev/ttyAMA0` reporting a baud rate you didn't set is a red flag.** If the kernel says 115200 and your code sets 1Mbps, something else owns the port. Check `/proc/cmdline` for `console=ttyAMA0` / `console=serial0` and `systemctl is-enabled serial-getty@ttyAMA0.service`.

2. **A pyserial loopback test is the cheapest UART sanity check available.** Jumper TX↔RX on the GPIO header. If the Pi can't echo its own bytes, every higher-level theory is wasted effort.

3. **`dmesg | grep -iE "uart|serial|tty"` revealed the answer in three lines.** `console=ttyAMA0,115200` + `serial-getty@ttyAMA0.service` was right there at boot — checking dmesg should be in the first ten things to do when a Pi UART misbehaves, not the last.

4. **Misdiagnoses can be self-confirming.** The Phase 4 "framing error" theory was internally consistent — every observed symptom (0/5/6, never 1–4, retry helps) had a plausible explanation. None of those explanations were right. **The cure for a confirmable theory is a falsifying experiment**: in this case, the loopback test, which collapsed the whole story in one command.

5. **Custom modifications to SDK internals (`port_handler.readPort`) need to be auditable for side effects across all SDK callers, not just the one you're testing.** The `length+1` trick worked for single-transaction reads and broke multi-transaction ones. If you must monkey-patch an SDK, do it at the smallest possible scope (an outer retry wrapper) and leave the inner machinery stock.

6. **On a Pi, `raspi-config → Interface Options → Serial Port` correctly sets BOTH the console and the getty in one step.** Always use it instead of hand-editing `cmdline.txt` and `systemctl disable` separately. Cleaner, harder to get wrong, easier to undo.

7. **Pi Zero 2W gotcha to remember:** the default Ubuntu 24.04 image ships with `console=serial0,115200` in `/boot/firmware/cmdline.txt` AND `serial-getty@ttyAMA0.service` enabled. Either alone breaks high-baud UART; together they're invisible.

---

### Working Configuration as of 2026-05-25

```
Raspberry Pi Zero 2W (Ubuntu 24.04 server)
  GPIO 14 (TX)  ────────────────  TX  ┐
  GPIO 15 (RX)  ────────────────  RX  │  Waveshare Bus Servo Adapter (A)
  GND           ────────────────  GND ┘  (switch: UART-Servo)
                                          │ JST-PH
                                          ▼
                                       STS3215 servo (model 777)

UART:         /dev/ttyAMA0 (PL011)
Baud:         1,000,000
Console:      tty1 only (NOT serial0/ttyAMA0)
getty:        disabled on ttyAMA0 + serial0
SDK:          scservo_sdk (local copy), readPort = stock
Retry layer:  software/control/_serial_utils.py
```

Verified end-to-end: `raw_ping.py`, `ping_one.py`, `sdk_diag.py` (all 5 variants), `calibrate.py` — all working with clean 6/6 responses, sub-millisecond ping times, no retries needed in normal operation.
