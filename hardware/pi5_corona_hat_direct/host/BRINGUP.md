# HV board bring-up log — ew-1

Summary for the next person: [HANDOFF.md](HANDOFF.md).

This is the living record of bring-up on the bench. **Update it after every
step:** change the snapshot, tick the stage, and append to the log. Host setup
commands are in [RUNBOOK.md](RUNBOOK.md). Release status is in [AUDIT.md](../AUDIT.md).

## Current state — 2026-11-01 12:17 PST

**Stage reached: 6 of 7. Stages 0–6 pass.**
- Stage 5 (bulk enable) was run without the 5.0 inspection.
- Stage 6 is the reduced version (option 1): **the hardware OV trip, the D90
  latch and Q2 are unverified**, and firmware-only OV limits apply to stage 7.
- GPIO18/19 have never toggled with the board attached; no HV has ever been
  generated.

| Item | State |
|---|---|
| Host | Pi 5 ew-1, serial `9b8f9676cf6e79ad`, wlan0 192.168.0.130 (eth0 unplugged). Booted ~11:47 |
| Board | N-layout-17-hv-warnings on J2. **D3/D90/D91 re-fitted by hand** (all three were assembled reversed) |
| J3 USB-C | 65 W SPR supply (5/9/12/15 V @ 3 A, 20 V @ 3.2 A). **No PPS / AVS / EPR advertised.** Explicit **5 V / 3 A** contract. AIN2 ≈ 5.1 V |
| U7 | ENABLE = 1, attached, 5 V contract |
| Lid chain S3–S6 | Closed (GPIO23 = 1), K1 energized |
| Illumination mini board (TSL2591, 0x29) | Disconnected |
| HV output J60/J61 | Unchanged since attach, never energized |
| Pi outputs | GPIO18/19 PWM a3, low, channels not exported. GPIO24/25 low |
| Faults | DRV_nFAULT = 1, EFUSE_FLT = 1, HV_OV_TRIP = 0 |

**Next action:** write the **stage 7 plan** (first PWM / first HV) within the
option 1 limits in [STAGE6_PLAN.md](STAGE6_PLAN.md):
- 5 V contract only;
- software cutoff AIN0 > 0.50 V (≈ 3 kV);
- short bursts, lid closed.

It must also define:
- the J60/J61 termination/load;
- the HV probe and discharge-verification procedure;
- the drive frequency/duty start point (the model used 68 kHz);
- the handling of nFAULT current-chopping pulses (IMODE = 62 kΩ).

**Until the 28 V boot-up auto-request is mitigated in hardware/strapping, J3 may only be fed by a source that cannot offer EPR** (≤ 20 V, ≤ 100 W SPR, or 5 V only).

## Flow

Each stage has an entry gate and a pass criterion. Do not skip a stage. If any
abort condition appears, return to the previous safe state.

| # | Stage | Gate | Pass criterion | Status |
|---|---|---|---|---|
| 0 | Host setup (RUNBOOK §2–7) | Board detached | I²C, PWM on a3, 24/25 op dl, watchdog, EEPROM | ✅ 2026-10-31 (twice, after reimage) |
| 1 | Logic attach, J3 unplugged | Pi off when fitting | 0x42/0x48/0x76 present, BME280 id 0x60, ADC ≈ 0, faults idle | ✅ 2026-10-31 17:28 |
| 2 | J3 at default 5 V, lid open | Stage 1 pass | AIN2 ≈ 0.76 V (5 V). AIN0/1/3 ≈ 0. Faults idle. 3V3 steady | ✅ 2026-10-31 17:30 |
| 3 | Interlock chain | Stage 2 pass. Pi holds 24/25 low. J62↔J64, J63↔J65, J66↔J68, J67↔J69 wired | All four closed → GPIO23=1. Any one open → 0. Faults stay idle | ✅ 2026-11-01 10:35 (after D3/D90/D91 re-fit; S3–S6 each break the chain) |
| 4 | PD source readout / contract | Unofficial map in [HUSB238A.md](HUSB238A.md). Non-EPR source on J3. Attach question resolved | `srccap --arm` lists PDOs. `request V --arm --max V` shows V on AIN2 (×6.556) | ✅ 2026-10-31 18:07 (PDOs 5/9/12/15/20 V; 20 V auto-boot, 9 V & 5 V verified) |
| 5 | Bulk enable (GPIO25) at 5 V | Stage 3 pass, lid closed, explicit 5 V contract | 5.1 contract; 5.2 GPIO25 high → bridge ≈ 4.8 V, no EFUSE_FLT; 5.3 low → decays in about 3 s; 5.4 lid open cuts it in hardware; 5.5 (opt) 9 V | ⏳ 5.1 ✅ 10:47, 5.2 ✅ + 5.3 ✅ 10:51, 5.4 ✅ 10:53 (5.0 inspection skipped by user); 5.5 ✅ 10:57 (option a step-down) → **stage 5 complete** |
| 6 | Driver enable (GPIO24), no PWM — **reduced** | Stage 5 pass. [STAGE6_PLAN.md](STAGE6_PLAN.md) rev 3 (option 1) | 6.A′ no false trip at GPIO24 high. 6.B driver awake at 9 V with VM, nFAULT = 1, no drive. 6.C1 lid open → sleep. 6.C3 software safe-stop. **Hardware OV trip NOT verified** | ✅ 2026-11-01 12:17 (6.A′, 6.B, 6.C3, 6.C1 all passed; **hardware OV trip still unverified**) |
| 7 | PWM / first HV (option 1 limits) | Stage 6 pass. [STAGE7_PLAN.md](STAGE7_PLAN.md) approved. J60/J61 termination, grounding stick, lid closed | 7.1 dry PWM with driver asleep. 7.2 20 kHz single-ended 1 s burst. 7.3 sweep 25–50 kHz, stop at AIN0 ≥ 0.33 V (≈ 2 kV), abort > 0.50 V. 7.5 discharge timing | ⏳ plan rev 2 approved (2 kV limit); 7.1 ✅ 12:24; **7.2 ✅ 12:25 (first HV ≈ 50 V)**; 7.3 ✅ 12:27 (peak ≈ 165 V @ 30 kHz; gain falls above); 7.3b ✅ 12:32 (max ≈ 205 V @ 32 kHz; second peak 26 kHz); **7.4 ✅ 12:36 (complementary 32 kHz ≈ 357 V)** |

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
- **2026-10-31 18:35**: BME280 (U5, 0x76) forced read: chip ID 0x60, 26.87 °C,
  1009.11 hPa, 34.8 % RH (Pi SoC at 39.5 °C). Readings are plausible. The
  sensor works; the board temperature reads a little above room temperature.
- **2026-10-31 18:33**: stage 3 attempted. The user reports all lid switches
  S3–S6 closed.
  - **GPIO23 = 0, so stage 3 fails.** It was steady across three samples.
  - Everything else is unchanged and safe:
    - GPIO24/25 low; faults idle; OV trip 0;
    - 5 V / 3 A contract, AIN3 0.6 mV;
    - 3V3 3.30 V at 69 mA (58 mA earlier, cause unknown).
  - The netlist shows the chain only closes through wire pairs. Each switch's
    COM/NO nets (S3_1/S3_2 …) reach only its mini-board pads
    (J62/J63/J66/J67). The relay feed path is COIL_3V (U10) → J64.1,
    J64.2 → J65.1 (LOOP_1), J65.2 → J68.1, J68.2 → J69.1, J69.2 →
    RELAY_COIL_POS → R92 → GPIO23.
  - With no wires J62↔J64, J63↔J65, J66↔J68 and J67↔J69, the chain is open
    whatever the switch positions. Next: confirm the wiring and the COM/NO
    contact map.
- **2026-10-31 18:34–18:35**: the user reports one switch had come open, then
  that the switches "may be closed now".
  - GPIO23 is still 0 (5 and then 10 samples).
  - **Pi 3V3_SYS current is 545–555 mA, steady over 4 s.** It was 58–69 mA
    all session; 3V3 held at 3.30 V, throttled 0x0.
  - That is about 490 mA of new load on 3V3, which suggests a short. One
    candidate is COIL_3V (U10 output, J64.1) to GND in the switch wiring,
    which would put U10 into current limit and also explain GPIO23 = 0.
  - Advised immediate power-down.
- **2026-10-31 ~18:37**: powered ew-1 down (`systemctl poweroff`) at the
  user's request.
  - Just before shutdown: 3V3_SYS was **66 mA**, so the 550 mA load had
    already gone. That points to an intermittent short, probably from the
    switch wiring being handled. GPIO24/25 were 0.
  - ew-1 stopped answering ping within 15 s. With POWER_OFF_ON_HALT=1, the
    3V3 to the HV board is off.
  - Next: inspect U10 and the J62–J69 wiring, then measure COIL_3V (J64.1)
    and 3V3 to GND unpowered. Restart with J3 unplugged and confirm about
    60 mA on 3V3.
- **2026-10-31 18:46**: ew-1 back up after the power-down.
  - 3V3_SYS 55.6–71.2 mA at 3.30–3.32 V over 6 samples, throttled 0x0. The
    550 mA fault is not present.
  - Boot pin states are correct (18/19 a3 low, 24/25 op dl low). I²C sees
    0x42, 0x48 and 0x76.
  - J3 is still plugged in (AIN2 5.11 V). U7 came back with ENABLE = 0 and
    unattached, so its 3V3 was cut, there is no contract, and there was no
    automatic 20 V request.
  - AIN3 0.8 mV; faults idle; GPIO23 = 0. The interlock chain is still open
    or the switches are open. Cause of the 550 mA event not yet found.
- **2026-10-31 18:47**: the switches are taped closed. Over 5 s (10 samples):
  - GPIO23 = 0 throughout;
  - 3V3 52–62 mA. There was no rise, so the K1 coil (about 33 mA at 3 V) is
    not being fed, and the 550 mA fault did not recur.
  - Faults idle; GPIO24/25 low; AIN3 0.6 mV.
  - Conclusion: the interlock chain is open between COIL_3V (J64.1) and
    RELAY_COIL_POS (J69.2). Stage 3 still fails. It needs bench probing of the
    wire pairs and the COM/NO contacts.
- **2026-11-01 08:52**: the user reports the diodes have been flipped (re-fitted
  in the correct orientation; which of D3/D90/D91 not yet confirmed). ew-1 boot
  retest, read only:
  - 3V3_SYS 50–94 mA at 3.30–3.33 V, throttled 0x0. No 550 mA load.
  - Boot pin states correct (18/19 a3 low, 24/25 op dl low). I²C 0x42, 0x48,
    0x76 present.
  - J3 plugged in (AIN2 5.07 V). U7 ENABLE=0, unattached, no automatic request.
  - Faults idle, GPIO26=0, AIN3 0.6 mV.
  - **GPIO23 = 0.** Switch state at this moment not confirmed, so stage 3 is
    not yet re-run.
- **2026-11-01 10:26**: **GPIO23 = 1** (6 samples). 3V3_SYS 80–89 mA, about
  25–30 mA above the ~57 mA baseline, which is consistent with the K1 coil
  (about 33 mA at 3 V) being fed through a closed chain. No 490 mA fault.
  - GPIO24/25 op dl low, faults idle, GPIO26 = 0, AIN3 0.8 mV.
  - With the diode re-fit, the closed half of stage 3 passes. Still to do:
    open each switch in turn and confirm GPIO23 → 0.
  - D90 orientation (silent OV-trip disable if reversed) should be confirmed
    by inspection and by an injected trip test before any HV.
- **2026-11-01 10:30**: user confirms **D3, D90 and D91 were all reversed as
  assembled** and have been re-fitted (flipped).
  - Same part, 1N4148WS C2128. This is systematic: `generate_jlcpcb_cpl.py`
    `ROTATION_OFFSETS` has no 180° entry for these parts, unlike the SS36
    D52–D55, U10 and Q2 entries. The JLCPCB-assembled orientation was 180° off.
  - Consequences, now corrected:
    - D3 reversed clamped RELAY_COIL_POS → the 490 mA U10 current limit and
      GPIO23 = 0.
    - D90 reversed would have silently disabled the hardware OV trip.
    - D91 reversed would have tripped OV as soon as GPIO24 went high.
  - U10 ran in current limit for several minutes; its output measures fine
    (coil fed, GPIO23 = 1).
  - Polarized parts still to inspect against their markings: D5 SMBJ15A,
    D50 VSSA310S, D51 SMBJ22A, D1/D4 BAT54S, and C60/C70 electrolytics.
  - New gate before HV: injected OV-trip test (latch via D90, clear via D91 /
    GPIO24 low).
- **2026-11-01 10:29**: switches taped closed.
  - GPIO23 = 1 steady (8 samples); 3V3_SYS 85–97 mA (K1 coil fed).
  - GPIO24/25 low, faults idle, GPIO26 = 0, AIN3 0.6 mV.
  - Closed half of stage 3 confirmed. Open-each-switch half still pending.
- **2026-11-01 10:31**: one switch opened (which one not stated).
  - GPIO23 = 0 steady (8 samples); 3V3_SYS 55–60 mA, back to baseline, so
    K1 has dropped out.
  - Faults idle, GPIO26 = 0, AIN3 0.6 mV.
  - Opening that one switch breaks the chain. Repeat for the remaining three
    to complete stage 3.
  - The user says it was the "top switch". On the board layout (front side,
    mini boards on the left) the top switch board is **S3**: J62 → J64, first
    in the chain from COIL_3V. Assumed, not confirmed physically.
  - Stage 3 progress: S3 ✅; S4, S5, S6 pending.
- **2026-11-01 10:32**: S4 open (S3 reclosed per sequence, not separately
  verified): GPIO23 = 0 steady (8 samples), 3V3_SYS 53–65 mA, faults idle,
  GPIO26 = 0, AIN3 0.6 mV. **S4 ✅.** S5, S6 pending.
- **2026-11-01 10:33**: S5 open: GPIO23 = 0 steady (8 samples), 3V3_SYS
  55–60 mA, faults idle, GPIO26 = 0, AIN3 0.6 mV. **S5 ✅.** S6 pending, then
  re-confirm all-closed GPIO23 = 1.
- **2026-11-01 10:33**: S6 open: GPIO23 = 0 steady (8 samples), 3V3_SYS
  53–71 mA, faults idle, GPIO26 = 0, AIN3 0.6 mV. **S6 ✅.** All four
  individual-open checks pass. Final all-closed GPIO23 = 1 re-check pending.
- **2026-11-01 10:34**: user reports all switches closed, but GPIO23 = 0 (18
  samples over about 16 s). 3V3_SYS 53–68 mA (one 99 mA spike), no coil
  current. At least one switch is not actually made: possibly not reclosed or
  re-taped after its open test, or plunger travel/tape is marginal. Faults
  idle, GPIO24/25 low, GPIO26 = 0. The all-closed re-check is not yet passed.
- **2026-11-01 10:35**: all switches closed: GPIO23 = 1 steady (10 samples),
  3V3_SYS 84–91 mA (one 137 mA spike) = K1 coil fed. GPIO24/25 low, faults
  idle, GPIO26 = 0, AIN3 0.6 mV, throttled 0x0.
  - **Stage 3 PASSED.** All closed → 1; S3, S4, S5 and S6 each open → 0, with
    the coil current dropping to baseline every time.
  - The earlier all-closed attempt at 10:34 read 0 because one switch was not
    made. It was mechanical (tape/plunger), not electrical.
- **2026-11-01 10:44**: **stage 5.1 attempted** (user skipped the 5.0
  inspection). `request_fixed(5)` set CONTROL1.ENABLE 0→1 (0x13 → 0x1b), then
  returned AMS success = False.
  - U7 stays **unattached**: STATUS 0x00, CC none/Ra, SNK_FSM 0x01. That held
    for about 8 s of polling; DPDM_STATUS raw = 0x08 (undocumented bit 3).
  - Chip VBUS 5.125 V. AIN2 5.02–5.19 V over 303 samples at about 200 Hz, so
    no automatic-request excursion. AIN3 ≤ 4 mV.
  - GPIO24/25 low, GPIO23 = 1, faults idle, GPIO26 = 0, 3V3 95 mA.
  - On 2026-10-31 the same command attached within tCCdeb. The difference
    since: the Pi was power-cycled with J3 left plugged in, so U7 lost VDD
    while VBUS stayed up. Likely needs a J3 re-attach. Not yet retried.
- **2026-11-01 10:47**: re-attach step 1: cleared U7 CONTROL1.ENABLE
  (0x1b → 0x13, read back 0x13). U7 disabled and unattached. AIN2 5.15 V,
  AIN3 0.6 mV, GPIO24/25 low, GPIO23 = 1, faults idle, GPIO26 = 0. Waiting
  for the user to unplug and replug J3.
- **2026-11-01 10:46**: the user replugged J3 (with U7 ENABLE = 0), then
  stage 5.1 was retried.
  - **Same failure:** ENABLE 0→1 but attach = 0, CC none/Ra (BC_LVL 0, no Rp
    seen), SNK_FSM 0x01, AMS success False.
  - VBUS 5.02–5.19 V (303 samples), no excursion. Chip VBUS 5.000 V.
    AIN3 ≤ 4 mV.
  - So re-attach is not the fix. VBUS without any Rp on CC points to the
    source/cable (USB-A→C, non-PD path) or CC continuity at J3/U7.3–4 after
    handling.
  - Set ENABLE back to 0, so a sudden attach cannot leave an automatic 20 V
    request standing. Stage 5.1 not passed.
- **2026-11-01 10:47**: J3 cable flipped and the correct supply connected (see
  the correction below), then stage 5.1 retried.
  **Stage 5.1 PASSED.**
  - `request_fixed(5)`: ENABLE 0→1, attach, AMS success True. Explicit
    **5 V / 3 A** contract (PD_CONTRACT 0x1, CC 3.0 A, SNK_FSM 0x06). Source
    PDOs 5/9/12/15 V @ 3 A and 20 V @ 3.2 A, not EPR.
  - VBUS sampled at about 200 Hz (714 samples, 3.55 s):
    - a dip to 0.02 V during attach/negotiation;
    - automatic-request excursion: **peak 19.61 V, above 5.6 V for 0.63 s**
      (1.835–2.460 s), then re-held to 5 V. That is within the abort-rule
      allowance (≤ 21 V, non-EPR, re-held at once).
  - AIN3 ≤ 5 mV throughout (U9 off). Final AIN2 5.11 V. GPIO24/25 low,
    GPIO23 = 1, faults idle, GPIO26 = 0, 3V3 92 mA.
  - ~~**Finding:** CC works in only one plug orientation~~ **Withdrawn
    2026-11-01 10:52** (see the correction entry below). The 10:44–10:46
    failures were caused by the wrong supply being plugged in, not by a CC
    defect.
- **2026-11-01 10:52 — correction.** The user reports the **wrong power supply
  was plugged into J3** during the 10:44–10:46 stage 5.1 attempts.
  - U7 seeing no Rp (CC none/Ra) with 5 V on VBUS was that supply, not a CC
    fault. The "CC works in one orientation only" finding is withdrawn; J3/CC
    repair is not indicated.
  - The supply attached since 10:47 was checked read-only. Fixed PDOs are
    5/9/12/15 V @ 3 A and 20 V @ 3.2 A. **SRC_PDO_PPS1–3 = 00 00 00,
    SRC_PPS_VOLTAGE = 00, SRC_PDO_AVS = 00, SOURCECAP_INFO = 00, so no PPS is
    advertised.** It matches the 2026-10-31 65 W SPR supply.
  - The user wants a PPS supply attached. **Not yet true.** Caveat: the PPS
    fields of the unofficial register map have never been seen populated, so
    confirm with the next (PPS) supply or a USB-PD tester.
- **2026-11-01 10:49**: **stage 5.2 run** (`host/stage5_2.py`, CSV
  `~/stage5_2_20261101_104922.csv` on ew-1).
  - Preconditions OK: PD 5 V contract, VBUS 5.12 V, bridge 3 mV, GPIO24 = 0,
    GPIO23 = 1, faults idle, 3V3 89 mA.
  - **GPIO25 high** (the first time ever with the board attached). The bridge
    rose to **4.88–4.90 V within 0.1 s**, matching the 4.8 V expected.
  - Steady for 7 s:
    - VBUS 5.09–5.11 V (no measurable dip);
    - EFUSE_FLT = 1, DRV_nFAULT = 1, OV trip 0, interlock 1;
    - 3V3 84–95 mA, since the bridge is powered from USB, not 3V3.
  - **Auto-abort at 7.0 s on "3V3 +35 mA".** It was a single vcgencmd sample
    of 123.9 mA, with 94.7 mA before and 85.9 mA after. The same size as the
    idle spikes seen earlier (99 and 137 mA), so it looks like a
    **false trip** on measurement noise, not a load.
  - **5.3 decay, from the abort:** the bridge fell below 2.0 V in 0.5 s,
    1.0 V in 1.0 s, 0.5 V in 1.5 s and 0.1 V in 2.9 s (τ ≈ 0.6 s; about
    0.75 s estimated from R60 × C). GPIO25 confirmed low afterwards.
  - Verdict: U9 path, D50 forward and D51 not shorting are all behaving
    correctly (no EFUSE_FLT, the bridge sits one Schottky drop below VBUS).
    The 30 s hold was not completed. The abort rule needs debouncing (median
    of 3 consecutive 3V3 samples) before a rerun.
- **2026-11-01 10:51**: **stage 5.2 rerun with the debounced 3V3 check**
  (median of 3), CSV `~/stage5_2_20261101_105101.csv`. **5.2 PASSED.**
  **5.3 PASSED.**
  - Preconditions OK (5 V contract, VBUS 5.10 V, bridge 3 mV, GPIO24 = 0,
    interlock 1, faults idle, 3V3 88 mA).
  - **GPIO25 high for 29.9 s, with no abort:**
    - bridge > 4.0 V within 0.1 s, steady **4.88–4.90 V** (300 samples at
      10 Hz);
    - VBUS 5.09–5.12 V;
    - EFUSE_FLT = 1, DRV_nFAULT = 1, OV trip 0, interlock 1 throughout;
    - 3V3 84.9–93.7 mA (no load on the Pi).
  - **5.3 decay after GPIO25 low:** below 2.0 V in 0.6 s, 1.0 V in 1.1 s,
    0.5 V in 1.6 s and **0.1 V in 3.1 s**. End: bridge 17 mV, VBUS 5.10 V.
  - GPIO25 confirmed low afterwards. Next: 5.4, interlock under power.
- **2026-11-01 10:53**: **stage 5.4 (interlock under power) PASSED**
  (`host/stage5_4.py`, CSV `~/stage5_4_20261101_105321.csv`).
  - Preconditions OK. GPIO25 high, and the bridge reached 4.90 V within
    0.1 s.
  - The user opened one lid switch at t = 0.70 s; GPIO23 → 0.
  - With **GPIO25 still high**, the bridge fell below 2.0 V in 0.6 s, 1.0 V
    in 1.1 s, 0.5 V in 1.6 s and **0.1 V in 2.8 s**, and was at 33 mV at the
    end of the 4 s hold. That matches the software turn-off decay, so K1
    dropping out opens BULK_EN and turns U9 off in hardware.
  - EFUSE_FLT = 1, DRV_nFAULT = 1, OV trip 0, VBUS 5.09–5.12 V throughout.
  - Then GPIO25 low; final bridge 7 mV. The switch is left open (GPIO23 = 0)
    pending the user reclosing it.
- **2026-11-01 10:55**: **stage 5.5** (`host/stage5_5.py`, CSV
  `~/stage5_5_20261101_105504.csv`). Preconditions OK (5 V contract,
  SRC_PDO_9V advertised 0x9e, interlock 1).
  - GPIO25 high at 5 V: bridge 4.90 V.
  - **request 9 V at t = 2.0 s → AMS True.** VBUS 8.96–8.97 V, bridge
    **8.73–8.74 V** over a 10 s hold. EFUSE_FLT/nFAULT 1, OV trip 0, 3V3
    86–91 mA. **5 → 9 V with the bridge powered: PASS.**
  - **request 5 V at t = 15.0 s → EFUSE_FLT low within 0.1 s** (VBUS 6.97 V,
    bridge 7.75 V at that sample). The script aborted: GPIO25 low, then a
    final request of 5 V (AMS True). EFUSE_FLT was back to 1 throughout the
    off phase; final PD contract 5 V, bridge 40 mV.
  - **Cause (TPS25947 datasheet, Table 7-3):** "Reverse Current
    (VOUT − VIN) > VREVTH" leads to reverse-current blocking, **not
    latched, FLT = L**. VREVTH is about −29 mV. On a downward PD step, VBUS
    falls faster than VIN_PROTECTED (C22 + C70 = 32 µF, which drains only
    through D50 → bridge → R60 10 kΩ), so U9 blocks and flags FLT until
    VOUT < VIN. It is an expected indication, not a hardware fault.
  - **Firmware implication:** EFUSE_FLT alone cannot tell an overcurrent or
    thermal fault from RCB during a voltage step-down. Either drop GPIO25
    before lowering the PD voltage, or treat FLT as RCB only while the
    bridge is above the new VBUS and only for a bounded time (≤ 3 s, about
    5 × τ of the R60 bleed).
- **2026-11-01 10:57**: **stage 5.5 rerun with option (a)** (GPIO25 low before
  the step-down; `host/stage5_5.py`, CSV `~/stage5_5a_20261101_105701.csv`).
  **PASSED. Stage 5 complete** (5.0 inspection skipped by the user).
  - 5 V on: bridge 4.90 V.
  - request 9 V (AMS True). Hold 10 s: VBUS 8.96–8.97 V, bridge
    8.73–8.74 V.
  - GPIO25 low at 15.01 s, request 5 V at 15.31 s (AMS True). The bridge
    fell 8.70 → 1.20 V by 16.31 s.
  - GPIO25 high again at 16.41 s, once the bridge was below VBUS − 0.5 V. The
    bridge returned to 4.88–4.91 V at VBUS 5.09–5.12 V for 3 s.
  - GPIO25 low at 19.41 s; bridge 30 mV at the end.
  - **EFUSE_FLT = 1, DRV_nFAULT = 1, OV trip 0, interlock 1 in every phase.**
    3V3 85–93 mA. Final PD contract 5 V.
  - **Firmware rule adopted:** always drop GPIO25 (BULK_CMD) before
    requesting a lower PD voltage. Re-enable only once the bridge is below
    the new VBUS − 0.5 V. With that rule, any EFUSE_FLT is a real fault.
- **2026-11-01 11:04**: powered down at the user's request.
  - State before shutdown: GPIO24/25 already low (forced low again),
    GPIO23 = 0 (lid open), VBUS 5.10 V, bridge 0.6 mV.
  - U7 CONTROL1 0x1b → 0x13 (ENABLE cleared), so it comes back disabled.
  - `systemctl poweroff`; ew-1 stopped answering ping within 15 s.
    POWER_OFF_ON_HALT=1 removes 3V3 from the board.
  - J3 may still be plugged in: VBUS stays on the input side, but U9 and
    downstream are off.
  - Stage 6 plan rev 2 drafted ([STAGE6_PLAN.md](STAGE6_PLAN.md)), awaiting
    approval.
- **2026-11-01 11:10**: stage 6 plan **rev 3 (option 1, user decision)**.
  - The injected OV-trip test is impractical (no clip point on HV_SENSE_RAW,
    no adjustable supply), so stage 6 is reduced to 6.A′/6.B/6.C1/6.C3.
  - **The hardware OV trip stays unverified**, including D90 latch and D91
    clear (both hand-re-fitted) and Q2.
  - Stage 7 limits: 5 V contract only, software cutoff AIN0 > 0.50 V
    (≈ 3 kV), short bursts, lid closed. Recorded in AUDIT.md.
  - Script: `host/stage6.py` (subcommands a, b, c1, c3).
- **2026-11-01 11:47–11:48**: ew-1 powered on again.
  - U7 came up disabled. `request 5 --arm --max 5` gave AMS True and a
    5 V / 3 A contract; AIN2 5.12 V, bridge 0.6 mV.
  - `stage6.py`/`husb238a.py` deployed (md5 matches the repo).
- **2026-11-01 11:48**: **6.A′ PASSED** (`stage6.py a`, CSV
  `~/stage6_a_20261101_114826.csv`). Lid open, which is allowed for 6.A′:
  D91's cathode is on DRV_SLEEP_CMD ahead of K1.
  - GPIO24 high for 5.0 s with the bridge off (GPIO25 low): **GPIO26 = 0 in
    all 79 samples**, so no false OV trip and D91 is not reversed.
  - AIN0 ≤ 1 mV, nFAULT 1, EFUSE_FLT 1, GPIO18/19 0, VBUS 5.09–5.12 V,
    bridge ≤ 4 mV.
  - GPIO24 low afterwards; safe-stop order logged (GPIO24 → PWM → GPIO25
    within 1.6 ms).
  - 6.B/6.C need the lid closed: GPIO23 = 0 at 11:48.
- **2026-11-01 12:15**: **6.B PASSED** (`stage6.py b`, CSV
  `~/stage6_b_20261101_121506.csv`). Lid closed (GPIO23 = 1).
  - request 9 V gave AMS True (VBUS 8.96–8.97 V). GPIO25 high gave a bridge
    of 8.74 V.
  - **GPIO24 high, driver awake with IN1 = IN2 = 0, for 30.0 s (469
    samples):**
    - nFAULT 1, EFUSE_FLT 1, OV trip 0, interlock 1;
    - **AIN0 ≤ 1 mV, so no drive and no HV**;
    - GPIO18/19 0;
    - bridge 8.701–8.708 V, about 30 mV below the asleep 8.74 V, which is
      consistent with the DRV8876 charge pump/quiescent current.
  - Safe-stop GPIO24 → PWM → GPIO25 within 1.6 ms. Bridge decayed to
    74 mV in 4 s. Then request 5 V (AMS True); VBUS 5.10–5.12 V, bridge
    22–33 mV.
- **2026-11-01 12:16**: **6.C3 PASSED** (`stage6.py c3`, CSV
  `~/stage6_c3_20261101_121552.csv`).
  - Driver awake at 9 V for 3 s: bridge 8.702–8.707 V, nFAULT 1, AIN0 ≤ 1 mV.
  - The **software safe-stop** ran in order: GPIO24 low (0 ms) → PWM
    disabled/normal (0.05 ms) → GPIO25 low (1.6 ms).
  - Bridge 8.70 → 0.066 V in 4 s. Back to 5 V (AMS True). All flags idle
    throughout.
  - Remaining: **6.C1** (the user opens a lid switch with the driver awake).
- **2026-11-01 12:17**: **6.C1 PASSED. Stage 6 (reduced) complete.**
  (`stage6.py c1`, CSV `~/stage6_c1_20261101_121638.csv`.)
  - 9 V contract. GPIO25 high gave a bridge of 8.74 V. GPIO24 high, driver
    awake, bridge 8.70 V.
  - The user opened one lid switch at t = 20.6 s, with **GPIO24 and GPIO25
    still high**. The hardware cut (K1 drops: R5 pulls DRV_nSLEEP low and
    BULK_EN opens) took the bridge below 4.0 V in 0.45 s, 1.0 V in 1.41 s
    and **0.1 V in 3.53 s**.
  - nFAULT 1, EFUSE_FLT 1, OV trip 0, AIN0 ≤ 1 mV throughout. No DRV8876
    UVLO fault was reported, because it was already asleep.
  - Safe-stop GPIO24 → PWM → GPIO25 within 1.6 ms. request 5 V gave AMS True
    with GPIO25 low. The user reclosed the switch afterwards (GPIO23 = 1).
  - **Stage 6 summary:**
    - D91 not reversed;
    - the driver wakes with VM present and stays idle at IN1 = IN2 = 0;
    - lid opening and the software safe-stop both sleep the driver and cut
      the bridge.
  - **Not verified:** the hardware OV trip / D90 latch / Q2 (option 1, see
    AUDIT.md). Stage 7 limits apply: 5 V contract, AIN0 > 0.50 V cutoff,
    short bursts, lid closed.
- **2026-11-01 12:20**: stage 7 plan **rev 2 approved** by the user.
  - J60 insulated and > 10 mm clear. **No grounding stick**, so discharge is
    ≥ 5 min wait + AIN0 < 0.01 V, and no hands in the HV section. Lid assumed
    on. 2 kV initial limit.
  - Script `host/stage7.py` (dry / burst / sweep / decay). Single-ended drive
    only (IN1 PWM ch2 50%, IN2 = 0, no inverted channel); f 20–50 kHz with
    sysfs readback; AIN0 abort 0.50 V, target 0.33 V; ≤ 1 s bursts,
    ≥ 10 s gaps.
- **2026-11-01 12:24**: **7.1 dry PWM check PASSED** (CSVs
  `~/stage7_dry_20261101_122422.csv`, `..._122425.csv`). Lid open, which is
  allowed for dry. Driver asleep (GPIO24 low), bridge off (GPIO25 low).
  - **20 kHz** and **50 kHz**: PWM ch2 configured, readback OK (period
    50000/20000 ns, 50%, normal).
  - Enabled for 1.0 s each. GPIO18 sampled high 17/29 and 16/29 times, so
    it is toggling.
  - AIN0 ≤ 0.8 mV (no HV with the driver asleep), AIN1 ≤ 2.1 mV, nFAULT 1,
    EFUSE_FLT 1, OV trip 0, VBUS 5.09–5.12 V, bridge ≤ 4 mV.
  - AIN0 sampled at ~205 Hz.
  - Safe-stop order held every time. Afterwards GPIO18/19 a3 low, pwm2
    disabled/normal, pwm3 never exported, GPIO24/25 low.
- **2026-11-01 12:25**: **7.2 PASSED: FIRST HV GENERATED.** (`stage7.py burst
  20000 1.0`, CSV `~/stage7_burst_20261101_122525.csv`; analysis with
  `host/stage7_analyze.py`.)
  - Lid closed (GPIO23 = 1), 5 V contract, bridge 4.90 V. GPIO24 high, then
    PWM ch2 at 20 kHz, 50%, single-ended, for 1.0 s.
  - **AIN0 rose 2.4 mV @ 18 ms → 7.3 mV @ 0.1 s → peak 8.5 mV (≈ 52 V HV_OUT
    nominal)**, with a plateau of about 8.2 mV.
  - Bridge sagged 4.90 → 4.83 V during drive. VBUS 5.09–5.11 V. AIN1
    ≤ 2.1 mV (offset only, no return current). nFAULT 1, EFUSE_FLT 1, OV
    trip 0.
  - **Discharge:** AIN0 fell below 0.5 mV within 0.5 s of the safe-stop
    (fit τ ≈ 0.2 s), and stayed near 0 for 15 s.
  - **Measured gain is about one third of the ideal lossless estimate**
    (≈ 150 V at 20 kHz single-ended). AIN0 is still uncalibrated.
  - Post: GPIO18/19/24/25 low, GPIO26 = 0.
- **2026-11-01 12:27**: **7.3 sweep completed, no abort** (`stage7.py sweep
  25000,…,50000`, CSV `~/stage7_sweep_20261101_122655.csv`). Single-ended,
  5 V bridge, 1 s bursts, 10 s gaps.

  | f (kHz) | 20 (7.2) | 25 | 30 | 35 | 40 | 45 | 50 |
  |---|---|---|---|---|---|---|---|
  | AIN0 plateau (mV) | 8.2 | 23.1 | **26.9** | 13.6 | 12.4 | 1.5 | 0.3 |
  | ≈ HV_OUT (V, nominal) | 50 | 141 | **164** | 83 | 76 | 9 | 2 |

  - Bridge 4.83 V under drive at every frequency (≈ 70 mV sag). AIN1 is
    offset only, nFAULT/EFUSE_FLT 1, OV trip 0. Every step discharged before
    the next.
  - **Finding:** the response **peaks near 30 kHz and falls toward 50 kHz**.
    That is the opposite of the C11 + L_pri (69 kHz) model, which predicted
    a steep rise toward 69 kHz. The real tank resonance is much lower,
    plausibly because the multiplier's input capacitance reflected through
    1:50 (×2500) dominates. The 68 kHz design drive point would give almost
    no output.
  - Peak ≈ 165 V at 5 V single-ended, far below the 2 kV target.
  - Script note: the end-of-sweep "decay" report uses the last t_stop
    against all decay rows (cosmetic bug); the per-step data is correct.
- **2026-11-01 12:30–12:33**: **7.3b fine sweep completed, no abort** (CSV
  `~/stage7_sweep_20261101_123015.csv`). Same conditions as 7.3, 1 kHz
  steps.

  | f (kHz) | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31 | **32** | 33 | 34 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | AIN0 peak (mV) | 4.1 | 6.0 | 14.6 | 24.6 | 28.4 | 20.6 | 21.4 | 23.9 | 28.4 | 28.6 | **33.6** | 31.4 | 21.4 |
  | ≈ HV_OUT (V) | 25 | 37 | 89 | 150 | 173 | 126 | 131 | 146 | 173 | 174 | **205** | 191 | 131 |

  - **Two maxima: ≈ 26 kHz and ≈ 32 kHz (best, ≈ 205 V), with a dip at
    27–28 kHz.** 25 and 30 kHz reproduce the 7.3 values to within 1 mV.
  - Bridge 4.83 V under drive; AIN1 offset only; nFAULT/EFUSE_FLT 1; OV trip
    0; all post-states low.
  - The twin peaks suggest two coupled resonances: C11 with the leakage
    inductance and the reflected multiplier capacitance, or a
    single-ended/coast artefact. Characterize further with complementary
    drive (7.4) or a scope on DRV_A/DRV_B.
- **2026-11-01 12:36**: **7.4 complementary drive PASSED** (approved by the
  user; `stage7.py comp 32000 1.0`, CSV `~/stage7_comp_20261101_123545.csv`).
  - Safety fix before the run: ch3 is kept **normal and disabled (pin low)**
    until IN1 is already toggling, then switched to `inversed` and enabled
    with readback. A disabled `inversed` channel idles HIGH, which would have
    put a static reverse-drive step on IN2 with the driver awake.
  - 32 kHz, IN1 = ch2 normal 50%, IN2 = ch3 inversed 50%, 1.0 s, 5 V
    bridge. **AIN0 peak 58.6 mV (≈ 357 V)**, end 56.0 mV: **1.74× the
    single-ended 33.6 mV** at the same frequency.
  - Bridge 4.833–4.844 V. AIN1 ≤ 2.4 mV. nFAULT/EFUSE_FLT 1, OV trip 0.
  - Discharge: below 305 V in 0.03 s and **below 61 V in 0.28 s**.
  - Post-stop check: ch3 enable 0, polarity normal; GPIO18/19 = 0;
    GPIO24/25 low; GPIO26 0.
  - **Best so far ≈ 0.36 kV at the 5 V bridge**, about 1/37 of the 13 kV
    design target. More output needs a higher bridge voltage, which stays
    blocked by option 1 until the hardware OV trip is verified.
- **2026-11-01 12:50**: wrote [GAIN_SHORTFALL.md](GAIN_SHORTFALL.md), a
  findings note on the 0.36 kV best case vs the 13.3 kV model.
  - The response peaks at 26/32 kHz, not at the 68 kHz design point.
  - H1/H2: secondary capacitance reflected ×2500 dominates the tank.
  - H3: 2CL75 VF ≤ 43 V threshold.
  - Next: scope/IPROPI measurements, a sweep below 20 kHz, and a re-model.
  - Bring-up CSVs from stages 5–7 copied to `host/data/`.
- **2026-11-01 12:51 — ⚠️ HV EXCEEDED THE APPROVED 2 kV LIMIT (two aborts, no
  damage observed).** Option A, user-confirmed 9 V override.
  `stage7.py comp 32000 1.0` (5 V reference) then `--vbus 9`. CSVs
  `data/stage7_comp_20261101_125126.csv`,
  `data/stage7_comp_9V_20261101_125144.csv`.
  - **5 V reference** (identical settings to the 12:36 run, which gave
    58.6 mV ≈ 0.36 kV):
    - AIN0 ramped 5 → 482 mV in 91 ms (≈ 2.9 kV);
    - **aborted at 175 ms on AIN0 0.5005 V (≈ 3.05 kV)**;
    - AIN1 peak 14.9 mV (≈ 1.5 µA) at the start; bridge dipped to 4.78 V.
  - **9 V** (request 9 V AMS True, VBUS 8.97 V, bridge 8.74 V):
    - AIN0 ramped at about 25 mV/ms (≈ 0.16 kV/ms);
    - **aborted at 23 ms on AIN0 0.531 V (≈ 3.24 kV)**;
    - **AIN0 kept rising after the safe-stop, to 0.716 V (≈ 4.37 kV) at
      +57 ms**. That is the 164 kΩ·C13 ≈ 16 ms sense-filter lag. The true
      HV_OUT at stop was **≥ 4.4 kV and possibly ~5–6 kV** (lag ≈ slope × τ);
    - AIN1 peak 25.6 mV (≈ 2.6 µA).
  - Both runs: nFAULT 1, EFUSE_FLT 1, OV trip 0 (hardware trip at 16.96 kV
    not reached). Safe-stop OK; post-stop ch3 normal/disabled, GPIO18/19 = 0.
    The 9 V run returned to 5 V (AMS True). HV decayed 4.37 → 1.13 kV in
    0.36 s, and AIN0 was 1.3 mV at +2 s.
  - **Findings:**
    1. **Complementary output is not repeatable.** At 5 V, 32 kHz, the same
       settings gave 0.36 kV at 12:36 and ≥ 3 kV at 12:51. Most likely
       cause: RP1 PWM ch2/ch3 are enabled separately, so the **phase between
       IN1 and IN2 is uncontrolled run to run**. Misaligned phase gives
       brake/coast overlap and much lower drive.
    2. **The software cutoff cannot hold a kV limit against fast ramps.**
       With the 16 ms sense filter, a 0.16 kV/ms ramp overshoots by about
       2.5 kV.
    3. **GAIN_SHORTFALL.md conclusions are invalidated.** Properly phased
       complementary drive at 5 V reaches ≥ 3 kV.
  - **Stopped. No further drive** until the drive phase is controlled and
    the overshoot is addressed: soft-start duty ramp, short bursts,
    predictive cutoff, hardware OV trip verified. Board idle: 5 V contract,
    GPIO18/19/24/25 low, AIN0 0.4 mV at 12:53.
- **2026-11-01 12:58–13:01**: user raised the HV limit to **6 kV** and asked for a slower
  ramp. Wrote `host/stage7_ramp.py`:
  - IN1 = ch2 normal at D·T, IN2 = ch3 inversed at (1−D)·T;
  - duty steps +0.005 every 20 ms, only while the HV slope is < 20 V/ms;
  - predictive abort at AIN0 or AIN0 + slope × 16 ms ≥ 0.984 V (6.0 kV);
  - target/hold, and every stage7.py abort.
- **12:58 phase diagnostic** (driver asleep; `host/pwm_phase_diag.py`):
  - at **1 kHz**, ch3 normal is in phase (IN1 ≠ IN2 4–5%) and ch3 inversed is
    complementary (97%);
  - at **32 kHz** both read random (34–63%). The ch2/ch3 phase is set by the
    ~5–15 µs gap between the sysfs enable writes, so it's random from run to
    run. That explains 0.36 kV (12:36) vs ≥ 3 kV (12:51).
  - The retry-align approach failed (30/30 tries ≤ 8%), so alignment is now
    advisory. The slew-limited ramp is gain-agnostic.
- **2026-11-01 13:00**: **slow ramp at a 5 V bridge, 32 kHz: PASSED, no
  abort.** CSV `data/stage7_ramp_ramp_5V_20261101_130025.csv`.
  - Duty 0.02 → **0.27** over 1.18 s; **5.0 kV target reached**, then held
    0.5 s at a fixed duty.
  - **Peak 5.31 kV** (AIN0 0.871 V): it crept 0.31 kV above target during
    the hold.
  - **Max slope 0.021 kV/ms**, against 0.16 kV/ms in the 12:51 step start.
    Post-stop readout max 5.26 kV, so **no lag overshoot**; the predictive
    6 kV abort was not needed.
  - Bridge min 4.77 V. AIN1 ≤ 2.4 mV. nFAULT/EFUSE_FLT 1, OV trip 0. HV
    decayed to 9 V-equivalent (1.5 mV) within 5 s.
  - **Milestones:** 1 kV at +54 ms (duty 0.03), 2 kV at +104 ms (0.04),
    3 kV at +152 ms (0.05), 4 kV at +231 ms (0.065), 5 kV at +1.18 s (0.27).
    The gain is high at small duty: the first ~4 kV ran at the 17–21 V/ms
    slew limit right from the D0 = 0.02 start. Use a lower D0 / smaller step
    next.
  - **Next:** make the hold regulate (back the duty off above target), fix
    the phase (one RP1 register write for both enables, or PIO), and only
    then consider 9 V.
- **2026-11-01 13:01–13:05**: **IN1/IN2 phase fixed; ramp control refined; 9 V
  ramp done.**
  - **Phase:** a single-read measurement (SYS_RIO0 +0x08, bits 18/19)
    showed the ch2/ch3 phase random per enable: 2.5–98% complementary over
    16 trials (`host/rp1_pwm_phase_test.py`).
  - The earlier `pinctrl` 32 kHz readings were sampling artefacts.
  - Fix, `host/rp1_pwm_sync.py` (root): clear and re-set both enable bits
    in **one GLOBAL_CTRL write with SET_UPDATE (bit 31)**. Gave **8/8
    trials 100% complementary**; without bit 31, no effect. It refuses
    unless GPIO24/25 are low and ch2/ch3 are configured as expected, and
    verifies ≥ 99%.
  - Register map verified: GLOBAL_CTRL 0x000; CHANn CTRL / RANGE / PHASE /
    DUTY at 0x14 / 18 / 1c / 20 + 0x10n; 50 MHz clock.
  - `stage7_ramp.py`: sync before the driver wakes (refuses on failure);
    D0 0.005, step 0.0025; the hold regulates (duty down above target, up
    below target − 0.1 kV).
- **13:04 5 V ramp, phase-synced** (`data/stage7_ramp_ramp_5V_20261101_130400.csv`):
  - 1 kV +282 ms (D 0.0350); 2 kV +353 ms (D 0.0425); 3 kV +426 ms (D 0.0500); 4 kV +519 ms (D 0.0600); 5 kV +691 ms (D 0.0775);
  - hold 4.83–5.13 kV (duty regulated 0.078 → 0.0575);
  - **peak 5.13 kV**, max slope 0.015 kV/ms;
  - bridge min 4.78 V, no faults. **PASS.**
- **13:04:47 9 V ramp, phase-synced** (user-approved 9 V, 6 kV limit;
  `data/stage7_ramp_ramp_9V_20261101_130447.csv`):
  - 1 kV +237 ms (D 0.0300); 2 kV +288 ms (D 0.0325); 3 kV +347 ms (D 0.0350); 4 kV +398 ms (D 0.0400); 5 kV +457 ms (D 0.0425);
  - hold 4.22–5.69 kV (duty 0.043 → 0.0325);
  - **peak 5.69 kV** (0.31 kV under the 6 kV abort), max slope 0.022 kV/ms;
  - bridge min 8.65 V, AIN1 ≤ 5.6 mV, no faults;
  - returned to 5 V (AMS True). **PASS, but small margin:** each 0.0025 duty
    step is worth more kV at 9 V. Next: a smaller step or slew limit at 9 V,
    or a lower target.
- **2026-11-01 13:07**: **hold loop tuned; 9 V ramp re-run: PASS** (`data/stage7_ramp_ramp_9V_20261101_130659.csv`).
  - Tuning:
    - duty step and slew limit per bridge voltage (9 V: 0.001 and 10 V/ms;
      5 V: 0.0025 and 20 V/ms);
    - target entry and hold regulation both use the **predicted** value
      (AIN0 + slope × 16 ms);
    - the hold corrects every 50 ms.
  - Results:
    - 5 kV (predicted) at duty 0.039, 0.93 s after wake;
    - hold 2.0 s over 4.78–5.31 kV; after the first
      0.5 s, 4.78–5.02 kV (mean 4.93,
      σ 0.051 kV);
    - **peak 5.31 kV** (was 5.69), max slope 0.012 kV/ms;
    - bridge min 8.65 V, AIN1 ≤ 4.7 mV, no faults; returned to 5 V.
  - The hold no longer limit-cycles (was 4.22–5.69 kV).
- **2026-11-01 13:09–13:13**: **phase-synced frequency recheck**, 5 V bridge,
  ramp to a 3 kV target (predicted), hold 0.3 s, 22–36 kHz in 1 kHz steps,
  10 s apart (`data/stage7_ramp_ramp_5V_20261101_1309*–1313*.csv`).
  Phase sync verified 100% every run. No aborts, no faults; bridge min
  4.78 V; AIN1 ≤ 3.1 mV.

  | f (kHz) | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31 | 32 | 33 | 34 | 35 | 36 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | duty at 3 kV | .0400 | .0400 | **.0375** | .0400 | .0425 | .0450 | .0450 | .0425 | .0425 | .0450 | .0475 | .0500 | .0525 | .0525 | .0500 |
  | peak (kV) | 3.53 | 3.47 | 3.54 | 3.85 | 3.46 | 3.38 | 3.45 | 3.46 | 3.66 | 3.72 | 3.49 | 3.29 | 3.30 | 3.26 | 3.33 |

  - **No distinct 26 kHz (or 32 kHz) peak.** With synced complementary
    drive, the duty needed for 3 kV is nearly flat across 22–36 kHz:
    0.0375–0.0525, a 1.4× spread. It is lowest at 22–25 kHz and rises
    slowly with frequency. The step is 0.0025, so the resolution is ±6%.
  - The 26/32 kHz twin peaks in the 7.3 / 7.3b / 7.4 data came from
    different drives: single-ended at 50% duty, and complementary with
    random phase. They don't describe the synced narrow-pulse drive used
    now. At ~4% duty each half-cycle is a short pulse that excites the tank
    broadly, so the gain depends only weakly on the repetition rate.
  - **5 V loop overshoot:** 0.26–0.85 kV over a 3 kV target with the 5 V
    tuning (step 0.0025, 20 V/ms). Use the 9 V-style tuning (0.001 /
    10 V/ms) at 5 V as well.
- **2026-11-01 13:17–13:22**: **phase-synced sweep 36–100 kHz** at a 5 V bridge
  (user request).
  - 3 kV target, hold 0.3 s, duty cap 0.25. Finer 5 V tuning (step 0.001,
    10 V/ms). `F_MAX` raised to 100 kHz (DRV8876 fPWM max).
  - All 14 runs completed: phase sync 100%, no aborts, no faults. Bridge
    min 4.77 V; AIN1 ≤ 4.0 mV.

  | f (kHz) | 36 | 40 | 45 | 50 | 55 | 60 | 65 | 70 | 75 | 80 | 85 | 90 | 95 | 100 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | duty at 3 kV | 0.045 | 0.049 | 0.060 | 0.057 | 0.063 | 0.069 | 0.074 | 0.086 | 0.078 | 0.083 | 0.089 | 0.095 | 0.103 | 0.107 |
  | pulse width D·T (µs) | 1.25 | 1.22 | 1.33 | 1.14 | 1.15 | 1.15 | 1.14 | 1.23 | 1.04 | 1.04 | 1.05 | 1.06 | 1.08 | 1.07 |
  | peak (kV) | 3.16 | 3.38 | 3.14 | 3.20 | 3.19 | 3.14 | 3.10 | 3.04 | 3.08 | 3.13 | 3.14 | 3.15 | 3.23 | 3.09 |

  - The required duty rises steadily from 0.045 (36 kHz) to 0.107
    (100 kHz), but the **pulse width per half-cycle stays nearly constant
    at ≈ 1.1–1.25 µs**. In the 22–36 kHz sweep it was ≈ 1.5–1.8 µs, with
    the coarser step.
  - So the HV is set mainly by **energy per pulse**, not by repetition
    rate: each narrow pulse rings the C11/T1/CW network, and the multiplier
    charges toward the peak of that ringing.
  - The frequency choice is free across 22–100 kHz as far as kV goes.
    Lower frequencies need less duty and switch less often, so they should
    have lower DRV8876 switching loss (eq. 12/13). Not measured: there is
    no input-current measurement.
  - At 100 kHz the pulse (≈ 1.07 µs) is close to the DRV8876 tPD (650 ns)
    + tDEAD (300 ns). Don't go higher.
  - The finer 5 V tuning cut the overshoot to ≤ 0.38 kV (peaks
    3.04–3.38 kV), from up to 0.85 kV.
- **2026-11-01 13:27–13:31 — OV-trip attempt at 17 kV by the forked session**
  (user-directed; this session stood down meanwhile; the user then told the
  fork to stand down).
  - Script `host/ov_trip_test.py` (imports the `stage7_ramp.py` helpers
    unchanged), CSV `data/ov_trip_test_9V_20261101_132910.csv`.
  - Settings: 9 V contract, 32 kHz, phase-synced 100%, slew 10 V/ms,
    firmware backstop 18.5 kV, duty swept up to 0.5.
  - **Result: 17 kV not reached. The hardware OV trip was not exercised
    (GPIO26 = 0 throughout). It stays UNVERIFIED.**
  - **New highest HV on this board: ≈ 12.5 kV** (AIN0 2.050 V, nominal
    scale) at duty ≈ 0.155–0.16. The previous maximum was 5.7 kV.
  - **HV vs duty is non-monotonic** (max per 0.01 duty bin, from the CSV):

    | duty | 0.03 | 0.04 | 0.06 | 0.07–0.12 | **0.16** | 0.20 | 0.24 | **0.30** | 0.38–0.50 |
    |---|---|---|---|---|---|---|---|---|---|
    | kV | 3.4 | 5.9 | 9.0 | ≈ 9.3–9.5 plateau | **12.5** | 11.8 | 9.1 | **11.1** | ≈ 6.7–7.0 |

  - The maxima fall at pulse widths ≈ 5.0 µs (D 0.16) and ≈ 9.4 µs (D 0.30)
    at 32 kHz. That spacing of ≈ 4.4 µs suggests ringing near ~230 kHz,
    which fits C11 (120 nF) with ~4 µH of T1 leakage inductance.
    **Hypothesis:** the pulse that ends in phase with that ringing transfers
    the most energy. Not measured; a scope on DRV_A/DRV_B would confirm.
  - **AIN1 rose to 70.6 mV (≈ 7 µA return current) near the 12.5 kV peak**,
    against ≈ 0.5 µA at 5 kV. That is the first sign of leakage/corona at
    the HV output or on the board, close to the 10 µA firmware abort.
  - Bridge 8.61–8.70 V; nFAULT and EFUSE_FLT 1 throughout. The safe-stop
    and the return to 5 V were clean.
  - End state, checked by this session at 13:31:24: GPIO18/19/24/25 = 0,
    GPIO26 = 0, GPIO23 = 1, pwm2/3 disabled and normal, 5 V contract, AIN0
    ≈ 0, AIN1 offset.
  - ew-1 `stage7_ramp.py` / `rp1_pwm_sync.py` / `husb238a.py` unchanged
    (md5 = repo `aaae859`).
  - **Implications:**
    - with this drive, HV peaks at ≈ 12.5 kV at a 9 V bridge;
    - beyond D ≈ 0.16 more duty gives *less* HV;
    - reaching the 16.96 kV trip would need a higher bridge voltage (12/15 V
      contract, beyond the approved 9 V), on insulation that already shows
      ≈ 7 µA at 12.5 kV.
    - The trip remains best tested with a temporarily lowered threshold
      (15 kΩ across R103 → ≈ 3.9 kV) or a fly-lead injection.
- **2026-11-01 13:37 — first corona run: 10 s into a bare ≈ 10 mm gap at J60.**
  - User request: leads ≈ 10 mm apart, not insulated; "10 kV for 10 s".
  - CSV `data/stage7_ramp_ramp_9V_20261101_133747.csv`.
  - Settings: 9 V contract, 32 kHz, phase-synced 100%, target 10 kV,
    predictive abort 11 kV, **duty capped at 0.17** (rising side of the
    non-monotonic curve).
  - **AIN1 abort raised to 0.5 V (50 µA)** for corona; the 100 MΩ ballast
    limits output current to ≈ 100 µA even into a spark. The lid interlock
    was checked closed before the run.
  - **Result:** 10 kV was *not* reached. The ramp hit the 0.17 duty cap and
    held **10.0 s at max duty**: HV_OUT **9.46 kV mean** (9.29–9.57, σ 0.05),
    peak 9.65 kV. No abort, no faults, bridge 8.60–8.61 V.
  - **Corona current (AIN1/R90): 24.2 µA mean (23.6–24.9, σ 0.2), very
    steady**, rising slightly 9.38 → 9.50 kV over the 10 s.
  - **Onset:** 0.3 µA at 2–4 kV, 0.5 µA at 6 kV (duty 0.046), 13.8 µA at
    8 kV (duty 0.126), 22.7 µA at 9 kV (duty 0.142). Corona starts between
    6 and 8 kV for this gap.
  - The load shifts the duty curve: unloaded, 9 kV needed duty ≈ 0.06.
  - Estimated ballast drop 24 µA × 100 MΩ ≈ 2.4 kV, so the multiplier
    output is ≈ 11.9 kV. Gap power ≈ 9.46 kV × 24 µA ≈ 0.23 W.
  - Safe-stop and the return to 5 V were clean. AIN0 decayed to 12 mV within
    5 s. Post: GPIO18/19/24/25/26 = 0, AIN1 offset.
  - Script: `--ain1-max` option added; the banner now prints the active
    abort level (it showed the 6 kV constant while the 11 kV abort was the
    one in effect).
- **2026-11-01 13:52–14:06 — HV dashboard deployed (no HV).**
  - [dashboard/README.md](dashboard/README.md); runs from `~/dashboard/` on ew-1, port 8080
    (camera helper 8081). Token in `~/.ew1-dashboard-token`. Run data in `~/dashboard_runs/`.
  - `stage7_ramp.py` refactored: `main()` → `run()` plus a thin CLI. It adds the optional
    `on_sample` / `stop` hooks and a shared HV-owner flock (`/run/lock/ew1-hv.lock`). With no
    hooks the behaviour is unchanged. The old ew-1 copy is kept as `~/stage7_ramp.py.orig-5aaeea89`.
  - Verified without HV:
    - SSE values match `ew1_selftest.py`;
    - auth: control endpoints return 401 without the token;
    - every out-of-limit parameter returns 400;
    - preconditions: start() refuses (412/409) with `run()` stubbed;
    - the monitor pauses whenever the HV lock is held (CLI or dashboard);
    - the CLI refuses while the lock is held;
    - dry phase-sync through the dashboard: 100% complementary;
    - the safe-stop paths: button, SIGTERM, SIGKILL→dead-man child, startup.
  - TSL2591 absent; no camera detected (ffmpeg / rpicam-apps / v4l2-ctl / picamera2 present).
  - End state 14:06: GPIO18/19/24/25 = 0, pwm2/3 disabled + normal, 5 V contract, AIN0 ≈ 0.
    Dashboard left running (started with `setsid nohup`, not as a service).
  - **Not yet exercised:**
    - an HV ramp from the dashboard, including the live run graphs;
    - heartbeat/watchdog aborts mid-run;
    - SAFE STOP mid-run;
    - the 9 V round-trip;
    - camera auto-record.
- **2026-11-01 14:37**: dashboard limits changed at the user's request
  ("allow up to 10 kV").
  - `target_kv` max is now **10.0** (was 10.5). `abort_kv` max stays
    **11.0**.
  - **`max_duty` max raised 0.17 → 0.25**, so a corona-loaded gap can reach
    10 kV. At 13:37 the 0.17 cap held a 10 mm gap at 9.46 kV / 24 µA.
    Raising it cannot cause overvoltage: HV vs duty is non-monotonic
    (unloaded peak ≈ 0.16), so past the peak more duty gives *less* HV,
    and the predictive 11 kV abort is unchanged.
  - Default `max_duty` left at 0.17.
  - Deployed and restarted 14:37:54 (safe-stop on stop and start). Served
    `/api/limits` shows the new caps. Target 10.5 and duty 0.26 are
    rejected with 400. Unit tests updated and passing.
