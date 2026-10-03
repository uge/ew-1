# KiCad version requirement

Use KiCad 10 for all schematic edits, project saves, and generated KiCad artifacts in this directory. Before exporting, confirm `kicad-cli version` reports 10.x. Do not downgrade or convert these files to an earlier KiCad format.

# Mandatory supply and ground symbols

Use actual KiCad power symbols for every supply and ground rail. Plain text, local labels, or global labels must not substitute for power symbols on circuit rails. This includes 3.3 V, USB-C VBUS, protected/switched supplies, and high-voltage supplies and returns. Use a named custom power symbol when a standard symbol does not match the rail's exact net name.

Preserve net names and intended scope when adding symbols. Never merge raw, fused, protected, or switched rails, or connect an isolated high-voltage return to logic GND through a shared power-symbol name. Hierarchical pins may express sheet interfaces; signal and measurement nets may use ordinary labels.

PWR_FLAG declares an ERC power source; it does not replace the rail's power symbol. Place flags on short wire extensions, hide power-symbol and flag pin numbers, and keep symbol fields clear of wires, pins, and other text. Align symbols to the grid, with supply symbols pointing up and ground symbols down where practical.

Before delivery, inspect every sheet for text-only supply rails and visual overlaps, and run ERC plus a connectivity comparison after any power-symbol conversion.

# Break-off sensor and USB-PD capacitance constraints

Keep U8, J51, C80 and C81 on the illumination mini-board sheet; J50 belongs on the HAT. Both JST SH connectors use pin 1 GND, 2 Pi 3V3, 3 SDA, 4 SCL. The PCB break-off neck may carry only these four nets. Do not add sensor LEDs or parallel I²C pull-ups without reviewing low-light interference and bus loading.

U9 must isolate downstream bulk capacitance until GPIO25/BULK_EN is asserted after an explicit PD contract. Maintain the external default-off pulldown. Recalculate the complete capacitance budget, including positive tolerances, controller bypass capacitors, the bridge reservoir, and parasitic reserve, whenever a capacitor or power path changes. Keep the present design below 10 µF exposed at attachment and 100 µF after negotiation; larger banks require a separately validated surge-current-limiting design. Do not restore the former 220 µF reservoir without that review.

# JLCPCB procurement fields

Use `procurement/part-assignments.json` and the dated catalog evidence when modifying selected parts. Maintain hidden, consistent `LCSC`, `LCSC Part`, `JLCPCB Part #`, `Manufacturer`, and `MPN` fields on each placed symbol. Match exact package/pad numbering, ratings and positive tolerances; a catalog ID alone is not verification. Keep all component and power references unique, including native instance annotations.

Leave catalog fields empty for PCB features and parts without a verified suitable match; document the procurement status instead of inventing IDs. Do not assign C8465 to the 15 kV output termination. Keep the relay's electrical-review hold and the transformer external-sourcing exception until resolved. Never set DNP merely because a part is unavailable, through-hole or manually assembled. Regenerate the complete procurement BOM, JLCPCB matching BOM and exception report after selections change; preserve the current C63/R64 DNP flags.

Use Bourns CHV2512-JW-107ELF (C2089706), 100 MΩ / 5%, 3 kV, Resistor_SMD:R_2512_6332Metric for R30–R39 and all multiplier bleeders. Preserve ten series divider parts and three series parts per 300 MΩ bleeder bank. Never bypass R39. Recalculate voltage sharing and discharge behavior when changing these banks; calibrate HV sensing across operating voltages.

MP1 is an explicitly requested board-only Raspberry Pi 5 mechanical reference. Keep it DNP, locked, padless, excluded from BOM and position files, with the official STEP model and its MIT license. This is an exception to the schematic-only C63/R64 DNP list, not an additional assembled part. Preserve J2's corrected GPIO XY alignment and document the assumed standoff height and connector interference. Do not hide the interference by silently moving the Pi model or changing the connector selection.

The active PCB is the compact **two-layer** F-layout-2 placement. Preserve J2 on F.Cu at (58.37,54.23) mm, rotated 90 degrees, and MP1's inverted/outboard pose at (50,3) mm with model rotation (180,0,0) degrees and offset (0,0,13.306) mm. Only H1/H2 align with Pi mounting holes; the Pi's other supports are outboard. Keep the 12 mm standoff explicitly provisional.

Preserve the 24 × 10 mm USB relief notch at x = 117–141, y = 50–60 mm. The solid-model check depends on this notch to avoid Pi USB housing interference. Main carrier envelope is 296 × 155 mm; the break-off mini board increases the PCB envelope to 296 × 180 mm. Pi outboard projection increases the assembled envelope further, so use the actual 3D assembly for enclosure checks.

Preserve assigned HV netclasses and the custom rules file: 4 mm stage clearance, 10 mm highest-voltage clearance and 10 mm highest-voltage edge setback. The documented rated-part/adjacent-series-node rules are narrow voltage-differential rules, not universal HV exemptions. Leave J60/T1/USB-C package violations visible until verified remedies exist. Block copper pours on both sides in the HV area; keep the logic GND pour in the low-voltage area. Recalculate creepage, clearance, board-edge setbacks and geometric fit after compaction. Initial DRC guards do not establish a safe or certified 15 kV layout.

The legacy pcbnew file API can overwrite project settings when saving a board. Preserve and restore the actual .kicad_pro contents around these PCB saves, including netclasses and text variables; never allow a default project to replace them.
