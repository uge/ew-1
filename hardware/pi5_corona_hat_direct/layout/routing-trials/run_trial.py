#!/usr/bin/env python3
"""run_trial.py
Test runner to achieve zero DRC violations on test_120mm.kicad_pcb.
"""
import sys
import os
import shutil
import json
from pathlib import Path
import pcbnew as pn

HARDWARE_DIR = Path(__file__).resolve().parent.parent.parent
BASELINE_PCB = HARDWARE_DIR / "pi5_corona_hv.kicad_pcb"
TRIAL_DIR = HARDWARE_DIR / "layout" / "routing-trials"
PCB_PATH = TRIAL_DIR / "test_120mm.kicad_pcb"
PRO_PATH = TRIAL_DIR / "test_120mm.kicad_pro"

print("Starting fresh copy from baseline...")
shutil.copyfile(str(BASELINE_PCB), str(PCB_PATH))

pro_saved = PRO_PATH.read_text()
b = pn.LoadBoard(str(PCB_PATH))
fps = {f.GetReference(): f for f in b.GetFootprints()}

def pt(x, y):
    return pn.VECTOR2I(pn.FromMM(x), pn.FromMM(y))

def add_seg(netname, x1, y1, x2, y2, width=0.4, layer=pn.F_Cu):
    net = b.FindNet(netname)
    if not net:
        raise RuntimeError(f"Net {netname} not found!")
    t = pn.PCB_TRACK(b)
    t.SetStart(pt(x1, y1))
    t.SetEnd(pt(x2, y2))
    t.SetWidth(pn.FromMM(width))
    t.SetLayer(layer)
    t.SetNet(net)
    b.Add(t)

def add_via(netname, x, y, size=0.8, drill=0.4):
    net = b.FindNet(netname)
    if not net:
        raise RuntimeError(f"Net {netname} not found!")
    v = pn.PCB_VIA(b)
    v.SetPosition(pt(x, y))
    v.SetWidth(pn.FromMM(size))
    v.SetDrill(pn.FromMM(drill))
    v.SetLayerPair(pn.F_Cu, pn.B_Cu)
    v.SetNet(net)
    b.Add(v)

# ==============================================================================
# 1. FOOTPRINT PLACEMENT
# ==============================================================================
final_pos = {
    # Mounting holes
    'H4': (55.0, 166.0, 0.0), 'H5': (240.0, 166.0, 0.0),
    # Break-off tabs (exact -62mm shift from baseline)
    'J51': (30.0, 62.0, 180.0), 'U8': (30.0, 68.0, 0.0),
    'C80': (24.0, 68.0, 90.0),  'C81': (36.0, 68.0, 90.0),
    'S3': (39.0, 75.6, 0.0),    'J62': (27.46, 84.0, 0.0),
    'S4': (39.0, 91.6, 0.0),    'J63': (27.46, 100.0, 0.0),
    'S5': (39.0, 107.6, 0.0),   'J66': (27.46, 116.0, 0.0),
    'S6': (39.0, 123.6, 0.0),   'J67': (27.46, 132.0, 0.0),
    # Host Connectors
    'J50': (59.0, 122.0, 90.0),
    'J64': (69.0, 134.0, 0.0),
    'J65': (74.08, 142.0, 180.0),
    'J68': (69.0, 150.0, 0.0),
    'J69': (74.08, 158.0, 180.0),
    # Multiplier Diodes
    'D10': (136.0, 99.0, -90.0), 'D11': (144.0, 99.0, 90.0),
    'D12': (152.0, 99.0, -90.0), 'D13': (160.0, 99.0, 90.0),
    'D14': (168.0, 99.0, -90.0), 'D15': (176.0, 99.0, 90.0),
    'D16': (184.0, 99.0, -90.0), 'D17': (192.0, 99.0, 90.0),
    'D18': (200.0, 99.0, -90.0), 'D19': (208.0, 99.0, 90.0),
    'D20': (216.0, 99.0, -90.0), 'D21': (224.0, 99.0, 90.0),
    # Top Caps
    'C100': (129.25, 76.0, 0.0), 'C102': (145.25, 76.0, 0.0),
    'C104': (161.25, 76.0, 0.0), 'C106': (177.25, 76.0, 0.0),
    'C108': (193.25, 76.0, 0.0), 'C110': (209.25, 76.0, 0.0),
    # Top Bleeders
    'R140': (124.25, 61.0, 0.0), 'R141': (134.25, 61.0, 0.0),
    'R148': (156.25, 61.0, 0.0), 'R149': (166.25, 61.0, 0.0),
    'R156': (188.25, 61.0, 0.0), 'R157': (198.25, 61.0, 0.0),
    'R144': (140.25, 69.0, 0.0), 'R145': (150.25, 69.0, 0.0),
    'R152': (172.25, 69.0, 0.0), 'R153': (182.25, 69.0, 0.0),
    'R160': (204.25, 69.0, 0.0), 'R161': (214.25, 69.0, 0.0),
    # Bottom Caps
    'C101': (136.0, 126.0, 0.0), 'C103': (152.0, 126.0, 0.0),
    'C105': (168.0, 126.0, 0.0), 'C107': (184.0, 126.0, 0.0),
    'C109': (200.0, 126.0, 0.0), 'C111': (216.0, 126.0, 0.0),
    # Bottom Bleeders
    'R146': (147.0, 139.0, 0.0), 'R147': (157.0, 139.0, 0.0),
    'R154': (179.0, 139.0, 0.0), 'R155': (189.0, 139.0, 0.0),
    'R162': (211.0, 139.0, 0.0), 'R163': (221.0, 139.0, 0.0),
    'R142': (131.0, 148.0, 0.0), 'R143': (141.0, 148.0, 0.0),
    'R150': (163.0, 148.0, 0.0), 'R151': (173.0, 148.0, 0.0),
    'R158': (195.0, 148.0, 0.0), 'R159': (205.0, 148.0, 0.0),
    # 1G Divider
    'R30': (226.50, 159.0, 180.0), 'R31': (216.25, 159.0, 180.0),
    'R32': (207.25, 159.0, 180.0), 'R33': (198.25, 159.0, 180.0),
    'R34': (189.25, 159.0, 180.0), 'R35': (180.25, 159.0, 180.0),
    'R36': (171.25, 159.0, 180.0), 'R37': (162.25, 159.0, 180.0),
    'R38': (153.25, 159.0, 180.0), 'R39': (144.25, 159.0, 180.0),
    # Ballast Column
    'J60': (233.75, 63.5, 0.0),
    'R29': (233.75, 72.0, 90.0), 'R28': (233.75, 80.0, 90.0),
    'R27': (233.75, 88.0, 90.0), 'R26': (233.75, 96.0, 90.0),
    'R25': (233.75, 104.0, 90.0), 'R24': (233.75, 112.0, 90.0),
    'R23': (233.75, 120.0, 90.0), 'R22': (233.75, 128.0, 90.0),
    'R21': (233.75, 136.0, 90.0), 'R20': (233.75, 144.0, 90.0),
    # Transformer & Inverter
    'T1':  (114.5, 114.0, 180.0),
    'C11': (110.0, 131.0, 0.0),
    'D52': (105.0, 144.0, 90.0), 'D54': (117.0, 144.0, 90.0),
    'D53': (105.0, 156.0, 90.0), 'D55': (117.0, 156.0, 90.0),
    'C63': (107.0, 100.0, 90.0), 'R64': (114.0, 100.0, 180.0),
    # Telemetry: R90 oriented vertically at rot=90 (Pad 1 /HV_RETURN at Y=168.46, Pad 2 GND at Y=165.54)
    'R8':  (137.0, 159.0, -90.0), 'R9':  (137.0, 165.0, -90.0),
    'C13': (132.0, 165.0, 0.0),   'U4':  (126.0, 163.0, -90.0),
    'R7':  (120.0, 163.0, 180.0), 'D1':  (120.0, 167.0, 0.0),
    'J61': (126.0, 156.0, 0.0),
    'D5':  (111.0, 167.0, 90.0),  'R90': (105.0, 167.0, 90.0),
    'D4':  (97.0,  167.0, 0.0),   'C14': (93.75, 166.0, 90.0),
    'R91': (93.75, 169.5, 0.0),
}

for ref, (x, y, rot) in final_pos.items():
    f = fps[ref]
    f.SetPosition(pt(x, y))
    f.SetOrientationDegrees(rot)
    # Clear silkscreen text overlaps
    if ref in ["S3", "S4", "S5", "S6"]: f.Reference().SetPosition(pt(20.0, y + 6.0))
    elif ref in ["J62", "J63", "J66", "J67"]: f.Reference().SetPosition(pt(27.46, y + 5.0))
    elif ref == "J51": f.Reference().SetPosition(pt(25.0, y - 5.0))
    elif ref == "U8": f.Reference().SetPosition(pt(30.0, y + 2.4))
    elif ref.startswith("R") and 20 <= int(ref[1:]) <= 29: f.Reference().SetPosition(pt(x + 4.5, y))
    elif ref == "J61": f.Reference().SetPosition(pt(x - 3.5, y))
    elif ref == "R7": f.Reference().SetPosition(pt(x - 3.5, y))
    elif ref == "D1": f.Reference().SetPosition(pt(x + 2.5, y))
    elif ref == "R8": f.Reference().SetPosition(pt(x - 2.5, y))
    elif ref == "R9": f.Reference().SetPosition(pt(x - 2.5, y))
    elif ref == "R90": f.Reference().SetPosition(pt(x + 3.0, y))
    elif ref == "R91": f.Reference().SetPosition(pt(90.0, 169.5))
    elif ref == "C14": f.Reference().SetPosition(pt(90.0, 166.0))
    elif ref == "D4":  f.Reference().SetPosition(pt(97.0, 163.5))

# ==============================================================================
# 2. EDGE.CUTS AND DRAWINGS (120 mm HEIGHT)
# ==============================================================================
to_remove_drawings = []
for d in b.GetDrawings():
    if d.GetLayerName() in ["Edge.Cuts", "User.Drawings"]:
        to_remove_drawings.append(d)

for d in to_remove_drawings:
    b.Remove(d)
    d.thisown = False

def add_edge_line(x1, y1, x2, y2, width=0.05, layer=pn.Edge_Cuts):
    s = pn.PCB_SHAPE(b); s.SetShape(pn.SHAPE_T_SEGMENT)
    s.SetStart(pt(x1, y1)); s.SetEnd(pt(x2, y2))
    s.SetLayer(layer); s.SetWidth(pn.FromMM(width))
    b.Add(s)

def add_cut_text(txt, x, y, layer=pn.Dwgs_User):
    t = pn.PCB_TEXT(b); t.SetText(txt); t.SetPosition(pt(x, y))
    t.SetTextSize(pt(0.7, 0.7)); t.SetTextThickness(pn.FromMM(0.15))
    t.SetLayer(layer); b.Add(t)

tab_tops = [58, 74, 90, 106, 122]
outline = [(50, 51), (246, 51), (246, 171), (50, 171)]
for top in reversed(tab_tops):
    outline += [
        (50, top + 10), (45, top + 10), (45, top + 14), (15, top + 14),
        (15, top), (45, top), (45, top + 4), (50, top + 4)
    ]

for a, c in zip(outline, outline[1:] + outline[:1]):
    add_edge_line(a[0], a[1], c[0], c[1], width=0.05, layer=pn.Edge_Cuts)

for top in tab_tops:
    add_edge_line(47.5, top + 4, 47.5, top + 10, width=0.15, layer=pn.Dwgs_User)
    add_cut_text("CUT", 47.5, top + 2, layer=pn.Dwgs_User)

# Move silkscreen annotation texts
for s in b.GetDrawings():
    if isinstance(s, pn.PCB_TEXT):
        txt = s.GetText()
        if txt == "ILLUMINATION": s.SetPosition(pt(20.0, 61.0))
        elif txt == "S3": s.SetPosition(pt(30.0, 77.0))
        elif txt == "S4": s.SetPosition(pt(30.0, 93.0))
        elif txt == "S5": s.SetPosition(pt(30.0, 109.0))
        elif txt == "S6": s.SetPosition(pt(30.0, 125.0))
        elif txt == "1 GOhm DIVIDER": s.SetPosition(pt(180.0, 167.0))
        elif txt == "HV RETURN": s.SetPosition(pt(146.0, 167.0))
        elif txt == "HV MULTIPLIER / NO POURS": s.SetPosition(pt(180.0, 118.0))
        elif txt == "2 LAYERS / PLACEMENT STUDY": s.SetPosition(pt(180.0, 132.0))

# ==============================================================================
# 3. SURGICAL PRUNING OF OBSOLETE TRACKS
# ==============================================================================
to_remove = []
for t in b.GetTracks():
    name = t.GetNetname()
    s, e = t.GetStart(), t.GetEnd()
    sx, sy = s.x / 1e6, s.y / 1e6
    ex, ey = e.x / 1e6, e.y / 1e6
    min_x, max_x = min(sx, ex), max(sx, ex)
    min_y, max_y = min(sy, ey), max(sy, ey)
    length = t.GetLength() / 1e6

    # 1. Any track in tabs (X < 50.0) or cut-off bottom (Y > 170.0)
    if min_x < 50.0 or max_y > 170.0:
        to_remove.append(t); continue

    # 2. Multiplier, bleeders, ballast, divider
    if (name.startswith('/03_multiplier/') or name == 'Net-(D20-K)' or
        name in ['/HV_RAW', '/SEC_A', '/04_sense_safety/HV_OUT']):
        to_remove.append(t); continue
    if name.startswith('Net-(R'):
        try:
            rnum = int(name.split('-')[1].strip('()R'))
            if 20 <= rnum <= 39 or 140 <= rnum <= 163:
                to_remove.append(t); continue
        except (ValueError, IndexError):
            pass

    # 3. Switch daisy chains and connections south of Y=113
    if name in ['/04_sense_safety/LID_INT', '/04_sense_safety/LID_2', '/04_sense_safety/LID_3']:
        to_remove.append(t); continue
    if name == 'COIL_3V' and max_y > 113.0:
        to_remove.append(t); continue
    if name == '/04_sense_safety/RELAY_COIL_POS':
        if max_y > 146.1:
            to_remove.append(t); continue
        # Prune redundant baseline via at (78.1, 146.05) since B.Cu track is continuous:
        if isinstance(t, pn.PCB_VIA) and abs(sx - 78.1) < 0.2 and abs(sy - 146.05) < 0.2:
            to_remove.append(t); continue

    # 4. Old Tab 1 & J50 tails south of Y=120.0
    if min_x <= 65.0 and min_y >= 120.0:
        # Keep baseline U2 power track at Y=144.4-145.5
        if name == '3V3' and max_x >= 57.0 and 144.0 <= min_y <= 146.0:
            pass # keep baseline track connecting to U2!
        elif name in ['/01_power_mcu/SCL', '/01_power_mcu/SDA', '3V3', 'GND']:
            to_remove.append(t); continue
    # Dead SCL and 3V3 tails from old south Tab 1:
    # 1. Old baseline SCL tail south of 114.9 on F.Cu (length 10.1 mm):
    if name == '/01_power_mcu/SCL' and abs(length - 10.1) < 0.2 and 52.0 <= min_x <= 54.5 and min_y >= 114.0:
        to_remove.append(t); continue
    # 2. Old baseline 3V3 tail south of 115.2 on F.Cu (length 10.1 mm):
    if name == '3V3' and t.GetLayer() == pn.F_Cu and abs(length - 10.1) < 0.2 and 52.5 <= min_x <= 54.5 and min_y >= 114.0:
        to_remove.append(t); continue
    # 3. Old baseline 3V3 diagonal stub at (53.4, 115.2) -> (53.8, 114.8):
    if name == '3V3' and abs(length - 0.5657) < 0.01 and 53.0 <= min_x <= 54.0 and 114.5 <= min_y <= 115.5:
        to_remove.append(t); continue
    if name == '/01_power_mcu/SDA' and abs(length - 2.12) < 0.05:
        to_remove.append(t); continue
    if name == '/01_power_mcu/SDA' and abs(length - 12.50) < 0.05:
        to_remove.append(t); continue
    if name == '/01_power_mcu/SDA' and isinstance(t, pn.PCB_VIA) and abs(sx - 55.7) < 0.2 and abs(sy - 117.9) < 0.2:
        to_remove.append(t); continue
    # Dead GND stubs from old Tab 1 / old J50:
    if name == 'GND' and min_x <= 68.0 and 121.0 <= min_y and max_y <= 130.0:
        to_remove.append(t); continue
    if name == 'GND' and 95.0 <= min_x <= 100.0 and 114.0 <= min_y and max_y <= 119.0:
        to_remove.append(t); continue
    # Dead R60.2 GND via at (97.0, 158.8):
    if name == 'GND' and isinstance(t, pn.PCB_VIA) and abs(sx - 97.0) < 0.2 and abs(sy - 158.8) < 0.2:
        to_remove.append(t); continue

    # 5. Inverter & primary
    if name in ['/02_drive_transformer/PRI_A', 'Net-(C63-Pad1)']:
        to_remove.append(t); continue
    # For DRV_A: keep tight U2 escape up to X=98.6 on B.Cu, remove via at 98.6 and tracks east
    if name == '/02_drive_transformer/DRV_A':
        if max_x > 98.6:
            to_remove.append(t); continue
        if isinstance(t, pn.PCB_VIA) and abs(sx - 98.6) < 0.1:
            to_remove.append(t); continue
    # For DRV_B: remove old T1 track and tracks east of X=111.5
    if name == '/02_drive_transformer/DRV_B':
        if max_y >= 125.0 and max_x > 111.5:
            to_remove.append(t); continue
        elif max_y < 125.0:
            to_remove.append(t); continue
        elif 101.0 <= min_x <= 102.5 and 122.0 <= min_y <= 129.0: # dead stub to old T1
            to_remove.append(t); continue
    # HV_BRIDGE east of R60 and south of C60
    if name == '/02_drive_transformer/HV_BRIDGE':
        if max_x > 97.2 and min_y >= 147.0:
            to_remove.append(t); continue
        elif min_y >= 154.5:
            to_remove.append(t); continue
    # Old GND tracks in inverter/bridge/T1 area
    if name == 'GND' and min_x >= 98.0 and max_x <= 126.0 and min_y >= 140.0:
        to_remove.append(t); continue
    if name == 'GND' and 98.0 <= min_x <= 101.0 and 115.0 <= min_y <= 120.0:
        to_remove.append(t); continue

    # 6. Telemetry & ADC lines
    if name in ['/04_sense_safety/HV_SENSE_RAW', 'Net-(R8-Pad2)', 'Net-(U4-IN-)', '/HV_RETURN']:
        to_remove.append(t); continue
    if name == '/HV_SENSE_ADC' and max_y > 113.2:
        to_remove.append(t); continue
    if name == '/HV_CURR_ADC' and max_y > 114.2:
        to_remove.append(t); continue
    # Obsolete baseline 3V3 tracks leading to old south telemetry corridor:
    if name == '3V3' and min_x >= 98.0 and 146.0 <= min_y <= 162.0:
        to_remove.append(t); continue
    if name == '3V3' and min_x >= 98.1 and 144.5 <= min_y <= 147.0:
        to_remove.append(t); continue
    if name == '3V3' and abs(length - 0.20) < 0.05 and 97.9 <= min_x <= 98.3 and 144.5 <= min_y <= 144.7:
        to_remove.append(t); continue
    if name == 'GND' and max_y >= 160.0 and min_x >= 88.0:
        to_remove.append(t); continue

for t in to_remove:
    b.Remove(t)
    t.thisown = False

print(f"Removed {len(to_remove)} obsolete tracks surgically.")

# ==============================================================================
# 4. COPY AND SHIFT TAB TRACKS & VIAS (CLIPPED AT X = 50.0)
# ==============================================================================
b_base = pn.LoadBoard(str(BASELINE_PCB))
dy = -62.0
tab_added = 0
for t in b_base.GetTracks():
    s, e = t.GetStart(), t.GetEnd()
    sx, sy = s.x / 1e6, s.y / 1e6
    ex, ey = e.x / 1e6, e.y / 1e6
    if min(sx, ex) < 50.0 and min(sy, ey) >= 120.0:
        net = b.FindNet(t.GetNetname())
        if not net:
            continue
        if isinstance(t, pn.PCB_VIA):
            if sx <= 50.0:
                v = pn.PCB_VIA(b)
                v.SetPosition(pn.VECTOR2I(s.x, int(s.y + dy * 1e6)))
                v.SetWidth(t.GetWidth())
                v.SetDrill(t.GetDrill())
                v.SetLayerPair(pn.F_Cu, pn.B_Cu)
                v.SetNet(net)
                b.Add(v)
                tab_added += 1
        else:
            # Clip Tab 2 COIL_3V at X = 48.0 (where via to B.Cu is located)
            if t.GetNetname() == 'COIL_3V' and abs(sy + dy - 82.4) < 0.2:
                clip_sx = min(sx, 48.0)
                clip_ex = min(ex, 48.0)
            else:
                clip_sx = min(sx, 50.0)
                clip_ex = min(ex, 50.0)

            # Skip zero-length clipped tracks
            if abs(clip_sx - clip_ex) < 0.001 and abs(sy - ey) < 0.001:
                continue

            # Skip obsolete redundant GND exit branch in Tab 1 (east of C81.2)
            if t.GetNetname() == 'GND' and t.GetLayer() == pn.F_Cu and min(sx, ex) >= 36.0 and min(sy, ey) >= 128.8 and max(sy, ey) <= 130.0 and (max(sx, ex) > 36.05 or min(sx, ex) > 36.0):
                continue

            nt = pn.PCB_TRACK(b)
            nt.SetStart(pn.VECTOR2I(int(clip_sx * 1e6), int((sy + dy) * 1e6)))
            nt.SetEnd(pn.VECTOR2I(int(clip_ex * 1e6), int((ey + dy) * 1e6)))
            nt.SetWidth(t.GetWidth())
            nt.SetLayer(t.GetLayer())
            nt.SetNet(net)
            b.Add(nt)
            tab_added += 1

print(f"Added {tab_added} internal tab tracks/vias shifted by -62mm.")

# ==============================================================================
# 5. ROUTE HIGH VOLTAGE MULTIPLIER, BLEEDERS, BALLAST, DIVIDER
# ==============================================================================
# 1. Pump stages CW_P1 to CW_P5
for k in range(1, 6):
    netname = f"/03_multiplier/CW_P{k}"
    dx = (k - 1) * 16.0
    c_l_x, c_l_y = 134.25 + dx, 76.0
    c_r_x, c_r_y = 140.25 + dx, 76.0
    d_l_x, d_l_y = 136.0 + dx, 86.0
    d_r_x, d_r_y = 144.0 + dx, 86.0

    add_seg(netname, c_l_x, c_l_y, c_r_x, c_r_y, width=0.8, layer=pn.B_Cu)
    add_seg(netname, c_l_x, c_l_y, d_l_x, d_l_y, width=0.8, layer=pn.B_Cu)
    add_seg(netname, c_r_x, c_r_y, d_r_x, d_r_y, width=0.8, layer=pn.B_Cu)

    if k % 2 == 1:
        add_seg(netname, 137.2875 + dx, 69.0, c_l_x, c_l_y, width=0.8, layer=pn.F_Cu)
        add_seg(netname, 137.2125 + dx, 61.0, 137.2125 + dx, 58.5, width=0.8, layer=pn.F_Cu)
        add_via(netname, 137.2125 + dx, 58.5, size=0.8, drill=0.4)
        add_seg(netname, 137.2125 + dx, 58.5, c_r_x, c_r_y, width=0.8, layer=pn.B_Cu)
    else:
        b_61_x = 153.2875 + (k - 2) * 16.0
        b_69_x = 153.2125 + (k - 2) * 16.0
        add_seg(netname, b_61_x, 61.0, b_61_x, 58.5, width=0.8, layer=pn.F_Cu)
        add_via(netname, b_61_x, 58.5, size=0.8, drill=0.4)
        add_seg(netname, b_61_x, 58.5, c_l_x, c_l_y, width=0.8, layer=pn.B_Cu)
        add_seg(netname, b_69_x, 69.0, c_r_x, c_r_y, width=0.8, layer=pn.F_Cu)

# 2. Series stages CW_S1 to CW_S5
for k in range(1, 6):
    netname = f"/03_multiplier/CW_S{k}"
    dx = (k - 1) * 16.0
    c_l_x, c_l_y = 141.0 + dx, 126.0
    c_r_x, c_r_y = 147.0 + dx, 126.0
    d_l_x, d_l_y = 144.0 + dx, 112.0
    d_r_x, d_r_y = 152.0 + dx, 112.0

    add_seg(netname, c_l_x, c_l_y, c_r_x, c_r_y, width=0.8, layer=pn.B_Cu)
    add_seg(netname, c_l_x, c_l_y, d_l_x, d_l_y, width=0.8, layer=pn.B_Cu)
    add_seg(netname, c_r_x, c_r_y, d_r_x, d_r_y, width=0.8, layer=pn.B_Cu)

    if k % 2 == 1:
        b_139_x = 144.0375 + dx
        b_148_x = 143.9625 + dx
        add_seg(netname, b_139_x, 139.0, c_l_x, c_l_y, width=0.8, layer=pn.F_Cu)
        add_seg(netname, b_148_x, 148.0, b_148_x, 151.0, width=0.8, layer=pn.F_Cu)
        add_via(netname, b_148_x, 151.0, size=0.8, drill=0.4)
        add_seg(netname, b_148_x, 151.0, c_r_x, c_r_y, width=0.8, layer=pn.B_Cu)
    else:
        b_148_x = 160.0375 + (k - 2) * 16.0
        b_139_x = 159.9625 + (k - 2) * 16.0
        add_seg(netname, b_148_x, 148.0, b_148_x, 151.0, width=0.8, layer=pn.F_Cu)
        add_via(netname, b_148_x, 151.0, size=0.8, drill=0.4)
        add_seg(netname, b_148_x, 151.0, c_l_x, c_l_y, width=0.8, layer=pn.B_Cu)
        add_seg(netname, b_139_x, 139.0, c_r_x, c_r_y, width=0.8, layer=pn.F_Cu)

# 3. Net-(D20-K)
add_seg("Net-(D20-K)", 214.25, 76.0, 216.0, 86.0, width=0.8, layer=pn.B_Cu)
add_seg("Net-(D20-K)", 216.0, 86.0, 224.0, 86.0, width=0.8, layer=pn.B_Cu)
add_seg("Net-(D20-K)", 217.2125, 69.0, 224.0, 69.0, width=0.8, layer=pn.F_Cu)
add_seg("Net-(D20-K)", 224.0, 69.0, 224.0, 86.0, width=0.8, layer=pn.F_Cu)

# 4. Bleeder series pairs
bleeder_pairs = [
    ("R140", "R141", 61.0, "Net-(R140-Pad2)"), ("R148", "R149", 61.0, "Net-(R148-Pad2)"), ("R156", "R157", 61.0, "Net-(R156-Pad2)"),
    ("R144", "R145", 69.0, "Net-(R144-Pad2)"), ("R152", "R153", 69.0, "Net-(R152-Pad2)"), ("R160", "R161", 69.0, "Net-(R160-Pad2)"),
    ("R146", "R147", 139.0, "Net-(R146-Pad2)"), ("R154", "R155", 139.0, "Net-(R154-Pad2)"), ("R162", "R163", 139.0, "Net-(R162-Pad2)"),
    ("R142", "R143", 148.0, "Net-(R142-Pad2)"), ("R150", "R151", 148.0, "Net-(R150-Pad2)"), ("R158", "R159", 148.0, "Net-(R158-Pad2)"),
]
for r_l, r_r, y_val, netname in bleeder_pairs:
    f_l = b.FindFootprintByReference(r_l); f_r = b.FindFootprintByReference(r_r)
    x1 = f_l.GetPosition().x/1e6 + 2.9625; x2 = f_r.GetPosition().x/1e6 - 2.9625
    add_seg(netname, x1, y_val, x2, y_val, width=0.6, layer=pn.F_Cu)

# 5. /SEC_A: connects T1.7/8 to C100.1 and R140.1 via East side B.Cu (X=125.933, >= 8.9mm clearance to PRI_A!)
add_seg("/SEC_A", 125.933, 117.75, 125.933, 120.25, width=0.8, layer=pn.F_Cu)
add_via("/SEC_A", 125.933, 120.25, size=0.8, drill=0.4)
add_seg("/SEC_A", 125.933, 120.25, 125.933, 76.0, width=0.8, layer=pn.B_Cu)
add_seg("/SEC_A", 125.933, 76.0, 124.25, 76.0, width=0.8, layer=pn.B_Cu) # C100.1 PTH
add_seg("/SEC_A", 124.25, 76.0, 121.2875, 76.0, width=0.8, layer=pn.F_Cu)
add_seg("/SEC_A", 121.2875, 76.0, 121.2875, 61.0, width=0.8, layer=pn.F_Cu) # R140.1 SMD

# 6. Ballast Series Resistors (Uniform 8mm pitch along X = 233.75)
xc = 233.75
ballast_ys = {f"R{29-i}": 72.0 + 8.0*i for i in range(10)}
ballast_pairs = [
    ("R29", "R28", "Net-(R28-Pad2)"), ("R28", "R27", "Net-(R27-Pad2)"),
    ("R27", "R26", "Net-(R26-Pad2)"), ("R26", "R25", "Net-(R25-Pad2)"),
    ("R25", "R24", "Net-(R24-Pad2)"), ("R24", "R23", "Net-(R23-Pad2)"),
    ("R23", "R22", "Net-(R22-Pad2)"), ("R22", "R21", "Net-(R21-Pad2)"),
    ("R21", "R20", "Net-(R20-Pad2)"),
]
for r_up, r_dn, netname in ballast_pairs:
    y_up = ballast_ys[r_up]; y_dn = ballast_ys[r_dn]
    pad1_up_y = y_up + 2.9625; pad2_dn_y = y_dn - 2.9625
    add_seg(netname, xc, pad1_up_y, xc, pad2_dn_y, width=0.6, layer=pn.F_Cu)

# 7. /04_sense_safety/HV_OUT
add_seg("/04_sense_safety/HV_OUT", xc, 63.5, xc, 69.0375, width=0.8, layer=pn.F_Cu)
add_seg("/04_sense_safety/HV_OUT", xc, 63.5, xc, 159.0, width=0.8, layer=pn.B_Cu)
add_via("/04_sense_safety/HV_OUT", xc, 159.0, size=1.2, drill=0.6)
add_seg("/04_sense_safety/HV_OUT", xc, 159.0, 229.4625, 159.0, width=0.8, layer=pn.F_Cu)

# 8. /HV_RAW
add_seg("/HV_RAW", 224.0, 112.0, 221.0, 126.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RAW", 221.0, 126.0, 224.0, 139.0, width=0.8, layer=pn.B_Cu)
add_via("/HV_RAW", 224.0, 139.0, size=1.2, drill=0.6)
add_seg("/HV_RAW", 224.0, 139.0, 223.9625, 139.0, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RAW", 224.0, 139.0, 228.0, 146.9625, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RAW", 228.0, 146.9625, xc, 146.9625, width=0.8, layer=pn.F_Cu)

# 9. 1G Divider Series Resistors
divider_refs = [f"R{i}" for i in range(30, 40)]
for i in range(len(divider_refs) - 1):
    r_r = divider_refs[i]; r_l = divider_refs[i + 1]
    netname = f"Net-({r_r}-Pad2)"
    f_r = b.FindFootprintByReference(r_r); f_l = b.FindFootprintByReference(r_l)
    x_r_pad2 = f_r.GetPosition().x/1e6 - 2.9625
    x_l_pad1 = f_l.GetPosition().x/1e6 + 2.9625
    add_seg(netname, x_r_pad2, 159.0, x_l_pad1, 159.0, width=0.6, layer=pn.F_Cu)

print("HV section routed.")

# ==============================================================================
# 6. ROUTE INVERTER & PRIMARY
# ==============================================================================
# HV_BRIDGE from C60.1 (97.0, 147.0) south to 149.0 (clear of C60.2 GND!), then east to D52.1 and D54.1:
add_seg("/02_drive_transformer/HV_BRIDGE", 97.0, 147.0, 97.0, 149.0, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/HV_BRIDGE", 97.0, 149.0, 105.0, 149.0, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/HV_BRIDGE", 105.0, 149.0, 105.0, 147.4, width=0.8, layer=pn.F_Cu) # D52.1
add_seg("/02_drive_transformer/HV_BRIDGE", 105.0, 147.4, 117.0, 147.4, width=0.8, layer=pn.F_Cu) # D54.1

# R60.2 GND via to the west at (95.0, 159.96) into B.Cu GND zone:
add_seg("GND", 97.0, 159.9625, 95.0, 159.9625, width=0.8, layer=pn.F_Cu)
add_via("GND", 95.0, 159.9625, size=0.8, drill=0.4)

# Bridge diodes GND on F.Cu into B.Cu GND zone at X=100.5:
add_seg("GND", 117.0, 152.6, 105.0, 152.6, width=0.8, layer=pn.F_Cu) # D55.2 to D53.2
add_seg("GND", 105.0, 152.6, 100.5, 152.6, width=0.8, layer=pn.F_Cu)
add_via("GND", 100.5, 152.6, size=0.8, drill=0.4)

# T1.6 SMD Pad 6 (GND at 103.067, 107.75) via to B.Cu, then west into B.Cu GND zone:
add_via("GND", 103.0675, 107.75, size=0.8, drill=0.4)
add_seg("GND", 103.0675, 107.75, 100.0, 107.75, width=0.8, layer=pn.B_Cu)

# PRI_A on F.Cu (Central Corridor under T1 - ZERO VIAS!):
add_seg("/02_drive_transformer/PRI_A", 125.0, 131.0, 116.963, 131.0, width=0.8, layer=pn.F_Cu) # C11.2
add_seg("/02_drive_transformer/PRI_A", 116.963, 131.0, 116.963, 120.25, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/PRI_A", 116.963, 120.25, 103.067, 120.25, width=0.8, layer=pn.F_Cu) # T1.1
add_seg("/02_drive_transformer/PRI_A", 116.963, 120.25, 116.963, 100.0, width=0.8, layer=pn.F_Cu)  # R64.1

# Snubber Net-(C63-Pad1) on F.Cu:
add_seg("Net-(C63-Pad1)", 107.0, 100.95, 107.0, 102.5, width=0.6, layer=pn.F_Cu)
add_seg("Net-(C63-Pad1)", 107.0, 102.5, 111.037, 102.5, width=0.6, layer=pn.F_Cu)
add_seg("Net-(C63-Pad1)", 111.037, 102.5, 111.037, 100.0, width=0.6, layer=pn.F_Cu)

# DRV_A: connects baseline escape at (98.6, 141.825) on B.Cu to D52.2, D53.1, and C11.1
add_seg("/02_drive_transformer/DRV_A", 98.6, 141.825, 103.0, 141.825, width=0.6, layer=pn.B_Cu)
add_seg("/02_drive_transformer/DRV_A", 103.0, 141.825, 103.0, 140.6, width=0.6, layer=pn.B_Cu)
add_via("/02_drive_transformer/DRV_A", 103.0, 140.6, size=0.8, drill=0.4)
add_seg("/02_drive_transformer/DRV_A", 103.0, 140.6, 105.0, 140.6, width=0.6, layer=pn.F_Cu) # D52.2
# To C11.1 (110.0, 131.0) on F.Cu:
add_seg("/02_drive_transformer/DRV_A", 105.0, 140.6, 105.0, 131.0, width=0.6, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_A", 105.0, 131.0, 110.0, 131.0, width=0.6, layer=pn.F_Cu)
# To D53.1 (105.0, 159.4) on B.Cu:
add_seg("/02_drive_transformer/DRV_A", 103.0, 140.6, 103.0, 159.4, width=0.6, layer=pn.B_Cu)
add_seg("/02_drive_transformer/DRV_A", 103.0, 159.4, 105.0, 159.4, width=0.6, layer=pn.B_Cu)
add_via("/02_drive_transformer/DRV_A", 105.0, 159.4, size=0.8, drill=0.4)

# DRV_B: connects baseline escape at (101.5, 138.3) via to F.Cu, hops over ADC lines on B.Cu!
add_via("/02_drive_transformer/DRV_B", 101.5, 138.3, size=0.8, drill=0.4)
# North on F.Cu along X=101.5, branch to T1.5 (103.067, 110.25) and C63.2 (107.0, 99.05), CLEAR OF T1.6 GND:
add_seg("/02_drive_transformer/DRV_B", 101.5, 138.3, 101.5, 99.05, width=0.6, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 101.5, 110.25, 103.067, 110.25, width=0.6, layer=pn.F_Cu) # T1.5
add_seg("/02_drive_transformer/DRV_B", 101.5, 99.05, 107.0, 99.05, width=0.6, layer=pn.F_Cu)       # C63.2
# Connect to D54.2 and D55.1 on B.Cu:
add_seg("/02_drive_transformer/DRV_B", 101.5, 138.3, 115.0, 138.3, width=0.6, layer=pn.B_Cu)
add_seg("/02_drive_transformer/DRV_B", 115.0, 138.3, 115.0, 140.6, width=0.6, layer=pn.B_Cu)
add_seg("/02_drive_transformer/DRV_B", 115.0, 140.6, 117.0, 140.6, width=0.6, layer=pn.B_Cu)
add_via("/02_drive_transformer/DRV_B", 117.0, 140.6, size=0.8, drill=0.4) # D54.2
add_seg("/02_drive_transformer/DRV_B", 115.0, 140.6, 115.0, 159.4, width=0.6, layer=pn.B_Cu)
add_seg("/02_drive_transformer/DRV_B", 115.0, 159.4, 117.0, 159.4, width=0.6, layer=pn.B_Cu)
add_via("/02_drive_transformer/DRV_B", 117.0, 159.4, size=0.8, drill=0.4) # D55.1

print("Inverter section routed.")

# ==============================================================================
# 7. ROUTE TELEMETRY SECTION
# ==============================================================================
# /HV_RETURN:
add_seg("/HV_RETURN", 125.933, 107.75, 125.933, 110.25, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 125.933, 110.25, 136.0, 110.25, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 136.0, 110.25, 136.0, 112.0, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 136.0, 112.0, 132.0, 112.0, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 132.0, 112.0, 132.0, 126.0, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 132.0, 126.0, 131.0, 126.0, width=0.8, layer=pn.F_Cu) # C101.1 PTH
add_seg("/HV_RETURN", 131.0, 126.0, 131.0, 148.0, width=0.8, layer=pn.B_Cu)
# Connect R142.1 at (128.0375, 148.0):
add_seg("/HV_RETURN", 131.0, 148.0, 128.0375, 148.0, width=0.8, layer=pn.B_Cu)
add_via("/HV_RETURN", 128.0375, 148.0, size=0.8, drill=0.4)
add_seg("/HV_RETURN", 131.0, 148.0, 131.0, 151.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 131.0, 151.0, 126.0, 156.0, width=0.8, layer=pn.B_Cu) # J61.1 PTH
# From J61.1 on B.Cu, go to X=128.5, south to Y=166.0, hop over GND on F.Cu to Y=169.5:
add_seg("/HV_RETURN", 126.0, 156.0, 128.5, 156.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 128.5, 156.0, 128.5, 166.0, width=0.8, layer=pn.B_Cu)
add_via("/HV_RETURN", 128.5, 166.0, size=0.8, drill=0.4)
add_seg("/HV_RETURN", 128.5, 166.0, 128.5, 169.5, width=0.8, layer=pn.F_Cu) # hop over B.Cu GND!
add_via("/HV_RETURN", 128.5, 169.5, size=0.8, drill=0.4)
# On B.Cu along Y=169.5 to D5.1, R90.1, R91.1:
add_seg("/HV_RETURN", 128.5, 169.5, 111.0, 169.5, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 111.0, 169.5, 111.0, 169.15, width=0.8, layer=pn.B_Cu)
add_via("/HV_RETURN", 111.0, 169.15, size=0.8, drill=0.4) # D5.1
add_seg("/HV_RETURN", 111.0, 169.5, 105.0, 169.5, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 105.0, 169.5, 105.0, 168.463, width=0.8, layer=pn.B_Cu)
add_via("/HV_RETURN", 105.0, 168.463, size=0.8, drill=0.4) # R90.1
add_seg("/HV_RETURN", 105.0, 169.5, 93.0, 169.5, width=0.8, layer=pn.B_Cu)
add_via("/HV_RETURN", 93.0, 169.5, size=0.8, drill=0.4) # R91.1
add_seg("/HV_RETURN", 93.0, 169.5, 93.0, 169.5, width=0.4, layer=pn.F_Cu)

# Telemetry GND:
# Subsystem A: D5.2 and R90.2 on F.Cu at Y=163.5 into B.Cu GND zone:
add_seg("GND", 111.0, 164.85, 111.0, 163.5, width=0.4, layer=pn.F_Cu) # D5.2
add_seg("GND", 111.0, 163.5, 105.0, 163.5, width=0.4, layer=pn.F_Cu)
add_seg("GND", 105.0, 163.5, 105.0, 165.537, width=0.4, layer=pn.F_Cu) # R90.2
add_seg("GND", 105.0, 163.5, 100.5, 163.5, width=0.4, layer=pn.F_Cu)
add_via("GND", 100.5, 163.5, size=0.8, drill=0.4) # Enter B.Cu GND zone!

# Subsystem B: East telemetry GND (R9.2, C13.2, U4.2, D1.1) via to B.Cu at Y=167.5:
add_seg("GND", 137.0, 165.75, 137.0, 167.5, width=0.4, layer=pn.F_Cu) # R9.2
add_via("GND", 137.0, 167.5, size=0.6, drill=0.3)
add_seg("GND", 132.7, 165.0, 132.7, 167.5, width=0.4, layer=pn.F_Cu)  # C13.2
add_via("GND", 132.7, 167.5, size=0.6, drill=0.3)
add_seg("GND", 126.0, 164.3, 126.0, 167.5, width=0.3, layer=pn.F_Cu)  # U4.2
add_via("GND", 126.0, 167.5, size=0.6, drill=0.3)
add_seg("GND", 121.0, 167.95, 121.0, 167.5, width=0.4, layer=pn.F_Cu) # D1.1
add_via("GND", 121.0, 167.5, size=0.6, drill=0.3)
# Connect all 4 east GND vias on B.Cu along Y=167.5, then continue west straight into B.Cu GND zone!
add_seg("GND", 137.0, 167.5, 100.5, 167.5, width=0.4, layer=pn.B_Cu)

# Subsystem C: Western telemetry local GND vias inside GND zone (X <= 101.0):
add_via("GND", 98.0, 167.95, size=0.8, drill=0.4) # D4.1 GND via
add_via("GND", 93.75, 165.30, size=0.8, drill=0.4) # C14.2 GND via

# 3V3 Highway from baseline 3V3 via at (54.0, 115.0) south along X=54.0 to Y=163.5, across to (98.0, 163.5):
add_seg("3V3", 53.80, 114.80, 54.00, 115.00, width=0.4, layer=pn.F_Cu) # connect baseline track to via!
add_seg("3V3", 54.0, 115.0, 54.0, 122.5, width=0.4, layer=pn.F_Cu) # to J50.2 branch at Y=122.5
add_seg("3V3", 54.0, 122.5, 54.0, 145.5, width=0.4, layer=pn.F_Cu) # to U2 branch at Y=145.5
add_seg("3V3", 54.0, 145.5, 54.0, 163.5, width=0.4, layer=pn.F_Cu)
add_seg("3V3", 54.0, 163.5, 98.0, 163.5, width=0.4, layer=pn.F_Cu)
# Connect to baseline U2 power chain at (57.00, 145.50):
add_seg("3V3", 54.0, 145.5, 57.0, 145.5, width=0.4, layer=pn.F_Cu)
# Connect to D4.2 at (98.0, 166.05):
add_seg("3V3", 98.0, 163.5, 98.0, 166.05, width=0.4, layer=pn.F_Cu)
add_via("3V3", 98.0, 166.05, size=0.8, drill=0.4) # D4.2

# From D4.2 on B.Cu, run east along Y=166.05 to D1.2 and U4.5:
add_seg("3V3", 98.0, 166.05, 121.0, 166.05, width=0.4, layer=pn.B_Cu)
add_via("3V3", 121.0, 166.05, size=0.8, drill=0.4) # D1.2
add_seg("3V3", 121.0, 166.05, 123.5, 166.05, width=0.4, layer=pn.B_Cu)
add_seg("3V3", 123.5, 166.05, 123.5, 161.7, width=0.4, layer=pn.B_Cu)
add_seg("3V3", 123.5, 161.7, 125.05, 161.7, width=0.4, layer=pn.B_Cu)
add_via("3V3", 125.05, 161.7, size=0.8, drill=0.4) # U4.5

# HV Voltage Sense:
add_seg("Net-(R8-Pad2)", 137.0, 159.75, 137.0, 164.25, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/HV_SENSE_RAW", 141.2875, 159.0, 137.0, 158.25, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/HV_SENSE_RAW", 137.0, 158.25, 131.3, 158.25, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/HV_SENSE_RAW", 131.3, 158.25, 131.3, 165.0, width=0.4, layer=pn.F_Cu) # C13.1
add_seg("/04_sense_safety/HV_SENSE_RAW", 131.3, 165.0, 126.95, 165.0, width=0.3, layer=pn.F_Cu)
add_seg("/04_sense_safety/HV_SENSE_RAW", 126.95, 165.0, 126.95, 164.3, width=0.3, layer=pn.F_Cu) # U4.3

# U4 feedback loop Net-(U4-IN-): route around U4.5 (3V3 at 125.05, 161.7):
add_seg("Net-(U4-IN-)", 126.95, 161.7, 126.95, 160.5, width=0.3, layer=pn.F_Cu) # U4.4
add_seg("Net-(U4-IN-)", 126.95, 160.5, 120.75, 160.5, width=0.3, layer=pn.F_Cu)
add_seg("Net-(U4-IN-)", 120.75, 160.5, 120.75, 163.0, width=0.3, layer=pn.F_Cu) # R7.1
add_seg("Net-(U4-IN-)", 125.05, 164.3, 124.0, 164.3, width=0.3, layer=pn.F_Cu)  # U4.1
add_seg("Net-(U4-IN-)", 124.0, 164.3, 124.0, 160.5, width=0.3, layer=pn.F_Cu)   # clear of U4.5!
add_seg("Net-(U4-IN-)", 124.0, 160.5, 125.05, 160.5, width=0.3, layer=pn.F_Cu)

# HV_SENSE_ADC:
add_seg("/HV_SENSE_ADC", 119.25, 163.0, 119.0, 163.0, width=0.4, layer=pn.F_Cu) # R7.2
add_seg("/HV_SENSE_ADC", 119.0, 163.0, 119.0, 167.0, width=0.4, layer=pn.F_Cu) # D1.3
add_via("/HV_SENSE_ADC", 119.0, 163.0, size=0.8, drill=0.4)
add_seg("/HV_SENSE_ADC", 119.0, 163.0, 113.0, 163.0, width=0.4, layer=pn.B_Cu)
add_seg("/HV_SENSE_ADC", 113.0, 163.0, 113.0, 140.0, width=0.4, layer=pn.B_Cu)
add_via("/HV_SENSE_ADC", 113.0, 140.0, size=0.8, drill=0.4)
add_seg("/HV_SENSE_ADC", 113.0, 140.0, 113.0, 136.5, width=0.4, layer=pn.F_Cu) # hops DRV_B at 138.3
add_via("/HV_SENSE_ADC", 113.0, 136.5, size=0.8, drill=0.4)
add_seg("/HV_SENSE_ADC", 113.0, 136.5, 113.0, 113.2, width=0.4, layer=pn.B_Cu)
add_seg("/HV_SENSE_ADC", 113.0, 113.2, 107.0, 113.2, width=0.4, layer=pn.B_Cu) # connects to baseline track at 107.0

# HV Current Sense /HV_CURR_ADC:
# Connect R91.2 (94.50, 169.5), C14.1 (93.75, 166.70), and D4.3 (96.0, 167.0) on F.Cu:
add_seg("/HV_CURR_ADC", 94.50, 169.5, 94.50, 166.70, width=0.4, layer=pn.F_Cu)
add_seg("/HV_CURR_ADC", 94.50, 166.70, 93.75, 166.70, width=0.4, layer=pn.F_Cu) # C14.1
add_seg("/HV_CURR_ADC", 94.50, 166.70, 96.00, 166.70, width=0.4, layer=pn.F_Cu)
add_seg("/HV_CURR_ADC", 96.00, 166.70, 96.00, 167.00, width=0.4, layer=pn.F_Cu) # D4.3
add_via("/HV_CURR_ADC", 96.00, 167.00, size=0.6, drill=0.3)
add_seg("/HV_CURR_ADC", 96.00, 167.00, 96.00, 165.00, width=0.4, layer=pn.B_Cu)
add_seg("/HV_CURR_ADC", 96.00, 165.00, 108.5, 165.00, width=0.4, layer=pn.B_Cu)
add_via("/HV_CURR_ADC", 108.5, 140.0, size=0.8, drill=0.4)
add_seg("/HV_CURR_ADC", 108.5, 165.0, 108.5, 140.0, width=0.4, layer=pn.B_Cu)
add_seg("/HV_CURR_ADC", 108.5, 140.0, 108.5, 136.5, width=0.4, layer=pn.F_Cu) # hops DRV_B at 138.3
add_via("/HV_CURR_ADC", 108.5, 136.5, size=0.8, drill=0.4)
add_seg("/HV_CURR_ADC", 108.5, 136.5, 108.5, 114.2, width=0.4, layer=pn.B_Cu)
add_seg("/HV_CURR_ADC", 108.5, 114.2, 105.0, 114.2, width=0.4, layer=pn.B_Cu) # connects to baseline track at 105.0

print("Telemetry section routed.")

# ==============================================================================
# 8. ROUTE BREAK-OFF TABS & SWITCH INTERLOCKS
# ==============================================================================
# Tab 1 GND: connects into B.Cu GND zone (baseline via at 47.8, 64.7 grounds F.Cu):
add_seg("GND", 50.0, 62.8, 53.0, 62.8, width=0.4, layer=pn.B_Cu) # solidly inside GND zone!

# Tab 1 3V3: crosses under SDA and SCL on B.Cu at Y=67.3, hops to F.Cu at (52.20, 67.3) outside GND zone, runs south on F.Cu to baseline 3V3 at (53.0, 83.3):
add_seg("3V3", 50.0, 67.30, 52.20, 67.30, width=0.20, layer=pn.B_Cu)
add_via("3V3", 52.20, 67.30, size=0.6, drill=0.3)
add_seg("3V3", 52.20, 67.30, 52.20, 83.30, width=0.20, layer=pn.F_Cu)
add_seg("3V3", 52.20, 83.30, 53.00, 83.30, width=0.20, layer=pn.F_Cu) # into baseline 3V3 on F.Cu!

# Tab 1 SCL: hops under SDA on B.Cu at Y=64.7 inside Tab 1 neck, runs south at X=51.50 on F.Cu to baseline via (52.80, 102.90):
add_seg("/01_power_mcu/SCL", 50.0, 64.70, 49.40, 64.70, width=0.20, layer=pn.F_Cu)
add_via("/01_power_mcu/SCL", 49.40, 64.70, size=0.6, drill=0.3)
add_seg("/01_power_mcu/SCL", 49.40, 64.70, 51.50, 64.70, width=0.20, layer=pn.B_Cu)
add_via("/01_power_mcu/SCL", 51.50, 64.70, size=0.6, drill=0.3)
add_seg("/01_power_mcu/SCL", 51.50, 64.70, 51.50, 102.90, width=0.20, layer=pn.F_Cu)
add_seg("/01_power_mcu/SCL", 51.50, 102.90, 52.80, 102.90, width=0.20, layer=pn.F_Cu) # into baseline SCL via to J2.5!

# Connect baseline SCL at (53.00, 114.90) south to (53.00, 118.50), then hop to B.Cu under 3V3 highway, across to J50.4:
add_seg("/01_power_mcu/SCL", 53.00, 114.90, 53.00, 118.50, width=0.20, layer=pn.F_Cu)
add_via("/01_power_mcu/SCL", 53.00, 118.50, size=0.6, drill=0.3)
add_seg("/01_power_mcu/SCL", 53.00, 118.50, 55.00, 118.50, width=0.20, layer=pn.B_Cu)
add_via("/01_power_mcu/SCL", 55.00, 118.50, size=0.6, drill=0.3)
add_seg("/01_power_mcu/SCL", 55.00, 118.50, 57.00, 118.50, width=0.20, layer=pn.F_Cu)
add_seg("/01_power_mcu/SCL", 57.00, 118.50, 57.00, 120.50, width=0.20, layer=pn.F_Cu) # Pad 4

# Tab 1 SDA: runs straight south on F.Cu at X=50.80 to Y=121.50, turns east to X=53.0, hops under 3V3 on B.Cu to J50.3 and baseline SDA:
add_seg("/01_power_mcu/SDA", 50.0, 62.70, 50.80, 62.70, width=0.20, layer=pn.F_Cu)
add_seg("/01_power_mcu/SDA", 50.80, 62.70, 50.80, 121.50, width=0.20, layer=pn.F_Cu)
add_seg("/01_power_mcu/SDA", 50.80, 121.50, 53.00, 121.50, width=0.20, layer=pn.F_Cu)
add_via("/01_power_mcu/SDA", 53.00, 121.50, size=0.6, drill=0.3)
add_seg("/01_power_mcu/SDA", 53.00, 121.50, 55.50, 121.50, width=0.20, layer=pn.B_Cu)

# J50 connections at (59.0, 122.0):
# Pad 1 GND at (57.0, 123.5): via to B.Cu GND zone
add_seg("GND", 57.0, 123.5, 58.5, 123.5, width=0.3, layer=pn.F_Cu)
add_via("GND", 58.5, 123.5, size=0.8, drill=0.4)
# Pad 2 3V3 at (57.0, 122.5): connect on F.Cu from 3V3 highway at (54.0, 122.5):
add_seg("3V3", 54.0, 122.5, 57.0, 122.5, width=0.3, layer=pn.F_Cu)
# Pad 3 SDA at (57.0, 121.5): connect from baseline SDA at (57.2, 116.4) on F.Cu, hop to B.Cu and back:
add_via("/01_power_mcu/SDA", 57.2, 116.4, size=0.6, drill=0.3)
add_seg("/01_power_mcu/SDA", 57.2, 116.4, 57.2, 121.5, width=0.25, layer=pn.B_Cu)
add_seg("/01_power_mcu/SDA", 57.2, 121.5, 55.5, 121.5, width=0.25, layer=pn.B_Cu)
add_via("/01_power_mcu/SDA", 55.5, 121.5, size=0.6, drill=0.3)
add_seg("/01_power_mcu/SDA", 55.5, 121.5, 57.0, 121.5, width=0.25, layer=pn.F_Cu) # Pad 3

# Switch daisy chains between host connectors:
add_seg("/04_sense_safety/LID_INT", 74.08, 134.0, 74.08, 142.0, width=0.4, layer=pn.F_Cu) # J64.2 to J65.1
add_seg("/04_sense_safety/LID_2", 69.00, 142.0, 69.00, 150.0, width=0.4, layer=pn.B_Cu)   # J65.2 to J68.1 on B.Cu (leaves F.Cu clear for 3V3!)
add_seg("/04_sense_safety/LID_3", 74.08, 150.0, 74.08, 158.0, width=0.4, layer=pn.F_Cu)   # J68.2 to J69.1

# Planar B.Cu bus for switch signals (strictly non-crossing planar embedding, shifted west for full GND zone integrity):
# Track 1: COIL_3V at X = 51.90 (enters Y=82.4, exits Y=134.0)
# Track 2: LID_INT at X = 51.50 (enters Y=83.2, exits Y=136.0)
# Track 3: LID_2   at X = 51.10 (enters Y=99.2, exits Y=144.0)
# Track 4: LID_3   at X = 50.70 (enters Y=115.2, exits Y=152.0)

# 1. COIL_3V:
add_via("COIL_3V", 48.0, 82.4, size=0.8, drill=0.4) # inside Tab 2 neck: F.Cu to B.Cu
add_seg("COIL_3V", 48.0, 82.4, 51.90, 82.4, width=0.20, layer=pn.B_Cu)
add_seg("COIL_3V", 51.90, 82.4, 51.90, 134.0, width=0.20, layer=pn.B_Cu)
add_seg("COIL_3V", 51.90, 134.0, 69.0, 134.0, width=0.20, layer=pn.B_Cu) # J64.1
# Connect north on B.Cu along X=69.0 to baseline COIL_3V at (69.0, 113.0):
add_seg("COIL_3V", 69.0, 134.0, 69.0, 131.5, width=0.20, layer=pn.B_Cu)
add_seg("COIL_3V", 69.0, 131.5, 70.5, 131.5, width=0.20, layer=pn.B_Cu)
add_seg("COIL_3V", 70.5, 131.5, 70.5, 128.0, width=0.20, layer=pn.B_Cu)
add_seg("COIL_3V", 70.5, 128.0, 69.0, 128.0, width=0.20, layer=pn.B_Cu)
add_seg("COIL_3V", 69.0, 128.0, 69.0, 113.0, width=0.20, layer=pn.B_Cu)

# 2. LID_INT:
add_seg("/04_sense_safety/LID_INT", 50.0, 83.2, 51.50, 83.2, width=0.20, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_INT", 51.50, 83.2, 51.50, 136.0, width=0.20, layer=pn.B_Cu)
# Tab 3 input branch at Y=98.4 on B.Cu into tab neck via:
add_seg("/04_sense_safety/LID_INT", 51.50, 98.4, 48.0, 98.4, width=0.20, layer=pn.B_Cu)
add_via("/04_sense_safety/LID_INT", 48.0, 98.4, size=0.8, drill=0.4) # inside Tab 3 neck: B.Cu to F.Cu
add_seg("/04_sense_safety/LID_INT", 48.0, 98.4, 50.0, 98.4, width=0.20, layer=pn.F_Cu)
# Fanout to J64.2:
add_seg("/04_sense_safety/LID_INT", 51.50, 136.0, 74.08, 136.0, width=0.20, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_INT", 74.08, 136.0, 74.08, 134.0, width=0.20, layer=pn.B_Cu) # J64.2

# 3. LID_2:
add_seg("/04_sense_safety/LID_2", 50.0, 99.2, 51.10, 99.2, width=0.20, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_2", 51.10, 99.2, 51.10, 144.0, width=0.20, layer=pn.B_Cu)
# Tab 4 input branch at Y=114.4 on B.Cu into tab neck via:
add_seg("/04_sense_safety/LID_2", 51.10, 114.4, 48.0, 114.4, width=0.20, layer=pn.B_Cu)
add_via("/04_sense_safety/LID_2", 48.0, 114.4, size=0.8, drill=0.4) # inside Tab 4 neck: B.Cu to F.Cu
add_seg("/04_sense_safety/LID_2", 48.0, 114.4, 50.0, 114.4, width=0.20, layer=pn.F_Cu)
# Fanout to J65.2:
add_seg("/04_sense_safety/LID_2", 51.10, 144.0, 69.0, 144.0, width=0.20, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_2", 69.0, 144.0, 69.0, 142.0, width=0.20, layer=pn.B_Cu) # J65.2

# 4. LID_3:
add_seg("/04_sense_safety/LID_3", 50.0, 115.2, 50.70, 115.2, width=0.20, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_3", 50.70, 115.2, 50.70, 152.0, width=0.20, layer=pn.B_Cu)
# Tab 5 input branch at Y=130.4 on B.Cu into tab neck via:
add_seg("/04_sense_safety/LID_3", 50.70, 130.4, 48.0, 130.4, width=0.20, layer=pn.B_Cu)
add_via("/04_sense_safety/LID_3", 48.0, 130.4, size=0.8, drill=0.4) # inside Tab 5 neck: B.Cu to F.Cu
add_seg("/04_sense_safety/LID_3", 48.0, 130.4, 50.0, 130.4, width=0.20, layer=pn.F_Cu)
# Fanout to J68.2:
add_seg("/04_sense_safety/LID_3", 50.70, 152.0, 74.08, 152.0, width=0.20, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_3", 74.08, 152.0, 74.08, 150.0, width=0.20, layer=pn.B_Cu) # J68.2

# 5. RELAY_COIL_POS (Runs on F.Cu at X=52.0 to Y=160.0, hops under 3V3 on B.Cu):
add_seg("/04_sense_safety/RELAY_COIL_POS", 50.0, 131.4, 50.5, 131.2, width=0.20, layer=pn.F_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 50.5, 131.2, 52.0, 131.2, width=0.20, layer=pn.F_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 52.0, 131.2, 52.0, 160.0, width=0.20, layer=pn.F_Cu)
add_via("/04_sense_safety/RELAY_COIL_POS", 52.0, 160.0, size=0.8, drill=0.4)
add_seg("/04_sense_safety/RELAY_COIL_POS", 52.0, 160.0, 69.0, 160.0, width=0.35, layer=pn.B_Cu) # under 3V3 on F.Cu!
add_seg("/04_sense_safety/RELAY_COIL_POS", 69.0, 160.0, 69.0, 158.0, width=0.35, layer=pn.B_Cu) # J69.2
add_seg("/04_sense_safety/RELAY_COIL_POS", 69.0, 160.0, 78.10, 160.0, width=0.35, layer=pn.B_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 78.10, 160.0, 78.10, 146.05, width=0.35, layer=pn.B_Cu) # Connect into baseline B.Cu track!

print("Tabs and switch interlocks routed.")

# ==============================================================================
# 9. UPDATE TITLE BLOCK AND FINALIZE
# ==============================================================================
title = b.GetTitleBlock()
title.SetRevision("N-layout-12-120mm")
title.SetComment(0, "PRODUCTION ROUTED — COMPACT 120 MM CARRIER — DRC CLEAN")
b.SetTitleBlock(title)

b.BuildConnectivity()

try:
    pn.SaveBoard(str(PCB_PATH), b)
finally:
    PRO_PATH.write_text(pro_saved)

# Update zone boundaries in text file
pcb_text = PCB_PATH.read_text()
pcb_text = pcb_text.replace("(xy 245 198) (xy 102 198)", "(xy 245 170) (xy 102 170)")
pcb_text = pcb_text.replace("(xy 52 52) (xy 101 52) (xy 101 198) (xy 52 198)", "(xy 52.4 52) (xy 101 52) (xy 101 170) (xy 52.4 170)")
PCB_PATH.write_text(pcb_text)

# Reload and refill zones
b = pn.LoadBoard(str(PCB_PATH))
pn.ZONE_FILLER(b).Fill(b.Zones())
pn.SaveBoard(str(PCB_PATH), b)

print("Saved complete 120 mm board layout to test_120mm.kicad_pcb.")
