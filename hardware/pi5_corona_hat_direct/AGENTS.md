# KiCad version requirement

Use KiCad 10 for all schematic edits, project saves, and generated KiCad artifacts in this directory. Before exporting, confirm `kicad-cli version` reports 10.x. Do not downgrade or convert these files to an earlier KiCad format.

# Mandatory supply and ground symbols

Use actual KiCad power symbols for every supply and ground rail. Plain text, local labels, or global labels must not substitute for power symbols on circuit rails. This includes 3.3 V, USB-C VBUS, protected/switched supplies, and high-voltage supplies and returns. Use a named custom power symbol when a standard symbol does not match the rail's exact net name.

Preserve net names and intended scope when adding symbols. Never merge raw, fused, protected, or switched rails, or connect an isolated high-voltage return to logic GND through a shared power-symbol name. Hierarchical pins may express sheet interfaces; signal and measurement nets may use ordinary labels.

PWR_FLAG declares an ERC power source; it does not replace the rail's power symbol. Place flags on short wire extensions, hide power-symbol and flag pin numbers, and keep symbol fields clear of wires, pins, and other text. Align symbols to the grid, with supply symbols pointing up and ground symbols down where practical.

Before delivery, inspect every sheet for text-only supply rails and visual overlaps, and run ERC plus a connectivity comparison after any power-symbol conversion.

# Break-off sensor and USB-PD capacitance constraints

Keep U8, J51, C80 and C81 on the illumination mini-board sheet; J50 belongs on the HAT. Both JST SH connectors use pin 1 GND, 2 Pi 3V3, 3 SDA, 4 SCL. The PCB break-off neck may carry only these four nets. Do not add sensor LEDs or parallel I²C pull-ups without reviewing low-light interference and bus loading.

U9 must isolate downstream bulk capacitance until GPIO25/BULK_CMD, gated by K1 to BULK_EN is asserted after an explicit PD contract. Maintain the external default-off pulldown. Recalculate the complete capacitance budget, including positive tolerances, controller bypass capacitors, the bridge reservoir, and parasitic reserve, whenever a capacitor or power path changes. Keep the present design below 10 µF exposed at attachment and 100 µF after negotiation; larger banks require a separately validated surge-current-limiting design. Do not restore the former 220 µF reservoir without that review.

# JLCPCB procurement fields

Use `procurement/part-assignments.json` and the dated catalog evidence when modifying selected parts. Maintain hidden, consistent `LCSC`, `LCSC Part`, `JLCPCB Part #`, `Manufacturer`, and `MPN` fields on each placed symbol. Match exact package/pad numbering, ratings and positive tolerances; a catalog ID alone is not verification. Keep all component and power references unique, including native instance annotations.

Leave catalog fields empty for PCB features and parts without a verified suitable match; document the procurement status instead of inventing IDs. Do not assign C8465 to the 15 kV output termination. Keep the transformer external-sourcing exception. K1 is a regulated 3 V logic-contact relay; do not put bridge current or USB-PD voltage on its coil or contacts. Never set DNP merely because a part is unavailable, through-hole or manually assembled. Regenerate the complete procurement BOM, JLCPCB matching BOM and exception report after selections change; preserve the current C63/R64 DNP flags.

Use Bourns CHV2512-JW-107ELF (C2089706), 100 MΩ / 5%, 3 kV, Resistor_SMD:R_2512_6332Metric for R30–R39 and all multiplier bleeders. Preserve ten series divider parts and two series parts per 200 MΩ bleeder bank (R140–R163). Never bypass R39. Recalculate voltage sharing and discharge behavior when changing these banks; calibrate HV sensing across operating voltages.

MP1 is an explicitly requested board-only Raspberry Pi 5 mechanical reference. Keep it DNP, locked, padless, excluded from BOM and position files, with the official STEP model and its MIT license. This is an exception to the schematic-only C63/R64 DNP list, not an additional assembled part. Preserve J2's corrected GPIO XY alignment and document the assumed standoff height and connector interference. Do not hide the interference by silently moving the Pi model or changing the connector selection.

The active PCB is the compact **two-layer** N-layout-14-surge (120 mm carrier height), with complete routing and a low-voltage placement/routing optimization accepted on 2026-10-19. Preserve J2 on F.Cu at (54.23,106.63) mm, rotated 180 degrees, and MP1's inverted/outboard pose at (3,115) mm with footprint rotation 90 degrees, model rotation (180,0,0) degrees and offset (0,0,13.306) mm. This is a 90-degree counterclockwise rotation from F-layout-2, with the socket along the left edge. H1/H2 at (55.5,111.5) and (55.5,53.5) align with the Pi GPIO-side mounting holes; H3 at (105,55) and H4 at (55,166) sit on the LV side of the isolation barrier (East HV mounting holes H5/H6 are omitted to maintain >= 10 mm HV hole clearance). Keep the 12 mm standoff explicitly provisional. No USB relief notch is needed in this pose; the exact Pi-to-substrate fit check reports zero intersections.

Main carrier envelope is 196 × 120 mm (x50–246, y51–171); five left-side 30 × 14 mm mini boards make the overall envelope 231 × 120 mm. S3/J62, S4/J63, S5/J66 and S6/J67 occupy separate switch mini boards. Matching host solder-pad pairs are J64, J65, J68 and J69 respectively: pin 1 COM, pin 2 NO. Only those two nets may cross each switch neck; NC remains unused. J60 and J61 are separate solder-wire terminations for HV_OUT and HV_RETURN, not generic low-voltage connector parts. Validate wire insulation and strain relief.

Use **Sunmate 2CL75 (C424512)** for D10–D21: 16 kV, 5 mA average, 0.5 A non-repetitive surge, maximum trr 100 ns at 25 C and Cj 1 pF at 0 V / 1 MHz. Require confirmed positive JLCPCB stock when making a new selection. Use ionic_thrust_hv:Sunmate_2CL75_D3_L12_P26; pad 1 is cathode/band, pad 2 anode. Keep the current 26 mm formed lead pitch and 0.9 mm drills unless placement and lead-forming requirements are reviewed. Validate repetitive charging pulses, startup surge, operating temperature, recovery conditions and formed-lead tolerances before release. Do not treat the 150 uA output current as the peak diode current. Preserve populated flags and exact diode polarity/nets.

Preserve HV net-name constraints in the custom rules file and router clearance map: 4 mm stage clearance, 10 mm highest-voltage clearance, 10 mm highest-voltage edge setback, and 10 mm NPTH mounting-hole clearance. The documented rated-part/adjacent-series-node rules are narrow voltage-differential rules, not universal HV exemptions. Block copper pours on both sides in the HV area; keep the logic GND pour in the low-voltage area. Recalculate creepage, clearance, board-edge setbacks and geometric fit after compaction. Initial DRC guards do not establish a safe or certified 15 kV layout.

The legacy pcbnew file API can overwrite project settings when saving a board. Preserve and restore the actual .kicad_pro contents around these PCB saves, including netclasses and text variables; never allow a default project to replace them.

# Audit fixes and verification

K1 G6K-2F-Y DC3 is powered from Pi 3V3 through U10 TPS7A0230 (3 V). Its series lid switches interrupt the coil. Contact pair 3/4 gates BULK_CMD to BULK_EN; pair 6/5 gates DRV_SLEEP_CMD to DRV_nSLEEP. GPIO23 reads the switched coil through R92 (10 kΩ); it must never share the GPIO24 command net. This feedback senses the lid-chain feed, not independently proven relay contact state. Keep external default-off pulldowns on both enables.

T1 FL2015-4LD uses the manufacturer SMT Package 1 land pattern (counter-clockwise pin numbering per Coilcraft Document 293-2, with Pad 1 opposite Pad 10 and Pad 6 opposite Pad 7): primary 1/5, center tap 3 unused, feedback 2/4 unused, secondary 8/9. Unwound terminal guards 6/GND, 7/SEC_A and 10/GND maintain secondary pad clearance; secondary return 9/10 connects to GND so external return current from J61 flows through R90 without generator circulation bypassing the shunt. U7 (HUSB238A-BB001-QN16R) has Pin 5 (VDD) powered from Pi 3V3 (defaulting safely to 5 V USB-C VBUS on attach and programmable from 5 V to 20 V over I2C at 0x42). R73 (1.2 kΩ, C22765) sets the TPS259470 eFuse current limit to 2.78 A, strictly above the DRV8876 H-bridge current limit of 2.20 A set by R61 (1.5 kΩ, C22843).

Keep R90 CRCW120610K0FKEAHP pulse-rated 1206, D5 SMBJ15A cathode/pad 1 to HV_RETURN and anode/pad 2 to GND, and R91 at 10 kΩ ahead of the ADC clamps. Preserve C73 at 1 µF / 50 V / 10%; current conservative PD budgets are 9.10242 µF at attachment and 97.34662 µF after contract. C82/C83 are Pi-powered and excluded from that USB budget. Confirm at least 0.5 µF effective LDO output capacitance at bias and temperature.

Run layout/validation/check_audit_nets.rb after refreshing the native-export connectivity manifest. Native ERC and DRC must pass; zero violations with unconnected items is still a fabrication hold. The board generator recreates placement and discards accepted routes; preserve routing before any regeneration.

# Four-switch placement constraints

Keep S3–S6 normally-open contacts in series: COIL_3V → S3 → LID_INT → S4 → LID_2 → S5 → LID_3 → S6 → RELAY_COIL_POS. NC pins remain unused and every switch is populated. Each break-off switch board has its own matching two-wire host/mini solder pads; never bypass a switch in the attached or detached topology. Mini-board top edges are y120 (illumination), y136/S3, y152/S4, y168/S5 and y184/S6. Each neck is 5 × 6 mm, x45–50, at top+4 through top+10. Only the corresponding two chain nets may cross a switch neck. The illumination neck permits GND/3V3/SDA/SCL only.

The compact multiplier uses 16 mm cell pitch, 8 mm inner diode offsets and a 12 mm final-diode offset; bleeder rows are staggered by 8 mm. Keep the 11.75 mm R30-to-R31 spacing and verify native 10 mm highest-net clearance before further compaction. Accepted rotations are recorded in layout/optimized-placement.json and loaded by the board generator. The Euclidean net-tree metric is a placement proxy, not actual routed length or proof of a global optimum.

# Compact LV and USB edge placement

The LV band is 51 mm wide, with its GND pour x52–101 and both-layer HV no-pour region starting x102. Preserve the current J3 left-edge pose at (55.8,144.4), rotation -90 degrees, inherited from the working N-layout-12 board. This supersedes the historical top-edge pose at (88,54.675). The Pi GPIO socket and mechanical pose remain fixed.

M-layout-8 packs PD/eFuse at the top, ADC/relay control in the middle and the bridge near T1. Accepted locations and reference fields are stored in layout/optimized-placement.json. Moving pads invalidates old routes; the complete prior K-layout-6 board and routes are saved under revisions/K-layout-6/. J2 ground pad 6 uses a solid local ground-zone connection to avoid an isolated single-spoke thermal island; no HV clearance rule is changed.

## Parallel-actuation microswitch replacement

S3–S6 now use DEALON TK-0013-R, C19724218, populated on all four break-off boards. The user accepted this selection on 2026-10-03. JLCPCB catalog snapshot reports 910 units, Extended/manualWeld (THT), $0.3099 at 1–49 and $0.245 at 50–149; stock is not reserved. The manufacturer drawing shows COM/NO/NC despite the catalog SPST-NC description and omits electrical ratings. Preserve this unresolved procurement qualification in the production checklist; confirm contact mapping and relay-coil load ratings on actual parts.

Custom footprint ionic_thrust_hv:SW_TK-0013-R uses pad 1 COM, pad 2 NO and pad 3 NC. Pads have 2.5 mm pitch, 0.7 × 1.5 mm oval holes and 1.3 × 2.1 mm lands. Body is 8.3 × 6.2 × 2.7 mm and actuation is parallel to the board; free lever envelope extends 9.8 mm from the rear body edge. The four footprint origins are (39,137.6), (39,153.6), (39,169.6), (39,185.6), all rotation 0. Lever tips may project 0.1 mm beyond each mini-board lower edge; account for lever travel and enclosure clearance. All COM/NO neck conductors are retained, NC unused, DNP unchanged. The previous board is preserved under revisions/L-layout-7/. Native ERC/DRC and schematic parity pass; 191 unconnected items remain in the overall partial layout.

## Accepted LV optimization — N-layout-13-LV

The active board has 0 native KiCad 10 DRC violations, 0 unconnected items, 0 schematic parity issues and 0 ERC violations. All 13 audit connectivity checks pass after refreshing the native netlist manifest. These results do not replace the existing HV insulation/component qualification work in layout/validation/README.md.

The low-voltage pad-tree placement metric (excluding the ground plane) decreased from 1927.549 to 1269.254 mm (34.15%). Forty-three footprint poses changed. Power trunk targets are 1.5 mm for USB-PD and bridge supplies, 1.0 mm for bridge outputs, 0.6 mm for 3V3 and 0.5 mm for COIL_3V. Locally narrower escapes remain where pads and clearances require them. Preserve the staggered U7 clock/CC1/USB data escapes and the short U2 charge-pump routes.

The exact prior working PCB/project/rules, including pre-existing uncommitted edits, are saved in revisions/N-layout-12-before-LV-optimization/. All HV net track geometry, fixed connectors/mechanics, pad nets, packages and DNP states were preserved. The project and custom rule files were preserved byte-for-byte. Current accepted placements and reference positions are in layout/optimized-placement.json; do not regenerate the board over accepted routes. Detailed metrics, widths and validation are in exports/lv-layout-optimization.json and exports/lv-layout-drc.json. Existing manufacturing archives were not regenerated for this layout revision.

## Accepted surge-path improvement — N-layout-14-surge

Preserve J61 at (126,156), D5 at (132.5,158) / 90° and R90 at (132.5,162.95) / 180°. J61-to-D5 is 8.219 mm and J61-to-R90 is 11.625 mm, both entirely on F.Cu with no intervening vias. Keep the 1.5 mm incoming return and direct generator-ground routing, the two parallel ground vias at (127.5,150.5) and (128.5,150.5), and the 1.5 mm back-side generator-ground trunk. R90 remains 10 kΩ / 0.75 W pulse-rated; the sense branch originates at its return pad. T1.6/9/10 stay on GND; never bypass R90 or move the generator return to /HV_RETURN. Preserve the local HV_SENSE_RAW/C13-ground reroute.

Native DRC/ERC/parity/open counts are all zero, and all 13 connectivity audits pass. Existing HV insulation screening failures and arc qualification remain unresolved. See exports/hv-surge-improvement.json and exports/hv-return-layout-review.md. Exact prior files are preserved in revisions/N-layout-13-before-surge-path/. Current accepted placements are in layout/optimized-placement.json. Earlier N-layout-13 LV metrics/reports describe that archived revision.
