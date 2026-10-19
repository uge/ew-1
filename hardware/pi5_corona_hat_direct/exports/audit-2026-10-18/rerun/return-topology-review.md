# Return-topology review — 2026-10-18

**Conclusion:** The current schematic and PCB implement the correct topology for measuring external electrode current with a ground-referenced low-side shunt. The existing transformer-return assertion describes the former common-return topology and is inappropriate for that measurement. Do not reconnect the transformer/multiplier return to /HV_RETURN just to satisfy it.

Fresh native netlist and PCB pad inspection agree:

- Generator ground: T1.9/T1.10/T1.6, C101.1, D10.2, R142.1, R90.2 and D5.2 are on GND.
- Sensed external return: J61.1, R90.1, D5.1 and R91.1 are on /HV_RETURN.
- ADC path: /HV_RETURN → R91 (10 kΩ) → /HV_CURR_ADC → U6.5 (ADS1115 AIN1). C14 returns to GND; D4 clamps the ADC node to GND/3V3.
- D5 is across R90, cathode to /HV_RETURN and anode to GND. This orientation is consistent with a positive normal return voltage.

Normal conventional-current path:

```
grounded HV generator → multiplier → ballast → J60
                                              ↓
                                       external electrode load
                                              ↓
generator GND ← R90 (10 kΩ) ← /HV_RETURN ← J61
```

The multiplier bleeders and HV voltage divider return directly to GND, so their currents are excluded from R90's reading. With negligible ADC/protection leakage, V(HV_RETURN) = I(external load) × 10 kΩ. The voltage divider measures HV_OUT relative to GND; the electrode voltage between J60 and J61 is that value minus V(HV_RETURN).

## Simulation cross-check

An eight-case ngspice comparison used the native-derived passive circuit, 1250 V peak / 68 kHz source and 350 Ω secondary series resistance. The former topology was reconstructed only for comparison by moving the source return, C101.1, D10.2 and R142.1 to /HV_RETURN. No design file was changed.

| External DC load | Current circuit: V(return) | Current inferred through R90 |
| --- | --- | --- |
| 0 µA | 0 V | 0 µA |
| 10 µA | 0.100 V | 10 µA |
| 50 µA | 0.500 V | 50 µA |
| 100 µA | 1.000 V | 100 µA |

With the former common-return topology, load current closes directly into the generator return rather than through R90. At a 50 µA external load the simulation instead gives approximately −0.0867 V across R90 (−8.67 µA), reflecting the ground-referenced divider's return current. Thus restoring that topology would defeat the intended positive external-current measurement.

## Limits and remaining work

- This confirms normal current-path functionality, not surge or arc safety. The comparison omits the ADC input and protection devices; their loading, leakage, rail injection and transient behavior need separate qualification. D5 is a 15 V TVS, not a direct 3.3 V ADC clamp; R91/D4 provide the subsequent protection stage.
- All external electrode return current must use J61. A chassis, earth, USB/instrument ground or other connection that joins /HV_RETURN directly to GND bypasses R90 and can make the reading under-report the actual current.
- HV_RETURN is ground-referenced through R90 and protection devices; it is not a galvanically isolated system return.
- The required Ruby assertion and AGENTS.md transformer-return description still specify the former wiring. They need a documented update to preserve the generator-GND/external-return separation and explicitly reject a direct short between those nets. This review leaves both unchanged and records why the assertion currently fails.
- Guard-terminal suitability on the actual transformer, current-loop copper geometry and physical fault-current behavior remain unqualified.

Evidence: fresh export `/tmp/return-check.xml`; native PCB pad inspection; `return-topology-simulation.json` in this directory. The board and schematic were not saved or altered.
