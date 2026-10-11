#!/usr/bin/env python3
"""
Generate JLCPCB-compatible CPL (Component Placement List / Pick and Place) file.
Applies centroid corrections (for footprints where KiCad origin is Pin 1 rather than center)
and rotation offsets (where KiCad library orientation differs from JLCPCB/EasyEDA orientation).
"""

import csv
import re
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Rotation offsets to add to KiCad native rotation to match JLCPCB / EasyEDA library
# (Degrees counter-clockwise in CPL coordinates)
ROTATION_OFFSETS = {
    # Raspberry Pi 40-pin header: KiCad vertical (rot 180) -> JLCPCB EasyEDA horizontal (rot 0 + 90 = vertical)
    "J2": 270.0,  # 180 + 270 = 450 = 90.0 deg
    # BME280: KiCad horizontal top/bottom pins -> JLCPCB EasyEDA vertical left/right pins
    "U5": 90.0,   # 0 + 90 = 90.0 deg
    # AO4407A SO-8 MOSFET: KiCad vertical (rot 0) -> EasyEDA horizontal (rot 270)
    "Q1": 270.0,  # 0 + 270 = 270.0 deg
    # DRV8876PWPR HTSSOP-16: KiCad vertical (rot 0) -> EasyEDA horizontal (rot 270)
    "U2": 270.0,  # 0 + 270 = 270.0 deg
    # ADS1115 MSOP-10: KiCad vertical (rot 90) -> EasyEDA horizontal (rot 0)
    "U6": 270.0,  # 90 + 270 = 360 = 0.0 deg
    # HUSB238A QFN-16: KiCad Pin 1 top-left -> EasyEDA Pin 1 bottom-left (rot 270)
    "U7": 270.0,  # 0 + 270 = 270.0 deg
    # TSL2591 DFN-6: KiCad vertical (rot 0) -> EasyEDA horizontal (rot 270)
    "U8": 270.0,  # 0 + 270 = 270.0 deg
    # TPS7A0230 SOT-23-5: KiCad standard footprint inverted 180 deg vs EasyEDA
    "U10": 180.0, # 90 + 180 = 270.0 deg
    # Omron G6K-2F-Y DPDT Relay: KiCad vertical (rot 180) -> EasyEDA horizontal (rot 90)
    "K1": 270.0,  # 180 + 270 = 450 = 90.0 deg
    # SS36 SMC Schottky diodes: KiCad cathode pin 1 is left, EasyEDA C16237 pin 1 is right (180 deg flip)
    "D52": 180.0, # 90 + 180 = 270.0 deg
    "D53": 180.0, # 90 + 180 = 270.0 deg
    "D54": 180.0, # 90 + 180 = 270.0 deg
    "D55": 180.0, # 90 + 180 = 270.0 deg
}

# Centroid overrides (Mid X, Mid Y) in board coordinates (mm)
# KiCad CPL uses (PosX, -PosY)
CENTROID_OVERRIDES = {
    # J2: KiCad origin is Pin 1 at (54.23, 106.63). True geometric midpoint is (55.5000, 82.5000).
    "J2": (55.5000, 82.5000),
    # C11: KiCad origin is Pin 1 at (110.0, 131.0). True geometric midpoint is (117.5000, 131.0000).
    "C11": (117.5000, 131.0000),
    # C60: KiCad origin is Pin 1 at (97.0, 147.0). True geometric midpoint is (98.0000, 147.0000).
    "C60": (98.0000, 147.0000),
    # C70: KiCad origin is Pin 1 at (97.0, 104.0). True geometric midpoint is (98.0000, 104.0000).
    "C70": (98.0000, 104.0000),
    # J3: USB-C receptacle origin is at front edge (88.0, 54.675). True package center is at (88.0000, 56.1730).
    "J3": (88.0000, 56.1730),
}


def generate_cpl():
    pcb_file = BASE_DIR / "pi5_corona_hv.kicad_pcb"
    bom_file = BASE_DIR / "exports" / "jlcpcb-bom.csv"
    raw_pos_file = BASE_DIR / "exports" / "pi5_corona_hv_cpl.csv"
    out_cpl_file = BASE_DIR / "exports" / "jlcpcb-cpl.csv"

    # Always re-export raw position file strictly in MILLIMETERS
    subprocess.run(
        [
            "kicad-cli", "pcb", "export", "pos",
            "--units", "mm",
            "--format", "csv",
            "--output", str(raw_pos_file),
            str(pcb_file)
        ],
        check=True
    )

    with open(bom_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        bom_parts = {}
        for r in reader:
            for des in r["Designator"].split(","):
                bom_parts[des.strip()] = r

    with open(raw_pos_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_pos = {r["Ref"].strip('"'): r for r in reader}

    missing = set(bom_parts.keys()) - set(raw_pos.keys())
    if missing:
        print(f"ERROR: Missing positions for {missing}", file=sys.stderr)
        sys.exit(1)

    cpl_rows = []
    for des in bom_parts.keys():
        pos = raw_pos[des]
        
        # Centroid position in millimeters
        if des in CENTROID_OVERRIDES:
            bx, by = CENTROID_OVERRIDES[des]
            px = bx
            py = -by
        else:
            px = float(pos["PosX"])
            py = float(pos["PosY"])

        # Rotation: normalize to [0.0, 360.0)
        pr = float(pos["Rot"])
        if des in ROTATION_OFFSETS:
            pr += ROTATION_OFFSETS[des]
        pr = pr % 360.0
        if pr < 0.0:
            pr += 360.0

        layer = "Top" if pos["Side"].lower() == "top" else "Bottom"

        cpl_rows.append({
            "Designator": des,
            "Mid X": f"{px:.4f}",
            "Mid Y": f"{py:.4f}",
            "Layer": layer,
            "Rotation": f"{pr:.1f}",
        })

    def sort_key(r):
        m = re.match(r"^([A-Za-z]+)(\d+)", r["Designator"])
        if m:
            return (m.group(1), int(m.group(2)))
        return (r["Designator"], 0)

    cpl_rows.sort(key=sort_key)

    with open(out_cpl_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]
        )
        writer.writeheader()
        writer.writerows(cpl_rows)

    print(f"Generated {len(cpl_rows)} rows in {out_cpl_file}")


if __name__ == "__main__":
    generate_cpl()
