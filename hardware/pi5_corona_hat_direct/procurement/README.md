# Revision F component selection

The active project is `../pi5_corona_hv.kicad_pro`, a KiCad 10 Raspberry Pi 5 HAT with USB-C PD input and an illumination break-off board. Catalog checks were performed on 2026-10-02, with the Bourns selection checked on 2026-10-03 using JLCPCB's component-detail API; the installed offline catalog is dated 2026-09-13. Stock is a snapshot, not a reservation or assembly-service guarantee.

149 of 152 placed items have catalog assignments. Each placed symbol carries hidden `LCSC`, `LCSC Part`, `JLCPCB Part #`, `Manufacturer`, `MPN`, catalog source/date, assembly process, and procurement status fields. Catalog metadata does not clutter the drawing. Revision F changes the multiplier bleeders to 300 MΩ per bank; the divider remains nominally 1 GΩ.

- [`../exports/procurement-bom.csv`](../exports/procurement-bom.csv) includes every placed item, including DNP parts and exceptions.
- [`../exports/jlcpcb-bom.csv`](../exports/jlcpcb-bom.csv) is the four-column grouped JLCPCB matching BOM. It excludes the two DNP parts, the three items without catalog assignments, and the relay under electrical review. Out-of-stock catalog matches remain in it so the vendor can identify the required parts.
- [`../exports/procurement-exceptions.csv`](../exports/procurement-exceptions.csv) identifies sourcing and design holds.
- [`part-assignments.json`](part-assignments.json) is the per-sheet selection record; [`jlcpcb-catalog-2026-10-02.json`](jlcpcb-catalog-2026-10-02.json) preserves catalog attributes used to check value, rating, tolerance, package and assembly process.

This is a procurement BOM. An compact two-layer PCB placement now exists. Routing and production CPL remain incomplete; these files are not a fabrication release.

| Circuit | Selected MPN | JLCPCB/LCSC ID |
|---|---|---|
| U2 bridge | DRV8876PWPR | C575551 |
| U4 buffer | TLV9001IDBVR | C398363 |
| U5 environment | BME280 | C92489 |
| U6 ADC | ADS1115IDGSR | C37593 |
| U7 PD sink | AP33772SDKZ-13-FA01 | C24374260 |
| U8 illumination | TSL25911FN | C176812 |
| U9 eFuse | TPS259470LRPWR | C3662793 |
| Q1 switch | AO4262E | C431178 |
| J3 USB-C | HC-TYPE-C-16P-01A | C2894897 |
| J50/J51 cable connectors | SM04B-SRSS-TB(LF)(SN) | C160404 |

Part IDs are supported by the linked catalog records, for example [U7](https://jlcpcb.com/partdetail/C24374260), [U9](https://jlcpcb.com/partdetail/C3662793), and [J50/J51](https://jlcpcb.com/partdetail/C160404). Check stock and service availability again at ordering.

# Physical and annotation corrections

The duplicate multiplier capacitors C20–C31 are now C100–C111. The sense-sheet R10/R11 are R90/R91, and its former J3 is J60. USB-C J3 and host-sheet component references are retained. Duplicate power references and missing native instance annotations were repaired. Netlist export no longer produces an annotation warning.

Q1's generic three-pin symbol was incompatible with its SO-8 footprint. The native AO4262E symbol now exposes all physical pads: gate 4, input/drain 5–8, and output/source 1–3, preserving the original transistor orientation and functional nets. The [manufacturer datasheet](https://www.aosmd.com/sites/default/files/res/datasheets/AO4262E.pdf) specifies 60 V VDS and 6.5 mΩ maximum RDS(on) at 10 V gate drive. U7's exposed pad 25 is now explicitly connected to GND. Connector `MP` pads are mechanical mounting pads, not missing electrical symbol pins.

R71 uses an 0805 footprint for the selected 976 kΩ / 0.1% part. C73 uses a 2220 footprint for the selected 1.8 µF / 50 V / 5% part; the PD budget conservatively retains its original 10% tolerance. C60 uses a 5 mm diameter / 2 mm pitch footprint for Rubycon 50YXJ33M5X11; C70 uses the same pad pitch for 50YXF22MEFC5X11. C11 is KYET MMKP124J2J1501, 120 nF / 630 V / 5% metallized polypropylene, with a native 18 × 10 mm / 15 mm pitch footprint. Its physical dimensions were checked against the **JLCEDA/EasyEDA Official Library** ([JLCEDA](https://lceda.cn/), [EasyEDA](https://easyeda.com), [component record](https://easyeda.com/api/products/C2991056/components)); this footprint is written in native KiCad 10 syntax. Verify manufacturer drawings, lead diameter, body tolerances and resonant capacitor RMS-current capability before fabrication.

# Procurement and electrical holds

- T1: no exact FL2015-4LD catalog match was found. Buy from [Coilcraft](https://www.coilcraft.com/en-us/products/transformers/power-transformers/ccfl-transformers/fl/fl2015-4l/) and arrange consignment or manual installation. PFL2015 inductors are not substitutes.
- TP50: copper test pad, no purchased component required.
- J60: the existing WJ500V-5.08-2P footprint corresponds to a [250 V terminal](https://www.lcsc.com/product-detail/C8465.html), unsuitable for the intended 15 kV output. No catalog ID is assigned; select a rated HV termination and redesign its footprint/clearances before fabrication.
- K1: C52195125 identifies the original N4078-2C-DC12V-0.2W relay family. Its 12 V coil remains on the variable HV_VM supply. Provide a fixed rated coil supply or redesign the interlock before release. It is listed in the full procurement BOM but excluded from the matching BOM.
- C73 has zero stock in the checked catalog. Source it before ordering assembly. C63 is also out of stock but remains intentionally DNP.
- NTC1 is NCP18XH103F03RB: 10 kΩ / 1%, B25/50 = 3380 K. Confirm the PD-controller thermal settings against this curve. Confirm AP33772S FA01 firmware compatibility with the host driver.
- Verify C60/C70 ripple current, ESR, temperature rise, C11 resonant current and ceramic DC-bias derating on the built circuit. Selecting catalog IDs does not replace these checks.

C63 and R64 are the only DNP components. Neither missing stock nor manual/THT assembly changes a part's intended population flag. The existing shared INTERLOCK_OK/DRV_nSLEEP connection also remains an electrical-review item.

# Bourns high-voltage resistor selection

R30–R39 and the multiplier bleeders use **Bourns CHV2512-JW-107ELF**, **C2089706**, 100 MΩ / 5%, 1 W, 2512, 3 kV continuous maximum. There are 46 fitted parts: ten divider resistors and twelve banks of three series resistors. R40–R51 are the middle parts; R140–R163 complete the banks. See the [manufacturer datasheet](https://www.bourns.com/docs/Product-Datasheets/CHV.pdf) and [catalog snapshot](bourns-catalog-2026-10-03.json).

Three parts per bleeder make each bank 300 MΩ. At 6 kV per capacitor, nominal resistor voltage is 2 kV; the worst static split from ±5% tolerance is about 2.14 kV. At a 20 kV divider input, the worst tolerance split is about 2.19 kV per resistor. These calculations assume constant resistance; voltage coefficient and PCB leakage require validation.

R39's former wire bypass is corrected. Ten series 100 MΩ resistors above R8 + R9 (164 kΩ) give a nominal 6098.56:1 ratio: about 2.460 V and 15 µA at 15 kV. Calibrate at multiple operating voltages: the Bourns datasheet specifies up to ±300 ppm/V voltage coefficient for these values, measured only up to 500 V. Do not extrapolate that test into a guaranteed error at operating voltage.

A 300 MΩ / 1 nF bank has a nominal 0.30 s time constant (0.378 s with +5% resistance and +20% capacitance). An ideal constant-resistance model gives about 1.81 s for one 6 kV capacitor to fall below 50 V. This is a calculation, not a verified discharge time; measure the assembled multiplier before relying on a delay or safe-to-touch indication.
