# Revision J component selection

The active project is `../pi5_corona_hv.kicad_pro`, a KiCad 10 Raspberry Pi 5 HAT with USB-C PD input and an illumination break-off board. Catalog checks were performed on 2026-10-02, with the Bourns selection checked on 2026-10-03 using JLCPCB's component-detail API; the installed offline catalog is dated 2026-09-13. Stock is a snapshot, not a reservation or assembly-service guarantee.

156 placed items are tracked in the schematic procurement manifest. Each placed symbol carries hidden `LCSC`, `LCSC Part`, `JLCPCB Part #`, `Manufacturer`, `MPN`, catalog source/date, assembly process, and procurement status fields. Catalog metadata does not clutter the drawing. The multiplier bleeders use 200 MΩ per bank (2× 100 MΩ series resistors, R140–R163); the divider remains nominally 1 GΩ (R30–R39).

- [`../exports/procurement-bom.csv`](../exports/procurement-bom.csv) includes every placed item, including DNP parts and exceptions.
- [`../exports/jlcpcb-bom.csv`](../exports/jlcpcb-bom.csv) is the four-column grouped JLCPCB matching BOM. It excludes the two DNP parts, the twelve PCB features/external-sourcing items without catalog assignments. Out-of-stock catalog matches remain in it so the vendor can identify the required parts.
- [`../exports/procurement-exceptions.csv`](../exports/procurement-exceptions.csv) identifies sourcing and design holds.
- [`part-assignments.json`](part-assignments.json) is the per-sheet selection record; [`jlcpcb-catalog-2026-10-02.json`](jlcpcb-catalog-2026-10-02.json) preserves catalog attributes used to check value, rating, tolerance, package and assembly process.

| Circuit | Selected MPN | JLCPCB/LCSC ID |
|---|---|---|
| U2 bridge | DRV8876PWPR | C575551 |
| U4 buffer | TLV9001IDBVR | C398363 |
| U5 environment | BME280 | C92489 |
| U6 ADC | ADS1115IDGSR | C37593 |
| U7 PD sink | HUSB238A-BB001-QN16R | C22382397 |
| U8 illumination | TSL25911FN | C176812 |
| U9 eFuse | TPS259470LRPWR | C3662793 |
| Q1 switch | AO4407A | C495938 |
| J3 USB-C | HC-TYPE-C-16P-01A | C2894897 |
| J50/J51 cable connectors | SM04B-SRSS-TB(LF)(SN) | C160404 |
| R73 eFuse ILM (2.78 A) | 0603WAF1201T5E (1.2k 1%) | C22765 |
| R61 DRV8876 IPROPI (2.20 A) | 0603WAF1501T5E (1.5k 1%) | C22843 |

Part IDs are supported by the linked catalog records, for example [U7](https://jlcpcb.com/partdetail/C22382397), [U9](https://jlcpcb.com/partdetail/C3662793), and [J50/J51](https://jlcpcb.com/partdetail/C160404). Check stock and service availability again at ordering.

# Physical and annotation corrections

The duplicate multiplier capacitors C20–C31 are now C100–C111. The sense-sheet R10/R11 are R90/R91, and its former J3 is J60. USB-C J3 and host-sheet component references are retained. Duplicate power references and missing native instance annotations were repaired. Netlist export no longer produces an annotation warning.

Q1 uses AO4407A (SO-8 P-channel MOSFET, -30 V VDS, +/-20 V VGS) with all physical pads exposed: gate 4, input/source 1–3, and output/drain 5–8. U7 (HUSB238A-BB001-QN16R) Pin 5 (VDD) is supplied from Pi 3V3, defaulting safely to 5 V on USB-C attachment while supporting 5–20 V I2C negotiation at 0x42, and exposed pad 17 is connected to GND. Connector `MP` pads are mechanical mounting pads, not missing electrical symbol pins.

R71 uses an 0805 footprint for the selected 976 kΩ / 0.1% part. C73 is now Samsung CL10B105KB8NQNC (C5199872), 1 µF / 50 V / 10% X7R in 0603, replacing the zero-stock 1.8 µF part. C60 uses a 5 mm diameter / 2 mm pitch footprint for Rubycon 50YXJ33M5X11; C70 uses the same pad pitch for 50YXF22MEFC5X11. C11 is KYET MMKP124J2J1501, 120 nF / 630 V / 5% metallized polypropylene, with a native 18 × 10 mm / 15 mm pitch footprint. Its physical dimensions were checked against the **JLCEDA/EasyEDA Official Library** ([JLCEDA](https://lceda.cn/), [EasyEDA](https://easyeda.com), [component record](https://easyeda.com/api/products/C2991056/components)); this footprint is written in native KiCad 10 syntax. Verify manufacturer drawings, lead diameter, body tolerances and resonant capacitor RMS-current capability before fabrication.

# Procurement and electrical holds

- T1: no exact FL2015-4LD catalog match was found. Buy from [Coilcraft](https://www.coilcraft.com/en-us/products/transformers/power-transformers/ccfl-transformers/fl/fl2015-4l/) and arrange consignment or manual installation. PFL2015 inductors are not substitutes.
- TP50: copper test pad, no purchased component required.
- J60/J61: separate single solder-wire HV terminations; no purchased connector or invented catalog ID. Verify external wire insulation, spacing, enclosure and strain relief. J62–J69 are solderable plated-hole pairs for detached microswitch connections; no purchased parts are required.
- K1: Omron G6K-2F-Y DC3 C93168, regulated 3 V coil and independent logic contacts; pickup and fault behavior require bench qualification.
- C73 has an in-stock 1 µF replacement. C63 remains intentionally DNP; C82/C83 are assigned to Samsung CL21A225KBQNNNE (C377773), 2.2 µF / 50 V / X5R in 0805, JLCPCB Basic Library.
- NTC1 is NCP18XH103F03RB: 10 kΩ / 1%, B25/50 = 3380 K.
- Verify C60/C70 ripple current, ESR, temperature rise, C11 resonant current and ceramic DC-bias derating on the built circuit. Selecting catalog IDs does not replace these checks.

C63 and R64 are the only DNP components. Neither missing stock nor manual/THT assembly changes a part's intended population flag. INTERLOCK_OK, DRV_SLEEP_CMD and DRV_nSLEEP are now distinct nets, verified by regression checks.

# Bourns high-voltage resistor selection

R30–R39 and the multiplier bleeders use **Bourns CHV2512-JW-107ELF**, **C2089706**, 100 MΩ / 5%, 1 W, 2512, 3 kV continuous maximum. There are 34 fitted parts: ten divider resistors (R30–R39) and twelve banks of two series resistors (R140–R163, 24 resistors total). See the [manufacturer datasheet](https://www.bourns.com/docs/Product-Datasheets/CHV.pdf) and [catalog snapshot](bourns-catalog-2026-10-03.json).

Two parts per bleeder make each bank 200 MΩ. At 2.5 kV nominal per stage capacitor, nominal resistor voltage is 1.25 kV (< 3 kV continuous rating). At a 20 kV divider input, the worst tolerance split is about 2.19 kV per resistor. These calculations assume constant resistance; voltage coefficient and PCB leakage require validation.

R39's former wire bypass is corrected. Ten series 100 MΩ resistors above R8 + R9 (164 kΩ) give a nominal 6098.56:1 ratio: about 2.460 V and 15 µA at 15 kV. Calibrate at multiple operating voltages: the Bourns datasheet specifies up to ±300 ppm/V voltage coefficient for these values, measured only up to 500 V. Do not extrapolate that test into a guaranteed error at operating voltage.

A 200 MΩ / 1 nF bank has a nominal 0.20 s time constant. Under the full coupled ladder model (`native_multiplier.py`), nominal shutdown cases fall below the 50 V threshold in approximately 0.93 s. Measure the assembled multiplier before relying on a delay or safe-to-touch indication.

# Revision H multiplier diode replacement

D10–D21 use **SUNMATE Elec 2CL75, C424512**, replacing HVM12. Its manufacturer datasheet specifies 16 kV repetitive reverse voltage, 5 mA average current, 0.5 A non-repetitive surge, 100 ns maximum reverse-recovery time at 25 C and 1 pF junction capacitance at 0 V / 1 MHz. Leakage is at most 2 uA at 25 C and 5 uA at 100 C; forward drop is at most 43 V at 5 mA. The recovery table does not give forward/reverse test-current conditions or Qrr, so validate recovery under the actual waveform. See [saved manufacturer datasheet](Sunmate_2CL75_C424512.pdf) and [dated live JLCPCB evidence](sunmate-catalog-2026-10-03.json).

The 2026-10-03 API snapshot reports 1,006 in stock, Extended, manualWeld/THT, with an indicative price of $0.2678 each for 1–49. Twelve parts total $3.2136 before assembly, losses and other order charges. Stock is not reserved. Yangjie C2995522 is excluded because it has zero JLCPCB stock.

The native footprint has a 3 × 12 mm body, 0.6 mm leads, 26 mm formed pitch, 0.9 mm plated drills and 1.8 mm pads. Pad 1 is cathode (band), pad 2 anode. Existing pad centers, board pose, traces and polarity are preserved. The VRML model is project-authored approximate geometry. This is not a current/surge-equivalent replacement: verify startup, repetitive charging pulses and short-circuit behavior before production. The 150 uA output target alone does not establish diode pulse-current suitability.

## Audit selections, 2026-10-03

K1: Omron G6K-2F-Y DC3 C93168; U10: TI TPS7A0230PDBVR C3747031; R90: Vishay CRCW120610K0FKEAHP C313977; D5: LRC SMBJ15A C2912077; C82/C83: Samsung CL21A225KBQNNNE C377773 (2.2 µF / 50 V / X5R 0805 Basic); R91/R92: UNI 0603WAF1002T5E C25804. Live evidence and manufacturer PDFs are saved here. Confirm effective LDO capacitance and relay pickup over supply/temperature; these selections do not close bench holds.

Transformer T1 remains externally sourced. Its native footprint now follows Coilcraft's SMT Package 1, and the corrected pin map is in AUDIT.md.

## Four-switch safety chain, revision J

S3–S6 use the user-approved DEALON TK-0013-R (C19724218), replacing Omron D2F-L. All four switches are populated and wired in series. J66/J67 are their mini-board COM/NO solder pads; J68/J69 are the matching host pairs. These four added pad features need no purchased component or catalog ID. The refreshed matching BOM has 154 populated catalog-matched parts; schematic DNP remains C63/R64 only.

## Parallel-actuation microswitch replacement

S3–S6 now use DEALON TK-0013-R, C19724218, populated on all four break-off boards. The user accepted this selection on 2026-10-03. JLCPCB catalog snapshot reports 910 units, Extended/manualWeld (THT), $0.3099 at 1–49 and $0.245 at 50–149; stock is not reserved. The manufacturer drawing shows COM/NO/NC despite the catalog SPST-NC description and omits electrical ratings. Preserve this unresolved procurement qualification in the production checklist; confirm contact mapping and relay-coil load ratings on actual parts.

Custom footprint ionic_thrust_hv:SW_TK-0013-R uses pad 1 COM, pad 2 NO and pad 3 NC. Pads have 2.5 mm pitch, 0.7 × 1.5 mm oval holes and 1.3 × 2.1 mm lands. Body is 8.3 × 6.2 × 2.7 mm and actuation is parallel to the board; free lever envelope extends 9.8 mm from the rear body edge. The four footprint origins are (39,137.6), (39,153.6), (39,169.6), (39,185.6), all rotation 0. Lever tips may project 0.1 mm beyond each mini-board lower edge; account for lever travel and enclosure clearance. All COM/NO neck conductors are retained, NC unused, DNP unchanged. The previous board is preserved under revisions/L-layout-7/. Native ERC/DRC and schematic parity pass; 191 unconnected items remain in the overall partial layout.

The TK-0013-R VRML model is an approximate project envelope, not a manufacturer model or a lever-travel simulation.
