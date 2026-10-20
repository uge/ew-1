# HV return layout — N-layout-14-surge

The surge path was improved on 2026-10-19. J61 and all HV multiplier, transformer and divider footprints retain their positions. D5 moved to (132.5,158), rotation 90°, and R90 moved to (132.5,162.95), rotation 180°. Packages, ratings, polarity, pad nets and DNP flags are unchanged.

| Path | Before | After | Layer changes before → after |
| --- | ---: | ---: | ---: |
| J61 → D5 cathode | 33.85 mm | **8.219 mm** | **3 → 0** |
| J61 → R90.1 | 40.538 mm | **11.625 mm** | **3 → 0** |

Lengths are routed copper centerlines, excluding vertical barrel length. The clamp path is 75.72% shorter; the shunt path is 71.32% shorter. Incoming return copper is now 1.5 mm wide and reaches the clamp directly on F.Cu. The shunt leg is 0.8 mm wide and also stays on F.Cu.

D5 has a new short, wide front-side connection to generator ground, with two parallel 0.8 mm / 0.4 mm drilled ground vias at (127.5,150.5) and (128.5,150.5). The associated back-side generator-ground trunk was widened from 0.8 to 1.5 mm. The existing grounding and isolation topology is preserved: D5 is across R90, J61 reaches generator ground through the 10 kΩ shunt, and T1.6/9/10 remain on GND. No copper bypasses R90.

The positive sense branch now starts at R90.1 independently of the incoming surge trunk. R91 remains in the LV area; J61-to-R91 routed length increases from 53.914 to 63.427 mm. This separates the pickup from the surge-current segment but does not establish improved ADC noise performance. The low-voltage divider output and C13 ground were rerouted locally to clear the new clamp path; R39 and all divider connections remain intact. No capacitor or resistor value changed.

Validation: native KiCad 10.0.7 DRC **0 violations**, **0 unconnected items**, **0 schematic parity issues**; native ERC **0 violations**; all **13 refreshed connectivity audits pass**. All other footprint poses, HV-net track geometry, project settings and custom clearance rules were preserved. The closest same-layer sensed-return/HV copper spacing is **7.413 mm** at R142.2, above the current 4 mm stage rule.

The before/after legacy insulation screen still reports **51 critical pairs, 146 cautions and 11 edge-screening failures** in each case. Its all-board minimum screened same-layer spacing changes from 4.452 to 4.319 mm; native rules pass. These screening coefficients are not a certification standard. Arc energy, TVS pulse capacity, transient overshoot, ADC rail injection, enclosure, coating/materials and external return paths remain unqualified. This is a geometric routing improvement, not an arc-survival or fabrication-release claim. Existing manufacturing archives were not regenerated.

The previous board/project/rules and original review are preserved in `../revisions/N-layout-13-before-surge-path/`. See [copper view](hv-return-layout.png), [geometry](hv-return-layout-geometry.json), [change report](hv-surge-improvement.json), [DRC](hv-surge-drc.json) and [ERC](hv-surge-erc.json).
