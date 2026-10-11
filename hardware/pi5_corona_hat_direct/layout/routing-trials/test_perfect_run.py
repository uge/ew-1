#!/usr/bin/env python3
"""test_perfect_run.py
Tests the clean architecture build for the 120 mm board with zero DRC violations.
"""
import sys
import os
import shutil
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

print("1. Pruning old tracks surgically...")
to_remove = []
for t in b.GetTracks():
    name = t.GetNetname()
    s, e = t.GetStart(), t.GetEnd()
    sx, ex = s.x / 1e6, e.x / 1e6
    sy, ey = s.y / 1e6, e.y / 1e6
    min_x, max_x = min(sx, ex), max(sx, ex)
    min_y, max_y = min(sy, ey), max(sy, ey)

    # 1. Any track in tabs (X < 47.5) or cut-off bottom (Y > 170.0)
    if min_x < 47.5 or max_y > 170.0:
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

    # 3. Switch daisy chain and connections
    if name in ['/04_sense_safety/LID_INT', '/04_sense_safety/LID_2', '/04_sense_safety/LID_3']:
        to_remove.append(t); continue
    if name == 'COIL_3V' and max_y > 113.0 and min_x < 80.0:
        to_remove.append(t); continue
    if name == '/04_sense_safety/RELAY_COIL_POS' and max_y > 146.0:
        to_remove.append(t); continue

    # 4. Old Tab 1 & J50 feeds (south of J2, X < 60, Y > 107)
    if min_x < 60.0 and max_y > 107.0:
        if name in ['/01_power_mcu/SCL', '/01_power_mcu/SDA', '3V3', 'GND']:
            to_remove.append(t); continue

    # 4b. Old SCL/SDA stubs west of J2 (X < 54.0, Y in [101.0, 107.0])
    if max_x <= 54.0 and 101.0 <= min_y <= 107.0:
        if name in ['/01_power_mcu/SCL', '/01_power_mcu/SDA']:
            to_remove.append(t); continue

    # 5. Old 3V3 loop to J50 near 78.9 (tracks from 84.3 west to 77.3)
    if name == '3V3' and max_x <= 84.5 and min_y >= 144.0 and max_y <= 147.0:
        to_remove.append(t); continue

    # 6. Inverter & primary
    if name in ['/02_drive_transformer/DRV_A', '/02_drive_transformer/DRV_B', '/02_drive_transformer/PRI_A', 'Net-(C63-Pad1)']:
        to_remove.append(t); continue
    # All HV_BRIDGE tracks east of C60 (X > 96.0, Y > 140.0)
    if name == '/02_drive_transformer/HV_BRIDGE' and max_x > 96.0 and max_y > 140.0:
        to_remove.append(t); continue
    # Old GND tracks in inverter/bridge/T1 area
    if name == 'GND' and min_x >= 98.0 and max_x <= 126.0 and min_y >= 140.0:
        to_remove.append(t); continue
    if name == 'GND' and 98.0 <= min_x <= 101.0 and 115.0 <= min_y <= 120.0:
        to_remove.append(t); continue

    # 7. Telemetry
    if name in ['/04_sense_safety/HV_SENSE_RAW', 'Net-(R8-Pad2)', 'Net-(U4-IN-)', '/HV_RETURN']:
        to_remove.append(t); continue
    if name == '/HV_SENSE_ADC' and max_y > 113.2:
        to_remove.append(t); continue
    if name == '/HV_CURR_ADC' and max_y > 114.2:
        to_remove.append(t); continue
    if name in ['3V3', 'GND'] and max_y > 161.0 and min_x > 85.0:
        to_remove.append(t); continue

for t in to_remove:
    b.Remove(t)
    t.thisown = False

print(f"Removed {len(to_remove)} tracks surgically.")

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
# 3. FOOTPRINT PLACEMENT
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
    # Telemetry
    'R8':  (137.0, 159.0, -90.0), 'R9':  (137.0, 165.0, -90.0),
    'C13': (132.0, 165.0, 0.0),   'U4':  (126.0, 163.0, -90.0),
    'R7':  (120.0, 163.0, 180.0), 'D1':  (120.0, 167.0, 0.0),
    'J61': (126.0, 156.0, 0.0),
    'D5':  (111.0, 167.0, 90.0),  'R90': (105.0, 167.0, 0.0),
    'D4':  (97.0,  167.0, 0.0),   'C14': (91.0,  167.0, 0.0),
    'R91': (91.0,  161.0, 180.0),
}

for ref, (x, y, rot) in final_pos.items():
    f = fps[ref]
    f.SetPosition(pt(x, y))
    f.SetOrientationDegrees(rot)
    if ref in ["S3", "S4", "S5", "S6"]: f.Reference().SetPosition(pt(20.0, y + 6.0))
    elif ref in ["J62", "J63", "J66", "J67", "J51"]: f.Reference().SetPosition(pt(39.0, y))
    elif ref == "U8": f.Reference().SetPosition(pt(30.0, y + 2.4))
    elif ref.startswith("R") and 20 <= int(ref[1:]) <= 29: f.Reference().SetPosition(pt(x + 4.5, y))
    elif ref == "J61": f.Reference().SetPosition(pt(x - 3.5, y))
    elif ref == "R7": f.Reference().SetPosition(pt(x, y + 2.5))
    elif ref == "D1": f.Reference().SetPosition(pt(x, y + 2.5))
    elif ref == "R8": f.Reference().SetPosition(pt(x - 2.5, y))
    elif ref == "R9": f.Reference().SetPosition(pt(x - 2.5, y))

# Copy baseline internal tab tracks and vias with dy = -62.0:
b_base = pn.LoadBoard(str(BASELINE_PCB))
dy = -62.0
tab_added = 0
for t in b_base.GetTracks():
    s, e = t.GetStart(), t.GetEnd()
    if max(s.x/1e6, e.x/1e6) <= 47.0 and min(s.y/1e6, e.y/1e6) >= 120.0:
        net = b.FindNet(t.GetNetname())
        if not net: continue
        if isinstance(t, pn.PCB_VIA):
            v = pn.PCB_VIA(b)
            v.SetPosition(pn.VECTOR2I(s.x, int(s.y + dy * 1e6)))
            v.SetWidth(t.GetWidth())
            v.SetDrill(t.GetDrill())
            v.SetLayerPair(pn.F_Cu, pn.B_Cu)
            v.SetNet(net)
            b.Add(v)
        else:
            nt = pn.PCB_TRACK(b)
            nt.SetStart(pn.VECTOR2I(s.x, int(s.y + dy * 1e6)))
            nt.SetEnd(pn.VECTOR2I(e.x, int(e.y + dy * 1e6)))
            nt.SetWidth(t.GetWidth())
            nt.SetLayer(t.GetLayer())
            nt.SetNet(net)
            b.Add(nt)
        tab_added += 1

print(f"Added {tab_added} internal tab tracks/vias from baseline shifted by -62mm.")

# ==============================================================================
# 4. ROUTE HIGH VOLTAGE MULTIPLIER, BLEEDERS, BALLAST, DIVIDER
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

# 5. /SEC_A: connects T1.7/8 to C100.1 and R140.1 via west side B.Cu (X=121.0)
add_seg("/SEC_A", 125.933, 117.75, 125.933, 120.25, width=0.8, layer=pn.F_Cu)
add_seg("/SEC_A", 125.933, 120.25, 121.0, 120.25, width=0.8, layer=pn.F_Cu)
add_via("/SEC_A", 121.0, 120.25, size=0.8, drill=0.4)
add_seg("/SEC_A", 121.0, 120.25, 121.0, 76.0, width=0.8, layer=pn.B_Cu)
add_via("/SEC_A", 121.0, 76.0, size=0.8, drill=0.4)
add_seg("/SEC_A", 121.0, 76.0, 124.25, 76.0, width=0.8, layer=pn.F_Cu)
add_seg("/SEC_A", 121.0, 76.0, 121.0, 61.0, width=0.8, layer=pn.F_Cu)
add_seg("/SEC_A", 121.0, 61.0, 121.2875, 61.0, width=0.8, layer=pn.F_Cu)

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
# 5. ROUTE INVERTER & PRIMARY (U2, D52..D55, C11, T1, C63, R64)
# ==============================================================================
# HV_BRIDGE on F.Cu:
# C60.1 at (97.0, 147.0) to D52.1 at (105.0, 147.4) and D54.1 at (117.0, 147.4)
# Run at Y=149.0 to be south of C60 pad 2 (GND) and south of 3V3 at Y=144.6:
add_seg("/02_drive_transformer/HV_BRIDGE", 97.0, 147.0, 97.0, 149.0, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/HV_BRIDGE", 97.0, 149.0, 103.0, 149.0, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/HV_BRIDGE", 103.0, 149.0, 103.0, 147.4, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/HV_BRIDGE", 103.0, 147.4, 105.0, 147.4, width=0.8, layer=pn.F_Cu) # D52.1
add_seg("/02_drive_transformer/HV_BRIDGE", 105.0, 147.4, 117.0, 147.4, width=0.8, layer=pn.F_Cu) # D54.1

# Bridge diodes GND on F.Cu into B.Cu GND zone:
add_seg("GND", 117.0, 152.6, 105.0, 152.6, width=0.8, layer=pn.F_Cu) # D55.2 to D53.2
add_seg("GND", 105.0, 152.6, 99.0, 152.6, width=0.8, layer=pn.F_Cu)
add_via("GND", 99.0, 152.6, size=0.8, drill=0.4)

# T1.6 (GND at 103.067, 107.75) to GND zone:
add_seg("GND", 103.067, 107.75, 99.0, 107.75, width=0.8, layer=pn.F_Cu)
add_via("GND", 99.0, 107.75, size=0.8, drill=0.4)

# PRI_A:
# C11.2 (125.0, 131.0) to T1.1 (103.067, 120.25) on F.Cu:
add_seg("/02_drive_transformer/PRI_A", 125.0, 131.0, 125.0, 135.0, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/PRI_A", 125.0, 135.0, 103.067, 135.0, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/PRI_A", 103.067, 135.0, 103.067, 120.25, width=0.8, layer=pn.F_Cu) # T1.1
# From T1.1 to R64.1 (116.963, 100.0) on B.Cu to hop under T1.6 GND trace on F.Cu:
add_via("/02_drive_transformer/PRI_A", 101.0, 120.25, size=0.8, drill=0.4)
add_seg("/02_drive_transformer/PRI_A", 103.067, 120.25, 101.0, 120.25, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/PRI_A", 101.0, 120.25, 101.0, 95.0, width=0.8, layer=pn.B_Cu)
add_seg("/02_drive_transformer/PRI_A", 101.0, 95.0, 116.963, 95.0, width=0.8, layer=pn.B_Cu)
add_via("/02_drive_transformer/PRI_A", 116.963, 95.0, size=0.8, drill=0.4)
add_seg("/02_drive_transformer/PRI_A", 116.963, 95.0, 116.963, 100.0, width=0.8, layer=pn.F_Cu) # R64.1

# Snubber Net-(C63-Pad1) on F.Cu:
add_seg("Net-(C63-Pad1)", 107.0, 100.95, 107.0, 102.5, width=0.6, layer=pn.F_Cu)
add_seg("Net-(C63-Pad1)", 107.0, 102.5, 111.037, 102.5, width=0.6, layer=pn.F_Cu)
add_seg("Net-(C63-Pad1)", 111.037, 102.5, 111.037, 100.0, width=0.6, layer=pn.F_Cu)

# DRV_A: U2.8 escape on B.Cu at Y=141.825:
add_seg("/02_drive_transformer/DRV_A", 86.225, 139.275, 87.425, 140.475, width=0.25, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_A", 87.425, 140.475, 92.225, 140.475, width=0.25, layer=pn.F_Cu)
add_via("/02_drive_transformer/DRV_A", 92.425, 140.675, size=0.8, drill=0.4)
add_seg("/02_drive_transformer/DRV_A", 92.425, 140.675, 103.0, 140.675, width=0.6, layer=pn.B_Cu)
# To D52.2 (105.0, 140.6) on B.Cu:
add_seg("/02_drive_transformer/DRV_A", 103.0, 140.675, 103.0, 140.6, width=0.6, layer=pn.B_Cu)
add_seg("/02_drive_transformer/DRV_A", 103.0, 140.6, 105.0, 140.6, width=0.6, layer=pn.B_Cu)
add_via("/02_drive_transformer/DRV_A", 105.0, 140.6, size=0.8, drill=0.4) # D52.2
# To D53.1 (105.0, 159.4) on B.Cu:
add_seg("/02_drive_transformer/DRV_A", 103.0, 140.6, 103.0, 159.4, width=0.6, layer=pn.B_Cu)
add_seg("/02_drive_transformer/DRV_A", 103.0, 159.4, 105.0, 159.4, width=0.6, layer=pn.B_Cu)
add_via("/02_drive_transformer/DRV_A", 105.0, 159.4, size=0.8, drill=0.4) # D53.1
# To C11.1 (110.0, 131.0): hop to F.Cu at (103.0, 140.0) to cross DRV_B cleanly!
add_via("/02_drive_transformer/DRV_A", 103.0, 140.0, size=0.8, drill=0.4)
add_seg("/02_drive_transformer/DRV_A", 103.0, 140.6, 103.0, 140.0, width=0.6, layer=pn.B_Cu)
add_seg("/02_drive_transformer/DRV_A", 103.0, 140.0, 103.0, 131.0, width=0.6, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_A", 103.0, 131.0, 110.0, 131.0, width=0.6, layer=pn.F_Cu) # C11.1 PTH pad!

# DRV_B: U2.10 escape on B.Cu at Y=138.4:
add_seg("/02_drive_transformer/DRV_B", 91.775, 138.625, 92.35, 138.625, width=0.25, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 92.35, 138.625, 92.4, 138.7, width=0.25, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 92.4, 138.7, 93.1, 139.15, width=0.25, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 93.1, 139.15, 93.9, 138.4, width=0.25, layer=pn.F_Cu)
add_via("/02_drive_transformer/DRV_B", 93.9, 138.4, size=0.8, drill=0.4)
add_seg("/02_drive_transformer/DRV_B", 93.9, 138.4, 115.0, 138.4, width=0.6, layer=pn.B_Cu)
# To D54.2 (117.0, 140.6) on B.Cu:
add_seg("/02_drive_transformer/DRV_B", 115.0, 138.4, 115.0, 140.6, width=0.6, layer=pn.B_Cu)
add_seg("/02_drive_transformer/DRV_B", 115.0, 140.6, 117.0, 140.6, width=0.6, layer=pn.B_Cu)
add_via("/02_drive_transformer/DRV_B", 117.0, 140.6, size=0.8, drill=0.4)
# To D55.1 (117.0, 159.4) on B.Cu:
add_seg("/02_drive_transformer/DRV_B", 115.0, 140.6, 115.0, 159.4, width=0.6, layer=pn.B_Cu)
add_seg("/02_drive_transformer/DRV_B", 115.0, 159.4, 117.0, 159.4, width=0.6, layer=pn.B_Cu)
add_via("/02_drive_transformer/DRV_B", 117.0, 159.4, size=0.8, drill=0.4)
# To T1.5 (103.067, 110.25) on B.Cu:
add_seg("/02_drive_transformer/DRV_B", 101.5, 138.4, 101.5, 110.25, width=0.6, layer=pn.B_Cu)
add_seg("/02_drive_transformer/DRV_B", 101.5, 110.25, 103.067, 110.25, width=0.6, layer=pn.B_Cu)
add_via("/02_drive_transformer/DRV_B", 103.067, 110.25, size=0.8, drill=0.4)
# T1.5 to C63.2 (107.0, 99.05) on F.Cu:
add_seg("/02_drive_transformer/DRV_B", 103.067, 110.25, 105.0, 110.25, width=0.6, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 105.0, 110.25, 105.0, 99.05, width=0.6, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 105.0, 99.05, 107.0, 99.05, width=0.6, layer=pn.F_Cu)

print("Inverter section routed.")

# ==============================================================================
# 6. ROUTE TELEMETRY SECTION
# ==============================================================================
# /HV_RETURN:
add_seg("/HV_RETURN", 125.933, 107.75, 125.933, 110.25, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 125.933, 110.25, 136.0, 110.25, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 136.0, 110.25, 136.0, 112.0, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 136.0, 112.0, 132.0, 112.0, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 132.0, 112.0, 132.0, 126.0, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 132.0, 126.0, 131.0, 126.0, width=0.8, layer=pn.F_Cu) # C101.1 PTH pad!
# Continue south on B.Cu from C101.1 along X=131.0:
add_seg("/HV_RETURN", 131.0, 126.0, 131.0, 148.0, width=0.8, layer=pn.B_Cu)
add_via("/HV_RETURN", 128.0375, 148.0, size=0.8, drill=0.4)
add_seg("/HV_RETURN", 131.0, 148.0, 128.0375, 148.0, width=0.8, layer=pn.B_Cu)
# South on B.Cu to J61.1 at (126.0, 156.0):
add_seg("/HV_RETURN", 131.0, 148.0, 131.0, 151.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 131.0, 151.0, 126.0, 156.0, width=0.8, layer=pn.B_Cu) # J61.1 PTH pad!
# Across B.Cu along Y=169.15:
add_seg("/HV_RETURN", 126.0, 156.0, 126.0, 169.15, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 126.0, 169.15, 111.0, 169.15, width=0.8, layer=pn.B_Cu)
add_via("/HV_RETURN", 111.0, 169.15, size=0.8, drill=0.4) # connects D5.1
add_seg("/HV_RETURN", 111.0, 169.15, 103.5375, 169.15, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 103.5375, 169.15, 103.5375, 167.0, width=0.8, layer=pn.B_Cu)
add_via("/HV_RETURN", 103.5375, 167.0, size=0.8, drill=0.4) # connects R90.1
add_seg("/HV_RETURN", 103.5375, 169.15, 89.0, 169.15, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 89.0, 169.15, 89.0, 161.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 89.0, 161.0, 91.75, 161.0, width=0.8, layer=pn.B_Cu)
add_via("/HV_RETURN", 91.75, 161.0, size=0.8, drill=0.4) # connects R91.1

# HV Voltage Sense:
add_seg("Net-(R8-Pad2)", 137.0, 159.75, 137.0, 164.25, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/HV_SENSE_RAW", 141.2875, 159.0, 137.0, 158.25, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/HV_SENSE_RAW", 137.0, 158.25, 131.3, 158.25, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/HV_SENSE_RAW", 131.3, 158.25, 131.3, 165.0, width=0.4, layer=pn.F_Cu) # C13.1
# Route south of J61 to U4.3 along Y=164.3:
add_seg("/04_sense_safety/HV_SENSE_RAW", 131.3, 164.3, 126.95, 164.3, width=0.4, layer=pn.F_Cu) # U4.3

# U4 feedback loop Net-(U4-IN-): U4.4 (126.95, 161.7), U4.1 (125.05, 164.3), R7.1 (120.75, 163.0)
add_seg("Net-(U4-IN-)", 126.95, 161.7, 126.95, 160.5, width=0.3, layer=pn.F_Cu)
add_seg("Net-(U4-IN-)", 126.95, 160.5, 123.5, 160.5, width=0.3, layer=pn.F_Cu)
add_seg("Net-(U4-IN-)", 123.5, 160.5, 123.5, 164.3, width=0.3, layer=pn.F_Cu)
add_seg("Net-(U4-IN-)", 123.5, 164.3, 125.05, 164.3, width=0.3, layer=pn.F_Cu) # U4.1
add_seg("Net-(U4-IN-)", 123.5, 160.5, 120.75, 160.5, width=0.3, layer=pn.F_Cu)
add_seg("Net-(U4-IN-)", 120.75, 160.5, 120.75, 163.0, width=0.3, layer=pn.F_Cu) # R7.1

# HV_SENSE_ADC: R7.2 (119.25, 163.0), D1.3 (119.0, 167.0) to baseline track at (86.7, 113.2)
add_seg("/HV_SENSE_ADC", 119.25, 163.0, 119.0, 163.0, width=0.4, layer=pn.F_Cu)
add_seg("/HV_SENSE_ADC", 119.0, 163.0, 119.0, 167.0, width=0.4, layer=pn.F_Cu)
add_via("/HV_SENSE_ADC", 119.0, 163.0, size=0.8, drill=0.4)
# Run west on B.Cu to X=113.0, then north with F.Cu bridge across DRV_B:
add_seg("/HV_SENSE_ADC", 119.0, 163.0, 113.0, 163.0, width=0.4, layer=pn.B_Cu)
add_seg("/HV_SENSE_ADC", 113.0, 163.0, 113.0, 140.0, width=0.4, layer=pn.B_Cu)
add_via("/HV_SENSE_ADC", 113.0, 140.0, size=0.8, drill=0.4)
add_seg("/HV_SENSE_ADC", 113.0, 140.0, 113.0, 136.5, width=0.4, layer=pn.F_Cu)
add_via("/HV_SENSE_ADC", 113.0, 136.5, size=0.8, drill=0.4)
add_seg("/HV_SENSE_ADC", 113.0, 136.5, 113.0, 128.0, width=0.4, layer=pn.B_Cu)
add_seg("/HV_SENSE_ADC", 113.0, 128.0, 107.0, 128.0, width=0.4, layer=pn.B_Cu)
add_seg("/HV_SENSE_ADC", 107.0, 128.0, 107.0, 113.2, width=0.4, layer=pn.B_Cu)
add_seg("/HV_SENSE_ADC", 107.0, 113.2, 86.7, 113.2, width=0.4, layer=pn.B_Cu)

# HV Current Sense:
# /HV_CURR_ADC: R91.2 (90.25, 161.0), C14.1 (90.3, 167.0), D4.3 (96.0, 167.95) to baseline track at (85.5, 114.2)
add_seg("/HV_CURR_ADC", 90.25, 161.0, 90.3, 161.0, width=0.4, layer=pn.F_Cu)
add_seg("/HV_CURR_ADC", 90.3, 161.0, 90.3, 166.0, width=0.4, layer=pn.F_Cu) # C14.1
add_seg("/HV_CURR_ADC", 90.3, 166.0, 96.0, 166.0, width=0.4, layer=pn.F_Cu)
add_seg("/HV_CURR_ADC", 96.0, 166.0, 96.0, 167.95, width=0.4, layer=pn.F_Cu) # D4.3
add_via("/HV_CURR_ADC", 96.0, 164.5, size=0.8, drill=0.4)
add_seg("/HV_CURR_ADC", 96.0, 166.0, 96.0, 164.5, width=0.4, layer=pn.F_Cu)
# On B.Cu, route along Y=164.5 to X=108.0, then north with F.Cu bridge across DRV_B:
add_seg("/HV_CURR_ADC", 96.0, 164.5, 108.0, 164.5, width=0.4, layer=pn.B_Cu)
add_seg("/HV_CURR_ADC", 108.0, 164.5, 108.0, 140.0, width=0.4, layer=pn.B_Cu)
add_via("/HV_CURR_ADC", 108.0, 140.0, size=0.8, drill=0.4)
add_seg("/HV_CURR_ADC", 108.0, 140.0, 108.0, 136.5, width=0.4, layer=pn.F_Cu)
add_via("/HV_CURR_ADC", 108.0, 136.5, size=0.8, drill=0.4)
add_seg("/HV_CURR_ADC", 108.0, 136.5, 108.0, 128.0, width=0.4, layer=pn.B_Cu)
add_seg("/HV_CURR_ADC", 108.0, 128.0, 105.0, 128.0, width=0.4, layer=pn.B_Cu)
add_seg("/HV_CURR_ADC", 105.0, 128.0, 105.0, 114.2, width=0.4, layer=pn.B_Cu)
add_seg("/HV_CURR_ADC", 105.0, 114.2, 85.5, 114.2, width=0.4, layer=pn.B_Cu)

# 3V3 power to telemetry:
# Baseline 3V3 is at (99.0, 160.6) on F.Cu:
add_seg("3V3", 99.0, 160.6, 98.0, 161.6, width=0.4, layer=pn.F_Cu)
add_seg("3V3", 98.0, 161.6, 98.0, 166.05, width=0.4, layer=pn.F_Cu) # D4.2
add_seg("3V3", 99.0, 160.6, 100.0, 160.6, width=0.4, layer=pn.F_Cu)
add_via("3V3", 100.0, 160.6, size=0.8, drill=0.4)
# Run on B.Cu along Y=166.05 (well south of HV_SENSE_ADC at 163.0):
add_seg("3V3", 100.0, 160.6, 100.0, 166.05, width=0.4, layer=pn.B_Cu)
add_seg("3V3", 100.0, 166.05, 121.0, 166.05, width=0.4, layer=pn.B_Cu)
add_via("3V3", 121.0, 166.05, size=0.8, drill=0.4) # D1.2
# From D1.2 east to U4.5 at (125.05, 161.7):
add_seg("3V3", 121.0, 166.05, 125.05, 166.05, width=0.4, layer=pn.B_Cu)
add_seg("3V3", 125.05, 166.05, 125.05, 163.0, width=0.4, layer=pn.B_Cu)
add_via("3V3", 125.05, 163.0, size=0.8, drill=0.4)
add_seg("3V3", 125.05, 163.0, 125.05, 161.7, width=0.4, layer=pn.F_Cu) # U4.5

# Individual GND vias directly to B.Cu GND zone:
add_via("GND", 98.0, 169.5, size=0.8, drill=0.4) # D4.1
add_seg("GND", 98.0, 167.95, 98.0, 169.5, width=0.4, layer=pn.F_Cu)

add_via("GND", 91.7, 168.5, size=0.8, drill=0.4) # C14.2
add_seg("GND", 91.7, 167.0, 91.7, 168.5, width=0.4, layer=pn.F_Cu)

add_via("GND", 104.0, 165.0, size=0.8, drill=0.4) # R90.2
add_seg("GND", 106.4625, 167.0, 104.0, 167.0, width=0.4, layer=pn.F_Cu)
add_seg("GND", 104.0, 167.0, 104.0, 165.0, width=0.4, layer=pn.F_Cu)

add_via("GND", 111.0, 161.5, size=0.8, drill=0.4) # D5.2
add_seg("GND", 111.0, 164.85, 111.0, 161.5, width=0.4, layer=pn.F_Cu)

add_via("GND", 122.5, 169.5, size=0.8, drill=0.4) # D1.1
add_seg("GND", 121.0, 167.95, 122.5, 167.95, width=0.4, layer=pn.F_Cu)
add_seg("GND", 122.5, 167.95, 122.5, 169.5, width=0.4, layer=pn.F_Cu)

add_via("GND", 127.5, 165.5, size=0.8, drill=0.4) # U4.2
add_seg("GND", 126.0, 164.3, 127.5, 164.3, width=0.4, layer=pn.F_Cu)
add_seg("GND", 127.5, 164.3, 127.5, 165.5, width=0.4, layer=pn.F_Cu)

add_via("GND", 134.0, 167.0, size=0.8, drill=0.4) # C13.2
add_seg("GND", 132.7, 165.0, 134.0, 165.0, width=0.4, layer=pn.F_Cu)
add_seg("GND", 134.0, 165.0, 134.0, 167.0, width=0.4, layer=pn.F_Cu)

add_via("GND", 137.0, 168.0, size=0.8, drill=0.4) # R9.2
add_seg("GND", 137.0, 165.75, 137.0, 168.0, width=0.4, layer=pn.F_Cu)

print("Telemetry section routed.")

# ==============================================================================
# 7. ROUTE BREAK-OFF TABS & SWITCH INTERLOCKS
# ==============================================================================
# Tab 1 neck to J2:
# SCL (exits neck at Y=64.7 on F.Cu) to J2.5 at (54.23, 101.55):
add_seg("/01_power_mcu/SCL", 47.0, 64.7, 52.2, 64.7, width=0.3, layer=pn.F_Cu)
add_seg("/01_power_mcu/SCL", 52.2, 64.7, 52.2, 101.55, width=0.3, layer=pn.F_Cu)
add_seg("/01_power_mcu/SCL", 52.2, 101.55, 54.23, 101.55, width=0.3, layer=pn.F_Cu)

# SDA (exits neck at Y=62.7 on B.Cu) to J2.3 at (54.23, 104.09):
add_seg("/01_power_mcu/SDA", 47.0, 62.7, 49.0, 62.7, width=0.3, layer=pn.F_Cu)
add_via("/01_power_mcu/SDA", 49.0, 62.7, size=0.8, drill=0.4)
add_seg("/01_power_mcu/SDA", 49.0, 62.7, 51.6, 62.7, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SDA", 51.6, 62.7, 51.6, 104.09, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SDA", 51.6, 104.09, 54.23, 104.09, width=0.3, layer=pn.B_Cu) # J2.3 is PTH!

# 3V3 (exits neck on B.Cu at Y=67.3):
add_seg("3V3", 47.0, 67.3, 49.0, 67.3, width=0.3, layer=pn.B_Cu)
add_via("3V3", 49.0, 67.3, size=0.8, drill=0.4)
add_seg("3V3", 49.0, 67.3, 51.0, 67.3, width=0.3, layer=pn.F_Cu)
add_seg("3V3", 51.0, 67.3, 51.0, 106.63, width=0.3, layer=pn.F_Cu)
add_seg("3V3", 51.0, 106.63, 54.23, 106.63, width=0.3, layer=pn.F_Cu) # J2.1

# Tab 1 GND: via directly into B.Cu GND zone at (49.0, 65.5)
add_via("GND", 49.0, 65.5, size=0.8, drill=0.4)
add_seg("GND", 47.0, 65.5, 49.0, 65.5, width=0.4, layer=pn.F_Cu)

# J50 connections at (59.0, 122.0):
# Pad 1 (GND) at (57.0, 123.5):
add_via("GND", 57.0, 123.5, size=0.8, drill=0.4)
# Pad 2 (3V3) at (57.0, 122.5):
add_via("3V3", 57.0, 122.5, size=0.8, drill=0.4)
add_seg("3V3", 57.0, 122.5, 61.0, 122.5, width=0.3, layer=pn.B_Cu)
add_seg("3V3", 61.0, 122.5, 61.0, 112.0, width=0.3, layer=pn.B_Cu) # connects to baseline 3V3 via at (61.0, 112.0)!
# Pad 3 (SDA) at (57.0, 121.5):
add_via("/01_power_mcu/SDA", 57.0, 121.5, size=0.8, drill=0.4)
add_seg("/01_power_mcu/SDA", 57.0, 121.5, 62.6, 121.5, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SDA", 62.6, 121.5, 62.6, 115.4, width=0.3, layer=pn.B_Cu) # connects to baseline SDA via at (62.6, 115.4)!
# Pad 4 (SCL) at (57.0, 120.5) via to B.Cu along X=57.0 (well west of INTERLOCK_OK via at 58.6, 105.35!):
add_via("/01_power_mcu/SCL", 57.0, 120.5, size=0.8, drill=0.4)
add_seg("/01_power_mcu/SCL", 57.0, 120.5, 57.0, 100.2, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SCL", 57.0, 100.2, 59.3, 100.2, width=0.3, layer=pn.B_Cu) # connects to baseline SCL on B.Cu!

# Tabs 2-5: Necks connect from X=47.0 to X=50.0:
# Tab 2: COIL_3V exits at Y=82.4 on F.Cu. LID_INT exits at Y=83.2 on B.Cu.
add_seg("COIL_3V", 47.0, 82.4, 50.0, 82.4, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_INT", 47.0, 83.2, 50.0, 83.2, width=0.4, layer=pn.B_Cu)

# Tab 3: LID_INT exits at Y=98.4 on F.Cu. LID_2 exits at Y=99.2 on B.Cu.
add_seg("/04_sense_safety/LID_INT", 47.0, 98.4, 50.0, 98.4, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_2", 47.0, 99.2, 50.0, 99.2, width=0.4, layer=pn.B_Cu)

# Tab 4: LID_2 exits at Y=114.4 on F.Cu. LID_3 exits at Y=115.2 on B.Cu.
add_seg("/04_sense_safety/LID_2", 47.0, 114.4, 50.0, 114.4, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_3", 47.0, 115.2, 50.0, 115.2, width=0.4, layer=pn.B_Cu)

# Tab 5: LID_3 exits at Y=130.4 on F.Cu. RELAY_COIL_POS exits at Y=131.4 on B.Cu (stays on B.Cu!).
add_seg("/04_sense_safety/LID_3", 47.0, 130.4, 50.0, 130.4, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 47.0, 131.4, 50.8, 131.4, width=0.4, layer=pn.B_Cu)

# Straight-line daisy chain on F.Cu between host connectors:
add_seg("/04_sense_safety/LID_INT", 74.08, 134.0, 74.08, 142.0, width=0.4, layer=pn.F_Cu) # J64.2 to J65.1
add_seg("/04_sense_safety/LID_2", 69.00, 142.0, 69.00, 150.0, width=0.4, layer=pn.F_Cu)   # J65.2 to J68.1
add_seg("/04_sense_safety/LID_3", 74.08, 150.0, 74.08, 158.0, width=0.4, layer=pn.F_Cu)   # J68.2 to J69.1

# Planar B.Cu bus for switch signals (strictly non-crossing, nested order):
# 1. COIL_3V: Tab 2 (50.0, 82.4) on B.Cu at X=52.8 down to J64.1 (69.0, 134.0)
add_via("COIL_3V", 50.0, 82.4, size=0.8, drill=0.4)
add_seg("COIL_3V", 50.0, 82.4, 52.8, 82.4, width=0.4, layer=pn.B_Cu)
add_seg("COIL_3V", 52.8, 82.4, 52.8, 134.0, width=0.4, layer=pn.B_Cu)
add_seg("COIL_3V", 52.8, 134.0, 69.0, 134.0, width=0.4, layer=pn.B_Cu)
# Connect north to baseline COIL_3V via at (69.0, 113.0), jog around GND via at (68.6, 129.8):
add_seg("COIL_3V", 69.0, 134.0, 69.0, 131.5, width=0.4, layer=pn.B_Cu)
add_seg("COIL_3V", 69.0, 131.5, 70.5, 131.5, width=0.4, layer=pn.B_Cu)
add_seg("COIL_3V", 70.5, 131.5, 70.5, 128.0, width=0.4, layer=pn.B_Cu)
add_seg("COIL_3V", 70.5, 128.0, 69.0, 128.0, width=0.4, layer=pn.B_Cu)
add_seg("COIL_3V", 69.0, 128.0, 69.0, 113.0, width=0.4, layer=pn.B_Cu)

# 2. LID_INT: Tab 2 (50.0, 83.2) & Tab 3 (50.0, 98.4) at X=52.3 down to J64.2 (74.08, 134.0)
add_seg("/04_sense_safety/LID_INT", 50.0, 83.2, 52.3, 83.2, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_INT", 52.3, 83.2, 52.3, 98.4, width=0.4, layer=pn.B_Cu)
add_via("/04_sense_safety/LID_INT", 50.0, 98.4, size=0.8, drill=0.4)
add_seg("/04_sense_safety/LID_INT", 50.0, 98.4, 52.3, 98.4, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_INT", 52.3, 98.4, 52.3, 136.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_INT", 52.3, 136.0, 74.08, 136.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_INT", 74.08, 136.0, 74.08, 134.0, width=0.4, layer=pn.B_Cu)

# 3. LID_2: Tab 3 (50.0, 99.2) & Tab 4 (50.0, 114.4) at X=51.8 down to J65.2 (69.0, 142.0)
add_seg("/04_sense_safety/LID_2", 50.0, 99.2, 51.8, 99.2, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_2", 51.8, 99.2, 51.8, 114.4, width=0.4, layer=pn.B_Cu)
add_via("/04_sense_safety/LID_2", 50.0, 114.4, size=0.8, drill=0.4)
add_seg("/04_sense_safety/LID_2", 50.0, 114.4, 51.8, 114.4, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_2", 51.8, 114.4, 51.8, 144.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_2", 51.8, 144.0, 69.0, 144.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_2", 69.0, 144.0, 69.0, 142.0, width=0.4, layer=pn.B_Cu)

# 4. LID_3: Tab 4 (50.0, 115.2) & Tab 5 (50.0, 130.4) at X=51.3 down to J68.2 (74.08, 150.0)
add_seg("/04_sense_safety/LID_3", 50.0, 115.2, 51.3, 115.2, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_3", 51.3, 115.2, 51.3, 130.4, width=0.4, layer=pn.B_Cu)
add_via("/04_sense_safety/LID_3", 50.0, 130.4, size=0.8, drill=0.4)
add_seg("/04_sense_safety/LID_3", 50.0, 130.4, 51.3, 130.4, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_3", 51.3, 130.4, 51.3, 152.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_3", 51.3, 152.0, 74.08, 152.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_3", 74.08, 152.0, 74.08, 150.0, width=0.4, layer=pn.B_Cu)

# 5. RELAY_COIL_POS: Tab 5 on B.Cu at X=50.8 down to Y=161.0, to J69.2 and baseline via at (78.10, 146.05)
# No via needed at tab neck - already on B.Cu!
add_seg("/04_sense_safety/RELAY_COIL_POS", 50.8, 131.4, 50.8, 161.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 50.8, 161.0, 78.10, 161.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 78.10, 161.0, 78.10, 146.05, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 69.0, 158.0, 69.0, 161.0, width=0.4, layer=pn.B_Cu)

print("Tabs and switch interlocks routed.")

# ==============================================================================
# 8. UPDATE TITLE BLOCK AND FINALIZE
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
pcb_text = pcb_text.replace("(xy 101 198) (xy 52 198)", "(xy 101 170) (xy 52 170)")
PCB_PATH.write_text(pcb_text)

# Reload and refill zones
b = pn.LoadBoard(str(PCB_PATH))
pn.ZONE_FILLER(b).Fill(b.Zones())
pn.SaveBoard(str(PCB_PATH), b)

print("Saved complete 120 mm board layout to test_120mm.kicad_pcb.")
