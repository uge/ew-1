# Current design status — N-layout-17-hv-warnings

This is the canonical working design. It includes completed routing, the accepted
C249245 capacitors and 5% C2095568 ballast resistors, D51 C49066946, and large
high-voltage warning graphics on both sides. It is not a qualified production release.

Native KiCad 10 ERC, DRC, open-connection and schematic-parity counts are zero;
all 17 connectivity audits pass. Current machine-readable reports are
`exports/erc.json`, `exports/jlcpcb-drc.json` and `exports/jlcpcb-validation.json`.
`exports/manufacturing-archive-validation.json` binds verified Gerber payloads to
the current board hash. `exports/working-version.json` identifies the promoted design.

Design-review fixes from 2026-10-20/21 are recorded in [AUDIT_TO_FIX.md](AUDIT_TO_FIX.md):
- bleeder edge clearance and voltage-tiered HV rules
- the hardware 17 kV overvoltage trip
- firmware fault and bridge telemetry
- R13 Kelvin pads, the U4 input resistor, J60 edge margin, R60 at 10 kΩ, and SOD-323 courtyards

The hardware trip still needs bench characterization.

## Open qualification and procurement issues

- HV insulation screening (2026-10-21), using the 0.00305 mm/V screening coefficient:
  - Phase-coherent model (`exports/voltage_audit_report_coherent.json`): 0 critical,
    0 edge failures. Achieved by staggering the CW diodes ±3.25 mm and other
    re-placement; see AUDIT_TO_FIX.md.
  - Independent-envelope model (`exports/voltage_audit_report.json`): 37 critical, of
    which most are pad gaps inside single rated parts.
  Legacy screening coefficients are not standards compliance or certification.
- Arc energy, repetitive charging pulses, shutdown faults, material/environment,
  transformer operating conditions and external HV wiring need qualification.
- The selected capacitors match the 10 mm pitch; height, lead tolerances and
  voltage-bias/pulse behavior remain unqualified. The old generic 3D model was removed.
- R14/C18 catalog mismatches were corrected on 2026-10-21 at the user's request:
  - R14 now uses C25819, which is exactly 0603WAF4702T5E (47 kΩ). The former C25816
    is a 383 kΩ part and would have left Q1 under-driven.
  - C18 keeps C15849, with its MPN corrected to CL10A105KB8NNNC (1 µF, 50 V, X5R).
- U7 HUSB238A-BB001-QN16R boot voltage (2026-10-31, **confirmed on this board**):
  - Factory `SNK_PDO2` for `-BB001` is 28 V / 3 A (datasheet Ordering Guide, p. 19).
  - While `CONTROL1.ENABLE = 0` (`0x13` at power-up), internal PD functions are off and `VBUS_RAW` stays at default 5 V. As soon as `CONTROL1.ENABLE = 1` (`0x1b`) is set in I²C mode, `U7` completes its 150 ms `tCCdeb` attach debounce and automatically negotiates the highest source PDO up to 28 V (`20 V / 3.0 A` measured on `AIN2 = 19.92 V` with a 65 W SPR supply) before any host `SELECT_PDO` command. See [host/HUSB238A.md](host/HUSB238A.md).
  - U7.14 FLGIN is tied to GND, so nothing holds Q1 off. On an EPR source, 28 V on VIN_PD would exceed U9's 28 V absolute max and F1's 24 V rating, even with BULK_EN low.
  - Until fixed in hardware (FLGIN host/K1 control, GPIO-mode VSET strapping, or `-BB004` 5 V variant), feed J3 only from sources that cannot offer EPR (≤ 20 V SPR).
- 1N4148WS (C2128) assembly orientation (2026-11-01, bench-confirmed):
  - D3, D90 and D91 came back from JLCPCB rotated 180°, with the cathode on
    the wrong pad. They have been re-fitted by hand on this board.
  - `layout/generate_jlcpcb_cpl.py` `ROTATION_OFFSETS` needs a 180° entry for
    D3/D90/D91. Then regenerate the CPL and check it in the JLCPCB placement
    preview before the next order.
  - D5, D50, D51, D1/D4 and C60/C70 have no offset entry either; check them.
- **Hardware HV overvoltage trip unverified on the bench** (2026-11-01, user decision):
  - The injected-trip test was impractical. HV_SENSE_RAW has no test point and
    no adjustable source was available.
  - The U4/U11 trip at 16.96 kV, the D90 latch, the D91 clear and the Q2
    action are untested. D90/D91 were hand-re-fitted after reversed assembly.
  - Until verified, stage 7 runs with firmware-only OV protection: a 5 V
    contract and an AIN0 > 0.50 V (≈ 3 kV) cutoff. See
    [host/STAGE6_PLAN.md](host/STAGE6_PLAN.md).
  - Next revision: add a test point on HV_SENSE_RAW, or a Pi-controlled
    self-test injection into OV_SENSE.
- **HV gain shortfall (2026-11-01, bench):** best HV_OUT ≈ 0.36 kV at a 4.8 V
  bridge (complementary, 32 kHz).
  - The response peaks at 26/32 kHz, not at the 68 kHz design drive point,
    and is ~0 by 50 kHz. A linear extrapolation gives only ≈ 1.5 kV at 20 V.
  - The drive-to-secondary path was never modelled (the SPICE run drove the
    secondary directly).
  - See [host/GAIN_SHORTFALL.md](host/GAIN_SHORTFALL.md).
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
