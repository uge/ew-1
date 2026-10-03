# Raspberry Pi 5 Corona HAT hardware handoff

This document describes the current KiCad 10 design draft in `hardware/pi5_corona_hat_direct/`. It supersedes the older ESP32/12 V handoff. The schematic now uses a Raspberry Pi 5 40-pin HAT interface, USB-C PD input, a programmable PD sink, voltage monitoring, and a low-light sensor. The PD input and high-side switch are not yet fabrication-ready; resolve the validation items below first.

## Current schematic architecture

- J2 is the Raspberry Pi 5 2x20 HAT connector. GPIO18 and GPIO19 provide PWM0/PWM1 to the transformer driver; GPIO23 reports the interlock and GPIO24 controls driver sleep. GPIO25 (physical pin 22) controls `BULK_EN`. The Pi-side logic is 3.3 V.
- J3 is a 16-pin USB-C receptacle for the high-voltage supply input. F1 is a 1 A hold, 30 V resettable fuse. R13 is a 5 mΩ current-sense element for the sink controller. Q1 is the controller-enabled N-channel output switch; its output is now the sheet-local `VIN_PD` rail, monitored by U7. U9 is a host-enabled TPS259470LRPW eFuse between `VIN_PD` and `VIN_PROTECTED`; it isolates downstream bulk capacitance until an explicit PD contract is established.
- U7 is the 24-pin AP33772S USB-C PD sink. The Pi host programs the requested PPS voltage and current over I²C. The intended selectable input range is 5 V through 20 V. The controller starts from the default 5 V profile, then accepts a host request. A connected charger must advertise a compatible PD/PPS profile; fixed-profile-only sources cannot provide every requested voltage.
- U6 is an ADS1115 16-bit, four-input I²C ADC at address 0x48. AIN0 measures the high-voltage divider, AIN1 measures return current, AIN2 measures the USB-C rail through R10=100 kΩ and R11=18 kΩ, and AIN3 is spare. At a 20 V input, the divider produces about 3.05 V.
- U8 is a TSL2591 light-to-digital sensor at address 0x29 on the new `05_illumination.kicad_sch` break-off mini-board sheet. It contains two integrating ADC channels (broadband and infrared) and reports data over I²C. Its manufacturer specifies sensitivity down to 188 µlux, below the 0.001 lux target. This low-light path is digital; it does not feed an analog output into U6. J50 on the HAT and J51 on the mini board accept a standard 3.3 V Qwiic/STEMMA QT cable after detachment.
- U5 is the existing BME280 at address 0x76. The BME280, TSL2591, ADS1115, and AP33772S share the Pi I²C bus.

The USB-C sink starts at 5 V until the Pi host is running and requests a new profile. Power the Pi from its normal 5 V supply while bringing up this HAT; do not depend on the PD input to boot the Pi. Firmware must read source capabilities, request only an advertised profile, set OVP/OCP thresholds, and keep GPIO25/`BULK_EN` low on startup, detach, reset, and fault. Do not treat the AP33772S output switch alone as proof of an explicit contract: it may enable its 5 V output in a non-PD fallback mode.

## USB-PD capacitance budget and bulk charging

USB PD Rev. 3.2 v1.0 section 7.2.2 and table 7.26 specify a 100 µF ordinary sink bulk-capacitance ceiling after successful negotiation. The attachment limit is 10 µF under the referenced USB/Type-C rules. Distributed capacitance counts, including the bridge reservoir when its power path is closed. The specification permits larger banks with appropriate VBUS surge-current limiting, but this revision deliberately stays below the ordinary 100 µF budget. [USB-IF specification download](https://www.usb.org/sites/default/files/USB%20PD%20R3.2%20V1.0_1.zip), [TI discussion of the attachment and negotiated limits](https://www.ti.com/lit/ds/symlink/tps25751.pdf).

| Location / components | Nominal capacitance | Maximum with specified positive tolerance |
| --- | ---: | ---: |
| Unswitched VBUS: C21, C73, C17 | 4.7 + 1.8 + 1.0 µF | 8.250 µF |
| Conservatively counted controller bypass/filter caps: C18, C19, C20 | 0.1 + 1.0 + 0.1 µF | 1.320 µF |
| U9 input bypass C71 and conservatively counted slew capacitor C72 | 0.1 + 0.0022 µF | 0.11242 µF |
| Switched main bulk: C22, C70 | 10 + 22 µF | 37.400 µF |
| Switched bridge: C10, C12, C60, C61, C62 | 0.1 + 10 + 33 + 0.1 + 0.022 µF | 50.8442 µF |
| Reserve for unlisted device/PCB parasitics | — | 0.300 µF |
| **Exposed at attachment with U9 off, including reserve** | — | **9.98242 µF** |
| **All PD-derived capacitors connected, including reserve** | — | **98.22662 µF** |

C21/C73/C17/C22/C71 are 50 V capacitors with 10% tolerance; C70 is 22 µF/50 V with 20% tolerance. C60 is reduced from 220 µF to 33 µF/50 V with 20% tolerance so the entire sink stays within this budget. Bridge ceramics use 10% tolerance; their voltage ratings are shown on the sheet. Pi-powered optical capacitors C80/C81 are outside the USB-C power path and are not counted. Do not substitute capacitors with a larger positive tolerance or add rail capacitors without recalculating the budget. The budget bounds nominal capacitance plus tolerance without taking credit for DC-bias derating; actual energy storage must still be checked at operating voltage. C70 and C60 now use 5 mm diameter / 2 mm pitch footprints for the selected Rubycon 50YXF22MEFC5X11 and 50YXJ33M5X11 parts. Ripple ratings remain subject to bench validation. C73's selected 1.8 µF / 50 V part has 5% tolerance and a 2220 footprint; this budget conservatively retains 10%.

U9 has back-to-back internal switches, controlled output slew, reverse-current blocking, and latched protection. R70 (100 kΩ) holds EN low when the Pi is unconfigured. R73 (3.32 kΩ, 1%) sets about 1.0 A nominal current limit; negotiate a source current of at least 1.25 A and verify the limit tolerances and fuse behavior. C72 (2.2 nF) sets about 0.91 V/ms nominal output slew, corresponding to roughly 80 mA capacitive inrush for the worst-case downstream bank and about 22 ms rise time at 20 V, excluding load current and device tolerances. R71/R72 (976 kΩ/56.2 kΩ, 0.1%) set approximately 22 V overvoltage lockout. AUXOFF, FLT, and ITIMER are intentionally unused; an open ITIMER selects the fastest overcurrent response. The custom RPW0010A footprint follows TI's 10-pin land-pattern drawing and was parsed/exported by KiCad 10. [TI TPS25947 datasheet](https://www.ti.com/lit/ds/symlink/tps25947.pdf).

Firmware must confirm the explicit contract and stable requested voltage before asserting GPIO25, keep the bridge asleep during bulk charging, and allow for the measured ramp time before HV enable. Turn the bulk path off before renegotiating and on detach, reset, or fault. Validate attachment capacitance, inrush, PD voltage transitions, shutdown/discharge timing, and the parasitic reserve on the assembled board; the calculated budget and zero ERC are not USB-PD certification.

## Bridge inductive overvoltage protection

U2 is now DRV8876PWPR, replacing the DRV8220. Its 4.5–37 V operating range and 40 V absolute maximum provide room for a transient clamp above the normal 20 V input. The 16-pin HTSSOP symbol follows the PWP package pin table, including grounded thermal pad 17. The PCB footprint uses an exposed-pad HTSSOP with thermal vias; check its land pattern against the TI package drawing before fabrication.

- D50, VSSA310S-M3 (100 V Schottky), passes the interlocked `HV_VM` input into the sheet-local `HV_BRIDGE` rail and blocks regenerated energy from reaching the upstream USB-C switch and relay supply. It is not a substitute for USB-C input protection.
- C10 (100 nF, 50 V X7R), C12 (10 µF, 50 V X7R), and C60 (33 µF, 50 V low ESR) absorb local switching and returned energy. Select C60 for measured ripple current and temperature; the selected Rubycon 50YXJ33M5X11 uses a 5 mm diameter, 2 mm pitch footprint. Account for ceramic capacitance loss with DC bias. Revalidate TVS pulse energy with the smaller reservoir.
- D51 is a populated, unidirectional SMBJ22A TVS: cathode to `HV_BRIDGE`, anode to GND. It has 22 V standoff and a specified 35.5 V clamp at the manufacturer's test pulse current, below U2's ratings. This voltage is not a guarantee for arbitrary pulse energy, temperature, or PCB inductance.
- D52–D55 are populated SS36 60 V/3 A Schottky recirculation diodes. Each output has a diode from GND to the output and another from the output to `HV_BRIDGE`. Use the specified Vishay SMC package and keep loops short.
- R60 (1 kΩ, 1 W) bleeds the local reservoir after supply removal. C60 alone gives a nominal 0.033 s time constant; the bridge can retain energy briefly after the relay opens, so verify interlock shutdown including all connected capacitors.
- R64 (100 Ω, 1 W) and C63 (1 nF, 100 V) form an optional series RC snubber across the transformer primary, after resonant capacitor C11. **Both are marked DNP**. Populate only after measuring ringing and choosing values for damping and resistor dissipation; all protection diodes and reservoir capacitors are populated.

PMODE and VREF use Pi 3.3 V. R61 (3.3 kΩ, 1%) sets a nominal 1 A current-regulation threshold using the driver's 1000 µA/A current mirror. R62 (62 kΩ, 1%) selects cycle-by-cycle regulation and latched overcurrent response. R5 holds sleep low by default; R63 pulls the local fault output up to 3.3 V, accessible at TP50. C61 (100 nF, 16 V) connects VCP to VM, and C62 (22 nF, 50 V) connects CPH to CPL, as required by TI. PWM must remain at or below 100 kHz.

The PD input remains selectable from 5–20 V, but firmware must request at least 6 V before enabling HV and verify that local `HV_BRIDGE` stays at or above 4.5 V under load after diode and wiring drops. Start transformer testing at reduced drive; driver voltage capability does not establish transformer flux, insulation, or multiplier limits. Measure supply/output excursions during switching, loss of load, sleep entry, and relay opening. Validate TVS pulse/repetition energy, bulk-capacitor ripple, diode losses, and temperatures before release. A TVS is not intended to dissipate sustained regeneration continuously.

## Electrical validation still required

The current USB-C design also needs a final part-level review for the MOSFET, current-sense resistor power, fuse trip curve, connector rating, decoupling voltage derating, and input transient protection. The schematic uses a single output MOSFET following the AP33772S application circuit’s simplified option; verify reverse-current behavior for the actual downstream supply.

## Measurement and illumination notes

The ADS1115 is a multiplexed 16-bit ADC with a 0.86 kSPS maximum rate. Firmware must use the configured PGA range, apply the actual divider and shunt tolerances, and calibrate the HV voltage and current channels against suitable instruments. Confirm the Pi HAT I²C pull-ups are 3.3 V and do not add parallel pull-ups without checking bus loading; the AP33772S requires external I²C pull-ups.

The TSL2591 calculates lux from its two optical channels using the manufacturer's empirical response formula. Its 188 µlux sensitivity supports detecting 0.001 lux, but absolute lux accuracy depends on source spectrum, sensor orientation, enclosure window, contamination, and calibration. Give U8 a clear optical aperture, shade it from board LEDs and corona glow, and calibrate in the final enclosure. The package has no integrated diffuser.

### Illumination break-off board and cable

J50 belongs on the main HAT; J51, U8, C80 (100 nF), and C81 (1 µF) belong on the break-off mini board. Both connectors use JST SH SM04B-SRSS-TB, 1.0 mm pitch, with the same numbered pinout:

| Pin | Net | Standard cable color |
| --- | --- | --- |
| 1 | GND | Black |
| 2 | 3.3 V from Pi | Red |
| 3 | SDA | Blue |
| 4 | SCL | Yellow |

Use a straight-through Qwiic/STEMMA QT four-wire cable; do not apply 5 V to this sensor. TSL2591 SDA is package pin 6, SCL is pin 1, VDD is pin 5, and GND is pin 3. INT (pin 2) and NC (pin 4) remain unconnected; firmware polls the device. C80/C81 must be beside U8, and the mini board adds no parallel I²C pull-ups or indicator LEDs. [SparkFun Qwiic connector/cable convention](https://www.sparkfun.com/qwiic-cable-breadboard-jumper-4-pin.html).

The PCB layout must put these parts inside a scored or perforated mini-board outline and route only GND, 3V3, SDA, and SCL through the sacrificial neck. After cutting all four copper connections, the cable restores them through J50/J51. Keep the connectors and decoupling on their respective sides of the break line, provide cable strain relief, and keep the optical board away from the HV section. Start cable operation at 100 kHz and verify rise times and the combined bus/cable capacitance before increasing speed. The schematic shows the intended attached/cabled electrical nets; this project currently has no PCB layout implementing the break line.

## High-voltage safety and bring-up

The Raspberry Pi and firmware are supervisory controls only. The existing mechanical lid interlock and relay must remove driver power independently of software. Keep the high-voltage multiplier, transformer secondary, ballast, divider, output connector, bleeders, and enclosure clearances under the established high-voltage review rules. Never probe an energized high-voltage node with a grounded oscilloscope probe.

Bring up in this order:

1. Run ERC and inspect every hierarchical rail, no-connect marker, power flag, and connector pin assignment.
2. Power the Pi HAT and sensor bus from a current-limited low-voltage source. Confirm 3.3 V, I²C addresses 0x48/0x29/0x76, and the AP33772S default 5 V state. Check J50/J51 pin order, then repeat the 0x29 sensor test through the cable with the neck disconnected. Verify GPIO25/`BULK_EN` stays low and U9 isolates downstream capacitance before a contract.
3. With the HV driver disabled, request each supported PPS setting from 5 V to 20 V. Confirm an explicit contract and sufficient current before enabling U9. Measure the USB-C rail, divider reading, eFuse ramp/inrush, switch behavior, input current, OVP/OCP response, and disable/discharge behavior on detach and reset.
4. Resolve the shared interlock/sleep connection before HV enable. Request at least 6 V, verify local bridge VM under load, then test the interlock at reduced energy, including reservoir discharge. Keep PWM at or below 100 kHz.
5. Calibrate the ADS1115 voltage/current channels and the TSL2591 lux calculation in the final optical and electrical assembly.
6. Only then test the transformer and multiplier at reduced drive, using rated isolated instrumentation and a closed interlocked enclosure. Check VM and output spikes, clamp energy and temperatures during switching and shutdown; leave R64/C63 DNP until the snubber is tuned.

## Schematic presentation

### Mandatory supply-symbol convention

All schematic edits must use actual KiCad power symbols for supplies and grounds, rather than plain text or local/global labels as the visible rail identifier. Apply this to 3.3 V, `VBUS_RAW`, `VBUS_IN`, `VIN_PROTECTED`, `HV_VM`, and high-voltage supplies and returns. Use a named custom power symbol when the standard library does not match the exact rail name. Preserve existing net names and scope; distinct supply stages and isolated returns must remain separate. Hierarchical pins may represent sheet interfaces, and signal or measurement nets may retain ordinary labels.

`PWR_FLAG` identifies a power source for ERC and must accompany, rather than replace, the appropriate supply symbol. Place flags on short net extensions and hide power-symbol and flag pin numbers. Keep fields clear of wires and other text, align symbols to the grid, and orient supplies upward and grounds downward where practical. Inspect every sheet for text-only supply rails and overlaps, then run ERC and compare connectivity after converting rail labels. This convention is mandatory for future edits.

The same rule is recorded in `hardware/pi5_corona_hat_direct/AGENTS.md` and in the project's Konnect design rules. Supply rails use named power symbols, with hierarchical pins retained at sheet interfaces. Explicit junctions and wire extensions connect the symbols to the buses; isolated `HV_RETURN` remains separate from logic GND. ERC source flags are on extensions with hidden pin numbers.

Revision F is exported to `hardware/pi5_corona_hat_direct/exports/pi5_corona_hv.pdf`, with six page previews alongside it. The host sheet adds cable connector J50 and the post-contract eFuse/bulk-power block; the illumination sheet contains the mini board and connector J51. The bridge sheet separates input energy protection, output clamps, PWM control, charge-pump capacitors, and the resonant transformer. KiCad 10.0.6 ERC reports zero violations. `exports/breakoff-pd-validation.json` records cable pin mapping, eFuse wiring, sensor placement, DNP status, retained-circuit connectivity and the calculated capacitance budget. `exports/inductive-protection-validation.json` retains bridge protection checks; `exports/protection-bom.csv` and `exports/breakoff-pd-bom.csv` list affected components and population status.

The source design's shared `INTERLOCK_OK` / `DRV_nSLEEP` connection is retained and still requires electrical review before HV enable. Revision E repairs the duplicate references and instance annotations; netlist export now has no annotation warning. The USB-C switch-drive validation and PCB transient/thermal checks above remain required.

## Manufacturer references

- Diodes AP33772S datasheet: <https://www.diodes.com/datasheet/download/AP33772S.pdf>
- TI ADS1115 product page and datasheet: <https://www.ti.com/product/ADS1115> · <https://www.ti.com/lit/ds/symlink/ads1115.pdf>
- ams OSRAM TSL2591 product page and datasheet: <https://ams-osram.com/products/sensor-solutions/ambient-light-color-spectral-proximity-sensors/ams-tsl25911-ambient-light-sensor> · <https://look.ams-osram.com/m/c901de8e97608f8/original/TSL2591-DS000338.pdf>
- TI DRV8876 datasheet and PWP pin table: <https://www.ti.com/lit/ds/symlink/drv8876.pdf>
- Diodes Incorporated SMBJ22A transient ratings: <https://www.diodes.com/part/view/SMBJ22A>
- Vishay VSSA310S-M3 blocking diode: <https://www.vishay.com/docs/89405/vssa310s.pdf>
- Vishay SS36 recirculation diode: <https://www.vishay.com/docs/88751/ss32.pdf>
- TI TPS25947 eFuse, pin table, slew/current-limit equations, and RPW0010A land pattern: <https://www.ti.com/lit/ds/symlink/tps25947.pdf>
- USB-IF USB PD Rev. 3.2 v1.0 specification bundle: <https://www.usb.org/sites/default/files/USB%20PD%20R3.2%20V1.0_1.zip>
- SparkFun Qwiic four-wire cable convention: <https://www.sparkfun.com/qwiic-cable-breadboard-jumper-4-pin.html>

## JLCPCB component assignments

Revision F includes hidden catalog/manufacturer fields on every placed part and assigns 149 catalog IDs among 152 items. See [procurement selections and holds](../hardware/pi5_corona_hat_direct/procurement/README.md), [complete BOM](../hardware/pi5_corona_hat_direct/exports/procurement-bom.csv), [JLCPCB matching BOM](../hardware/pi5_corona_hat_direct/exports/jlcpcb-bom.csv), and [exceptions](../hardware/pi5_corona_hat_direct/exports/procurement-exceptions.csv). Stock is a dated snapshot; no parts have been ordered or reserved.

Multiplier capacitors formerly C20–C31 are now C100–C111; sense-sheet R10/R11 are R90/R91 and the HV output connector is J60. Q1 now has the correct AO4262E SO-8 pad mapping and U7 has a grounded exposed pad 25. R71, C73, C60 and C11 footprints were matched to selected packages. Circuit capacitances and the conservative USB-PD budget are unchanged.

T1 requires external sourcing, TP50 is a PCB feature, and J60 has no acceptable catalog match: the original 250 V terminal is unsuitable for the 15 kV output. K1's selected 12 V coil also requires a fixed rated supply or interlock redesign before fabrication. These holds are documented rather than hidden with DNP flags; C63/R64 remain the only DNP parts. An compact two-layer placement now exists; routing and production CPL remain incomplete.

## Revision F high-voltage resistors

R30–R39 and the multiplier bleeders use **Bourns CHV2512-JW-107ELF**, **C2089706**, 100 MΩ / 5%, 1 W, 2512, 3 kV continuous maximum. There are 46 fitted parts: ten divider resistors and twelve banks of three series resistors. R40–R51 are the middle parts; R140–R163 complete the banks. See the [manufacturer datasheet](https://www.bourns.com/docs/Product-Datasheets/CHV.pdf) and [catalog snapshot](../hardware/pi5_corona_hat_direct/procurement/bourns-catalog-2026-10-03.json).

Three parts per bleeder make each bank 300 MΩ. At 6 kV per capacitor, nominal resistor voltage is 2 kV; the worst static split from ±5% tolerance is about 2.14 kV. At a 20 kV divider input, the worst tolerance split is about 2.19 kV per resistor. These calculations assume constant resistance; voltage coefficient and PCB leakage require validation.

R39's former wire bypass is corrected. Ten series 100 MΩ resistors above R8 + R9 (164 kΩ) give a nominal 6098.56:1 ratio: about 2.460 V and 15 µA at 15 kV. Calibrate at multiple operating voltages: the Bourns datasheet specifies up to ±300 ppm/V voltage coefficient for these values, measured only up to 500 V. Do not extrapolate that test into a guaranteed error at operating voltage.

A 300 MΩ / 1 nF bank has a nominal 0.30 s time constant (0.378 s with +5% resistance and +20% capacitance). An ideal constant-resistance model gives about 1.81 s for one 6 kV capacitor to fall below 50 V. This is a calculation, not a verified discharge time; measure the assembled multiplier before relying on a delay or safe-to-touch indication.
