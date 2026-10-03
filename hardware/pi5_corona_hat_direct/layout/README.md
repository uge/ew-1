# Compact two-layer PCB placement — F-layout-2

Open `../pi5_corona_hv.kicad_pro` and its PCB editor. This is native KiCad 10, with all 152 schematic footprints, net assignments, procurement fields and schematic paths preserved. MP1 is a separate board-only DNP mechanical reference. C63/R64 retain their schematic DNP flags. Routing remains incomplete; this is not a fabrication release.

## Dimensions and Pi orientation

The main carrier is **296 × 155 mm**, reduced from 340 × 180 mm: **25.0% less rectangular board area**. The 30 × 20 mm optical daughterboard and 12 × 5 mm neck make the PCB envelope **296 × 180 mm**, reduced from 340 × 205 mm. The Pi projects beyond the top edge, so the assembled envelope including the Pi is approximately 296 × 229 mm; the reduced PCB envelope is not the full enclosure envelope.

J2 is now on **F.Cu**, rotated 90 degrees. MP1's official Pi STEP model is inverted 180 degrees around X with its body outboard above the carrier's top edge. The model anchor is (50,3) mm, offset (0,0,13.306) mm, unit scale. The component face of the Pi PCB is 12 mm above the carrier front face. The Pi GPIO pins point down into the upward-facing socket. The tall USB/Ethernet bodies project outboard, rather than intersecting the carrier substrate. A 24 × 10 mm top-edge notch at x = 117–141, y = 50–60 mm clears the remaining USB housing corner. The exact solid-model check finds zero Pi-to-carrier substrate intersections.

All 40 GPIO XY positions are checked against the official STEP pin grid: pin 1 (58.37,54.23), pin 2 (58.37,56.77), pin 40 (106.63,56.77) mm. Carrier holes H1/H2 at (53.5,55.5) and (111.5,55.5) mm align with the Pi's GPIO-side mounting holes. The other two Pi holes at y = 6.5 mm are outboard and need enclosure/standoff support. H3–H7 are carrier supports, not additional aligned Pi holes. This is an extended carrier, not a standard HAT outline.

The 12 mm spacing is a model assumption, not a guaranteed socket engagement or mechanical tolerance specification. Cooler, cables and enclosure are excluded from the fit check. The official model and its supplied MIT license are kept in `ionic_thrust_hv.3dshapes`; source: [Raspberry Pi product portal](https://pip.raspberrypi.com/categories/892-raspberry-pi-5).

## Layers and HV spacing

Only **F.Cu and B.Cu** are enabled; nominal thickness remains 1.6 mm. Components and J2 are on the front. The logic GND pour is on B.Cu, limited to x = 52–121 mm. A rule area blocks copper fills on both sides beneath the transformer/HV region, x = 122–345 mm. Individual tracks and pads remain routable. No internal layers or former internal-layer zones remain. HV_RETURN stays distinct from logic GND.

Multiplier column pitch is reduced from 36 to 30 mm, diode pair spacing from 18 to 16 mm, and capacitor-row separation from 71 to 54 mm. Ballast pitch is 17 mm instead of 21 mm; divider pitch is 16 mm instead of 21 mm. The divider remains a straight string with the high-voltage end adjacent to the final multiplier stage; it is not folded back next to the low-voltage end. All twelve three-resistor bleeders remain intact. No capacitances, part values or power-path connections change.

HV netclasses are now assigned to the 56 relevant nets, rather than left unassigned. Custom rules enforce **4 mm stage clearance**, **10 mm highest-voltage clearance**, and **10 mm highest-voltage copper-to-board-edge setback**. These are initial layout guards, not a certification of 15 kV creepage/insulation. Final requirements depend on working and transient voltages, PCB material, pollution, altitude, enclosure and any validated encapsulation. Reference: [TI high-voltage spacing guidance](https://www.ti.com/lit/pdf/slup419). No reduction is justified by assuming solder mask or unqualified conformal coating provides HV insulation.

Four explicit pair rules distinguish voltage across a rated part from its common-mode voltage: R30's own pins, R163's own pins, the adjacent R51/R163 series nodes, and C111's own pins use the 4 mm stage guard. These are not blanket exemptions for the HV output net. The Bourns package has 4.7 mm pad-edge spacing and a 3 kV working rating; divider/bleeder voltage sharing must still be validated. The selected 6 kV capacitor has 8.25 mm pad-edge spacing; its lead-area creepage and encapsulation remain review items. No exceptions suppress J60 or T1 clearance failures.

The break-off sensor retains U8, J51, C80 and C81. J50 stays on the carrier. Only GND, 3V3, SDA and SCL may cross the neck; neck traces and the cutting process are not yet implemented.

## Checks and remaining work

Schematic parity is zero, every schematic pin's PCB net matches, and there are no courtyard overlaps. DRC reports **280 unconnected items** and **five remaining violations**:

- J60: 3.08 mm between output and return versus the 10 mm guard, reported on both copper layers. The existing terminal is unsuitable for 15 kV; select a rated termination and footprint.
- T1: 3.2 mm secondary pad spacing versus the 4 mm guard, reported on both layers. Verify the transformer drawing and insulation before deciding its final footprint/spacing.
- D3: its placed silkscreen was moved to F.Fab to avoid pad overlap, so it differs from the library copy.

These are retained review blockers, not waived errors. Earlier checks also identified a USB-C pad-to-NPTH spacing concern; verify its manufacturer geometry and fabrication requirements even though it is not reported by the current two-layer DRC. Complete routing, creepage review, transformer/bridge current and thermal checks, relay supply/interlock review, and physical mechanical measurements before fabrication. The capacitor budget and procurement BOM are unchanged.

Review `../exports/compact-pcb-layout.pdf`, `.svg`, `.png`, `compact-pi5-assembly.png`, `compact-pcb-drc.json`, and `compact-pcb-validation.json`. The substrate fit check is recorded in `compact-pi5-substrate-fit.json`; it does not validate all component, cooler or enclosure collisions. Enable **Show DNP footprints** in KiCad's 3D Viewer to display MP1; STEP exports include it unless `--no-dnp` is passed.

`create_initial_board.py` uses the PCB API only and preserves project settings. Re-running it rebuilds the board and discards later routing. `add_pi5_mechanical.py` updates only the socket pose and MP1. Both retain MP1 as DNP, locked, padless and excluded from BOM/placement files. `check_pi5_compact_fit.py` runs in FreeCADCmd and checks the Pi model against the carrier substrate. The original four-layer placement is retained under `revisions/F-layout-1/`. No fabrication package is emitted.
