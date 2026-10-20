# HV return layout review — N-layout-13-LV

Reviewed 2026-10-19 using KiCad 10.0.7 native copper polygons and a fresh native DRC with schematic parity. The PCB and schematic were not modified.

**Finding: correct normal-current topology and no native DRC failures; improve the clamp/return geometry before surge qualification.**

## Connectivity

The external current path is J61 → /HV_RETURN → R90.1 → R90 (10 kΩ) → R90.2/GND → generator return. T1.6/9/10 remain on GND, not /HV_RETURN. D5 cathode is on /HV_RETURN and its anode is on GND, in parallel with R90. R91.1 picks up /HV_RETURN; R91.2 feeds U6.5 through /HV_CURR_ADC with C14/D4 filtering and clamping. No copper short bypasses R90 in the native check. Off-board/chassis connections were not assessed.

## Measured layout

| Routed path | Copper centerline length | Via layer changes | Direct pad-center distance |
| --- | ---: | ---: | ---: |
| J61 → R90.1 | 40.54 mm | 3 | 24.42 mm |
| J61 → D5 cathode | 33.85 mm | 3 | 19.95 mm |
| J61 → R91.1 | 53.91 mm | 3 | 35.65 mm |

Lengths exclude vertical barrel length. The 0.8 mm return trunk runs from J61 on B.Cu to (128.5,166), changes to F.Cu for 3.5 mm, changes back at (128.5,169.5), then travels west along B.Cu to the D5/R90 branches. Each front-side SMD branch has another via. The two layer changes around the 3.5 mm segment are a clear target for rerouting, subject to the crossing sense nets and existing HV rules.

1. **Highest priority: shorten the connector-to-clamp path.** D5 is reached only after 33.85 mm and three vias. This adds avoidable impedance/inductance to an incoming transient path. Cluster J61/D5/R90 more tightly, route directly into the clamp node, and give D5 a short, deliberate route back to generator GND. Preserve the HV no-pour area and voltage-dependent clearances. This is a layout concern, not a simulated or measured arc-failure prediction. TI recommends protection close to the connector and minimizing source-to-TVS-to-ground inductance ([SLVA785, section 4](https://www.ti.com/lit/an/slva785/slva785.pdf)); this general principle does not itself qualify this HV arc circuit.
2. **Lower priority: make the sense pickup deliberate.** R91 sits about 12 mm west of the R90 branch on the same bottom return trunk, rather than taking a separate connection at the shunt pad. The ADC filter/clamps remain near the bottom edge while U6 is at (81,112), so the filtered signal has a long route through the power region. A separate pickup from R90.1 and a quiet shunt-ground reference, with filtering near the ADC where practical, would reduce shared-path/noise exposure. With a 10 kΩ shunt and 150 µA nominal current, copper resistance is not the dominant DC error; do not confuse this with a milliohm high-current shunt problem.
3. **Steady-current width and native spacing pass.** At 150 µA, the 10 kΩ shunt produces 1.5 V and dissipates 0.225 mW. The main return copper is 0.8 mm; the R91 sense spur has 0.2 mm segments. The nearest same-layer HV copper is R142.2, 7.5478 mm from the return pad/copper, satisfying the present 4 mm stage rule. Neither this width nor native DRC proves survival of a real arc.

Fresh native DRC: **0 violations, 0 unconnected items, 0 schematic parity issues**. Creepage/material/coating/environment, real arc energy, TVS pulse limits, current-loop inductance, ADC rail injection and off-board return paths remain outside this geometric check. In particular, D5 is a 15 V TVS; do not infer an ADC-safe clamp voltage from its name.

Evidence: [copper view](hv-return-layout.png), [measured geometry](hv-return-layout-geometry.json). Red is sensed /HV_RETURN, gray is GND, yellow is modelled HV copper and blue is other copper. The view is explanatory; native DRC uses the actual copper and holes.
