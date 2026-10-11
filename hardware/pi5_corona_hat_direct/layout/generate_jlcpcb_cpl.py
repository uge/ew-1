#!/usr/bin/env python3
"""
Generate JLCPCB-compatible CPL (Component Placement List / Pick and Place) file.
Applies centroid corrections (for footprints where KiCad origin is Pin 1 rather than center)
and rotation offsets (where KiCad library orientation differs from JLCPCB/EasyEDA orientation).
"""

import csv
import re
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
}

# Centroid overrides (Mid X, Mid Y) in board coordinates (mm)
# KiCad CPL uses (PosX, -PosY)
CENTROID_OVERRIDES = {
    # J2: KiCad origin is Pin 1 at (54.23, 106.63).
    # True geometric midpoint is (55.5000, 82.5000).
    "J2": (55.5000, 82.5000),
}


def generate_cpl():
    bom_file = BASE_DIR / "exports" / "jlcpcb-bom.csv"
    raw_pos_file = BASE_DIR / "exports" / "pi5_corona_hv_cpl.csv"
    out_cpl_file = BASE_DIR / "exports" / "jlcpcb-cpl.csv"

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
        val = pos["Val"].strip('"')
        pkg = pos["Package"].strip('"')
        
        # Centroid position
        if des in CENTROID_OVERRIDES:
            bx, by = CENTROID_OVERRIDES[des]
            px = bx
            py = -by
        else:
            px = float(pos["PosX"])
            py = float(pos["PosY"])

        # Rotation
        pr = float(pos["Rot"])
        if des in ROTATION_OFFSETS:
            pr = (pr + ROTATION_OFFSETS[des]) % 360.0

        layer = "Top" if pos["Side"].lower() == "top" else "Bottom"

        cpl_rows.append({
            "Designator": des,
            "Val": val,
            "Package": pkg,
            "Mid X": f"{px:.4f}",
            "Mid Y": f"{py:.4f}",
            "Rotation": f"{pr:.1f}",
            "Layer": layer,
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
            fieldnames=["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"]
        )
        writer.writeheader()
        writer.writerows(cpl_rows)

    print(f"Generated {len(cpl_rows)} rows in {out_cpl_file}")


if __name__ == "__main__":
    generate_cpl()
