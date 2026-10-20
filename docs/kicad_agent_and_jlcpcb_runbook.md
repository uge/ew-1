> Historical reference. The current working design and commands are in [the project guide](../hardware/pi5_corona_hat_direct/README.md). Older paths and release claims below are superseded.

# KiCad 10 and JLCPCB runbook

The active project is `hardware/pi5_corona_hat_direct/pi5_corona_hv.kicad_pro`: a Raspberry Pi 5 HAT with programmable USB-C PD input, DRV8876 bridge protection, BME280, ADS1115 and a TSL2591 break-off illumination board. Earlier ESP32 projects and their component mappings are historical and must not be used for procurement.

Read the active project's [AGENTS.md](../hardware/pi5_corona_hat_direct/AGENTS.md) and [hardware handoff](ionic_thrust_hv_kicad_handoff.md) before editing. Use KiCad 10 and write native schematic files directly. All supply rails use power symbols, with readable fields and flags on wire extensions.

## Catalog selections

The canonical [selection record](../hardware/pi5_corona_hat_direct/procurement/part-assignments.json) maps each sheet/reference to its manufacturer part and catalog ID. [Procurement notes](../hardware/pi5_corona_hat_direct/procurement/README.md) explain package corrections, stock and electrical holds. The dated [catalog snapshot](../hardware/pi5_corona_hat_direct/procurement/jlcpcb-catalog-2026-10-02.json) records attributes checked through JLCPCB's public component-detail endpoint.

Each placed symbol carries hidden `LCSC`, `LCSC Part`, `JLCPCB Part #`, `Manufacturer`, `MPN`, source/date, assembly process and procurement-status fields. Keep the catalog fields consistent and references unique. Confirm exact pin-to-pad mapping, value, tolerance, voltage, power and physical dimensions. Do not substitute a same-name component in a different package.

Use these outputs:

- [Complete procurement BOM](../hardware/pi5_corona_hat_direct/exports/procurement-bom.csv): every placed item, including DNP and unmatched items.
- [JLCPCB matching BOM](../hardware/pi5_corona_hat_direct/exports/jlcpcb-bom.csv): `Comment, Designator, Footprint, LCSC Part #`, grouped by selected part and footprint. DNP, unmatched and electrical-review items are excluded. Out-of-stock matches remain identifiable.
- [Exceptions](../hardware/pi5_corona_hat_direct/exports/procurement-exceptions.csv): missing matches, stock and review holds.
- [Validation](../hardware/pi5_corona_hat_direct/exports/jlcpcb-validation.json): assignment coverage, annotation, connectivity and pin/pad checks.

Recheck stock and assembly service at ordering. No order, reservation or consignment has been made. THT/manual assembly is an assembly-process designation, not a reason to set DNP. C63/R64 are the only current DNP parts.

## Verification

From `hardware/`:

```bash
kicad-cli version
kicad-cli sch erc --format json --exit-code-violations \
  --output pi5_corona_hat_direct/exports/erc.json \
  pi5_corona_hat_direct/pi5_corona_hv.kicad_sch
kicad-cli sch export netlist \
  --output /tmp/pi5_corona_hv.net \
  pi5_corona_hat_direct/pi5_corona_hv.kicad_sch
kicad-cli sch export pdf \
  --output pi5_corona_hat_direct/exports/pi5_corona_hv.pdf \
  pi5_corona_hat_direct/pi5_corona_hv.kicad_sch
```

Inspect all six PDF pages and run Konnect's `check_schematic_overlaps` on every sheet. Validate connectivity after any symbol or pin-number changes. Recalculate the tolerance-inclusive USB-PD capacitance budget when any capacitor selection changes. A zero ERC count does not certify voltage spacing, thermal behavior or component suitability.

The `kicad-jlcpcb-tools` plugin and its catalog are installed under `~/.local/share/kicad/10.0/3rdparty/plugins/com_github_bouni_kicad-jlcpcb-tools/`. Its `LCSC` selection field is populated by this project. Optional component imports must use a staging library, preserve native project symbols and verified pad mapping, and receive footprint/model review before replacement.

## Fabrication holds

The active project has no PCB layout or CPL. Before fabrication, resolve the HV output termination, relay coil supply, shared INTERLOCK_OK/DRV_nSLEEP connection, sourcing exceptions and firmware controls described in the handoff. Then implement the mini-board neck and PCB, verify land patterns and mechanical fit, run DRC, and generate Gerbers, drill data and an actual rotation-reviewed placement list. Do not generate a placeholder CPL or treat this procurement BOM as a production release.
