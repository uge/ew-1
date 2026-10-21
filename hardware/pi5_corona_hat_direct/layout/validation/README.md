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
The current result is in `exports/voltage_audit_report.json`: 51 critical pairs,
145 cautions and 0 edge-screening failures. These remain release holds.

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
