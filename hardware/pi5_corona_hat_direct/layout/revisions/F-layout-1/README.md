# Initial four-layer PCB placement

Open `../pi5_corona_hv.kicad_pro` and its PCB editor. The board is saved in KiCad 10 format. All 152 schematic footprints, net assignments, procurement fields and native schematic paths are imported. C63 and R64 remain DNP. Seven board-only mounting holes are added.

The main carrier is **340 × 180 mm**. The optical daughterboard is **30 × 20 mm**, connected by a **12 × 5 mm** break-off neck, for an overall **340 × 205 mm** envelope. These dimensions are an initial accommodation of the large through-hole multiplier parts and linear resistor strings, subject to enclosure and clearance review.

The upper-left 65 × 56 mm reference envelope contains the Pi interface. Four mounting holes use a 58 × 49 mm pitch. J2 is on B.Cu to mate with the Pi header: pad 1 at (58.37, 54.77), pad 2 at (58.37, 52.23), and pad 40 at (106.63, 52.23) mm. The mounting-hole drill is nominally 2.7 mm. Review mechanical tolerances and the Pi 5 cooler, cables and enclosure. This extended carrier is not a standard HAT outline or a claim of HAT certification. Mechanical reference: https://github.com/raspberrypi/hats/blob/master/hat-board-mechanical.pdf.

| Layer | Intended use |
|---|---|
| F.Cu | Components, short critical connections and HV routing |
| In1.Cu | Filled logic GND plane limited to the low-voltage area |
| In2.Cu | Reserved for local low-voltage power distribution |
| B.Cu | Pi socket and additional signal routing |

Nominal board thickness is 1.6 mm. Manufacturer dielectric thicknesses and copper weights remain to be selected. Internal-layer rule areas prohibit tracks, vias and fills under the transformer and HV area, starting at x = 122 mm. Through-hole annuli are permitted. GND is not poured beneath the HV ladder, ballast or divider. HV_RETURN remains a separate schematic net. These restrictions do not establish a verified creepage or voltage rating.

USB-C, PD negotiation, the eFuse and bulk capacitance form a distinct placement group. Bridge decoupling and recirculation clamps are near U2, and T1 bridges toward the multiplier. Six multiplier columns have paired capacitors, diodes and three-resistor bleeders. The ballast and divider are linear strings; the divider progresses back toward U4. U8, J51, C80 and C81 are on the optical mini-board; J50 is on the main board. Only GND, 3V3, SDA and SCL may eventually cross its break-off neck. Neck traces and the mechanical cutting process are not yet implemented.

## Validation and remaining work

The final checks report **zero schematic parity issues**, matching net assignments for every schematic pin, and no courtyard overlaps. The initial routing pass has **285 unconnected-item reports**. One DRC warning documents the D3 instance's silkscreen adjustment: its silk was moved to F.Fab to avoid pad overlap, so it differs from the library copy. The DRC report is retained in `../exports/initial-pcb-drc.json`; validation is in `../exports/initial-pcb-validation.json`.

Before routing/release, resolve the existing J60 termination rating, relay supply/interlock review and transformer footprint verification. Replace the J60 placeholder with a rated termination and rework its local placement. Complete routing, establish HV clearance/creepage rules and any isolation slots, review leakage around the divider, and validate transformer/bridge thermal and current paths. Do not fabricate this placement study.

Review drawings: `../exports/initial-pcb-layout.pdf`, `.svg` and `.png`. No fabrication package or production pick-and-place file is emitted.

`create_initial_board.py` uses the KiCad 10 pcbnew PCB API and `schematic-connectivity.json`. It does not generate schematics. Re-running it overwrites the PCB with the initial placement and discards subsequent routing, so use it only deliberately. The connectivity snapshot corresponds to schematic revision F and must be refreshed after schematic changes.

## DNP Raspberry Pi 5 mechanical model

**MP1** is a locked, padless board-only footprint, explicitly DNP and excluded from BOM and placement files. It uses the official Raspberry Pi 5 STEP model from [Raspberry Pi's product portal](https://pip.raspberrypi.com/categories/892-raspberry-pi-5), stored locally with the supplied MIT license in `ionic_thrust_hv.3dshapes`. It is not an electrically connected or assembled HAT component. The footprint is on F.Cu solely to retain the native model orientation; its model is translated beneath the carrier.

The native model's PCB spans x = 0–85 and y = 0–56 mm. Its upper PCB face is at z = 1.306 mm. MP1's board anchor is (50,106) mm, with model scale 1, rotation 0 and offset (0,0,-14.906) mm. This places the Pi PCB upper face **12 mm below the carrier underside**, assuming the carrier's 1.6 mm thickness. This height is a fit-check assumption, not a validated connector mating specification.

The official header pins are centered at y = 51.23 and 53.77 mm in native CAD coordinates. Comparing these with the PCB exposed a 1.27 mm GPIO row offset; J2 was moved by -1.27 mm in board Y. All 40 pin coordinates now match the model's grid, and the four Pi mounting locations align. The existing schematic connections and connector selection are preserved.

**The extended carrier collides with the tall Pi connectors at the assumed 12 mm spacing.** The model reaches z = 17.526 mm, or 16.220 mm above the Pi PCB upper face. Geometric clearance requires more than 16.22 mm standoff spacing plus a mechanical margin, or carrier cut-outs. A taller stack also requires an appropriate GPIO extender; do not assume J2 alone provides that height. A cooler, cables and enclosure are not included in this model and need separate checks.

In KiCad's 3D Viewer, enable **Show DNP footprints** to display MP1. STEP export includes it unless `--no-dnp` is passed. The saved PCB remains DNP; the bottom-view preview was rendered from a temporary display copy with MP1 visible. See `../exports/pi5-mechanical-bottom.png` and `../exports/pi5-mechanical-validation.json`. `add_pi5_mechanical.py` updates only MP1 and the corrected J2 XY location without rebuilding the PCB or discarding routing. The initial-board script also restores MP1 when deliberately rebuilding.
