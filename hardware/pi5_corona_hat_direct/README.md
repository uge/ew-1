# Working design — N-layout-17-hv-warnings

Open `pi5_corona_hv.kicad_pro` in KiCad 10. The adjacent PCB, root schematic,
five hierarchical sheets, custom symbol/footprint libraries and 3D assets form
the single working project. Standard KiCad 10 libraries must be installed separately.
Keep all these project files together; library tables use `${KIPRJMOD}` paths.

The board is two-layer, 1.6 mm thick, with a 196 × 120 mm carrier and five
break-off mini boards (231 × 120 mm overall envelope). Accepted LV routing,
the shortened HV return surge path and large warning graphics on both sides
are present in the native PCB. DNP parts are C63/R64; MP1 is a DNP mechanical reference.

| References | Current selection |
|---|---|
| C100–C111 | STE A12B1D102KN0B0S0N0 / C249245; 1 nF, 6 kV, Y5P, 10%, 10 mm pitch |
| R20–R29 | Bourns CHV2512-JW-106ELF / C2095568; 10 MΩ, 5%, 1 W, 3 kV, 2512 |
| D51 | hongjiacheng SMBJ22A / C49066946 |
| T1 | Coilcraft FL2015-4LD; external sourcing required |

Use the current JLCPCB deliverables for Gerbers/drills, BOM and CPL: 159 components
across 53 matching BOM rows. `exports/jlcpcb-bom.csv`, `exports/jlcpcb-cpl.csv` and
`exports/jlcpcb-gerbers.zip` are the upload files. Only T1 remains a purchased-component
external-source exception. DNP parts and PCB-only features are excluded.

[Front](renders/hv-warning-front.png) and [back](renders/hv-warning-back.png)
previews show current markings. These are diagnostic layer previews, not 3D assembly
fit certification. Dated procurement evidence remains under `procurement/`.
Stock evidence is a snapshot, not a reservation or guarantee of orderability.

[Validation/export instructions](layout/README.md) reproduce current outputs.
[Design status](AUDIT.md) records the unresolved HV and procurement issues.
The native files are the working design, not an archival or experimental copy.
Earlier tracked versions can be recovered from Git history.
