#!/usr/bin/env python3
"""
Generate JLCPCB-compatible CPL (Component Placement List / Pick and Place) file.
Applies centroid corrections (for footprints where KiCad origin is Pin 1 rather than center)
and rotation offsets (where KiCad library orientation differs from JLCPCB/EasyEDA orientation).
"""

import csv
import math
import pcbnew
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
    # AO3400A SOT-23: KiCad standard footprint inverted 180 deg vs EasyEDA (verify in JLCPCB preview)
    "Q2": 180.0,  # 0 + 180 = 180.0 deg
    # Omron G6K-2F-Y DPDT Relay: KiCad vertical (rot 180) -> EasyEDA horizontal (rot 90)
    "K1": 270.0,  # 180 + 270 = 450 = 90.0 deg
    # SS36 SMC Schottky diodes: KiCad cathode pin 1 is left, EasyEDA C16237 pin 1 is right (180 deg flip)
    "D52": 180.0, # 90 + 180 = 270.0 deg
    "D53": 180.0, # 90 + 180 = 270.0 deg
    "D54": 180.0, # 90 + 180 = 270.0 deg
    "D55": 180.0, # 90 + 180 = 270.0 deg
}

# Derive centroids from the current board; never store absolute placement overrides.
def current_centroids(board):
    result = {}
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref in {"J2", "C11", "C60", "C70"}:
            pads = [p for p in fp.Pads() if p.GetNumber().isdigit()]
            result[ref] = tuple(sum(p.GetPosition()[i] for p in pads) / len(pads) / 1e6 for i in (0, 1))
        elif ref == "J3":
            # Receptacle F.Fab body is centered on its footprint origin.
            result[ref] = (fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6)
        elif ref in {"S3", "S4", "S5", "S6"}:
            # Manufacturer body spans local y=2.7..8.9; origin is pad 2.
            angle = math.radians(fp.GetOrientationDegrees())
            result[ref] = (fp.GetPosition().x / 1e6 + 5.8 * math.sin(angle),
                           fp.GetPosition().y / 1e6 + 5.8 * math.cos(angle))
    return result


def generate_cpl():
    pcb_file = BASE_DIR / "pi5_corona_hv.kicad_pcb"
    centroids = current_centroids(pcbnew.LoadBoard(str(pcb_file)))
    bom_file = BASE_DIR / "exports" / "jlcpcb-bom.csv"
    raw_pos_file = BASE_DIR / "exports" / "pi5_corona_hv_cpl.csv"
    out_cpl_file = BASE_DIR / "exports" / "jlcpcb-cpl.csv"

    # Always re-export raw position file strictly in MILLIMETERS
    subprocess.run(
        [
            "kicad-cli", "pcb", "export", "pos",
            "--units", "mm",
            "--format", "csv",
            "--exclude-dnp",
            "--output", str(raw_pos_file),
            str(pcb_file)
        ],
        check=True
    )

    # Keep native CSV data with repository-standard line endings.
    raw_pos_file.write_text(raw_pos_file.read_text())

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
        if des in centroids:
            bx, by = centroids[des]
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
            fieldnames=["Designator", "Mid X", "Mid Y", "Layer", "Rotation"],
            lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(cpl_rows)

    print(f"Generated {len(cpl_rows)} rows in {out_cpl_file}")


if __name__ == "__main__":
    generate_cpl()
