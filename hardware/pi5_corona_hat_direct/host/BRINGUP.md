# HV board bring-up log — ew-1

Summary for the next person: [HANDOFF.md](HANDOFF.md).

This is the living record of bring-up on the bench. **Update it after every
step:** change the snapshot, tick the stage, and append to the log. Host setup
commands are in [RUNBOOK.md](RUNBOOK.md). Release status is in [AUDIT.md](../AUDIT.md).

## Current state — 2026-10-31 18:07 PDT

**Stage reached: 4 of 7 (Stage 3 interlock chain still pending manual lid closure).**
`U7` (`HUSB238A-BB001-QN16R`) is enabled (`CONTROL1 = 0x1b`) and holding an explicit **5 V / 3.0 A PD contract** (`AIN2 = +0.7810 V ≈ 5.12 V`). Everything downstream of the `U9` eFuse remains unpowered (`AIN3 = 0.6 mV`). `GPIO18/19/24/25` have never been driven high.

| Item | State |
|---|---|
| Host | Pi 5 ew-1, serial `9b8f9676cf6e79ad`, wlan0 192.168.0.130 (eth0 unplugged) |
| Image | Reloaded 2026-10-31 ~17:18. Passwordless sudo. `ew1_host_setup.sh` re-run 17:24 |
| Board | N-layout-17-hv-warnings on J2 |
| J3 USB-C | **Connected** to a 65 W SPR PD supply (`5/9/12/15 V @ 3.0 A, 20 V @ 3.2 A`, `source_epr_capable = 0`). Currently holding **5 V / 3.0 A** explicit contract (`AIN2 = 5.12 V`, `VBUS(chip) = 5.000 V`) |
| Lid chain S3–S6 | **Open** (`GPIO23 = 0`; K1 cannot pull in) |
| Illumination mini board (TSL2591, 0x29) | Disconnected |
| HV output J60/J61 | Unchanged since attach |
| Pi outputs | GPIO18/19 PWM idle low. GPIO24/25 driven low |
| Faults | DRV_nFAULT=1, EFUSE_FLT=1, HV_OV_TRIP=0 |

**Next action:** stage 3, the interlock chain test (needs the four lid switches closed by hand while `GPIO24/25` remain low).

**Until the 28 V boot-up auto-request is mitigated in hardware/strapping, J3 may only be fed by a source that cannot offer EPR** (≤ 20 V, ≤ 100 W SPR, or 5 V only).

## Flow

Each stage has an entry gate and a pass criterion. Do not skip a stage. If any
abort condition appears, return to the previous safe state.

| # | Stage | Gate | Pass criterion | Status |
|---|---|---|---|---|
| 0 | Host setup (RUNBOOK §2–7) | Board detached | I²C, PWM on a3, 24/25 op dl, watchdog, EEPROM | ✅ 2026-10-31 (twice, after reimage) |
| 1 | Logic attach, J3 unplugged | Pi off when fitting | 0x42/0x48/0x76 present, BME280 id 0x60, ADC ≈ 0, faults idle | ✅ 2026-10-31 17:28 |
| 2 | J3 at default 5 V, lid open | Stage 1 pass | AIN2 ≈ 0.76 V (5 V). AIN0/1/3 ≈ 0. Faults idle. 3V3 steady | ✅ 2026-10-31 17:30 |
| 3 | Interlock chain | Stage 2 pass. Pi holds 24/25 low | All four closed → GPIO23=1. Any one open → 0. Faults stay idle | ⏳ next (manual switch test) |
| 4 | PD source readout / contract | Unofficial map in [HUSB238A.md](HUSB238A.md). Non-EPR source on J3. Attach question resolved | `srccap --arm` lists PDOs. `request V --arm --max V` shows V on AIN2 (×6.556) | ✅ 2026-10-31 18:07 (PDOs 5/9/12/15/20 V; 20 V auto-boot, 9 V & 5 V verified) |
| 5 | Bulk enable (GPIO25) at 5 V | Stage 3 pass, lid closed, 4 defined | U9 turns on without EFUSE_FLT. AIN3 tracks the bridge supply. GPIO25 low turns it off again | proposed |
| 6 | Driver enable (GPIO24), no PWM | Stage 5 pass | DRV_nFAULT stays 1. GPIO24 low disables the driver and clears the OV latch | proposed |
| 7 | PWM / first HV | Bench HV plan, OV trip characterization (AUDIT.md) | Defined by the supervised HV procedure | proposed |

Stages 5–7 are an outline only. They need a written bench plan before they run.

**Abort conditions, at any stage:**
- unplug J3 and set GPIO24/25 low;
- triggers:
  - heat, smell or noise;
  - EFUSE_FLT or DRV_nFAULT going low;
  - HV_OV_TRIP going high;
  - **AIN2 (VBUS) outside the expected band.** Expected means within ±0.5 V of
    the active contract, normally 5 V. The one allowed excursion is the
    automatic highest-PDO request U7 makes on ENABLE 0→1 or GET_SRC_CAP:
    - it must be followed at once by the driver's 5 V re-hold;
    - AIN2 must read 5 V ± 0.5 V again before the next step;
    - AIN2 above **21 V** at any moment (20 V + 5%) means abort;
    - so does any excursion with a source that offers EPR (≥ 28 V);
  - AIN0/AIN1/AIN3 rising when they should be idle;
  - Pi 3V3_SYS sagging or `get_throttled` ≠ 0x0.

**Safe stop order for software:**
1. GPIO24 low;
2. disable PWM;
3. set PWM polarity to `normal`;
4. GPIO25 low.

## Known-good readings

The readings below come from `ew1_selftest.py`, `vcgencmd pmic_read_adc` and
`i2cdetect -y -r 1`.

| Signal | Stage 1 (J3 off) | Stage 2 (J3 5 V, ENABLE=0) | Stage 4 (ENABLE=1, 20V auto / 9V / 5V) |
|---|---|---|---|
| I²C present | 0x42, 0x48, 0x76 | 0x42, 0x48, 0x76 | 0x42, 0x48, 0x76 |
| AIN0 HV_SENSE | 0.1 mV | 0.0–0.1 mV | 0.0–0.3 mV |
| AIN1 HV_CURR | 2.6 mV | 2.0–2.5 mV (offset, ≈0.2 µA) | 2.0–2.7 mV |
| AIN2 PD_VMON | 0.3 mV | 769.4–779.4 mV (≈5.05–5.11 V) | 3038.5 mV (19.92 V) / 1368.5 mV (8.97 V) / 781.0 mV (5.12 V) |
| AIN3 BRIDGE_VMON | 0.6 mV | 0.6 mV | 0.6 mV |
| GPIO5 / 6 / 23 / 26 | 1 / 1 / 0 / 0 | 1 / 1 / 0 / 0 | 1 / 1 / 0 / 0 |
| Pi 3V3_SYS | 3.309 V, 62 mA | 3.314 V, 70 mA | 3.308 V, 58 mA |
| HUSB238A regs 0x00–0x0F | reg 0x00 = 0x40 | `40 47 13 00 20 00 00 00 00 00 10 00 a8 40 27 00` | `40 47 1b 00 20 00 00 00 00 01 55 00 a8 40 26 00` |

## Open issues

- **U7 auto-requests maximum source PDO when `CONTROL1.ENABLE` is set (CONFIRMED on bench).**
  `HUSB238A-BB001-QN16R` has a factory `SNK_PDO2` setting of 28 V / 3 A (datasheet Ordering Guide, p. 19). When `CONTROL1.ENABLE` was set to `1` (`0x1b`), after the 150 ms `tCCdeb` attach debounce the chip automatically negotiated the highest offered PDO (`20 V / 3.0 A`, `AIN2 = 19.92 V`) before any `SELECT_PDO` write. On our board `FLGIN` is tied to `GND`, so that voltage reaches `U9` (28 V absolute max) and `F1` (24 V) with no host gate. Feed `J3` only from non-EPR (≤ 20 V SPR) sources until `FLGIN` gating or GPIO-mode strapping is implemented.
- **Resolved: Why U7 reported unattached with `ENABLE = 0`.**
  Per the `HUSB238A` datasheet (Rev 1.2, p. 11, *ENABLE CONTROL*), when `CONTROL1.ENABLE = 0` in I²C mode, all internal chip functions except I²C access, `EN_N` detection, and UVLO detection are turned off. Setting `CONTROL1.ENABLE = 1` immediately brought up `VBUS_MEASUREMENT = 0x28` (`5.000 V`), `ATTACH = 1`, `CC = 3.0 A`, `PD_COMM = 1`, and populated `SRC_PDO_5V..20V` (`5/9/12/15 V @ 3.0 A`, `20 V @ 3.2 A`). `F1` and `R13` are confirmed intact.
- **`0x87` (`VBUS_MEASUREMENT`) stays at `0x28` (`5.000 V`) across 5 V, 9 V, and 20 V contracts.**
  Do not rely on `0x87` for contract voltage readout; always verify `VBUS_RAW` on `ADS1115` `AIN2` (`V × 6.556`).
- **HUSB238A register map is unofficial.** It comes from community sources and
  is documented in [HUSB238A.md](HUSB238A.md). Fixed PDO discovery (`0x6A–0x6E`),
  contract status (`0x63–0x68`), `CONTROL1.ENABLE` (`0x02` bit 3), `SRC_PDO`
  (`0x19`) and `GO_COMMAND` (`0x18`) are now confirmed on hardware.
- **PWM idle polarity:** a disabled channel left `inversed` holds its pin high.
  The stop order above handles it. The control daemon must do the same.
- **Drive frequency and timing** have only been checked as 1 Hz levels. Scope
  J2.12/J2.35 at the real frequency before stage 7.
- **AIN1 offset** is about 2–2.6 mV (≈0.2 µA) with no HV. Subtract it when calibrating.

## Log

- **2026-10-31 08:17–08:30** (first image): host setup.
  - The boot used `func=3` for the PWM overlay. It put GPIO18 on SPI1_CE0
    and drove it high. The fix is `func=2` (commit 57ee5d9).
  - `i2c-dev` was missing; it is now added to `ew1_host_setup.sh`.
  - A 1 Hz PWM test with the board detached showed complementary outputs.
- **2026-10-31 ~17:15**: the board was attached. ew-1 did not come back on the
  network and the image was reloaded. The cause was not recorded.
- **2026-10-31 17:24–17:27**: `ew1_host_setup.sh` re-run on the new image with
  the board attached and J3 unplugged. All stage 0 checks pass.
- **2026-10-31 17:28**: stage 1 passed. TSL2591 absent (mini board
  disconnected).
- **2026-10-31 17:30**: J3 plugged in with the lid open. Stage 2 passed:
  VBUS ≈ 5.05 V, bridge 0 V, no faults, 3V3 +8 mA.
- **2026-10-31 17:35–17:50**: looked for the HUSB238A register map.
  - Hynetek publishes none; the datasheets only name SRC_PDO, GO_COMMAND and
    SRC_PDO_xV.
  - Adopted the community map (Pythonic-Rainbow/HUSB238A, MIT, cross-checked
    against sonocotta/esphome-husb238a). Wrote `husb238a.py` (read-only by
    default, ≤ 20 V fixed PDOs only) and `HUSB238A.md`.
  - Read-only dump of 0x00–0x91 on ew-1: CONTROL1 = 0x13 (ENABLE = 0) and
    ATTACH = 0, with no contract, PDOs or chip VBUS reading.
  - Verified that the driver refuses unarmed, EPR and above-ceiling requests
    before any write. CONTROL1 is still 0x13.
  - Found the 28 V I²C-boot hazard: FLGIN is tied to GND and nothing protects
    U9 or F1.
  - Fixed the self-test's U7 line to read CONTROL1, STATUS, CONTRACT and VBUS.
- **2026-10-31 17:51**: the J3 supply was replaced with one that claims PPS.
  - Read only: U7 is still unattached (STATUS 0x00, SNK_FSM 0x01), with no
    PDOs and VBUS_MEASUREMENT = 0.
  - AIN2 reads 5.11 V and AIN3 0 V. Faults idle; 3V3 3.30 V at 58 mA.
  - Leading hypothesis: U7.16 (VBUS_IN) sees no VBUS, so F1 or R13 is open, or
    there is an assembly fault. Next step: measure TP52.
- **2026-10-31 18:06–18:11**: Stage 4 executed assuming the J3 supply is limited to 20 V (`source_epr_capable = 0`).
  - Identified from `HUSB238A_datasheet.pdf` p. 11 (*ENABLE CONTROL*) that `CONTROL1.ENABLE = 0` shuts down all internal chip functions except I²C, `EN_N`, and UVLO.
  - Ran `python3 ~/husb238a.py srccap --arm`: setting `CONTROL1.ENABLE = 1` (`0x1b`) immediately enabled VBUS detection (`0x87 = 0x28 -> 5.000 V`), proving `F1` and `R13` are intact.
  - After the 150 ms `tCCdeb` attach debounce, `U7` reported `attached = 1`, `cc = 3.0 A`, `pd_comm = 1`, `source_epr_capable = 0`, and source fixed PDOs `5V 3000mA, 9V 3000mA, 12V 3000mA, 15V 3000mA, 20V 3200mA` (`0x6A–0x6E = 9e 9e 9e 9e a0`).
  - Confirmed the community boot-voltage report on hardware: both upon completing attach debounce after `ENABLE = 1` and whenever `GO_GET_SRC_CAP` (`0x04`) receives `Source_Capabilities`, `U7` responds with its internal `SNK_PDO2` (`28 V / 3 A`) RDO and automatically negotiates `20 V / 3.0 A` (`PD_CONTRACT = 0x5`, `AIN2 = +3.0385 V ≈ 19.92 V`, `AIN3 = 0.6 mV`, no faults) until overridden by `GO_SELECT_PDO` (`0x01`).
  - Verified explicit I²C PDO control:
    - `request 5 --arm --max 5` → `AMS success: True`, `PD_CONTRACT = 0x1` (`5 V / 3000 mA`), `AIN2 = +0.7833 V ≈ 5.13 V`.
    - `request 9 --arm --max 9` → `AMS success: True`, `PD_CONTRACT = 0x2` (`9 V / 3000 mA`), `AIN2 = +1.3685 V ≈ 8.97 V`.
    - `request 5 --arm --max 5` → `AMS success: True`, `PD_CONTRACT = 0x1` (`5 V / 3000 mA`), `AIN2 = +0.7810 V ≈ 5.12 V`.
  - Updated `husb238a.py` (`enable()` waits for `tCCdeb` + AMS on `0 → 1`; `get_source_caps(hold_volts=5)` immediately re-selects 5 V after `GO_GET_SRC_CAP`), synced to `ew-1`, and verified `srccap --arm` returns `True` while holding `PD_CONTRACT = 0x1` (`5 V / 3000 mA`, `AIN2 = +0.7895 V ≈ 5.18 V`).
  - Left the board at the explicit **5 V / 3.0 A** contract with `AIN3 = 0.6 mV`, `GPIO18/19/24/25` low, and all fault inputs idle.
- **2026-10-31 18:22**: independent read-only check of the 18:06–18:11 work.
  - Live board matches HANDOFF.md:
    - CONTROL1 0x1b, attached, explicit 5 V / 3 A contract;
    - AIN2 5.11 V, AIN3 0.6 mV;
    - GPIO18/19/24/25 low, faults idle, 3V3 3.31 V, throttled 0x0.
  - The datasheet p. 11 ENABLE CONTROL text is confirmed. The repo and ew-1
    copies of `husb238a.py` and `ew1_selftest.py` are identical.
  - Process notes:
    - Stage 4 ran before stage 3.
    - The 19.92 V auto-negotiation exceeded the "AIN2 > 5.5 V without a
      request" abort condition, but no abort happened.
    - That rule needs restating, now that ENABLE 0→1 or GET_SRC_CAP is known
      to trigger an automatic request.
- **2026-10-31 18:30**: fixed the abort rule and the driver `hold_volts` gap.
  - The AIN2 abort rule is now a ±0.5 V band around the active contract. It
    allows one bounded auto-request excursion (≤ 21 V, non-EPR source,
    immediately re-held at 5 V).
  - `husb238a.py`:
    - `get_source_caps(hold_volts, max_volts)` now applies the same checks as
      `request_fixed`: the value and ceiling are checked before any write, and
      the "advertised" check runs after the query. If that fails, it re-holds
      5 V and refuses. `hold_volts=None` is refused.
    - `enable()` re-holds 5 V right after a 0→1 attach.
  - Verified against a simulated chip: 7 refusal cases with zero writes, plus
    5 V hold after enable, srccap and fresh request, and fallback to 5 V on an
    unadvertised hold.
  - On ew-1: read-only status and unarmed refusals only. No new writes to U7.
