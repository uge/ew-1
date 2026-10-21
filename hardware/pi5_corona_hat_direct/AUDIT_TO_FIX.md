# Review findings to fix — N-layout-17-hv-warnings

**Status 2026-10-21:** every item below is fixed except the bench checks noted under H2
and the items AUDIT.md already tracks.

Review date: 2026-10-20. Board SHA-256 `a36866aa…e880` (matches
`exports/working-version.json`). A fresh KiCad 10.0.7 run gives ERC 0, DRC 0,
unconnected 0 and parity 0. The items below are not caught by those checks because
the custom rules in `pi5_corona_hv.kicad_dru` do not cover them. Nothing here is a
creepage or insulation qualification; see [AUDIT.md](AUDIT.md) for the standing holds.

Fix the High items before ordering boards.

## High

### H1. HV bleeder pads 3.3 mm from the outer board edge — FIXED 2026-10-20

> **Resolution:** R140–R161 moved into one row at y=63 on an 8 mm pitch (adjacent
> pads share a net). Every HV pad is now ≥10.25 mm from Edge.Cuts. New DRU rule
> "HV_STAGE to board edge" (10 mm) enforces it; it reports 21 violations on the old
> layout and passes on the new one. Voltage-audit edge failures fell from 11 to 2
> (the remaining two are L1).


- **Where:** top bleeder row at y=56: R140/R141, R148/R149, R156/R157. Pads are on
  SEC_A, CW_P1–CW_P5 and the intermediate nodes `Net-(R140/R148/R156-Pad2)`.
  The board edge is at y=51.
- **Problem:** the pads are 3.33 mm from the edge. Per
  `exports/spice-multiplier-report.json`, CW_P5 reaches about 11–12.2 kV.
  `exports/voltage_audit_report.json` already lists these as edge FAILs.
- **Why DRC misses it:** the `edge_clearance` rule in the `.kicad_dru` only covers
  `/04_sense_safety/HV_OUT` and `/HV_RAW`. Stage nets fall back to the 0.5 mm default.
- **Fix:**
  - Add an `edge_clearance` rule (≥10 mm, or scaled by voltage) for all HV_STAGE
    nets and the bleeder intermediate nodes.
  - Move or rotate the top bleeder row at least about 7 mm inward.
  - Re-run the voltage audit afterwards.

### H2. No hardware limit on output voltage — FIXED 2026-10-20 (bench check pending)

> **Resolution:** a latched hardware overvoltage trip was added on sheet 04:
> - U11 TLV7031 compares 0.5933 × HV_SENSE_BUF with a 1.65 V reference. The trip
>   point is 16.96 kV nominal.
> - D90/R104 latch it; D91 resets it while DRV_SLEEP_CMD is low.
> - Q2 AO3400A pulls DRV_nSLEEP low, with R105 in series after the K1 contact.
> - R106 reports the trip on GPIO26 (J2.37).
>
> The new nets were routed with KiCadRoutingTools, with all existing copper locked
> and kept out of the primary switching area. ERC 0, DRC 0, parity 0 and 14/14
> audits pass. The BOM is now 154 components / 53 rows.
>
> **Still open:** bench measurement of secondary amplitude vs frequency, and the
> trip threshold and latency. The sense filter (~16 ms) means the trip limits
> steady-state voltage, not fast overshoot.


- **Where:** C11 (120 nF film) in series with the T1 primary (FL2015-4LD, 44 µH
  nominal, 1:50); U2 DRV8876 current limit set by R61.
- **Problem:**
  - C11 and the primary resonate at about 69 kHz, which is almost the 68 kHz
    drive frequency.
  - The only hardware limit on amplitude is the 2.2 A DRV8876 trip. That allows
    roughly 2.2 A × ωL ≈ 41 V on the primary, or about 2 kV on the secondary. This
    reaches T1's 2000 V instantaneous secondary limit and its 40 V primary limit.
  - Six stages would then give about 25 kV open-circuit, against a 15 kV design basis.
  - This is a first-order estimate (the multiplier load shifts the resonance), but
    today output voltage is limited only by firmware.
- **Fix:**
  - Add a hardware overvoltage comparator on HV_SENSE_RAW (or the U4 output) that
    pulls DRV_nSLEEP low, in series with the existing K1 contact, latched until
    software clears it.
  - Measure secondary amplitude versus frequency and PD voltage on the bench at
    low PD voltage before running at 20 V.
  - Consider detuning C11 so the operating point does not sit on the resonant peak.

### H3. Stage clearance is a flat 4 mm against every net, including GND — FIXED 2026-10-20

> **Resolution:** four "HV stage N mm to LV" rules now require clearance from each
> stage, bleeder, divider and ballast node to any non-HV net, scaled by the node's
> peak voltage to ground:
> - ≤2.5 kV: 4 mm
> - ≤5 kV: 6 mm
> - ≤7.5 kV: 8 mm
> - >7.5 kV: 10 mm
>
> The existing 4 mm stage-to-stage rule is unchanged. The current layout passes.
> An injected GND track 5.7 mm from CW_S5 is flagged by the 10 mm tier.


- **Where:** the `HV_STAGE copper clearance` rule in the `.kicad_dru`; the
  HV_STAGE net class.
- **Problem:** CW_S5 and CW_P5 are about 12 kV above GND, yet an LV or GND trace
  4 mm away still passes DRC. The current layout is only safe because the LV area
  (x<102) is physically far from the multiplier; the rule won't protect future edits.
- **Fix:** add stage-net ↔ GND/LV/Default-class rules scaled to each node's DC
  voltage (for example, set per column position), keeping the 4 mm rule only
  between adjacent stage nodes.

## Medium

### M1. Firmware can't see driver faults or the bridge supply — FIXED 2026-10-20

> **Resolution:**
> - DRV_nFAULT now goes to GPIO5 (J2.29) on a global label.
> - U9 FLT goes to GPIO6 (J2.31), with a new R107 10 kΩ pull-up.
> - HV_BRIDGE/11 (R108 100 kΩ, R109 10 kΩ, C92 100 nF, on sheet 02) goes to
>   ADS1115 AIN3 as BRIDGE_VMON.
>
> Routed with KiCadRoutingTools at the full 0.2 mm clearance. Making room meant
> re-routing PD_VMON, DRV_IN2, EFUSE_DVDT and DRV_nSLEEP, and moving C72 left of
> U9. Two GND pour islands created by the new B.Cu routes were re-joined with one
> stitching via and two short links.
>
> ERC 0, DRC 0, unconnected 0, parity 0 and 15/15 audits pass.
> The BOM is now 158 components / 53 rows.


- **Where:**
  - U2 nFAULT goes only to R63 and TP50.
  - U2 IPROPI goes only to R61.
  - U9 FLT (pin 4) is unconnected.
  - ADS1115 AIN3 (U6 pin 7) is unused.
- **Problem:** firmware can't detect a latched OCP or over-temperature in the
  driver, an eFuse fault, or a sagging HV_BRIDGE. The handoff doc requires firmware
  to confirm HV_BRIDGE ≥ 4.5 V under load, but PD_VMON measures VBUS_RAW, which is
  before the eFuse and D50.
- **Fix:**
  - Route DRV_nFAULT and U9 FLT (with a pull-up) to free Pi GPIOs.
  - Put an HV_BRIDGE divider on AIN3, or IPROPI if primary current is the more
    useful measurement. Choose the divider ratio to stay within ADS1115 VDD+0.3 V
    at the D51 clamp voltage.

### M2. R13 5 mΩ current shunt measures nothing — FIXED 2026-10-20 (kept as a bench shunt)

> **Resolution:** as you chose, R13 stays (15 mV drop at 3 A) with two Kelvin test
> pads added: TP51 on ISENP and TP52 on VBUS_IN, each joined by a 0.2 mm trace
> from the inner edge of its R13 pad. They are copper features like TP50, not BOM
> or CPL parts. Measure I = V(TP51 − TP52) / 5 mΩ. DRC 0 and 16/16 audits pass.


- **Where:** R13 between ISENP and VBUS_IN. The ISENP net connects only F1 and R13.
- **Fix:** remove R13 (short it), or add the missing current-sense amplifier.
  Update the BOM/CPL either way.

### M3. U4 op-amp input has no protection — FIXED 2026-10-20

> **Resolution:** R110 (10 kΩ, C25804) now sits between HV_SENSE_RAW and U4 IN+.
> A full-surface flashover dumping 100 pF at 15 kV into C13 gives about a 15 V
> spike, which R110 limits to about 1.5 mA, inside the TLV9001's 10 mA input-clamp
> rating. I didn't add an external Schottky clamp because its leakage (µA-class
> when hot) would put an error on the 1 GΩ divider. DRC 0 and 17/17 audits pass.


- **Where:** HV_SENSE_RAW goes straight to U4 IN+ (pin 3), with only C13 to GND.
  The ADC side is protected by R7 and the D1 clamp.
- **Problem:** a flashover across R39 (about 1.5 kV across it at 15 kV) or a
  divider fault injects a transient straight into the TLV9001 input.
- **Fix:** add about 10 kΩ in series with IN+ and a low-leakage clamp to 3V3/GND
  (for example a BAT54S). Include its leakage in the divider error budget.

## Low

- **L1. FIXED 2026-10-20:** J60 moved 0.5 mm left to (233.25, 63.5). HV_OUT is now ≥10.5 mm from the edge and the voltage audit reports 0 edge failures. *(Original finding:)* HV_OUT is 9.999 mm from the edge against a 10 mm rule. DRC passes but
  the voltage audit marks it FAIL on both F.Cu and B.Cu. Add margin, for example
  ≥10.5 mm.
- **L2. FIXED 2026-10-21:** as you chose, R60 is now 10 kΩ 1 W 2512 (25121WF1002T4E / C270956). Waste drops to 40 mW / 2 mA at 20 V. The ~45 µF reservoir bleeds to <1 V in about 1.4 s (τ ≈ 0.45 s) after interlock shutdown. *(Original finding:)* R60 (1 kΩ across HV_BRIDGE) wastes power. It dissipates 0.4 W and draws
  20 mA continuously at 20 V. If it is only there to bleed the rail down, raise the
  value. If it absorbs regenerated energy, document the reason.
- **L3. FIXED 2026-10-21:** the report labels now name C249245 and CHV2512-JW-106ELF, and `spice_verify_multiplier.py` was re-run. The results are unchanged (open circuit 14.64 kV raw / 13.31 kV out; 50 µA point 8.67 kV out) because the nominal values are the same. *(Original finding:)* Stale SPICE report. `exports/spice-multiplier-report.json` lists
  superseded parts: Vishay S102M59Z5UU83L0R capacitors and CHV2512-FX-1005ELF 1%
  ballast resistors. Re-run with C249245 and CHV2512-JW-106ELF (5%).
- **L4. FIXED 2026-10-21:** `ionic_thrust_hv:D_SOD-323` now has a 3.5 × 2.0 mm F.CrtYd, and D3, D90 and D91 on the board were updated to match the library. DRC courtyard-overlap passes. `missing_courtyard` is still set to ignore: only MB1–MB5 (mouse-bites) and MP1 (Pi mechanical) lack courtyards now, and both are intentionally padless. *(Original finding:)* D3 (1N4148WS) has no courtyard. It's hidden because `missing_courtyard`
  is set to ignore in the `.kicad_pro`. Add a courtyard to the footprint, then
  consider setting the rule back to warning; MB1–MB5 and MP1 can be excluded
  individually.

## Already tracked in AUDIT.md (still open, re-verified)

- R14 uses C25816 and C18 uses C15849; neither ID matches the specified MPN. Both
  are still in `exports/jlcpcb-bom.csv`. Candidates are C25819 and C5673.
- T1 still has to be sourced externally.
- 3D models for U2 and U8 don't resolve.
- The voltage audit has 51 CRITICAL and 146 CAUTION items, mostly 6.2 mm
  diode-pad gaps between adjacent stages.

## After fixing

Run `layout/validation/refresh_exports.py` and re-run the voltage audit. Update
`AUDIT.md` and `exports/working-version.json`, and regenerate the JLCPCB package.
