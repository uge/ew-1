# Insulation and shutdown verification

Run from the repository root using the system Python with KiCad 10 pcbnew, Shapely 2, NumPy, SciPy and matplotlib installed. ngspice and kicad-cli must be on PATH.

```
/usr/bin/python3 hardware/pi5_corona_hat_direct/layout/validation/test_safety_analysis.py
/usr/bin/python3 hardware/pi5_corona_hat_direct/layout/validation/map_board_voltages.py --pcb hardware/pi5_corona_hat_direct/pi5_corona_hv.kicad_pcb --output-dir hardware/pi5_corona_hat_direct/exports
/usr/bin/python3 hardware/pi5_corona_hat_direct/layout/validation/native_multiplier.py --external-cap-pf 100 --duration 5
/usr/bin/python3 hardware/pi5_corona_hat_direct/layout/validation/spice_verify_multiplier.py
/usr/bin/python3 hardware/pi5_corona_hat_direct/layout/validation/regenerate_manufacturing.py
```

The insulation checker refills zones in memory, uses native pad/track/via/zone copper polygons and actual Edge.Cuts including NPTH holes, and checks every same-layer net pair with at least 500 V worst-case differential. Non-flashed mechanical pads are excluded from copper. An outward 1 µm tolerance prevents polygon approximations from overstating clearance. Phase envelopes include negative secondary excursions and moving pump potentials; they conservatively combine endpoints independently. No component or transformer-breakout exception receives an automatic pass. JSON retains every qualifying pair; the console shows the worst 20. Legacy 0.00305/0.005 mm/V coefficients are screening thresholds, not insulation certification. All HV copper is screened against a conservative 10 mm edge target. Opposite-layer geometry is reported for material qualification without a dielectric-withstand pass.

The shutdown model exports a fresh native netlist and uses actual resistor/capacitor values, diode orientation, 164 kΩ sense leg and ground return. It charges the full passive network for 30 ms, checks cycle-to-cycle convergence, initializes every capacitor terminal from four AC phases and checks both all stored-node voltages to ground and capacitor differential voltages throughout discharge. The default run comprises 104 scenarios: four phases × two secondary termination surrogates × (nominal plus twelve individual bleeder-bank opens). One open resistor removes its bank. Output/cable capacitance defaults to 100 pF and must be set to the real installation maximum. Components use nominal tolerances and a generic diode model. The secondary models (350 Ω to ground and 1 TΩ to ground) are sensitivity cases, not a qualified transformer/bridge shutdown model. A null threshold time means at least one scenario has not discharged within the requested window; it never means zero seconds. No automatic enclosure access time is certified.

Current results: 57 same-layer screening failures, 143 cautions and 0 edge screening failures (after removing East HV mounting holes H5/H6 and shifting H3 to (105, 55)). Nominal shutdown cases reach the all-node 50 V threshold in at most about 0.933 s; some single-open cases remain above threshold at 5 s, up to about 1.225 kV. Physical insulation, shutdown and component qualification remain required. `AUDIT.md` historical production-ready claims are superseded by these results.

Manufacturing regeneration exports fresh Gerbers and separate plated/nonplated drill files into a temporary clean directory. Both ZIPs are checked for payload integrity, exact drill membership and plating headers. `exports/manufacturing-archive-validation.json` records file hashes and the source board hash. The old loose `exports/gerbers` directory is not used as an archive source; its historical mixed drill file may still exist. Board and schematic files are not saved by these tools.
