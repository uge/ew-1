---
name: kicad-jlcpcb
description: >-
  Instructions, commands, and workflows for automating KiCad 10 on the Ionic Thrust HV supply project.
  Includes LCSC component importing with 3D models (easyeda2kicad), headless ERC/DRC verification,
  4-layer stackup rules, and JLCPCB fabrication exports.
---

# KiCad 10 & JLCPCB Automation Skill

This skill guides agents through editing schematics, updating footprints, importing LCSC components, performing DRC/ERC, and generating production deliverables for the ESP32-controlled 12 V to 15 kV Ionic Thrust HV supply.

## 1. Quick Reference Commands

### Headless Verification
```bash
# Run Electrical Rules Check (Schematic)
kicad-cli sch erc --severity-all --exit-code-violations --format json --output hardware/erc_report.json hardware/ionic_thrust_hv.kicad_sch

# Run Design Rules Check (PCB)
kicad-cli pcb drc --severity-all --exit-code-violations --format json --output hardware/drc_report.json hardware/ionic_thrust_hv.kicad_pcb
```

### 3D Board Rendering
```bash
# Render Top View
kicad-cli pcb render --side top --quality high --width 1920 --height 1080 --output docs/media/pcb_render_top.png hardware/ionic_thrust_hv.kicad_pcb

# Render Perspective / Isometric View
kicad-cli pcb render --view isometric --quality high --width 1920 --height 1080 --output docs/media/pcb_render_iso.png hardware/ionic_thrust_hv.kicad_pcb
```

### Component & 3D Model Import via LCSC ID (Strict KiCad 10 Pipeline)
```bash
# 1. Fetch raw assets from EasyEDA / LCSC
pipx run easyeda2kicad \
  --full \
  --lcsc_id <LCSC_ID> \
  --output hardware/ionic_thrust_hv.kicad_sym \
  --project-relative \
  --overwrite

# 2. Immediately upgrade imported symbol library and footprint directory to native KiCad 10 format:
kicad-cli sym upgrade --force hardware/pi5_corona_hat_direct/pi5_corona_hv.kicad_sym
kicad-cli fp upgrade --force hardware/pi5_corona_hat_direct/ionic_thrust_hv.pretty

# 3. Verify project-wide KiCad 10 compliance:
python3 hardware/pi5_corona_hat_direct/layout/validation/verify_kicad10_compliance.py --root hardware
```

### KiCad 10 File Format Rules & Verification
Always maintain all project files in native KiCad 10 format:
- **PCBs (`.kicad_pcb`):** `(version 20260206) (generator "pcbnew") (generator_version "10.0")`
- **Schematics (`.kicad_sch`):** `(version 20260306) (generator "eeschema") (generator_version "10.0")`
- **Symbols (`.kicad_sym`):** `(version 20251024) (generator "kicad_symbol_editor") (generator_version "10.0")`
- **Footprints (`.kicad_mod`):** `(version 20260206) (generator "pcbnew") (generator_version "10.0")`
- **Library Tables (`fp-lib-table`, `sym-lib-table`):** `(version 7)`
- **Environment Variables:** Strict `${KICAD10_3DMODEL_DIR}` or `${KIPRJMOD}` only (zero `${KICAD8_*}` or generic `${KICAD_*}`).
```bash
# Run KiCad 10 Strict Compliance Verification
python3 hardware/pi5_corona_hat_direct/layout/validation/verify_kicad10_compliance.py --root hardware
```

### Fabrication Exports
```bash
# Export Gerbers
kicad-cli pcb export gerbers --output hardware/gerbers/ --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts hardware/ionic_thrust_hv.kicad_pcb

# Export Excellon Drill files
kicad-cli pcb export drill --output hardware/gerbers/ --format excellon --generate-map hardware/ionic_thrust_hv.kicad_pcb

# Export Centroid / CPL for JLCPCB SMT
kicad-cli pcb export pos --output hardware/ionic_thrust_hv_cpl.csv --format csv --units mm --side both hardware/ionic_thrust_hv.kicad_pcb

# Export BOM
kicad-cli sch export bom --output hardware/ionic_thrust_hv_bom.csv hardware/ionic_thrust_hv.kicad_sch
```

## 2. High Voltage Design Rules
When reviewing or modifying the layout, ensure:
1. **HV_STAGE Clearance:** At least 4.0 mm clearance between adjacent multiplier stage copper.
2. **HV_HIGH_TO_LV Clearance:** At least 20.0 mm (target 25.0 mm) physical clearance plus routed isolation slots on `Edge.Cuts`.
3. **Multi-layer Keepout:** Layers `In1.Cu` (GND) and `In2.Cu` (Power) MUST HAVE ZERO COPPER under the entire high-voltage domain (transformer secondary, CW ladder, bleeder resistors, ballast string, divider string, HV connector).
4. **DNP Attribute:** All manual HV parts (FL2015-4LD, HVM12, Vishay 6 kV disc caps, 3.5 kV axial resistors, relay, lid switches) must be flagged with `DNP` for automated SMT assembly.
