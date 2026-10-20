# Current design status — N-layout-17-hv-warnings

This is the canonical working design. It includes completed routing, the accepted
C249245 capacitors and 5% C2095568 ballast resistors, D51 C49066946, and large
high-voltage warning graphics on both sides. It is not a qualified production release.

Native KiCad 10 ERC, DRC, open-connection and schematic-parity counts are zero;
all 13 connectivity audits pass. Current machine-readable reports are
`exports/erc.json`, `exports/jlcpcb-drc.json` and `exports/jlcpcb-validation.json`.
`exports/manufacturing-archive-validation.json` binds verified Gerber payloads to
the current board hash. `exports/working-version.json` identifies the promoted design.

## Open qualification and procurement issues

- HV insulation screening still finds critical proximity/edge cases. The current
  `exports/voltage_audit_report.json` contains the full geometry-screening result.
  Legacy screening coefficients are not standards compliance or certification.
- Arc energy, repetitive charging pulses, shutdown faults, material/environment,
  transformer operating conditions and external HV wiring need qualification.
- The selected capacitors match the 10 mm pitch; height, lead tolerances and
  voltage-bias/pulse behavior remain unqualified. The old generic 3D model was removed.
- R14 currently assigns C25816 to specified MPN 0603WAF4702T5E; catalog evidence
  resolves that ID to a different resistance. Exact-MPN candidate is C25819.
- C18 currently assigns C15849 to specified MPN CL10A105KA8NNNC; catalog evidence
  resolves that ID to another MPN. Exact-MPN candidate is C5673.
- The user has not requested either R14/C18 correction; neither is represented as fixed.
- T1 remains externally sourced. Four-switch contact mapping/load ratings and Pi
  standoff/connector/enclosure assumptions remain to be confirmed physically.

D51's former C224015 stock shortage was resolved by the user-selected C49066946.
Its catalog ratings were verified, but the signed manufacturer datasheet link
was unavailable; no additional pulse qualification is claimed.

The ten 10 MΩ / 5% ballast parts give 95–105 MΩ at initial tolerance. With an
ideal 15 kV source and a shorted output, current is 142.857–157.895 µA; worst
initial single-part sharing is 1,640.625 V / 0.25635 W. Temperature derating,
VCR, leakage and fast transients are separate qualifications. Do not treat
summed component voltage ratings as proof of system withstand.

C63 and R64 form an optional primary RC snubber (1 nF / 100 Ω) and remain DNP.
The proposed values have not been validated against measured switching ringing.
Neither is omitted because of stock or assembly process.

Current selection/marking evidence:
`exports/stock-substitution-review.json`, `exports/d51-substitution-review.json`,
`exports/hv-warning-silkscreen-review.json`, and dated files in `procurement/`.
Older source hashes inside substitution reviews identify the design state when
that specific change was applied; the working-version manifest is authoritative
for the current PCB. Historical production-ready claims are superseded by this file.

Two pre-existing standard-library 3D references do not resolve on this installation:
U2 TSSOP-16-1EP_4.4x5mm_Pitch0.65mm_EP3.4x5mm.step and
U8 OptoDevice DFN-6_2x2.4mm_P0.65mm.step. All project-local model references
resolve. These render-only issues were preserved during cleanup so the native
checkpoint remains byte-identical; they do not change copper or connectivity.
