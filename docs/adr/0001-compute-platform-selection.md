# ADR 0001 — Compute Platform: Raspberry Pi Zero 2W → Jetson Orin Nano Super

**Status:** Accepted (decided 2026-05-26)

## Context

Hexarm's original compute platform was a Raspberry Pi Zero 2W, driving the servo
bus over its GPIO UART. Two constraints made it a dead end for where the project
was headed:

- **UART availability.** The Pi Zero 2W exposes only one hardware UART
  (`ttyAMA0` on GPIO 14/15, after `disable-bt` frees it from the Bluetooth
  modem). hexarm needs to drive two arms; a single-bus, single-UART design was
  possible in principle (see [ADR 0002](0002-single-bus-servo-topology.md)),
  but a second, software-UART, or USB-adapter path would have been needed for
  any two-bus layout, and none of those options were resolved — tracked as TBD
  in `config.py` before that file was retired.
- **LeRobot's compute requirements.** The project's end goal is imitation
  learning via Hugging Face LeRobot — recording demonstrations and then
  training/running an ACT (or diffusion) policy. That means a real CUDA-capable
  GPU for training, and Python ≥3.12 for current LeRobot. A Pi Zero 2W has
  neither — it was viable for teleoperation (pure servo bus I/O) but never for
  the training/inference half of the project.

## Decision

Retire the Pi Zero 2W (2026-05-26) in favor of an NVIDIA Jetson Orin Nano
Super: onboard CUDA GPU, enough compute to train and run an ACT policy
locally, and a full Linux userspace instead of a GPIO-constrained embedded
board.

The Jetson also turned out to need its own follow-up platform decision:
JetPack 6.2 (its initial flash) only ships cp310 CUDA torch wheels, and
LeRobot's main branch requires Python ≥3.12. The board was reflashed to
JetPack 7.2 (2026-08-04, via Jetson ISO, NVMe `/data` preserved untouched) once
that became a hard blocker — a firmware update on the same hardware, not a
second platform swap. Full details in `docs/context.md`'s "Jetson JP7.2
reflash" write-up.

## Consequences

- Full USB CDC-ACM connection to the Waveshare servo driver board
  (`/dev/ttyACM0` via the in-kernel `cdc_acm` driver) — no GPIO UART wiring,
  no UART-count ceiling for a future two-bus split.
- Real onboard training became possible: the 25,000-step ACT run for
  `hexarm/pick_and_place_v2` completed locally overnight (2026-08-14,
  ~6h12m) rather than requiring a round-trip to the cloud (though cloud
  training remains an option for larger runs — see `docs/context.md`).
- New failure surface that a Pi Zero 2W never had: the Jetson's unified
  memory pool can be exhausted by a training run with no swap configured,
  hard-freezing the board with no OOM-kill warning — hit twice, root-caused
  and fixed via `zram-tools` (see `docs/debugging/postmortems.md` #9).
- The full Pi-era UART bring-up chronology (PL011 vs. mini-UART,
  `disable-bt`, the serial-console/`getty` trap, straight-through Waveshare
  wiring) is preserved in
  [`docs/debugging/servo-comms-debug-log.md`](../debugging/servo-comms-debug-log.md)
  — one lesson from it (a serial console silently eating RX bytes on the
  servo UART) carried forward and was re-verified on the Jetson.
