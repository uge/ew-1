Audit of current working-tree board, 2026-10-18

Board: pi5_corona_hv.kicad_pcb, revision N-layout-12-120mm. Includes uncommitted changes. Two copper layers, 167 footprints including mechanical/board-only features, 1247 tracks/vias. Nominal carrier 196 × 120 mm; overall envelope including tabs 231 × 120 mm.

Disposition: hold fabrication release pending the findings below. No board, schematic, or manufacturing archive was changed by this audit.

1. High priority — fabrication archives include overlapping drill sets.

Both exports/jlcpcb-gerbers.zip and exports/pi5_corona_hv_gerbers.zip contain pi5_corona_hv.drl (MixedPlating) alongside pi5_corona_hv-PTH.drl and pi5_corona_hv-NPTH.drl. This makes the drill input ambiguous and duplicates the hole definitions across files. Build archives from a clean staging directory with only the chosen PTH/NPTH pair, then inspect the fabrication preview and plating assignment.

2. High priority — voltage-analysis PASS does not establish insulation adequacy.

layout/validation/map_board_voltages.py:367–445 compares nets >=500 V only against nets <=50 V; it misses clearance between two elevated stage nets. Track samples are centerline coordinates (157–180); width is stored but not subtracted from measured distance. Edges are hard-coded and evaluated against feature coordinates rather than copper boundaries (534–542). Package pairs automatically receive PASS_COMPONENT, while selected transformer breakout geometry receives PASS_BREAKOUT even below the script's own calculated requirement. The existing JSON gives one such breakout 6.067 mm against a calculated 7.625 mm requirement, yet marks it PASS_BREAKOUT.

Correct the geometry and pair coverage and explicitly qualify exceptions before relying on the report. This finding concerns incomplete verification; it is not a determination of a specific insulation standard violation or a replacement for physical HV testing.

3. Medium priority — required connectivity regression fails after return-topology changes.

Fresh native netlist: T1.9, T1.10, C101.1, D10.2 and R142.1 connect to GND. J61.1, R90.1, D5.1 and R91.1 remain on /HV_RETURN. The check at layout/validation/check_audit_nets.rb:38 requires T1.9/T1.10 on the latter net, so that group fails. The other 12 connectivity groups and transformer center-tap NC assertion pass when checked independently.

J61 load-return current can still flow through R90: the finding does not mean all current sensing is bypassed. Reconcile the intended topology, measurement coverage, instructions, and regression assertions; validate the revised return/arc-current path before release. Native schematic parity passes because schematic and PCB agree on the changed topology.

4. Medium priority — release documentation and validation summary describe older layouts.

AGENTS.md specifies M-layout-8, 148 mm carrier height and 191 unconnected items. layout/README.md describes N-layout-9 with the same incomplete-routing count. Current board is N-layout-12-120mm and fully connected. exports/jlcpcb-validation.json still identifies revision K and KiCad 10.0.6, with catalog evidence dated October 2–3, despite subsequent USB-PD and connector changes. Refresh validation from the exact release files and distinguish unresolved component qualification from historical checks. The existing production_release:false flag should remain until resolved.

Verification performed

- KiCad CLI version 10.0.7.
- Native PCB DRC with --severity-all --schematic-parity --refill-zones: zero violations, zero unconnected items, zero schematic parity issues. No --save-board used.
- Native schematic ERC: zero violations.
- Fresh native XML netlist and the project's safety/connectivity assertions, executed against a temporary manifest without replacing the project's manifest.
- Board metadata/pad-net inspection with KiCad 10 pcbnew, without saving.
- Visual inspection of the existing PCB PDF; manufacturing archive member and drill header inspection.

Ignored check categories remain configured, including missing courtyard, footprint filter/type mismatch, via centering and tuning geometry. Thus zero DRC is a pass of enabled rules, not an independent fabrication or 15 kV certification. Supplier stock, custom package dimensions, connector mating, Pi standoff fit, repetitive diode pulses, insulation system and physical HV performance were not requalified by this audit.

Evidence files in this directory: ew-audit-drc.json, ew-audit-erc.json, ew-audit-net.xml.
