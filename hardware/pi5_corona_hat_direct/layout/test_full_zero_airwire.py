#!/usr/bin/env python3
import sys
import pcbnew
import subprocess
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
trial = ROOT / "layout/routing-trials"
board_path = trial / "test_u6_unloop.kicad_pcb"
out_path = trial / "test_zero_airwire.kicad_pcb"

b = pcbnew.LoadBoard(str(board_path))

def get_net(name):
    net = b.FindNet(name)
    if not net:
        raise ValueError(f"Net {name} not found!")
    return net

# --- Step 1: Collect all tracks/vias to remove ---
to_remove = []

for t in b.GetTracks():
    netname = t.GetNetname()
    if isinstance(t, pcbnew.PCB_VIA):
        pos = t.GetPosition()
        vx, vy = pos.x/1e6, pos.y/1e6
        # Old VBUS_IN via at (85.45, 71.60)
        if netname == "/01_power_mcu/VBUS_IN" and abs(vx - 85.45) < 0.1 and abs(vy - 71.60) < 0.1:
            to_remove.append(t)
    else:
        s, e = t.GetStart(), t.GetEnd()
        sx, sy, ex, ey = s.x/1e6, s.y/1e6, e.x/1e6, e.y/1e6
        # Old VBUS_IN diagonal tracks around U7
        if netname == "/01_power_mcu/VBUS_IN":
            if min(sx, ex) >= 81.5 and max(sx, ex) <= 86.5 and min(sy, ey) >= 66.5 and max(sy, ey) <= 72.5:
                if not (abs(sy - 67.0) < 0.05 and abs(ey - 67.0) < 0.05 and max(sx, ex) <= 80.6):
                    to_remove.append(t)
        # Old SDA tracks around U7
        if netname == "/01_power_mcu/SDA":
            if min(sx, ex) >= 79.5 and max(sx, ex) <= 85.5 and min(sy, ey) >= 68.5 and max(sy, ey) <= 72.0:
                to_remove.append(t)
        # Old SCL stubs at U7.5
        if netname == "/01_power_mcu/SCL":
            if min(sx, ex) >= 83.5 and max(sx, ex) <= 85.0 and min(sy, ey) >= 71.0 and max(sy, ey) <= 71.5:
                to_remove.append(t)
        # Old VBUS_RAW stub at (77.45, 68.0)
        if netname == "/01_power_mcu/VBUS_RAW":
            if max(sx, ex) <= 77.5 and min(sy, ey) >= 67.5 and max(sy, ey) <= 68.5:
                to_remove.append(t)
        # Old V18 stub at (80.20, 69.00)
        if netname == "/01_power_mcu/V18":
            if abs(ex - 80.20) < 0.05 and abs(ey - 69.00) < 0.05:
                to_remove.append(t)
        # Redundant U2.9 GND stub to the east
        if netname == "GND":
            if min(sx, ex) >= 91.7 and max(sx, ex) <= 92.4 and abs(sy - 139.28) < 0.05:
                to_remove.append(t)
        # Old GND stub (84.90, 72.25) -> (84.90, 72.20)
        if netname == "GND":
            if abs(sx - 84.90) < 0.05 and abs(ex - 84.90) < 0.05 and min(sy, ey) >= 72.19 and max(sy, ey) <= 72.26:
                to_remove.append(t)

print(f"Removing {len(to_remove)} tracks/vias...")
for t in to_remove:
    b.Remove(t)
    t.thisown = False

# --- Step 2: Move GND via at (84.90, 72.25) to (84.90, 72.50) ---
print("Moving GND via...")
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        pos = t.GetPosition()
        if abs(pos.x/1e6 - 84.90) < 0.1 and abs(pos.y/1e6 - 72.25) < 0.1:
            t.SetPosition(pcbnew.VECTOR2I(int(84.90 * 1e6), int(72.50 * 1e6)))
    elif t.GetNetname() == "GND":
        s, e = t.GetStart(), t.GetEnd()
        # Adjust F.Cu track to C17.2:
        if abs(s.x/1e6 - 84.90) < 0.05 and abs(s.y/1e6 - 72.20) < 0.05 and abs(e.x/1e6 - 87.0) < 0.05:
            t.SetStart(pcbnew.VECTOR2I(int(84.90 * 1e6), int(72.50 * 1e6)))
        if abs(e.x/1e6 - 84.90) < 0.05 and abs(e.y/1e6 - 72.20) < 0.05 and abs(s.x/1e6 - 87.0) < 0.05:
            t.SetEnd(pcbnew.VECTOR2I(int(84.90 * 1e6), int(72.50 * 1e6)))
        # Adjust B.Cu track:
        if t.GetLayer() == pcbnew.B_Cu:
            if abs(s.x/1e6 - 84.90) < 0.05 and abs(s.y/1e6 - 72.20) < 0.05:
                t.SetStart(pcbnew.VECTOR2I(int(84.90 * 1e6), int(72.50 * 1e6)))
            if abs(e.x/1e6 - 84.90) < 0.05 and abs(e.y/1e6 - 72.20) < 0.05:
                t.SetEnd(pcbnew.VECTOR2I(int(84.90 * 1e6), int(72.50 * 1e6)))
        # Adjust F.Cu track from U7.3 (83.95, 72.25) -> (84.90, 72.25):
        if t.GetLayer() == pcbnew.F_Cu and abs(s.x/1e6 - 84.90) < 0.05 and abs(s.y/1e6 - 72.25) < 0.05:
            t.SetStart(pcbnew.VECTOR2I(int(84.90 * 1e6), int(72.50 * 1e6)))
        if t.GetLayer() == pcbnew.F_Cu and abs(e.x/1e6 - 84.90) < 0.05 and abs(e.y/1e6 - 72.25) < 0.05:
            t.SetEnd(pcbnew.VECTOR2I(int(84.90 * 1e6), int(72.50 * 1e6)))

def add_track(layer_num, x1, y1, x2, y2, net, width=0.20):
    t = pcbnew.PCB_TRACK(b)
    t.SetLayer(layer_num)
    t.SetStart(pcbnew.VECTOR2I(int(round(x1 * 1e6)), int(round(y1 * 1e6))))
    t.SetEnd(pcbnew.VECTOR2I(int(round(x2 * 1e6)), int(round(y2 * 1e6))))
    t.SetWidth(int(round(width * 1e6)))
    t.SetNet(net)
    b.Add(t)
    return t

def add_via(x, y, net, dia=0.60, drill=0.30):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(int(round(x * 1e6)), int(round(y * 1e6))))
    v.SetWidth(int(round(dia * 1e6)))
    v.SetDrill(int(round(drill * 1e6)))
    v.SetNet(net)
    b.Add(v)
    return v

# --- Step 3: Add new tracks and vias ---
print("Adding new routes...")

# VBUS_IN clean B.Cu route:
net_vbus_in = get_net("/01_power_mcu/VBUS_IN")
add_track(pcbnew.B_Cu, 80.55, 67.00, 80.55, 67.50, net_vbus_in)
add_track(pcbnew.B_Cu, 80.55, 67.50, 86.20, 67.50, net_vbus_in)
add_track(pcbnew.B_Cu, 86.20, 67.50, 86.20, 73.00, net_vbus_in)

# SDA F.Cu path:
net_sda = get_net("/01_power_mcu/SDA")
add_track(pcbnew.F_Cu, 83.963, 71.750, 85.250, 71.750, net_sda)
add_track(pcbnew.F_Cu, 85.250, 71.750, 85.250, 68.600, net_sda)
add_track(pcbnew.F_Cu, 85.250, 68.600, 80.050, 68.600, net_sda)
add_track(pcbnew.F_Cu, 80.050, 68.600, 80.000, 68.650, net_sda)
add_track(pcbnew.F_Cu, 80.000, 68.650, 79.975, 68.650, net_sda)
add_track(pcbnew.F_Cu, 79.975, 68.650, 79.550, 69.075, net_sda)
add_track(pcbnew.F_Cu, 79.550, 69.075, 79.550, 69.150, net_sda)

# SCL complete route:
net_scl = get_net("/01_power_mcu/SCL")
add_track(pcbnew.F_Cu, 83.963, 71.250, 84.700, 71.250, net_scl)
add_track(pcbnew.F_Cu, 84.700, 71.250, 84.700, 69.000, net_scl)
add_via(84.700, 69.000, net_scl)
add_track(pcbnew.B_Cu, 84.700, 69.000, 84.700, 68.000, net_scl)
add_track(pcbnew.B_Cu, 84.700, 68.000, 88.500, 68.000, net_scl)
add_track(pcbnew.B_Cu, 88.500, 68.000, 88.500, 105.500, net_scl)
add_track(pcbnew.B_Cu, 88.500, 105.500, 79.900, 105.500, net_scl)
add_track(pcbnew.B_Cu, 79.900, 105.500, 79.900, 105.200, net_scl)

# VBUS_RAW:
net_vbus_raw = get_net("/01_power_mcu/VBUS_RAW")
add_track(pcbnew.F_Cu, 72.225, 68.000, 70.500, 68.000, net_vbus_raw)
add_via(70.500, 68.000, net_vbus_raw)
add_track(pcbnew.B_Cu, 70.500, 68.000, 70.500, 95.750, net_vbus_raw)
add_track(pcbnew.B_Cu, 70.500, 95.750, 89.300, 95.750, net_vbus_raw)
add_track(pcbnew.B_Cu, 89.300, 95.750, 89.300, 111.000, net_vbus_raw)

# V18:
net_v18 = get_net("/01_power_mcu/V18")
add_track(pcbnew.F_Cu, 80.750, 69.575, 80.875, 67.850, net_v18)
add_via(80.875, 67.850, net_v18)
add_track(pcbnew.B_Cu, 80.875, 67.850, 80.875, 61.000, net_v18)
add_track(pcbnew.B_Cu, 80.875, 61.000, 76.225, 61.000, net_v18)
add_track(pcbnew.B_Cu, 76.225, 61.000, 76.225, 71.000, net_v18)
add_via(76.225, 71.000, net_v18)

# EFUSE_ILM:
net_ilm = get_net("/01_power_mcu/EFUSE_ILM")
add_track(pcbnew.F_Cu, 90.100, 92.225, 89.400, 92.500, net_ilm)
add_track(pcbnew.F_Cu, 89.400, 92.500, 88.000, 92.500, net_ilm)
add_via(88.000, 92.500, net_ilm)
add_track(pcbnew.B_Cu, 88.000, 92.500, 85.300, 92.500, net_ilm)
add_track(pcbnew.B_Cu, 85.300, 92.500, 85.300, 96.000, net_ilm)
add_track(pcbnew.B_Cu, 85.300, 96.000, 94.300, 96.000, net_ilm)
add_track(pcbnew.B_Cu, 94.300, 96.000, 94.300, 97.000, net_ilm)

# DRV_B:
net_drvb = get_net("/02_drive_transformer/DRV_B")
add_track(pcbnew.F_Cu, 91.775, 138.625, 93.000, 139.300, net_drvb)
add_via(93.000, 139.300, net_drvb)
add_track(pcbnew.B_Cu, 93.000, 139.300, 94.000, 138.300, net_drvb)
add_track(pcbnew.B_Cu, 94.000, 138.300, 111.700, 138.300, net_drvb)
add_via(111.700, 138.300, net_drvb)

# HV_SENSE_ADC:
net_sense_adc = get_net("/HV_SENSE_ADC")
add_track(pcbnew.F_Cu, 82.500, 109.150, 82.500, 110.000, net_sense_adc)
add_track(pcbnew.F_Cu, 82.500, 110.000, 82.800, 110.300, net_sense_adc)
add_track(pcbnew.F_Cu, 82.800, 110.300, 82.800, 111.000, net_sense_adc)
add_via(82.800, 111.000, net_sense_adc)
add_track(pcbnew.B_Cu, 82.800, 111.000, 82.800, 113.000, net_sense_adc)
add_track(pcbnew.B_Cu, 82.800, 113.000, 107.000, 113.000, net_sense_adc)
add_track(pcbnew.B_Cu, 107.000, 113.000, 107.000, 186.000, net_sense_adc)
add_track(pcbnew.B_Cu, 107.000, 186.000, 109.850, 186.000, net_sense_adc)
add_track(pcbnew.B_Cu, 109.850, 186.000, 109.850, 187.700, net_sense_adc)

# HV_CURR_ADC:
net_curr_adc = get_net("/HV_CURR_ADC")
add_track(pcbnew.F_Cu, 83.000, 109.150, 83.000, 110.000, net_curr_adc)
add_track(pcbnew.F_Cu, 83.000, 110.000, 83.500, 110.500, net_curr_adc)
add_track(pcbnew.F_Cu, 83.500, 110.500, 83.500, 113.000, net_curr_adc)
add_via(83.500, 113.000, net_curr_adc)
add_track(pcbnew.B_Cu, 83.500, 113.000, 83.500, 114.000, net_curr_adc)
add_track(pcbnew.B_Cu, 83.500, 114.000, 105.000, 114.000, net_curr_adc)
add_track(pcbnew.B_Cu, 105.000, 114.000, 105.000, 184.500, net_curr_adc)
add_track(pcbnew.B_Cu, 105.000, 184.500, 95.200, 184.500, net_curr_adc)
add_via(95.200, 184.500, net_curr_adc)
add_track(pcbnew.F_Cu, 95.200, 184.500, 95.200, 185.200, net_curr_adc)

# --- Step 4: Refill zones and save ---
print("Refilling zones...")
for z in b.Zones():
    z.SetLocalClearance(int(round(0.30 * 1e6)))

filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())

b.BuildConnectivity()

pro_src = ROOT / "pi5_corona_hv.kicad_pro"
dru_src = ROOT / "pi5_corona_hv.kicad_dru"
shutil.copy2(pro_src, trial / "test_zero_airwire.kicad_pro")
shutil.copy2(dru_src, trial / "test_zero_airwire.kicad_dru")

pcbnew.SaveBoard(str(out_path), b)
# Restore pro file
shutil.copy2(pro_src, trial / "test_zero_airwire.kicad_pro")

print("Saved test_zero_airwire.kicad_pcb.")

# Run DRC
drc_out = trial / "test_zero_airwire_drc.json"
subprocess.run([
    "kicad-cli", "pcb", "drc",
    "--format", "json",
    "-o", str(drc_out),
    str(out_path)
], capture_output=True)

with open(str(drc_out)) as f:
    d = json.load(f)

violations = d.get("violations", [])
unc = d.get("unconnected_items", [])

clearance_v = [v for v in violations if "clearance" in v.get("type", "")]
other_v = [v for v in violations if "clearance" not in v.get("type", "")]

print(f"\n==========================================")
print(f"DRC RESULTS:")
print(f"  Unconnected Items:     {len(unc)}")
print(f"  Clearance Violations:  {len(clearance_v)}")
print(f"  Other Violations:      {len(other_v)}")
print(f"==========================================")

if unc:
    print("\nUnconnected items:")
    for u in unc:
        items = [it.get("description") for it in u.get("items", [])]
        print(f"  - {u.get('type')}: {' VS '.join(items)}")

if clearance_v:
    print("\nClearance violations:")
    for v in clearance_v[:10]:
        print(f"  - {v.get('type')}: {v.get('description')}")

if other_v:
    print("\nOther violations:")
    for v in other_v[:10]:
        print(f"  - {v.get('type')}: {v.get('description')}")

