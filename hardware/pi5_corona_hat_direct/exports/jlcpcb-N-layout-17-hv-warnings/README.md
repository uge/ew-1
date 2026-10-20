# JLCPCB exports — N-layout-17-hv-warnings

Large bold DANGER HIGH VOLTAGE / stored-charge warnings and two lightning
triangles are on each silkscreen layer. Back markings read from the underside.
Front/back previews and silkscreen validation are included.

Canonical working-design exports generated with KiCad 10.0.7.
Upload gerbers.zip for the two-layer, 1.6 mm PCB. It contains copper, mask,
silkscreen, paste, outline, and separate metric PTH/NPTH drill files.
Upload bom.csv and cpl.csv for assembly: 141 components / 51 BOM rows.
CPL coordinates use mm, X right and Y up from KiCad absolute origin;
negative Y values are intentional. Rotations are counterclockwise with existing
JLC library offsets. Review placement/orientation in the JLCPCB assembly preview.

Accepted substitutions: C100–C111 = C249245, R20–R29 = C2095568 (5%).
D51 now uses hongjiacheng SMBJ22A / C49066946. Its current positive stock
evidence and metadata-only geometry check are in d51-substitution-review.json.
Dated stock evidence and electrical/footprint review are included; stock is not reserved.
manual-external-parts.csv contains 1 required externally sourced
component(s): T1. C63/R64 remain DNP; MP1 is a mechanical reference;
copper-only terminations and test pads require no purchased component.
THT/manual assembly service and component stock must be confirmed at order.

Zero ERC/DRC violations, opens and schematic parity issues; 13 connectivity
audits pass. Exact BOM/CPL reference and centroid correspondence and Gerber
archive payload hashes were validated. Copper/drills/placements/nets and DNP
states are unchanged by the substitutions. Capacitor drawings/courtyard and
procurement metadata were updated; its prior generic 3D model was removed.

RELEASE HOLD: existing HV insulation and arc qualification remain open.
Capacitor height, lead tolerances and pulse/bias behavior remain unqualified.
The unrelated R14/C18 catalog-ID mismatches remain unresolved. The old
D51 zero-quantity hold is superseded by the accepted C49066946 substitution.
stock-substitution-review describes N-layout-15 before the D51 change; its
old D51 stock warning is superseded by d51-substitution-review.json.
Dated procurement evidence is retained under procurement/ in the working project.
These files are manufacturing exports, not a qualified 15 kV production release.
