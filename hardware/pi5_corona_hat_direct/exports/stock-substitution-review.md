# Accepted stock substitutions — N-layout-15-stock

The user accepted both selections and the 5% ballast tolerance on 2026-10-19.

| References | Quantity | Selected component | JLCPCB |
|---|---:|---|---|
| C100–C111 | 12 | STE A12B1D102KN0B0S0N0, 1 nF / 6 kV / Y5P / 10%, 10 mm pitch | C249245 |
| R20–R29 | 10 | Bourns CHV2512-JW-106ELF, 10 MΩ / 5% / 1 W / 3 kV / 2512, 200 ppm/°C | C2095568 |

Native hidden catalog fields and procurement assignments agree. All 22 parts remain populated.
Fresh JLCPCB responses show C249245: 3,773 warehouse / 2,156 available;
C2095568: 177 warehouse / 126 available. Stock is not reserved.

The new capacitor footprint, STE_A12B1D102K_P10.0mm, covers the catalog
11 × 4.5 mm body with a conservative 13 × 4.5 mm fabrication envelope
and 15 × 5.5 mm courtyard. Earlier sourcing notes mistakenly checked the
unrelated C_Radial_P10.0mm footprint. This update starts from the actual
CAP-TH_L15.0-W4.0-P10.00-D0.6 footprint and preserves its pad centers,
1.75 mm lands and 1.100024 mm drills byte-for-byte. Silk and courtyard
thickness are corrected. The old part's 3D model was removed. Height,
formed-lead dimensions/tolerances and HV pulse/bias qualification remain open.

Ten ballast resistors give 100 MΩ nominal, 95–105 MΩ at initial tolerance.
An ideal 15 kV source with shorted output gives 142.857–157.895 µA.
With one 10.5 MΩ part and nine 9.5 MΩ parts, the highest single-part
voltage is 1,640.625 V and dissipation is 0.25635 W. These are below
3 kV / 1 W ratings at 70°C; apply power derating above 70°C. These are
initial-tolerance, steady-state calculations, not arc-energy or transient-sharing
validation; TCR, VCR, leakage and self-heating require separate evaluation.

USB capacitance budgets remain 9.10242 µF at attachment and 97.34662 µF
post-contract because no USB capacitor or power-path topology changed.

Source comparison proves that all pads, drills, positions, tracks, vias,
zones, outline, pad nets and DNP states are preserved. Native before/after
netlist connectivity is identical. Project settings and custom rules are
byte-identical. KiCad 10.0.7 reports zero ERC/DRC violations, open connections
or schematic parity issues; all 13 connectivity audits pass.

The current matching BOM/CPL includes 141 components over 51 rows.
Only T1 remains a purchased-component external-source exception.
Production holds persist: previous HV insulation screening and arc qualification;
new capacitor height/lead/pulse qualification; unrelated R14/C18 catalog-ID
mismatches and D51 zero available order quantity. No unrelated selections changed.

Evidence: procurement/accepted-stock-parts-2026-10-19.json and
exports/stock-substitution-review.json. The prior native project is preserved
under revisions/N-layout-14-before-stock-substitution/.

Manufacturer resistor ratings: https://www.bourns.com/docs/product-datasheets/CHV.pdf
