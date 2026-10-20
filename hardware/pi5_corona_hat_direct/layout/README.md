# Compact two-layer layout — N-layout-14-surge

Open `../pi5_corona_hv.kicad_pro` in KiCad 10. The low-voltage placement/routing and subsequent surge-path improvement were completed on 2026-10-19. The carrier remains 196 × 120 mm (x50–246, y51–171), with an overall 231 × 120 mm envelope including the break-off boards. Connectors, Pi mechanics, HV multiplier/transformer/divider positions and HV-net routing retain their starting poses and geometry; the D5/R90 moves are described below.

## Previous low-voltage optimization — N-layout-13-LV

Forty-three footprint poses changed. USB-PD/eFuse support parts now sit closer to their ICs, the bridge parts form a tighter group near the transformer, and the relay regulator and sensor/ADC support parts have shorter connections. The bounded translation/rotation search weighted power nets twice when evaluating per-net Euclidean minimum spanning trees. This is a local placement improvement, not a claim of a global optimum or actual routed-length reduction.

The low-voltage pad-tree metric, excluding ground because it uses a plane, fell from **1927.549 to 1269.254 mm (34.15%)**. The board went from **144 unconnected items to zero**. Both copper layers are used; the existing LV ground-plane envelope and HV no-pour rule area remain.

Power trunk targets are **1.5 mm** for USB-PD/bridge supplies, **1.0 mm** for bridge outputs, **0.6 mm** for 3V3 and **0.5 mm** for COIL_3V. A clearance-aware pass widened 460 routed segments. Pin escapes and constrained branches are narrower where necessary. The report records actual routed length by width for each power net; width alone does not qualify current capacity without copper-weight and thermal assumptions.

Preserve the staggered U7 fanout and the direct U2 charge-pump capacitor connections before attempting further routing. The accepted footprint and reference poses are recorded in `optimized-placement.json`. The board generator discards accepted routing.

## Validation and artifacts

- Native KiCad 10.0.7 DRC: **0 violations, 0 unconnected items**.
- Native schematic parity: **0 issues**.
- Native ERC: **0 violations**.
- Refreshed native-netlist audit: **13 checks pass**.
- All pad nets, packages, DNP states and fixed mechanical/connector/HV poses preserved.
- All HV net track geometry preserved; project settings and custom rules preserved byte-for-byte.

See `../exports/lv-layout-optimization.json`, `../exports/lv-layout-drc.json`, `../exports/lv-layout-erc.json` and `../exports/lv-layout-13-top.svg`. The exact prior working board/project/rules are in `../revisions/N-layout-12-before-LV-optimization/`, including edits that were already uncommitted before this optimization.

Native routing/DRC checks do not replace the existing HV insulation, shutdown and component qualifications described in `validation/README.md`. Manufacturing archives were not regenerated and do not represent this layout revision.

## HV return improvement — N-layout-14-surge

D5 and R90 now sit beside the unchanged J61 terminal. The 1.5 mm front-side clamp path is **8.219 mm with zero layer changes**, down from 33.85 mm / three changes. The shunt path is **11.625 mm with zero layer changes**, down from 40.538 mm / three changes. A direct clamp-ground connection, parallel ground vias and widened 1.5 mm generator-ground trunk replace the former detour. The sense branch starts separately at R90.1.

The schematic, packages, values, net assignments, other footprint poses, HV-net routing and project/custom rules are unchanged. Native DRC/ERC/parity/open counts are zero; all 13 connectivity audits pass. See `../exports/hv-return-layout-review.md`, `../exports/hv-surge-improvement.json` and `../exports/hv-return-layout.png`. The prior revision is in `../revisions/N-layout-13-before-surge-path/`. The earlier LV reports and SVG describe N-layout-13-LV; the current SVG is `../exports/hv-layout-14-top.svg`. Existing insulation screening failures and surge qualification remain open.
