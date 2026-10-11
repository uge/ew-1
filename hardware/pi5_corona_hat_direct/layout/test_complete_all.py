#!/usr/bin/env python3
"""
test_complete_all.py
Takes test_single_route.kicad_pcb (which already has BULK_EN solved)
and implements all remaining connections, removes old blocking loops/stubs,
refills zones, and tests DRC.
"""

from pathlib import Path
import json
import shutil
import subprocess
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
trial = ROOT / "layout/routing-trials"

pcb_in = trial / "test_single_route.kicad_pcb"
b = pcbnew.LoadBoard(str(pcb_in))

def add_track(layer, netname, x1, y1, x2, y2, width=0.2):
    net = b.FindNet(netname)
    if not net:
        raise ValueError(f"Net {netname} not found")
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(int(x1*1e6), int(y1*1e6)))
    t.SetEnd(pcbnew.VECTOR2I(int(x2*1e6), int(y2*1e6)))
    t.SetWidth(pcbnew.FromMM(width))
    t.SetLayer(layer)
    t.SetNet(net)
    b.Add(t)
    return t

def add_via(netname, x, y, size=0.6, drill=0.3):
    net = b.FindNet(netname)
    if not net:
        raise ValueError(f"Net {netname} not found")
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(int(x*1e6), int(y*1e6)))
    v.SetWidth(pcbnew.FromMM(size))
    v.SetDrill(pcbnew.FromMM(drill))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetNet(net)
    b.Add(v)
    return v

# =========================================================================
# Clean up old blocking tracks and dangling elements
# =========================================================================

# 1. Remove the old DRV_nFAULT F.Cu loop that cages U2 pins 5..8
for t in list(b.GetTracks()):
    if t.GetNetname() == "/02_drive_transformer/DRV_nFAULT" and t.GetLayer() == pcbnew.F_Cu:
        s, e = t.GetStart(), t.GetEnd()
        sx, sy, ex, ey = s.x/1e6, s.y/1e6, e.x/1e6, e.y/1e6
        # Remove the loop around U2
        if 85.0 <= sx <= 93.0 and 136.0 <= sy <= 140.5:
            b.Remove(t)
            t.thisown = False

# 2. Remove the dangling via on VBUS_IN at (80.55, 67.0)
for t in list(b.GetTracks()):
    if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == "/01_power_mcu/VBUS_IN":
        pos = t.GetPosition()
        if abs(pos.x/1e6 - 80.55) < 0.1 and abs(pos.y/1e6 - 67.0) < 0.1:
            b.Remove(t)
            t.thisown = False

# 3. Remove the dangling GND loop on F.Cu south of U6
for t in list(b.GetTracks()):
    if t.GetNetname() == "GND" and t.GetLayer() == pcbnew.F_Cu:
        s, e = t.GetStart(), t.GetEnd()
        sx, sy, ex, ey = s.x/1e6, s.y/1e6, e.x/1e6, e.y/1e6
        if 80.5 <= sx <= 84.0 and 109.8 <= sy <= 110.6:
            b.Remove(t)
            t.thisown = False

# Add a clean single GND via for U6 pins 1..3 at (81.0, 109.9)
add_via("GND", 81.0, 109.9)

# 4. Remove tiny stubs
for t in list(b.GetTracks()):
    if not isinstance(t, pcbnew.PCB_VIA):
        if t.GetLength() < pcbnew.FromMM(0.04):
            # very tiny stub
            b.Remove(t)
            t.thisown = False

# =========================================================================
# Route the remaining connections
# =========================================================================

# --- 1. USB_DP ---
# Pad A6 (88.25, 58.42) to Pad B6 (87.25, 58.42)
add_track(pcbnew.F_Cu, "/01_power_mcu/USB_DP", 87.25, 58.42, 88.25, 58.42, 0.25)

# --- 2. VIN_PD ---
# Connect B.Cu via at (86.2, 95.05) to track at (89.6, 93.4)
add_track(pcbnew.B_Cu, "/01_power_mcu/VIN_PD", 86.2, 95.05, 87.5, 93.4, 0.25)
add_track(pcbnew.B_Cu, "/01_power_mcu/VIN_PD", 87.5, 93.4, 89.6, 93.4, 0.25)

# --- 3. Net-(R8-Pad2) ---
# R8.2 (128.0, 183.25) to R9.1 (128.0, 191.25)
# Jog west to (124.0, 183.25), north to (124.0, 182.2), via to B.Cu, south to (124.0, 191.25), via to F.Cu, east to R9.1
add_track(pcbnew.F_Cu, "Net-(R8-Pad2)", 128.0, 183.25, 124.0, 183.25, 0.2)
add_track(pcbnew.F_Cu, "Net-(R8-Pad2)", 124.0, 183.25, 124.0, 182.2, 0.2)
add_via("Net-(R8-Pad2)", 124.0, 182.2)
add_track(pcbnew.B_Cu, "Net-(R8-Pad2)", 124.0, 182.2, 124.0, 191.25, 0.2)
add_via("Net-(R8-Pad2)", 124.0, 191.25)
add_track(pcbnew.F_Cu, "Net-(R8-Pad2)", 124.0, 191.25, 128.0, 191.25, 0.2)

# --- 4. HV_CURR_ADC ---
# Part A: R91.2 (91.25, 180.0) to C14.1 track at (91.15, 185.25)
add_track(pcbnew.F_Cu, "/HV_CURR_ADC", 91.25, 180.0, 91.25, 185.20, 0.2)
add_track(pcbnew.F_Cu, "/HV_CURR_ADC", 91.25, 185.20, 91.15, 185.25, 0.2)
# Part B: U6.5 (83.0, 109.15) to R91.2 (91.25, 180.0) via B.Cu
add_track(pcbnew.F_Cu, "/HV_CURR_ADC", 83.0, 109.15, 83.8, 110.5, 0.2)
add_via("/HV_CURR_ADC", 83.8, 110.5)
add_track(pcbnew.B_Cu, "/HV_CURR_ADC", 83.8, 110.5, 83.8, 112.0, 0.2)
add_track(pcbnew.B_Cu, "/HV_CURR_ADC", 83.8, 112.0, 98.0, 112.0, 0.2)
add_track(pcbnew.B_Cu, "/HV_CURR_ADC", 98.0, 112.0, 98.0, 178.0, 0.2)
add_track(pcbnew.B_Cu, "/HV_CURR_ADC", 98.0, 178.0, 91.25, 178.0, 0.2)
add_via("/HV_CURR_ADC", 91.25, 178.0)
add_track(pcbnew.F_Cu, "/HV_CURR_ADC", 91.25, 178.0, 91.25, 180.0, 0.2)

# --- 5. HV_SENSE_ADC ---
# U6.4 (82.5, 109.15) to D1.3 via at (109.85, 187.7) via B.Cu
add_track(pcbnew.F_Cu, "/HV_SENSE_ADC", 82.5, 109.15, 82.5, 110.5, 0.2)
add_via("/HV_SENSE_ADC", 82.5, 110.5)
add_track(pcbnew.B_Cu, "/HV_SENSE_ADC", 82.5, 110.5, 82.5, 113.0, 0.2)
add_track(pcbnew.B_Cu, "/HV_SENSE_ADC", 82.5, 113.0, 100.0, 113.0, 0.2)
add_track(pcbnew.B_Cu, "/HV_SENSE_ADC", 100.0, 113.0, 109.85, 170.0, 0.2)
add_track(pcbnew.B_Cu, "/HV_SENSE_ADC", 109.85, 170.0, 109.85, 187.7, 0.2)

# --- 6. DRV_B at C63 ---
# Pad 2 (110.0, 181.05) to D55.1 (117.0, 168.4) via B.Cu
add_track(pcbnew.F_Cu, "/02_drive_transformer/DRV_B", 110.0, 181.05, 108.5, 181.05, 0.25)
add_via("/02_drive_transformer/DRV_B", 108.5, 181.05)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_B", 108.5, 181.05, 108.5, 175.0, 0.25)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_B", 108.5, 175.0, 117.0, 170.0, 0.25)
add_via("/02_drive_transformer/DRV_B", 117.0, 170.0)
add_track(pcbnew.F_Cu, "/02_drive_transformer/DRV_B", 117.0, 170.0, 117.0, 168.4, 0.25)

# --- 7. DRV_B at U2.10 ---
# U2.10 (91.775, 138.625) to D54.2 at (122.0, 148.6)
add_track(pcbnew.F_Cu, "/02_drive_transformer/DRV_B", 91.775, 138.625, 92.4, 138.625, 0.25)
add_track(pcbnew.F_Cu, "/02_drive_transformer/DRV_B", 92.4, 138.625, 92.4, 141.8, 0.25)
add_via("/02_drive_transformer/DRV_B", 92.4, 141.8)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_B", 92.4, 141.8, 122.0, 141.8, 0.25)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_B", 122.0, 141.8, 122.0, 148.6, 0.25)
add_via("/02_drive_transformer/DRV_B", 122.0, 148.6)

# --- 8. DRV_A at U2.8 ---
# U2.8 (86.225, 139.275) to D52.2 at (105.0, 148.6)
add_track(pcbnew.F_Cu, "/02_drive_transformer/DRV_A", 86.225, 139.275, 86.225, 140.8, 0.25)
add_via("/02_drive_transformer/DRV_A", 86.225, 140.8)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_A", 86.225, 140.8, 105.0, 140.8, 0.25)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_A", 105.0, 140.8, 105.0, 148.6, 0.25)
add_via("/02_drive_transformer/DRV_A", 105.0, 148.6)

# --- 9. DRV_nFAULT (rerouted on B.Cu) ---
# U2.4 (86.225, 136.675) to R63.2 at (95.175, 137.0)
add_track(pcbnew.F_Cu, "/02_drive_transformer/DRV_nFAULT", 86.225, 136.675, 83.6, 136.675, 0.2)
add_via("/02_drive_transformer/DRV_nFAULT", 83.6, 136.675)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_nFAULT", 83.6, 136.675, 83.6, 142.8, 0.2)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_nFAULT", 83.6, 142.8, 95.175, 142.8, 0.2)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_nFAULT", 95.175, 142.8, 95.175, 137.0, 0.2)
add_via("/02_drive_transformer/DRV_nFAULT", 95.175, 137.0)

# --- 10. DRV_IPROPI at U2.6 ---
# U2.6 (86.225, 137.975) to R61.1 via at (87.2, 127.95)
add_track(pcbnew.F_Cu, "/02_drive_transformer/DRV_IPROPI", 86.225, 137.975, 83.6, 137.975, 0.2)
add_via("/02_drive_transformer/DRV_IPROPI", 83.6, 137.975)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_IPROPI", 83.6, 137.975, 83.6, 127.95, 0.2)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_IPROPI", 83.6, 127.95, 87.2, 127.95, 0.2)

# --- 11. DRV_IMODE at U2.7 ---
# U2.7 (86.225, 138.625) to R62.1 via at (95.0, 128.7)
add_track(pcbnew.F_Cu, "/02_drive_transformer/DRV_IMODE", 86.225, 138.625, 84.8, 138.625, 0.2)
add_via("/02_drive_transformer/DRV_IMODE", 84.8, 138.625)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_IMODE", 84.8, 138.625, 84.8, 128.7, 0.2)
add_track(pcbnew.B_Cu, "/02_drive_transformer/DRV_IMODE", 84.8, 128.7, 95.0, 128.7, 0.2)

# --- 12. 3V3 at U2.5 ---
# U2.5 (86.225, 137.325) to U2.16 (91.775, 134.725)
add_track(pcbnew.F_Cu, "3V3", 86.225, 137.325, 84.8, 137.325, 0.2)
add_via("3V3", 84.8, 137.325)
add_track(pcbnew.B_Cu, "3V3", 84.8, 137.325, 84.8, 133.5, 0.2)
add_track(pcbnew.B_Cu, "3V3", 84.8, 133.5, 91.775, 133.5, 0.2)
add_via("3V3", 91.775, 133.5)
add_track(pcbnew.F_Cu, "3V3", 91.775, 133.5, 91.775, 134.725, 0.2)

# --- 13. PD_VMON ---
# U6.6 (83.0, 104.85) to R10.2 (91.8, 111.0)
add_track(pcbnew.F_Cu, "/01_power_mcu/PD_VMON", 83.0, 104.85, 85.0, 104.5, 0.2)
add_via("/01_power_mcu/PD_VMON", 85.0, 104.5)
add_track(pcbnew.B_Cu, "/01_power_mcu/PD_VMON", 85.0, 104.5, 91.8, 104.5, 0.2)
add_track(pcbnew.B_Cu, "/01_power_mcu/PD_VMON", 91.8, 104.5, 91.8, 110.0, 0.2)
add_via("/01_power_mcu/PD_VMON", 91.8, 110.0)
add_track(pcbnew.F_Cu, "/01_power_mcu/PD_VMON", 91.8, 110.0, 91.8, 111.0, 0.2)

# --- 14. SCL ---
# U7.5 (83.95, 71.25) to SCL via at (79.90, 105.20)
add_track(pcbnew.F_Cu, "/01_power_mcu/SCL", 83.95, 71.25, 86.5, 71.20, 0.2)
add_via("/01_power_mcu/SCL", 86.5, 71.20)
add_track(pcbnew.B_Cu, "/01_power_mcu/SCL", 86.5, 71.20, 88.5, 71.20, 0.2)
add_track(pcbnew.B_Cu, "/01_power_mcu/SCL", 88.5, 71.20, 88.5, 104.8, 0.2)
add_track(pcbnew.B_Cu, "/01_power_mcu/SCL", 88.5, 104.8, 80.30, 104.80, 0.2)

# --- 15. V18 ---
# U7.12 track at (80.20, 69.00) to C18 pad 1 at (76.225, 71.0)
# Bridge under USB_DN via B.Cu: (79.8, 69.5) -> (77.8, 69.5)
add_track(pcbnew.F_Cu, "/01_power_mcu/V18", 80.20, 69.00, 79.8, 69.5, 0.2)
add_via("/01_power_mcu/V18", 79.8, 69.5)
add_track(pcbnew.B_Cu, "/01_power_mcu/V18", 79.8, 69.5, 77.8, 69.5, 0.2)
add_via("/01_power_mcu/V18", 77.8, 69.5)
add_track(pcbnew.F_Cu, "/01_power_mcu/V18", 77.8, 69.5, 76.225, 69.5, 0.2)
add_track(pcbnew.F_Cu, "/01_power_mcu/V18", 76.225, 69.5, 76.225, 71.0, 0.2)

# --- 16. EFUSE_ILM ---
# U9.9 (90.1, 92.225) to R73.1 via at (94.3, 97.0)
add_track(pcbnew.F_Cu, "/01_power_mcu/EFUSE_ILM", 90.1, 92.225, 88.5, 92.20, 0.2)
add_via("/01_power_mcu/EFUSE_ILM", 88.5, 92.20)
add_track(pcbnew.B_Cu, "/01_power_mcu/EFUSE_ILM", 88.5, 92.20, 88.5, 96.0, 0.2)
add_track(pcbnew.B_Cu, "/01_power_mcu/EFUSE_ILM", 88.5, 96.0, 94.3, 96.0, 0.2)
add_track(pcbnew.B_Cu, "/01_power_mcu/EFUSE_ILM", 94.3, 96.0, 94.3, 97.0, 0.2)

# Ensure local clearance on zones is 0.3mm to fix NPTH hole clearance
for z in b.Zones():
    if not z.GetIsRuleArea():
        z.SetLocalClearance(pcbnew.FromMM(0.3))

filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
b.BuildConnectivity()

out_pcb = trial / "test_complete_all.kicad_pcb"
pcbnew.SaveBoard(str(out_pcb), b)
shutil.copy2(ROOT / "pi5_corona_hv.kicad_pro", trial / "test_complete_all.kicad_pro")
shutil.copy2(ROOT / "pi5_corona_hv.kicad_dru", trial / "test_complete_all.kicad_dru")

drc_json = trial / "test_complete_all_drc.json"
subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "-o", str(drc_json), str(out_pcb)], capture_output=True)
with open(drc_json) as f:
    d = json.load(f)

unc = d.get("unconnected_items", [])
clearance_v = [x for x in d.get("violations", []) if x["type"] == "clearance"]
other_v = [x for x in d.get("violations", []) if x["type"] not in ["clearance", "lib_footprint_issues"]]

print("="*60)
print(f"DRC Clearance Violations: {len(clearance_v)}")
print(f"DRC Other Violations:     {len(other_v)}")
print(f"Unconnected Items:        {len(unc)}")
print("="*60)
for v in clearance_v[:10]:
    print("  Clearance:", v.get("description"), [i.get("description") for i in v.get("items", [])])
for o in other_v[:10]:
    print("  Other:", o.get("type"), o.get("description"), [i.get("description") for i in o.get("items", [])])
for u in unc[:10]:
    print("  Unconnected:", u.get("description"), [i.get("description") for i in u.get("items", [])])
