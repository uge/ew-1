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
        # Old orphan VBUS_IN via at (80.55, 67.00)
        if netname == "/01_power_mcu/VBUS_IN" and abs(vx - 80.55) < 0.1 and abs(vy - 67.00) < 0.1:
            to_remove.append(t)
        # Old GND via at (84.90, 72.25)
        if netname == "GND" and abs(vx - 84.90) < 0.1 and abs(vy - 72.25) < 0.1:
            to_remove.append(t)
    else:
        s, e = t.GetStart(), t.GetEnd()
        sx, sy, ex, ey = s.x/1e6, s.y/1e6, e.x/1e6, e.y/1e6
        # Old VBUS_IN diagonal tracks around U7
        if netname == "/01_power_mcu/VBUS_IN":
            if min(sx, ex) >= 79.0 and max(sx, ex) <= 86.5 and min(sy, ey) >= 66.5 and max(sy, ey) <= 72.5:
                to_remove.append(t)
            # Old dangling B.Cu stub (86.20, 73.00) -> (86.20, 72.35)
            if abs(sx - 86.20) < 0.05 and abs(ex - 86.20) < 0.05 and min(sy, ey) >= 72.30 and max(sy, ey) <= 73.05:
                to_remove.append(t)
            # Dangling VBUS_IN stub (79.475, 67.0) -> (80.55, 67.0)
            if min(sx, ex) >= 79.4 and max(sx, ex) <= 80.6 and abs(sy - 67.0) < 0.05:
                to_remove.append(t)
        # Old SDA tracks around U7
        if netname == "/01_power_mcu/SDA":
            if min(sx, ex) >= 79.5 and max(sx, ex) <= 86.0 and min(sy, ey) >= 68.4 and max(sy, ey) <= 72.0:
                to_remove.append(t)
        # Old SCL stubs at U7.5
        if netname == "/01_power_mcu/SCL":
            if min(sx, ex) >= 83.5 and max(sx, ex) <= 85.5 and min(sy, ey) >= 69.5 and max(sy, ey) <= 72.0:
                to_remove.append(t)
            # Old SCL dangling stub at U6.10: (81.000, 104.075) -> (80.500, 103.600)
            if min(sx, ex) >= 80.4 and max(sx, ex) <= 81.1 and min(sy, ey) >= 103.5 and max(sy, ey) <= 104.2:
                to_remove.append(t)
        # Old VBUS_RAW stub at (77.45, 68.0)
        if netname == "/01_power_mcu/VBUS_RAW":
            if max(sx, ex) <= 77.5 and min(sy, ey) >= 67.5 and max(sy, ey) <= 68.5:
                to_remove.append(t)
        # Old V18 tracks around U7 (clean all old stubs)
        if netname == "/01_power_mcu/V18":
            if min(sx, ex) >= 80.0 and max(sx, ex) <= 81.5 and min(sy, ey) >= 68.5 and max(sy, ey) <= 70.5:
                to_remove.append(t)
        # Redundant GND stubs
        if netname == "GND":
            if min(sx, ex) >= 91.7 and max(sx, ex) <= 92.4 and abs(sy - 139.275) < 0.05:
                to_remove.append(t)
            # Dangling stub at U2.15: (91.775, 135.375) -> (92.350, 135.375) -> (92.400, 135.300)
            if min(sx, ex) >= 91.7 and max(sx, ex) <= 92.5 and min(sy, ey) >= 135.2 and max(sy, ey) <= 135.5:
                to_remove.append(t)
            # Old GND stub (84.425, 72.25) -> (84.50, 72.30)
            if abs(sx - 84.425) < 0.05 and abs(sy - 72.25) < 0.05:
                to_remove.append(t)
            # Old GND stub (84.90, 72.25) -> (84.90, 72.20)
            if abs(sx - 84.90) < 0.05 and abs(ex - 84.90) < 0.05 and min(sy, ey) >= 72.19 and max(sy, ey) <= 72.26:
                to_remove.append(t)
            # Old GND track connected to (84.90, 72.25)
            if abs(sx - 84.90) < 0.05 and abs(sy - 72.25) < 0.05 and abs(ex - 83.95) < 0.05:
                to_remove.append(t)
            # Dangling GND stub at U6.1: (81.000, 109.925) -> (80.500, 110.400)
            if min(sx, ex) >= 80.4 and max(sx, ex) <= 81.1 and min(sy, ey) >= 109.9 and max(sy, ey) <= 110.5:
                to_remove.append(t)
            # Dangling GND stub at U6 via: (82.000, 110.500) -> (82.100, 110.400) -> (82.000, 110.300)
            if min(sx, ex) >= 81.9 and max(sx, ex) <= 82.2 and min(sy, ey) >= 110.2 and max(sy, ey) <= 110.6:
                to_remove.append(t)
            # Dangling GND stub at U9: (89.750, 91.775) -> (89.700, 91.800)
            if min(sx, ex) >= 89.6 and max(sx, ex) <= 89.8 and min(sy, ey) >= 91.7 and max(sy, ey) <= 91.9:
                to_remove.append(t)
            # Dangling GND stubs at U2 thermal pad
            if min(sx, ex) >= 87.0 and max(sx, ex) <= 91.0 and min(sy, ey) >= 133.7 and max(sy, ey) <= 134.9:
                if (abs(sx - 87.55) < 0.05 and abs(ex - 87.10) < 0.05) or \
                   (abs(sx - 89.35) < 0.05 and abs(ex - 90.40) < 0.05) or \
                   (abs(sx - 90.45) < 0.05 and abs(ex - 90.90) < 0.05):
                    to_remove.append(t)
        # Dangling EFUSE_ILM stub: (89.750, 92.225) -> (89.700, 92.200)
        if netname == "/01_power_mcu/EFUSE_ILM":
            if min(sx, ex) >= 89.6 and max(sx, ex) <= 89.8 and min(sy, ey) >= 92.1 and max(sy, ey) <= 92.3:
                to_remove.append(t)
        # Old Net-(R8-Pad2) tracks that swing too close to R142
        if netname == "Net-(R8-Pad2)":
            to_remove.append(t)
        # Old HV_BRIDGE B.Cu track between (93.850, 139.300) and (93.000, 138.450)
        if netname == "/02_drive_transformer/HV_BRIDGE" and t.GetLayer() == pcbnew.B_Cu:
            if abs(min(sx, ex) - 93.00) < 0.1 and abs(max(sx, ex) - 93.85) < 0.1:
                to_remove.append(t)
        # Old HV_RETURN B.Cu branch at Y=185: (121.000, 185.000) -> (131.000, 185.000) and (121.000, 177.000) -> (121.000, 185.000)
        if netname == "/HV_RETURN" and t.GetLayer() == pcbnew.B_Cu:
            if abs(sx - 121.000) < 0.1 and abs(ex - 121.000) < 0.1 and min(sy, ey) >= 176.9 and max(sy, ey) <= 185.1:
                to_remove.append(t)
            if min(sx, ex) >= 120.9 and max(sx, ex) <= 131.1 and abs(sy - 185.000) < 0.1 and abs(ey - 185.000) < 0.1:
                to_remove.append(t)

print(f"Removing {len(to_remove)} tracks/vias...")
for t in to_remove:
    b.Remove(t)
    t.thisown = False

# --- Step 2: Adjust shifted vias and tracks ---
print("Adjusting shifted vias and tracks...")
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        pos = t.GetPosition()
        vx, vy = pos.x/1e6, pos.y/1e6
        # HV_BRIDGE via 1 at (93.00, 138.45) -> move to (93.10, 138.30)
        if t.GetNetname() == "/02_drive_transformer/HV_BRIDGE" and abs(vx - 93.00) < 0.05 and abs(vy - 138.45) < 0.05:
            t.SetPosition(pcbnew.VECTOR2I(int(93.10 * 1e6), int(138.30 * 1e6)))
    elif t.GetNetname() == "/02_drive_transformer/HV_BRIDGE":
        s, e = t.GetStart(), t.GetEnd()
        # Adjust F.Cu track (92.65, 138.10) -> (93.00, 138.45)
        if abs(e.x/1e6 - 93.00) < 0.05 and abs(e.y/1e6 - 138.45) < 0.05:
            t.SetEnd(pcbnew.VECTOR2I(int(93.10 * 1e6), int(138.30 * 1e6)))
        if abs(s.x/1e6 - 93.00) < 0.05 and abs(s.y/1e6 - 138.45) < 0.05:
            t.SetStart(pcbnew.VECTOR2I(int(93.10 * 1e6), int(138.30 * 1e6)))

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

# --- Step 3: Add clean routes ---
print("Adding clean routes...")

# 1. Shifted GND via and track at U7.3:
net_gnd = get_net("GND")
add_track(pcbnew.F_Cu, 83.963, 72.250, 84.900, 72.250, net_gnd)
add_track(pcbnew.F_Cu, 84.900, 72.250, 84.900, 72.600, net_gnd)
add_via(84.900, 72.600, net_gnd)
add_track(pcbnew.B_Cu, 84.900, 72.600, 84.900, 72.200, net_gnd)

# 2. HV_RETURN shifted B.Cu branch at Y=188:
net_hv_return = get_net("/HV_RETURN")
add_track(pcbnew.B_Cu, 121.000, 177.000, 121.000, 188.000, net_hv_return)
add_track(pcbnew.B_Cu, 121.000, 188.000, 131.000, 188.000, net_hv_return)

# 3. Net-(R8-Pad2) west hop over PRI_A:
net_r8 = get_net("Net-(R8-Pad2)")
add_track(pcbnew.F_Cu, 128.000, 183.250, 126.500, 183.250, net_r8)
add_via(126.500, 183.250, net_r8)
add_track(pcbnew.B_Cu, 126.500, 183.250, 126.500, 185.500, net_r8)
add_via(126.500, 185.500, net_r8)
add_track(pcbnew.F_Cu, 126.500, 185.500, 126.500, 191.250, net_r8)
add_track(pcbnew.F_Cu, 126.500, 191.250, 128.000, 191.250, net_r8)

# 4. 3V3 bridge connection:
net_3v3 = get_net("3V3")
add_track(pcbnew.F_Cu, 93.400, 133.700, 93.175, 133.900, net_3v3)

# 5. HV_BRIDGE replacement B.Cu track (bent west to maximize clearance to DRV_B via):
net_hv_bridge = get_net("/02_drive_transformer/HV_BRIDGE")
add_track(pcbnew.B_Cu, 93.100, 138.300, 93.100, 138.800, net_hv_bridge)
add_track(pcbnew.B_Cu, 93.100, 138.800, 93.600, 139.300, net_hv_bridge)
add_track(pcbnew.B_Cu, 93.600, 139.300, 93.850, 139.300, net_hv_bridge)

# 6. DRV_B escape:
net_drvb = get_net("/02_drive_transformer/DRV_B")
add_track(pcbnew.F_Cu, 92.400, 138.700, 93.100, 139.150, net_drvb)
add_track(pcbnew.F_Cu, 93.100, 139.150, 93.900, 138.400, net_drvb)
add_via(93.900, 138.400, net_drvb)
add_track(pcbnew.B_Cu, 93.900, 138.400, 93.900, 138.300, net_drvb)
add_track(pcbnew.B_Cu, 93.900, 138.300, 111.000, 138.300, net_drvb)
add_track(pcbnew.B_Cu, 111.000, 138.300, 112.000, 137.300, net_drvb)
add_via(112.000, 137.300, net_drvb)
add_track(pcbnew.F_Cu, 112.000, 137.300, 111.700, 137.600, net_drvb)
add_track(pcbnew.F_Cu, 111.700, 137.600, 111.700, 138.300, net_drvb)

# 7. SCL route:
net_scl = get_net("/01_power_mcu/SCL")
add_track(pcbnew.F_Cu, 83.963, 71.250, 84.700, 71.250, net_scl)
add_track(pcbnew.F_Cu, 84.700, 71.250, 84.700, 70.000, net_scl)
add_via(84.700, 70.000, net_scl)
add_track(pcbnew.B_Cu, 84.700, 70.000, 84.700, 68.000, net_scl)
add_track(pcbnew.B_Cu, 84.700, 68.000, 95.000, 68.000, net_scl)
add_track(pcbnew.B_Cu, 95.000, 68.000, 95.000, 106.000, net_scl)
add_track(pcbnew.B_Cu, 95.000, 106.000, 90.600, 106.000, net_scl)
add_via(90.600, 106.000, net_scl)
add_track(pcbnew.F_Cu, 90.600, 106.000, 88.000, 106.000, net_scl)
add_via(88.000, 106.000, net_scl)
add_track(pcbnew.B_Cu, 88.000, 106.000, 86.200, 107.800, net_scl)
add_track(pcbnew.B_Cu, 86.200, 107.800, 79.900, 107.800, net_scl)
add_track(pcbnew.B_Cu, 79.900, 107.800, 79.900, 105.200, net_scl)

# 8. VBUS_RAW corridor:
net_vbus_raw = get_net("/01_power_mcu/VBUS_RAW")
add_via(72.225, 68.000, net_vbus_raw)
add_track(pcbnew.B_Cu, 72.225, 68.000, 70.500, 68.000, net_vbus_raw)
add_track(pcbnew.B_Cu, 70.500, 68.000, 70.500, 100.000, net_vbus_raw)
add_track(pcbnew.B_Cu, 70.500, 100.000, 89.300, 100.000, net_vbus_raw)
add_track(pcbnew.B_Cu, 89.300, 100.000, 89.300, 111.000, net_vbus_raw)

# 9. EFUSE_ILM:
net_ilm = get_net("/01_power_mcu/EFUSE_ILM")
add_track(pcbnew.F_Cu, 90.100, 92.225, 87.125, 92.225, net_ilm)
add_track(pcbnew.F_Cu, 87.125, 92.225, 86.300, 93.050, net_ilm)
add_via(86.300, 93.050, net_ilm)
add_track(pcbnew.B_Cu, 86.300, 93.050, 85.300, 93.050, net_ilm)
add_track(pcbnew.B_Cu, 85.300, 93.050, 85.300, 96.000, net_ilm)
add_track(pcbnew.B_Cu, 85.300, 96.000, 94.300, 96.000, net_ilm)
add_track(pcbnew.B_Cu, 94.300, 96.000, 94.300, 97.000, net_ilm)

# 10. V18:
net_v18 = get_net("/01_power_mcu/V18")
add_track(pcbnew.F_Cu, 80.750, 70.037, 80.500, 69.300, net_v18)
add_via(80.500, 69.300, net_v18)
add_track(pcbnew.B_Cu, 80.500, 69.300, 80.875, 69.300, net_v18)
add_track(pcbnew.B_Cu, 80.875, 69.300, 80.875, 61.000, net_v18)
add_track(pcbnew.B_Cu, 80.875, 61.000, 76.225, 61.000, net_v18)
add_track(pcbnew.B_Cu, 76.225, 61.000, 76.225, 71.000, net_v18)
add_via(76.225, 71.000, net_v18)

# 11. SDA F.Cu path:
net_sda = get_net("/01_power_mcu/SDA")
add_track(pcbnew.F_Cu, 83.963, 71.750, 85.400, 71.750, net_sda)
add_track(pcbnew.F_Cu, 85.400, 71.750, 85.400, 68.680, net_sda)
add_track(pcbnew.F_Cu, 85.400, 68.680, 80.150, 68.680, net_sda)
add_track(pcbnew.F_Cu, 80.150, 68.680, 79.550, 69.150, net_sda)

# 12. VBUS_IN clean route:
net_vbus_in = get_net("/01_power_mcu/VBUS_IN")
add_track(pcbnew.F_Cu, 79.475, 67.000, 79.475, 67.500, net_vbus_in)
add_track(pcbnew.F_Cu, 79.475, 67.500, 86.200, 67.500, net_vbus_in)
add_track(pcbnew.F_Cu, 86.200, 67.500, 86.200, 70.500, net_vbus_in)
add_via(86.200, 70.500, net_vbus_in)
add_track(pcbnew.B_Cu, 86.200, 70.500, 86.200, 73.000, net_vbus_in)

# 13. HV_CURR_ADC:
net_curr_adc = get_net("/HV_CURR_ADC")
add_track(pcbnew.F_Cu, 83.000, 109.150, 83.000, 109.700, net_curr_adc)
add_track(pcbnew.F_Cu, 83.000, 109.700, 83.700, 110.400, net_curr_adc)
add_track(pcbnew.F_Cu, 83.700, 110.400, 85.500, 110.400, net_curr_adc)
add_via(85.500, 110.400, net_curr_adc)
add_track(pcbnew.B_Cu, 85.500, 110.400, 85.500, 114.200, net_curr_adc)
add_track(pcbnew.B_Cu, 85.500, 114.200, 105.000, 114.200, net_curr_adc)
add_track(pcbnew.B_Cu, 105.000, 114.200, 105.000, 136.500, net_curr_adc)
add_via(105.000, 136.500, net_curr_adc)
add_track(pcbnew.F_Cu, 105.000, 136.500, 105.000, 140.000, net_curr_adc)
add_via(105.000, 140.000, net_curr_adc)
add_track(pcbnew.B_Cu, 105.000, 140.000, 105.000, 184.500, net_curr_adc)
add_track(pcbnew.B_Cu, 105.000, 184.500, 95.200, 184.500, net_curr_adc)
add_via(95.200, 184.500, net_curr_adc)
add_track(pcbnew.F_Cu, 95.200, 184.500, 95.200, 185.200, net_curr_adc)

# 14. HV_SENSE_ADC:
net_sense_adc = get_net("/HV_SENSE_ADC")
add_track(pcbnew.F_Cu, 82.500, 109.150, 82.500, 110.100, net_sense_adc)
add_track(pcbnew.F_Cu, 82.500, 110.100, 82.700, 110.300, net_sense_adc)
add_track(pcbnew.F_Cu, 82.700, 110.300, 82.700, 111.100, net_sense_adc)
add_track(pcbnew.F_Cu, 82.700, 111.100, 86.700, 111.100, net_sense_adc)
add_track(pcbnew.F_Cu, 86.700, 111.100, 86.700, 110.550, net_sense_adc)
add_via(86.700, 110.550, net_sense_adc)
add_track(pcbnew.B_Cu, 86.700, 110.550, 86.700, 113.200, net_sense_adc)
add_track(pcbnew.B_Cu, 86.700, 113.200, 107.000, 113.200, net_sense_adc)
add_track(pcbnew.B_Cu, 107.000, 113.200, 107.000, 136.500, net_sense_adc)
add_via(107.000, 136.500, net_sense_adc)
add_track(pcbnew.F_Cu, 107.000, 136.500, 107.000, 140.000, net_sense_adc)
add_via(107.000, 140.000, net_sense_adc)
add_track(pcbnew.B_Cu, 107.000, 140.000, 107.000, 186.000, net_sense_adc)
add_track(pcbnew.B_Cu, 107.000, 186.000, 109.850, 186.000, net_sense_adc)
add_track(pcbnew.B_Cu, 109.850, 186.000, 109.850, 187.700, net_sense_adc)

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
    "--severity-all",
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
    for v in clearance_v[:15]:
        items = [it.get("description") for it in v.get("items", [])]
        print(f"  - {v.get('type')}: {v.get('description')} | {' VS '.join(items)}")

if other_v:
    print("\nOther violations:")
    for v in other_v[:15]:
        items = [it.get("description") for it in v.get("items", [])]
        print(f"  - {v.get('type')}: {v.get('description')} | {' VS '.join(items)}")
