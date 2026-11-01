# HUSB238A (U7) register map and driver notes

Driver: [`husb238a.py`](husb238a.py). Bench status: [BRINGUP.md](BRINGUP.md) stage 4.

## Provenance and confidence

**Hynetek has not published a register map for the HUSB238A.** The datasheet in
`procurement/HUSB238A_datasheet.pdf` (Rev 1.2, 09/2025) and the LCSC copies of
Rev 0.7 and Rev 1.1 only name `SRC_PDO_5V…20V`, `SRC_PDO` and `GO_COMMAND`. They
give no addresses or bit fields. Hynetek's register document (Rev 1.1, 01/2021)
covers the older **HUSB238**, a different map (0x00–0x09 at address 0x08). It
does not apply here.

The map below comes from community sources, retrieved 2026-10-31:

| Source | License | Basis |
|---|---|---|
| [Pythonic-Rainbow/HUSB238A](https://github.com/Pythonic-Rainbow/HUSB238A) @ `51a52df` (2024-12-16) | MIT | Register-level C++ library. The other sources treat it as the reference map |
| [sonocotta/esphome-husb238a](https://github.com/sonocotta/esphome-husb238a) @ `0a36e5a` (2026-09-12) | GPL-2.0 | ESPHome component. Fixed-PDO select confirmed on hardware. It takes its addresses from the library above |
| [Hackaday.io project 197947](https://hackaday.io/project/197947-usb-c-power-delivery-31-breakout-with-i2c) | — | Bench reports on boot behavior, FLGIN and EPR |

Both code sources come from **one reverse-engineered map**, so treat every field
as provisional until it is confirmed on our board. `husb238a.py` is our own
implementation and copies no code from either repo.

**Confirmed on ew-1:**
- the I²C address is 0x42 (R15 1 MΩ ADDR/ORIENT to GND);
- registers 0x00–0x91 read back without NAK;
- when `CONTROL1.ENABLE` (`0x02` bit 3) = `0`, all internal functions except I²C, `EN_N` and UVLO are shut down (datasheet Rev 1.2, p. 11), so `STATUS`, `VBUS_MEASUREMENT` and `SRC_PDO_*` all read `0x00`;
- setting `CONTROL1.ENABLE = 1` (`0x1b`) brings up VBUS detection (`0x87 = 0x28`), runs the 150 ms `tCCdeb` attach debounce, sets `STATUS.ATTACH = 1`, populates `SRC_PDO_5V..20V` (`0x6A–0x6E`), and **automatically negotiates the highest source PDO up to its 28 V / 3 A factory `SNK_PDO2` ceiling** (`20 V / 3.0 A` on the 65 W SPR bench supply);
- writing `SRC_PDO` (`0x19`) and `GO_COMMAND = 0x01` (`SELECT_PDO`) cleanly switches contracts (`5 V` and `9 V` confirmed against `ADS1115` `AIN2`);
- `0x87` (`VBUS_MEASUREMENT`) stays at `0x28` (`5.000 V`) across 5 V, 9 V and 20 V contracts—do not use it as a contract voltage readout;
- 0x92 onward has not been probed.

## Board hazards (confirmed on bench — read before any write)

1. **Enabling I²C mode (`CONTROL1.ENABLE = 1`) or running `GET_SRC_CAP` automatically requests the highest voltage the source offers (up to 28 V).**
   - At power-up with `EN_N` tied to `GND`, `CONTROL1.ENABLE` (`0x02` bit 3) defaults to `0` (`0x13`), keeping all internal PD functions off so `VBUS_RAW` stays at default `vSafe5V` (`~5.1 V`).
   - Per `HUSB238A_datasheet.pdf` Rev 1.2 (p. 13–14, *Policy Engine*, and p. 19, *Ordering Guide*), `HUSB238A-BB001-QN16R` has a factory `SNK_PDO2` fuse setting of **28 V / 3 A**.
   - Confirmed on `ew-1` (2026-10-31): as soon as `CONTROL1.ENABLE = 1` (`0x1b`) is written—and whenever `GO_COMMAND = 0x04` (`GET_SRC_CAP`) triggers a fresh `Source_Capabilities` message from the charger—the chip's internal policy engine responds using its internal `28 V / 3 A` RDO and **automatically negotiates the highest source PDO ≤ 28 V** (`20 V / 3.0 A`, `AIN2 = 19.92 V` on our 65 W SPR supply) until the I²C master overwrites it via `SRC_PDO` (`0x19`) + `GO_COMMAND = 0x01` (`SELECT_PDO`).
   - This matches the Hackaday project 197947 bench report (*"in I2C mode, the device will automatic request 28V until the user config to lower the voltage"*).
2. **On our board nothing holds the VBUS switch off while U7 negotiates.**
   - U7.14 FLGIN is tied to GND, so FLGIN can never disable GATE.
   - U7.15 GATE drives Q1 (AO4407A) through R14/R12.
   - Whatever U7 negotiates therefore reaches VIN_PD, the U9 input, even while
     BULK_EN is low.
3. **Downstream ratings:**
   - U9 TPS25947 is rated 2.7–23 V operating and **28 V absolute max**.
   - F1 is a **24 V** PTC.
   - D51 SMBJ22A on the bridge rail clamps at about 24–35 V.
   - A 28 V EPR contract (28 V +5%, plus transients) would exceed U9's absolute
     maximum.
   - A 20 V SPR contract is inside the design range.
4. **Source restrictions and driver mitigation:**
   - **Never connect an EPR-capable source (> 20 V / > 100 W)** to J3 on this board revision; use only SPR-only (≤ 20 V, ≤ 100 W) or 5 V-only supplies.
   - In [`husb238a.py`](husb238a.py), `get_source_caps(hold_volts=5)` immediately issues a `5 V` `SELECT_PDO` after `GET_SRC_CAP` completes so querying capabilities does not leave `VBUS_RAW` at 20 V.

The hardware-level fix for a future board revision is to either drive `FLGIN` from a Pi GPIO / `K1` (holding `GATE` off until the host selects the PDO), use GPIO mode with `VSET` resistor strapping, or populate `HUSB238A-BB004-QN16R` (factory `SNK_PDO2 = 5 V / 3 A`).

## I²C

- 7-bit address 0x42 (ADDR/ORIENT to GND through about 900 kΩ). It is 0x62 when
  tied to VDD.
- Floating ADDR/ORIENT selects GPIO mode, which has no I²C.
- Fast-mode I²C is supported. Our bus runs at 100 kHz.
- **Every GO_COMMAND action is ignored unless CONTROL1.ENABLE (0x02 bit 3) = 1.**
  Writes to other registers are ACKed either way, so a missing ENABLE fails
  silently.
- A requested PDO is not kept across a power cycle or hard reset. The chip goes
  back to its boot default, which is the hazard above.

## Register map (unofficial)

### Control (0x00–0x0F)

| Addr | Name | Fields (bit) | ew-1 (`ENABLE=0`) | ew-1 (`ENABLE=1`) |
|---|---|---|---|---|
| 0x00 | PORTROLE | SINK_ONLY (2) | 0x40 | 0x40 |
| 0x01 | CONTROL | — | 0x47 | 0x47 |
| 0x02 | CONTROL1 | EN_DPM_HIZ (5), VDM_RESPOND (4), **ENABLE (3)**, TCCDEB [2:0] = 120 + 10·n ms | 0x13 (ENABLE = 0, 150 ms) | 0x1B (ENABLE = 1, 150 ms) |
| 0x03 | MANUAL | FORCE_DPM_HIZ (5), UNATT_SNK (3), DISABLED (1), ERROR_REC (0) | 0x00 | 0x00 |
| 0x04 | RESET | — | 0x20 | 0x20 |
| 0x05 / 06 / 07 | MASK / MASK1 / MASK2 | Interrupt masks, same bit layout as INTERRUPT1 / INTERRUPT2 / INTERRUPT | 0x00 | 0x00 |
| 0x09 | INTERRUPT | EXIT_EPR (3), GO_FAIL (2), EPR_MODE (1), PD_HV (0) | 0x00 | 0x01 (PD_HV) |
| 0x0A | INTERRUPT1 | FLGIN (7), ORIENT (6), FAULT (5), VBUS_CHG (4), VBUS_OV (3), BC_LVL (2), DETACH (1), ATTACH (0) | 0x10 (VBUS_CHG) | 0x55 (ORIENT, VBUS_CHG, BC_LVL, ATTACH) |
| 0x0B | INTERRUPT2 | TSD (7), VBUS_UV (6), DR_ROLE (5), SRC_ALERT (3), FRC_FAIL (2), FRC_SUCC (1), VDM_MSG (0) | 0x00 | 0x00 |
| 0x0C | USER_CFG0 | TSNKDSCNT [7:6], CC_DSCNTEN (5), TFAUL (4), TVBDSGTIMEOUT [3:2], TBC_LEVEL [1:0] | 0xA8 | 0xA8 |
| 0x0D | USER_CFG1 | EN_HVDCP (6), EN_VB_UV (3), EN_SVID3 (2), OUT2_SEL [1:0] | 0x40 | 0x40 |
| 0x0E | USER_CFG2 | EN_OUT2 (7), FLG_POLARITY (6), EN_FAULTIN (5), EN_OUT1 (4), PD_PRIOR (2), EN_DRS (1) | 0x27 | 0x26 |
| 0x0F | USER_CFG3 | PPS_CAP_SNK (6), AVS_CAP_SNK (5), MODAL_OPERATION (4), EPR_AVS_CAP_SNK (3), SNK_CAP_MIN_VOLTAGE (2), SNK_PDO1_CURRENT [1:0] (3 / 2.4 / 2.1 / 1.5 A) | 0x00 | 0x00 |

USER_CFG2 = 0x27 means EN_FAULTIN = 1, PD_PRIOR = 1 and EN_DRS = 1. U7.13
FAULT is not connected on our board.

### VDM (0x10–0x17)

SVID0/1 and MODE0/1 are each stored as an MSB/LSB register pair.

### Command and request (0x18–0x22)

| Addr | Name | Encoding |
|---|---|---|
| 0x18 | GO_COMMAND | GO [4:0]. Values: 0x01 SELECT_PDO, 0x02/0x03 BIST, 0x04 GET_SRC_CAP, 0x05 DR_SWAP, 0x07 GET_PPS_STATUS, 0x08 GET_MANUFACTURER_INFO, 0x09–0x10 discover/enter/exit modes, 0x18 EPR_GET_SOURCE_CAP, 0x19 EPR_MODE_ENTER, 0x1A EPR_MODE_EXIT, 0x1D SOFT_RESET, 0x1E HARD_RESET |
| 0x19 | SRC_PDO | PDO_SELECT [7:3]: 0x01 5 V, 0x02 9 V, 0x03 12 V, 0x04 15 V, 0x05 20 V, 0x06–0x08 PPS1–3, 0x09 SPR AVS, 0x10–0x12 QC2 5/9/12 V, 0x18 EPR 28 V, 0x1A 36 V, 0x1C 48 V, 0x1E EPR AVS. SNK_PPS_VOL_M [1:0] |
| 0x1A / 0x1B | SNK_PPS_VOLTAGE / SNK_PPS_CURRENT | PPS: 3000 mV + 20 mV·n (10-bit, MSBs in SRC_PDO[1:0]). Current 50 mA·n [6:0] |
| 0x1C / 0x1D | SNK_AVS_VOLTAGE / SNK_AVS_CURRENT | 100 mV·n. Current 50 mA·n [6:0], AVS_VOL_M (7) |
| 0x1E–0x1F / 0x20 | EPR_AVS_VOLTAGE / EPR_AVS_CURRENT | 100 mV·n (9-bit). Same current format (`0x1F` read `0x6C` after attach) |
| 0x21 / 0x22 | SNK_PDP / EPR_PDP | Sink power, [6:0] W |

### Status (0x63–0x79)

| Addr | Name | Fields | ew-1 (`ENABLE=0`) | ew-1 (`ENABLE=1`, 20V auto / 9V / 5V) |
|---|---|---|---|---|
| 0x63 | STATUS | AMS_PROCESS (7), PD_EPR_SNK (6), TSD (3), BC_LVL [2:1] (none / default / 1.5 A / 3 A), **ATTACH (0)** | 0x00 | 0x17 (ATTACH = 1, BC_LVL = 3.0 A) |
| 0x64 | STATUS1 | FLGIN (7), PD_HV (5), PD_COMM (4), SRC_ALERT (3), **AMS_SUCC (2)**, FAULT (1), DATA_ROLE (0) | 0x00 | 0x30 (20V/9V: PD_HV=1, PD_COMM=1) / 0x10 (5V: PD_HV=0, PD_COMM=1) |
| 0x65 | TYPE | CC_RX_ACTIVE (7), DEBUGSNK (5), SINK (4) | 0x00 | 0x10 (SINK = 1) |
| 0x66 | DPDM_STATUS | CDP (2), SDP (1), DIVIDER3 (0) | 0x00 | 0x18 |
| 0x67 | CONTRACT_STATUS0 | PD_CONTRACT [7:4]: 0 Type-C 5 V, 1–5 = 5/9/12/15/20 V, 6–8 PPS1–3, 9 SPR AVS, 0xA–0xC EPR 28/36/48 V, 0xD EPR AVS. DPM_CONTRACT [3:0]: 0 default, 1 divider3, 2 SDP, 3 CDP, 4 DCP, 5 HVDCP, 6/7 QC2 9/12 V | 0x00 | 0x55 (20 V) / 0x25 (9 V) / 0x15 (5 V) |
| 0x68 | CONTRACT_STATUS1 | Fixed PDO current: 500 + 20·n mA (n ≤ 0x7D), else 500 + 40·n. APDO: 50·n mA | 0x00 | 0x7D (3000 mA) |
| 0x69 | SOURCECAP_INFO | VDM_MODE (6), POWER_LIMIT (5), DRP (4), USB_SUSPEND (3), USB_COMM (2), DRD (1), **EPR_MODE_CAPABLE (0)** | 0x00 | 0x00 (SPR-only source) |
| 0x6A–0x71 | SRC_PDO_5V, 9V, 12V, 15V, 20V, 28V, 36V, 48V | DETECT (7), max current [6:0] × 100 mA | all 0x00 | `0x6A–0x6E` = `9e 9e 9e 9e a0` (5/9/12/15V @ 3.0A, 20V @ 3.2A); `0x6F–0x71` = `00` |
| 0x72–0x74 | SRC_PDO_PPS1–3 | Same format | 0x00 | 0x00 (note `USER_CFG3.PPS_CAP_SNK = 0`) |
| 0x75 | SRC_PPS_VOLTAGE | PPS1/2/3_MAX [7:6]/[5:4]/[3:2] (5.9 / 11 / 16 / 21 V), PPS_MIN [1:0] (3 / 3.3 / 5 V) | 0x00 | 0x00 |
| 0x76 | SRC_PDO_AVS | DETECT (7), AVS_MAX [6:3] (+5 V), AVS_MIN [1:0] (5 / 9 / 15 V) | 0x00 | 0x00 |
| 0x77 / 0x78 | SRC_AVS_PDP / EPR_AVS_PDP | W | 0x00 | 0x00 |
| 0x79 | SRC_EPR_AVS | DETECT (7), MAX [6:2] (+20 V), MIN [1:0] | 0x00 | 0x00 |

### VDM, alerts, misc (0x7A–0x91)

| Addr | Name | Notes | ew-1 (`ENABLE=0`) | ew-1 (`ENABLE=1`) |
|---|---|---|---|---|
| 0x7A–0x86 | VDM_HEADER, VDO1–3 (4 bytes each) | Header: OBJECT_POSITION [7:5], COMMAND_TYPE [4:3] (REQ / ACK / NAK / BUSY), VDM_TYPE [2:0] | 0x00 | 0x00 |
| 0x87 | VBUS_MEASUREMENT | n × 125 mV (does not track above 5 V on `-BB001`) | **0x00** | **0x28** (`5.000 V` across 5/9/20 V contracts) |
| 0x88 | SRC_ALERT | EXTENDED (7), OVP (6), SRC_INPUT (5), OP_CHANGE (4), OTP (3), OCP (2), BATTERY (1) | 0x00 | 0x00 |
| 0x89–0x8B | SRC_PPS_STATUS voltage / current / flag | Flag: PPS_VOL_M [7:6], OMF (3), PTF [2:1] | 0x00 | 0x00 |
| 0x8C–0x8F | MNF_OFST0–3 | Manufacturer info | 0x00 | 0x00 |
| 0x90 / 0x91 | SNK_FSM_STATE / SRC_FSM_STATE | Encoding undocumented | 0x01 / 0x00 | 0x06 / 0x00 |

Registers 0x23–0x62 are not in the community map. On ew-1, 0x39–0x61 read
non-zero (for example 0x50–0x5F = a0…ae), so they look like internal or
trim data. Never write them.

## Request sequence (fixed PDO)

1. Set `CONTROL1.ENABLE`: read-modify-write `0x02` with bit 3 set (`0x13 → 0x1B`).
   - If `ENABLE` was `0`, **wait for `tCCdeb` (150 ms) plus initial attach negotiation** (`STATUS.AMS_PROCESS == 0`) before issuing any `GO_COMMAND`. Issuing `GO_GET_SRC_CAP` immediately after setting `ENABLE = 1` fails because the chip is still in `tCCdeb` (`STATUS.ATTACH = 0`).
   - Initial attach already receives `Source_Capabilities`, populates `SRC_PDO_5V..20V` (`0x6A–0x6E`), and auto-requests the highest source PDO ≤ 28 V.
2. To explicitly re-query capabilities later, write `GO_COMMAND = 0x04` (`GET_SRC_CAP`), wait for `STATUS.AMS_PROCESS` to clear, and immediately issue a `SELECT_PDO` (step 3–4) because receiving `Source_Capabilities` triggers `U7` to respond with its internal 28 V / 3 A RDO.
3. Write `SRC_PDO = PDO_SELECT << 3`. Wait about 5 ms.
4. Write `GO_COMMAND = 0x01` (`SELECT_PDO`). Wait for `STATUS.AMS_PROCESS` to clear, then check `CONTRACT_STATUS0` (`0x67`).
5. Confirm the voltage independently with `ADS1115` `AIN2` (`VBUS_RAW = V × 6.556`).
   **Do not rely on `0x87` (`VBUS_MEASUREMENT`)**, which remains at `0x28` (`5.000 V`) even at 9 V and 20 V.

Never issue a second `GO_COMMAND` while `AMS_PROCESS = 1`.

## Driver (`husb238a.py`)

- The constructor default is `allow_write=False`. Every write raises
  `WriteRefused`.
- `enable()` sets `CONTROL1.ENABLE = 1`. On a `0 → 1` transition it waits for
  `tCCdeb` (150 ms) and the attach AMS to finish. If the chip is attached, it
  then **re-selects 5 V immediately**, so the automatic request doesn't stand.
- `get_source_caps(hold_volts=5, max_volts=5)` sends `GO_GET_SRC_CAP`, then
  re-selects `hold_volts`, so `srccap --arm` doesn't leave VBUS at the
  automatic 20 V/28 V request.
  - `hold_volts` goes through the same checks as `request_fixed`. The value
    and the `min(max_volts, 20)` ceiling are checked before any write. The
    "source advertised it" check runs after the query; if it fails, the
    driver re-selects 5 V and raises `WriteRefused`.
  - `hold_volts=None` is refused.
- `request_fixed(volts, max_volts=5)` accepts only 5/9/12/15/20 V, refuses
  anything above `min(max_volts, 20)`, and refuses PDOs the source didn't
  advertise. EPR, AVS and PPS are not implemented on purpose.
- CLI:
  - `status` / `dump` only read.
  - `srccap --arm` and `request V --arm [--max V]` write.
- Checked on ew-1 2026-10-31:
  - `status` and `dump` work.
  - Unarmed `request 5`, `request 28 --arm` and `request 9 --arm` (5 V
    default ceiling) were all refused before any write.
  - `srccap --arm` discovers `5/9/12/15 V @ 3000 mA, 20 V @ 3200 mA` and holds
    an explicit `5 V / 3000 mA` contract (`AIN2 = +0.7895 V ≈ 5.18 V`).
  - `request 9 --arm --max 9` negotiates `9 V / 3000 mA` (`CONTRACT_STATUS0 = 0x25`,
    `AIN2 = +1.3685 V ≈ 8.97 V`).
  - `request 5 --arm --max 5` negotiates `5 V / 3000 mA` (`CONTRACT_STATUS0 = 0x15`,
    `AIN2 = +0.7810 V ≈ 5.12 V`).

## Resolved question: why the chip reported unattached with 5 V on VBUS

With J3 plugged in and `CONTROL1 = 0x13` (`ENABLE = 0`):
- `ADS1115` `AIN2` showed `VBUS_RAW ≈ 5.05–5.15 V`.
- `U7` reported `ATTACH = 0`, no contract, no source PDOs, `VBUS_MEASUREMENT = 0` and `SNK_FSM_STATE = 0x01`.

**Root cause (resolved 2026-10-31 18:06):**
- Per `HUSB238A_datasheet.pdf` Rev 1.2 p. 11 (*ENABLE CONTROL*), when `EN_N` is low in I²C mode and `CONTROL1.ENABLE = 0`, all internal functions of the `HUSB238A` are turned off except I²C accessibility, `EN_N` detection, and UVLO detection.
- Setting `CONTROL1.ENABLE = 1` (`0x1b`) immediately enabled `VBUS` detection (`0x87 = 0x28` → `5.000 V`), proving `F1` and `R13` are intact (`U7.16` `VBUS_IN` receives VBUS).
- After the 150 ms `tCCdeb` debounce, `U7` reported `ATTACH = 1`, `CC = 3.0 A`, `PD_COMM = 1`, `SNK_FSM_STATE = 0x06`, and `SRC_PDO_5V..20V` (`5/9/12/15 V @ 3.0 A`, `20 V @ 3.2 A`), and auto-negotiated `20 V / 3.0 A` (`AIN2 = 19.92 V`) before being commanded to `5 V` (`AIN2 = 5.12 V`) and `9 V` (`AIN2 = 8.97 V`).
