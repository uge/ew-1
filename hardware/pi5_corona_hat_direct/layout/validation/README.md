# Working design verification

From the repository root, use KiCad 10, Ruby and the system Python with pcbnew:

```sh
/usr/bin/python3 hardware/pi5_corona_hat_direct/layout/validation/refresh_exports.py
```

This performs current native netlist/audit/ERC/DRC/parity and manufacturing checks.
It does not save or regenerate the native PCB. The design source hashes are
recorded in `exports/working-version.json`.

For insulation geometry screening, install Shapely 2, NumPy, SciPy and matplotlib:

```sh
/usr/bin/python3 hardware/pi5_corona_hat_direct/layout/validation/map_board_voltages.py --pcb hardware/pi5_corona_hat_direct/pi5_corona_hv.kicad_pcb --output-dir hardware/pi5_corona_hat_direct/exports --no-plot
/usr/bin/python3 hardware/pi5_corona_hat_direct/layout/validation/test_safety_analysis.py
```

The checker uses native pad/track/via/zone copper polygons, in-memory zone refill,
actual outlines and NPTH holes, with 1 µm outward geometry tolerance. Phase envelopes
conservatively combine independent endpoints. No package/breakout gets an automatic
pass. Legacy 0.00305/0.005 mm-per-volt coefficients are screening thresholds, not
certification. Opposite-layer distances do not certify material withstand.
Add `--coherent` to evaluate the phase-coherent Cockcroft-Walton model. In it, every
pump-column node is DC + k·SEC_A with k=1, and smoothing, ballast and divider nodes are
DC. Pair differences then use the shared secondary phase instead of independent
extremes. The SPICE phase snapshots support this: P-node differences stay at 2.45 kV
at every phase.

Current results (2026-10-21):
- `exports/voltage_audit_report.json` (independent envelopes): 37 critical, 159
  caution, 0 edge failures. Most criticals are pad gaps inside single rated parts,
  scored at envelope voltages.
- `exports/voltage_audit_report_coherent.json`: 0 critical, 136 caution, 0 edge
  failures; minimum margin +0.7% (CW_S5–HV_RAW).

Both use the legacy 0.00305 mm/V coated-board coefficient. That is screening, not
qualification.

Additional simulation tools require ngspice and the scientific Python packages:

```sh
/usr/bin/python3 hardware/pi5_corona_hat_direct/layout/validation/native_multiplier.py --external-cap-pf 100 --duration 5
/usr/bin/python3 hardware/pi5_corona_hat_direct/layout/validation/spice_verify_multiplier.py
```

The shutdown model exports a fresh native netlist and initializes the full passive
ladder at four phases. It evaluates nominal plus single bleeder-bank opens and two
secondary termination surrogates. The default 100 pF external capacitance must be
replaced with the installation maximum. Nominal-tolerance components and generic
diode/secondary models do not qualify real transformer/bridge shutdown or an
access delay. Null threshold times never mean zero discharge time.

Gerbers are generated in a fresh temporary directory, with separate metric PTH/NPTH
drills and verified ZIP payload/plating headers. Only the canonical
`jlcpcb-gerbers.zip` and the current revision package are retained. Historical
loose Gerbers and mixed drill files are no longer present.
