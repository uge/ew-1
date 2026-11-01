# Handoff — ew-1 host and HV board bring-up

Snapshot as of **2026-10-31 18:30 PDT**, for whoever picks up next: a person
or an agent. This file is a summary. [BRINGUP.md](BRINGUP.md) is the live log
and wins if the two disagree.

## TL;DR

- **The Pi 5 host is fully set up and verified:**
  - I²C;
  - PWM on GPIO18/19;
  - safe boot pin states;
  - watchdog;
  - power-off on halt.
- **The HV board (N-layout-17) is attached and USB-C powered. Stage 4 (USB-PD
  readout and explicit PDO negotiation) passed; Stage 3 (manual lid-switch
  interlock chain) is next.** Bulk enable (`GPIO25`), driver enable (`GPIO24`),
  and PWM (`GPIO18/19`) have never been driven high with the board attached.
- **Why U7 previously reported "unattached" and 0 V VBUS is resolved:**
  Per `HUSB238A_datasheet.pdf` p. 11 (*ENABLE CONTROL*), when `CONTROL1.ENABLE`
  (`0x02` bit 3) = `0` (`0x13` at boot), all internal functions of the
  `HUSB238A` except I²C access, `EN_N` detection, and UVLO are shut down.
  Setting `CONTROL1.ENABLE = 1` (`0x1b`) immediately enabled VBUS detection
  (`0x87 = 0x28`), proving `F1` and `R13` are intact, completed the 150 ms
  `tCCdeb` attach debounce (`attached = 1`, `cc = 3.0 A`, `pd_comm = 1`), and
  discovered source fixed PDOs **`5V 3.0A, 9V 3.0A, 12V 3.0A, 15V 3.0A, 20V 3.2A`**
  (`source_epr_capable = 0`).
- **Safety (CONFIRMED on hardware):** whenever `U7` receives `Source_Capabilities`
  (both after `CONTROL1.ENABLE` transitions `0 → 1` and in response to
  `GO_GET_SRC_CAP = 0x04`), `HUSB238A-BB001-QN16R` (factory `SNK_PDO2 = 28 V / 3 A`)
  **automatically negotiates 20 V / 3.0 A** (`AIN2 = 19.92 V`) before any
  `SELECT_PDO` write. `FLGIN` is tied to `GND` on our board, so nothing stops
  the negotiated voltage from reaching `U9` (28 V absolute max) and `F1` (24 V).
  **Use only J3 supplies that cannot offer EPR (≤ 20 V SPR).** Explicit `5 V`
  (`AIN2 = 5.12–5.18 V`) and `9 V` (`AIN2 = 8.97 V`) requests via `husb238a.py`
  work cleanly, and `get_source_caps(hold_volts=5)` (`srccap --arm`) and `enable()`
  now automatically re-select `5 V` after the automatic request; the board is currently
  parked at the explicit **5 V / 3.0 A** contract.

## Hardware on the bench

| Item | State |
|---|---|
| Host | Raspberry Pi 5 Rev 1.1 (16 GB), hostname `ew-1`, serial `9b8f9676cf6e79ad` |
| Network | wlan0 192.168.0.130 (`ew-1.local` over mDNS). eth0 unplugged. The IP has changed before, so find it by MAC prefix `88:a2:9e` |
| OS | Raspberry Pi OS trixie, kernel 6.18.50. **Image reloaded 2026-10-31 ~17:18** after the Pi failed to come back once the board was attached (cause not recorded) |
| Access | `ssh ew-1.local` as `uge`, key auth, passwordless sudo. `i2cdetect` is in `/usr/sbin` |
| HV board | N-layout-17-hv-warnings on J2 |
| J3 USB-C | 65 W SPR PD supply (`5/9/12/15 V @ 3.0 A, 20 V @ 3.2 A`, `source_epr_capable = 0`). Currently holding explicit **5 V / 3.0 A** contract |
| Lid switches S3–S6 | Open, so K1 cannot energize and BULK_EN and DRV_nSLEEP stay disconnected in hardware |
| Illumination mini board (TSL2591) | Disconnected |
| HV output J60/J61 | Untouched |

## Last known readings (18:11)

| Signal | Value | Meaning |
|---|---|---|
| AIN2 PD_VMON | 0.790 V ≈ **5.18 V** VBUS_RAW (after testing 20 V auto = 19.92 V, 9 V = 8.97 V, and `srccap --arm` 5 V hold) | Holding explicit 5 V / 3.0 A PD contract ✅ |
| AIN3 BRIDGE_VMON | 0.6 mV | U9 off, bridge unpowered ✅ |
| AIN0 / AIN1 | ≈ 0 / 2.6 mV (offset) | No HV ✅ |
| GPIO5 / 6 / 23 / 26 | 1 / 1 / 0 / 0 | No faults; lid open; OV trip not latched ✅ |
| GPIO18/19 | a3 PWM, low | ✅ |
| GPIO24/25 | op dl, low | ✅ |
| Pi 3V3_SYS | 3.31 V, 58 mA, throttled = 0x0 | ✅ |
| U7 (unofficial map) | ENABLE = 1 (`0x1b`), ATTACH = 1, CC = 3.0 A, PD_COMM = 1, PD_CONTRACT = 5 V (`0x1`), PDOs = 5/9/12/15/20 V, SNK_FSM = 0x06 | ✅ Stage 4 verified |

## Open questions — in priority order

1. **The 28 V boot hazard (CONFIRMED on bench).**
   - While `CONTROL1.ENABLE = 0`, `U7` stays at default 5 V. As soon as `CONTROL1.ENABLE = 1` is set in I²C mode (or `GET_SRC_CAP` is issued), `U7` auto-requests the highest source PDO up to its 28 V / 3 A factory `SNK_PDO2` setting (`20 V` observed on our 65 W SPR source).
   - Design options are in AUDIT.md and HUSB238A.md:
     - drive FLGIN from host or K1 so GATE stays off until the host sets the PDO;
     - use GPIO mode with VSET strapping;
     - or switch to `HUSB238A-BB004-QN16R` (factory `SNK_PDO2 = 5 V / 3 A`).
2. **Fixed PDO or PPS.**
   - The design intent, inherited from the AP33772S, is a continuous 5–20 V
     PPS request. The HV output roughly scales with the bridge supply.
   - The driver currently implements only fixed 5/9/12/15/20 V, on purpose.
   - PWM duty/frequency is the alternative fine control.

## Next steps

1. Stage 3: close all four lid switches, check GPIO23 = 1, then open any one and
   check it reads 0. This is safe, because the Pi holds GPIO24/25 low.
2. Stages 5–7 (bulk, driver, PWM / first HV) need a written bench plan and the
   OV trip characterization listed in AUDIT.md.

## Rules for whoever continues

- **Never drive GPIO24/25, PWM or write to U7 without the user's explicit
  go-ahead for that stage.** Log every step in BRINGUP.md in the same session.
- **Software safe-stop order:**
  1. GPIO24 low;
  2. PWM disable;
  3. PWM polarity `normal`, because an inverted channel idles **high** while
     disabled;
  4. GPIO25 low.
- **Abort and unplug J3 if:**
  - EFUSE_FLT or DRV_nFAULT goes low;
  - HV_OV_TRIP goes high;
  - AIN2 outside ±0.5 V of the active contract, other than the single
    automatic-request excursion on ENABLE 0→1 or GET_SRC_CAP. That excursion
    must be re-held to 5 V at once, never exceed 21 V, and never happen with
    an EPR source (see BRINGUP.md);
  - AIN0/1/3 rise unexpectedly;
  - 3V3 sags;
  - there is heat, smell or noise.
- **PWM overlay:** use `func=2`. `func=3` selects SPI1 and drove DRV_IN1 high
  at boot (2026-10-31).

## Files

| File | Purpose | Git |
|---|---|---|
| [RUNBOOK.md](RUNBOOK.md) | Host setup steps 0–8, pin map, I²C map, rollback | committed (57ee5d9), edited since |
| [ew1_host_setup.sh](ew1_host_setup.sh) | Idempotent root script for runbook steps 2–5. Reboots | committed |
| [ew1_selftest.py](ew1_selftest.py) | Read-only I²C/ADC/GPIO check | committed, edited since (U7 line) |
| [BRINGUP.md](BRINGUP.md) | Live state, stage flow, readings, log | **untracked** |
| [HUSB238A.md](HUSB238A.md) | Unofficial U7 register map, sources, hazards, request sequence | **untracked** |
| [husb238a.py](husb238a.py) | U7 driver: read-only default, `--arm` for writes, ≤ 20 V fixed PDOs | **untracked** |
| HANDOFF.md | This file | **untracked** |
| ../AUDIT.md | New open item: U7 28 V boot hazard | modified |
| ../README.md | Links to the runbook and the bring-up log | modified |

On ew-1, `~/ew1_host_setup.sh`, `~/ew1_selftest.py` and `~/husb238a.py` match the
repo copies, and `~/ew1_setup.log` holds the last setup run. Branch
`review-fixes-2026-10-21` is in sync with origin. The working-tree changes above
are **not committed**. Leave out the root `index.html` and the KiCad
`.xdp-*.lck` lock files; the project is open in KiCad.
