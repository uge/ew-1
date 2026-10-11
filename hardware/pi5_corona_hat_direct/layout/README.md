# Compact two-layer layout — N-layout-9

Open `../pi5_corona_hv.kicad_pro` in KiCad 10. Circuit revision J includes S5 and S6 on the normally-open series interlock chain. All 168 schematic footprints are present, plus the board-only DNP Pi model MP1. C63/R64 retain their DNP flags. Routing is partial: 191 unconnected items remain, so this is not a fabrication release.

## Dimensions and placement

The carrier is **196 × 148 mm**, spanning x50–246, y51–199 mm. The overall envelope including the five tabs is **231 × 148 mm**.
- **Width Boundary (196 mm):** The left edge x50 mm is constrained by invariant Raspberry Pi 5 socket J2 at (54.23, 106.63) mm and mounting holes H1/H2 at x55.5 mm. The right edge x246 mm is strictly constrained by the custom design rule `Highest voltage to board edge: min 10 mm` applied to J60 at (233.5, 84) mm (pad radius 2.25 mm requires edge >= 245.75 mm) and R20 Pad 1 at (234.75, 63) mm.
- **Height Boundary (148 mm):** The top edge y51 mm is constrained by Pi mounting hole H2 at y53.5 mm, USB-C receptacle J3 at y54.675 mm (mouth flush with edge), and top carrier mounting holes H3/H6 at y55 mm. The bottom edge y199 mm accommodates the 5 break-away tabs (S3–S6 perimeter interlocks, J51 illumination spanning y120–198 mm), bottom carrier mounting holes H4/H5 at y194 mm, HV Return terminal J61 at y196 mm, and return current shunt R90 at y192 mm.

## Ballast compaction and reverse E-field hazard elimination (N-layout-9)

In Revision M-layout-8, the 10-resistor ballast string R20–R29 looped across the top of the carrier from x228 down to x152 mm at y63 and y78 mm. At x152 mm, R24/R25 carried ~14.5 kV directly above Stage 2 pump bleeders (~4.5 kV) at y87 mm across an inverted 9 mm gap, generating an inverted 10.5 kV potential gradient (> 1.15 kV/mm E-field stress).

Revision N-layout-9 compacts the ballast string pitch to 15.5 mm (0.4 mm copper gap between adjacent pads on the same net, 15.0 mm row-to-row spacing satisfying the 10.0 mm `/HV_RAW` clearance rule):
- **Compacted Ballast Coordinates:**
  - Row 1 (y63.0 mm, rot 180°): R20 (228.0), R21 (212.5), R22 (197.0), R23 (181.5), R24 (166.0) mm.
  - Row 2 (y78.0 mm, rot 0°): R25 (166.0), R26 (181.5), R27 (197.0), R28 (212.5), R29 (228.0) mm.
  - HV Output J60: (233.5, 84.0) mm, rot 0°.
- **Hazard Relief:** The minimum X coordinate of the ballast string moves from 145.25 mm to **159.25 mm (+14.0 mm)**. The entire Stage 2 pump bleeder network (x <= 155 mm) is 100% vacated. Euclidean clearance from R25 to Stage 2 bleeders increases from 9.0 mm to **16.7 mm (almost doubled)**. Peak inverted E-field stress is reduced from 1.17 kV/mm to **0.42 kV/mm (a 64% reduction)**.
- **MST Optimization:** HV Minimum Spanning Tree length drops from 1081.99 mm to **1053.99 mm (-28.00 mm)**. All-net MST drops from 3904.79 mm to **3876.79 mm (-28.00 mm)**.
- **DRC Verification:** Native KiCad 10 DRC confirms **0 violations**, **0 schematic parity errors**, and exactly 191 unconnected items remaining from partial routing.

## Parallel-actuation microswitch replacement

S3–S6 use DEALON TK-0013-R, C19724218, populated on all four break-off boards. Footprint origins are (39, 137.6), (39, 153.6), (39, 169.6), (39, 185.6) mm, all rotation 0°. All COM/NO neck conductors are retained, NC unused, DNP unchanged.

Previous revisions are preserved under `revisions/M-layout-8/`, `revisions/L-layout-7/`, `revisions/K-layout-6/`, `revisions/J-layout-5/`, and `revisions/H-layout-3/`.
