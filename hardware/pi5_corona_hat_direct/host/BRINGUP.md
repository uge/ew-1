# HV board bring-up log — ew-1

Summary for the next person: [HANDOFF.md](HANDOFF.md).

This is the living record of bring-up on the bench. **Update it after every
step:** change the snapshot, tick the stage, and append to the log. Host setup
commands are in [RUNBOOK.md](RUNBOOK.md). Release status is in [AUDIT.md](../AUDIT.md).

## Current state — 2026-11-01 10:36 PST

**Stage reached: 4 of 7. Stages 0–4 all pass.** Stage 3 (interlock) passed
2026-11-01 10:35, after D3/D90/D91 were re-fitted. The lid switches are taped
closed, so K1 is energized. Through K1, GPIO24/25 now reach DRV_nSLEEP and
BULK_EN, but both are held low. The U7 PD contract was reset by the
2026-10-31 power-down: U7 is at ENABLE = 0, unattached, default 5 V.
GPIO18/19/24/25 have never been driven high with the board attached.

| Item | State |
|---|---|
| Host | Pi 5 ew-1, serial `9b8f9676cf6e79ad`, wlan0 192.168.0.130 (eth0 unplugged) |
| Image | Reloaded 2026-10-31 ~17:18. Passwordless sudo. `ew1_host_setup.sh` re-run 17:24 |
| Board | N-layout-17-hv-warnings on J2. **D3, D90, D91 re-fitted by hand** (all three were placed reversed) |
| J3 USB-C | **Connected** to a 65 W SPR PD supply (5/9/12/15 V @ 3 A, 20 V @ 3.2 A, not EPR). AIN2 ≈ 5.1 V. U7 ENABLE = 0, no contract |
| Lid chain S3–S6 | **Closed (taped)**. GPIO23 = 1, K1 energized (3V3 ≈ 85–90 mA) |
| Illumination mini board (TSL2591, 0x29) | Disconnected |
| HV output J60/J61 | Unchanged since attach |
| Pi outputs | GPIO18/19 PWM idle low. GPIO24/25 driven low |
| Faults | DRV_nFAULT = 1, EFUSE_FLT = 1, HV_OV_TRIP = 0 |

**Next action, before stage 5:**
1. Inspect the polarized parts that have no CPL rotation entry: D51, D50, D5,
   D1/D4, C60/C70 (see AUDIT.md). D51 or D50 reversed would show up at stage 5.
2. Write the stage 5–7 bench plan, including the injected OV-trip test (D90
   latch, D91 clear).
3. Re-establish an explicit 5 V contract
   (`husb238a.py request 5 --arm --max 5`) before any GPIO25 test.

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
