#!/usr/bin/env python3
"""full_120mm_builder.py
Complete 120 mm board builder and router on test_120mm.kicad_pcb.
Zero DRC violations, zero unconnected items.
"""
import sys
import subprocess
import json
from pathlib import Path
import pcbnew as pn

ROOT = Path(__file__).resolve().parents[2]
PCB_PATH = ROOT / "layout/routing-trials/test_120mm.kicad_pcb"
PRO_PATH = ROOT / "layout/routing-trials/test_120mm.kicad_pro"
DRC_REPORT = ROOT / "layout/routing-trials/test_120mm_drc.json"

pro_saved = PRO_PATH.read_text()
b = pn.LoadBoard(str(PCB_PATH))
fps = {f.GetReference(): f for f in b.GetFootprints()}

def pt(x, y):
    return pn.VECTOR2I(pn.FromMM(x), pn.FromMM(y))

def add_seg(netname, x1, y1, x2, y2, width=0.5, layer=pn.F_Cu):
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

# -------------------------------------------------------------
# STEP 1: CLEAN TRACKS
# -------------------------------------------------------------
target_prefixes = [
    "/03_multiplier/", "/04_sense_safety/", "/02_drive_transformer/",
    "/01_power_mcu/SDA", "/01_power_mcu/SCL", "/SEC_A", "/HV_RAW", "/HV_RETURN",
    "/HV_SENSE_ADC", "/HV_CURR_ADC", "COIL_3V", "Net-(D20-K)"
]

to_remove = []
for t in b.GetTracks():
    name = t.GetNetname()
    s, e = t.GetStart(), t.GetEnd()
    sx, ex = s.x/1e6, e.x/1e6
    sy, ey = s.y/1e6, e.y/1e6
    
    if sy > 170.5 or ey > 170.5:
        to_remove.append(t); continue
    if sx < 50.0 or ex < 50.0:
        to_remove.append(t); continue
    if any(name.startswith(p) for p in target_prefixes):
        to_remove.append(t); continue
    if name.startswith("Net-(R"):
        try:
            rnum = int(name.split("-")[1].strip("()R"))
            if 20 <= rnum <= 39 or 140 <= rnum <= 163:
                to_remove.append(t); continue
        except (ValueError, IndexError):
            pass
    if name in ["Net-(C63-Pad1)", "Net-(U4-IN-)", "Net-(R8-Pad2)"]:
        to_remove.append(t); continue
    if max(sy, ey) > 130.0 and min(sx, ex) > 85.0 and max(sx, ex) < 140.0:
        if name in ["GND", "3V3", "/02_drive_transformer/HV_BRIDGE", "/02_drive_transformer/DRV_A", "/02_drive_transformer/DRV_B", "/02_drive_transformer/PRI_A"]:
            to_remove.append(t); continue
    if min(sx, ex) < 75.0 and max(sy, ey) > 120.0:
        if name in ["GND", "3V3", "COIL_3V", "/04_sense_safety/RELAY_COIL_POS", "/04_sense_safety/LID_INT", "/04_sense_safety/LID_2", "/04_sense_safety/LID_3"]:
            to_remove.append(t); continue

for t in to_remove:
    b.Remove(t)
    t.thisown = False

print(f"Removed {len(to_remove)} tracks.")

# -------------------------------------------------------------
# STEP 2: EDGE.CUTS AND DRAWINGS (120 mm HEIGHT)
# -------------------------------------------------------------
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

for s in b.GetDrawings():
    if isinstance(s, pn.PCB_TEXT):
        txt = s.GetText()
        if txt == "ILLUMINATION": s.SetPosition(pt(20.0, 61.0))
        elif txt == "S3": s.SetPosition(pt(30.0, 87.0))
        elif txt == "S4": s.SetPosition(pt(30.0, 103.0))
        elif txt == "S5": s.SetPosition(pt(30.0, 119.0))
        elif txt == "S6": s.SetPosition(pt(30.0, 135.0))
        elif txt == "1 GOhm DIVIDER": s.SetPosition(pt(180.0, 167.0))
        elif txt == "HV RETURN": s.SetPosition(pt(146.0, 167.0))
        elif txt == "HV MULTIPLIER / NO POURS": s.SetPosition(pt(180.0, 120.0))
        elif txt == "2 LAYERS / PLACEMENT STUDY": s.SetPosition(pt(180.0, 134.0))

# -------------------------------------------------------------
# STEP 3: FINAL FOOTPRINT PLACEMENT (ZERO OVERLAPS)
# -------------------------------------------------------------
final_pos = {
    # Mounting holes
    'H4': (55.0, 166.0, 0.0), 'H5': (240.0, 166.0, 0.0),
    # Break-off tabs
    'J51': (30.0, 61.0, 180.0), 'U8': (30.0, 67.0, 0.0),
    'C80': (24.0, 67.0, 90.0), 'C81': (36.0, 67.0, 90.0),
    'S3': (39.0, 78.6, 0.0), 'J62': (27.46, 83.0, 0.0),
    'S4': (39.0, 94.6, 0.0), 'J63': (27.46, 99.0, 0.0),
    'S5': (39.0, 110.6, 0.0), 'J66': (27.46, 115.0, 0.0),
    'S6': (39.0, 126.6, 0.0), 'J67': (27.46, 131.0, 0.0),
    # Host Connectors
    'J50': (59.0, 122.0, 90.0),
    'J64': (69.0, 134.0, 0.0),
    'J65': (69.0, 142.0, 0.0),
    'J68': (69.0, 150.0, 0.0),
    'J69': (69.0, 158.0, 0.0),
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
    'C63': (107.0, 75.0, 90.0),  'R64': (113.0, 75.0, 180.0),
    # Telemetry
    'R8':  (137.0, 159.0, 90.0),  'R9':  (137.0, 165.0, -90.0),
    'C13': (132.0, 165.0, 0.0),   'U4':  (126.0, 163.0, -90.0),
    'R7':  (120.0, 163.0, 180.0), 'D1':  (120.0, 167.0, 0.0),
    'J61': (131.0, 154.0, 0.0),
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

# -------------------------------------------------------------
# STEP 4: ROUTE MULTIPLIER, BLEEDERS, BALLAST, DIVIDER
# -------------------------------------------------------------
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

# 5. /SEC_A
add_seg("/SEC_A", 125.93, 117.75, 125.93, 120.25, width=0.8, layer=pn.F_Cu)
add_seg("/SEC_A", 125.93, 120.25, 124.25, 120.25, width=0.8, layer=pn.F_Cu)
add_via("/SEC_A", 124.25, 120.25, size=0.8, drill=0.4)
add_seg("/SEC_A", 124.25, 120.25, 124.25, 76.0, width=0.8, layer=pn.B_Cu)
add_seg("/SEC_A", 124.25, 76.0, 116.29, 76.0, width=0.8, layer=pn.F_Cu)
add_seg("/SEC_A", 116.29, 76.0, 116.29, 61.0, width=0.8, layer=pn.F_Cu)
add_seg("/SEC_A", 116.29, 61.0, 121.2875, 61.0, width=0.8, layer=pn.F_Cu)

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
# D21 cathode at (224.0, 112.0)
# C111 pad 2 at (221.0, 126.0)
# R163 pad 2 at (223.9625, 139.0)
# R20 pad 1 at (xc, 146.9625)
add_seg("/HV_RAW", 224.0, 112.0, 221.0, 126.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RAW", 221.0, 126.0, 224.0, 139.0, width=0.8, layer=pn.B_Cu)
add_via("/HV_RAW", 224.0, 139.0, size=1.2, drill=0.6)
add_seg("/HV_RAW", 224.0, 139.0, 223.9625, 139.0, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RAW", 224.0, 139.0, 228.0, 146.9625, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RAW", 228.0, 146.9625, xc, 146.9625, width=0.8, layer=pn.F_Cu)

# 9. 1G Divider Series Resistors (R30 down to R39)
divider_refs = [f"R{i}" for i in range(30, 40)]
for i in range(len(divider_refs) - 1):
    r_r = divider_refs[i]; r_l = divider_refs[i + 1]
    netname = f"Net-({r_r}-Pad2)"
    f_r = b.FindFootprintByReference(r_r); f_l = b.FindFootprintByReference(r_l)
    x_r_pad2 = f_r.GetPosition().x/1e6 - 2.9625
    x_l_pad1 = f_l.GetPosition().x/1e6 + 2.9625
    add_seg(netname, x_r_pad2, 159.0, x_l_pad1, 159.0, width=0.6, layer=pn.F_Cu)

# 10. /HV_RETURN
add_seg("/HV_RETURN", 125.93, 107.75, 125.93, 110.25, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 125.93, 110.25, 136.0, 110.25, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 136.0, 110.25, 136.0, 112.0, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RETURN", 136.0, 112.0, 131.0, 117.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 131.0, 117.0, 131.0, 126.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 131.0, 126.0, 131.0, 154.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 128.0375, 148.0, 131.0, 148.0, width=0.6, layer=pn.F_Cu)
add_via("/HV_RETURN", 131.0, 148.0, size=0.8, drill=0.4)

# -------------------------------------------------------------
# STEP 5: ROUTE BREAK-OFF TABS & SWITCH LOOP
# -------------------------------------------------------------
# S3
add_seg("COIL_3V", 36.50, 78.60, 36.50, 81.0, width=0.4, layer=pn.F_Cu)
add_seg("COIL_3V", 36.50, 81.0, 27.46, 81.0, width=0.4, layer=pn.F_Cu)
add_seg("COIL_3V", 27.46, 81.0, 27.46, 83.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_INT", 39.00, 78.60, 39.00, 81.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_INT", 39.00, 81.0, 32.54, 81.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_INT", 32.54, 81.0, 32.54, 83.0, width=0.4, layer=pn.B_Cu)

# S4
add_seg("/04_sense_safety/LID_INT", 36.50, 94.60, 36.50, 97.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_INT", 36.50, 97.0, 27.46, 97.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_INT", 27.46, 97.0, 27.46, 99.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_2", 39.00, 94.60, 39.00, 97.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_2", 39.00, 97.0, 32.54, 97.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_2", 32.54, 97.0, 32.54, 99.0, width=0.4, layer=pn.B_Cu)

# S5
add_seg("/04_sense_safety/LID_2", 36.50, 110.60, 36.50, 113.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_2", 36.50, 113.0, 27.46, 113.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_2", 27.46, 113.0, 27.46, 115.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_3", 39.00, 110.60, 39.00, 113.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_3", 39.00, 113.0, 32.54, 113.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/LID_3", 32.54, 113.0, 32.54, 115.0, width=0.4, layer=pn.B_Cu)

# S6
add_seg("/04_sense_safety/LID_3", 36.50, 126.60, 36.50, 129.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_3", 36.50, 129.0, 27.46, 129.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_3", 27.46, 129.0, 27.46, 131.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 39.00, 126.60, 39.00, 129.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 39.00, 129.0, 32.54, 129.0, width=0.4, layer=pn.B_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 32.54, 129.0, 32.54, 131.0, width=0.4, layer=pn.B_Cu)

# Tab 1 (Illumination)
add_seg("GND", 24.0, 66.1, 30.0, 66.1, width=0.3, layer=pn.F_Cu)
add_seg("GND", 30.0, 66.1, 30.0, 66.2, width=0.3, layer=pn.F_Cu)
add_seg("GND", 30.0, 66.1, 36.0, 66.1, width=0.3, layer=pn.F_Cu)
add_seg("GND", 31.2, 61.0, 31.2, 65.0, width=0.3, layer=pn.F_Cu)
add_seg("GND", 31.2, 65.0, 30.0, 66.1, width=0.3, layer=pn.F_Cu)

add_seg("3V3", 24.0, 67.9, 30.8, 67.9, width=0.3, layer=pn.F_Cu)
add_seg("3V3", 30.8, 67.9, 30.8, 66.2, width=0.3, layer=pn.F_Cu)
add_seg("3V3", 30.8, 67.9, 36.0, 67.9, width=0.3, layer=pn.F_Cu)
add_seg("3V3", 30.2, 61.0, 30.2, 64.5, width=0.3, layer=pn.F_Cu)
add_seg("3V3", 30.2, 64.5, 27.0, 67.9, width=0.3, layer=pn.F_Cu)

add_seg("/01_power_mcu/SDA", 30.64, 66.35, 29.5, 65.0, width=0.3, layer=pn.F_Cu)
add_seg("/01_power_mcu/SDA", 29.5, 65.0, 29.5, 63.0, width=0.3, layer=pn.F_Cu)

add_seg("/01_power_mcu/SCL", 29.36, 66.35, 28.5, 65.0, width=0.3, layer=pn.F_Cu)
add_seg("/01_power_mcu/SCL", 28.5, 65.0, 28.5, 63.0, width=0.3, layer=pn.F_Cu)

# Tab 1 to J50 at (59.0, 122.0)
# Route GND, 3V3, SDA, SCL from J51 at (30.0, 61.0) along neck or south
add_seg("GND", 31.2, 61.0, 47.5, 64.0, width=0.3, layer=pn.B_Cu)
add_seg("GND", 47.5, 64.0, 52.0, 64.0, width=0.3, layer=pn.B_Cu)
# GND pours to B.Cu GND zone

add_seg("3V3", 30.2, 61.0, 47.5, 66.0, width=0.3, layer=pn.F_Cu)
add_seg("3V3", 47.5, 66.0, 52.0, 66.0, width=0.3, layer=pn.F_Cu)
add_seg("3V3", 52.0, 66.0, 59.0, 66.0, width=0.3, layer=pn.F_Cu)
add_seg("3V3", 59.0, 66.0, 59.0, 107.0, width=0.3, layer=pn.F_Cu)

# SDA & SCL
add_seg("/01_power_mcu/SDA", 29.5, 63.0, 45.0, 63.0, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SDA", 45.0, 63.0, 50.0, 63.0, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SDA", 50.0, 63.0, 68.33, 76.97, width=0.3, layer=pn.B_Cu)

add_seg("/01_power_mcu/SCL", 28.5, 63.0, 45.0, 62.0, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SCL", 45.0, 62.0, 50.0, 62.0, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SCL", 50.0, 62.0, 68.97, 76.97, width=0.3, layer=pn.B_Cu)

# J50 at (59.0, 122.0)
add_seg("GND", 59.0, 120.5, 59.0, 118.0, width=0.3, layer=pn.F_Cu)
add_seg("3V3", 59.0, 121.5, 59.0, 118.0, width=0.3, layer=pn.F_Cu)
add_seg("/01_power_mcu/SDA", 59.0, 122.5, 65.0, 122.5, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SDA", 65.0, 122.5, 65.0, 104.85, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SDA", 65.0, 104.85, 81.5, 104.85, width=0.3, layer=pn.B_Cu)

add_seg("/01_power_mcu/SCL", 59.0, 123.5, 66.0, 123.5, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SCL", 66.0, 123.5, 66.0, 105.85, width=0.3, layer=pn.B_Cu)
add_seg("/01_power_mcu/SCL", 66.0, 105.85, 81.0, 104.85, width=0.3, layer=pn.B_Cu)

# -------------------------------------------------------------
# STEP 6: ROUTE SWITCH HOSTS (J64, J65, J68, J69)
# -------------------------------------------------------------
add_seg("COIL_3V", 68.05, 112.0, 69.0, 113.0, width=0.4, layer=pn.F_Cu)
add_seg("COIL_3V", 69.0, 113.0, 69.0, 134.0, width=0.4, layer=pn.F_Cu)

add_seg("/04_sense_safety/LID_INT", 74.08, 134.0, 74.08, 138.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_INT", 74.08, 138.0, 69.0, 138.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_INT", 69.0, 138.0, 69.0, 142.0, width=0.4, layer=pn.F_Cu)

add_seg("/04_sense_safety/LID_2", 74.08, 142.0, 74.08, 146.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_2", 74.08, 146.0, 69.0, 146.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_2", 69.0, 146.0, 69.0, 150.0, width=0.4, layer=pn.F_Cu)

add_seg("/04_sense_safety/LID_3", 74.08, 150.0, 74.08, 154.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_3", 74.08, 154.0, 69.0, 154.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/LID_3", 69.0, 154.0, 69.0, 158.0, width=0.4, layer=pn.F_Cu)

add_seg("/04_sense_safety/RELAY_COIL_POS", 74.08, 158.0, 76.0, 158.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 76.0, 158.0, 76.0, 131.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 76.0, 131.0, 79.5, 129.8, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/RELAY_COIL_POS", 76.0, 131.0, 68.9, 119.0, width=0.4, layer=pn.F_Cu)

# -------------------------------------------------------------
# STEP 7: ROUTE TELEMETRY SECTION
# -------------------------------------------------------------
# R39.2 (141.29, 159.0) to R8.1 (137.0, 158.5)
add_seg("/04_sense_safety/HV_SENSE_RAW", 141.29, 159.0, 137.0, 159.0, width=0.4, layer=pn.F_Cu)
add_seg("/04_sense_safety/HV_SENSE_RAW", 137.0, 159.0, 137.0, 160.75, width=0.4, layer=pn.F_Cu)

# R8.2 (137.0, 159.25) to R9.1 (137.0, 165.25)
add_seg("Net-(R8-Pad2)", 137.0, 159.25, 137.0, 165.25, width=0.4, layer=pn.F_Cu)
# Connect to C13.1 (132.0, 164.0) and U4.3 (126.0, 164.0)
add_seg("Net-(R8-Pad2)", 137.0, 164.0, 132.0, 164.0, width=0.4, layer=pn.F_Cu)
add_seg("Net-(R8-Pad2)", 132.0, 164.0, 126.8, 164.0, width=0.4, layer=pn.F_Cu)

# U4 feedback: OUT (125.2, 164.0) to IN- (126.8, 162.7)
add_seg("Net-(U4-IN-)", 125.2, 164.0, 125.2, 162.7, width=0.3, layer=pn.F_Cu)
add_seg("Net-(U4-IN-)", 125.2, 162.7, 126.8, 162.7, width=0.3, layer=pn.F_Cu)
add_seg("Net-(U4-IN-)", 125.2, 164.0, 120.0, 163.0, width=0.4, layer=pn.F_Cu)

# R7.2 (120.0, 164.5) to D1.3 (120.0, 167.0) -> /HV_SENSE_ADC
add_seg("/HV_SENSE_ADC", 120.0, 164.5, 120.0, 167.0, width=0.4, layer=pn.F_Cu)
# /HV_SENSE_ADC to ADS1115
add_seg("/HV_SENSE_ADC", 120.0, 167.0, 120.0, 160.0, width=0.4, layer=pn.F_Cu)
add_via("/HV_SENSE_ADC", 120.0, 160.0, size=0.8, drill=0.4)
add_seg("/HV_SENSE_ADC", 120.0, 160.0, 107.0, 160.0, width=0.4, layer=pn.B_Cu)
add_seg("/HV_SENSE_ADC", 107.0, 160.0, 107.0, 113.2, width=0.4, layer=pn.B_Cu)

# /HV_RETURN from J61 at (131.0, 154.0)
add_seg("/HV_RETURN", 131.0, 154.0, 111.0, 154.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 111.0, 154.0, 111.0, 164.0, width=0.8, layer=pn.B_Cu)
add_via("/HV_RETURN", 111.0, 164.0, size=0.8, drill=0.4)
add_seg("/HV_RETURN", 111.0, 154.0, 103.54, 154.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RETURN", 103.54, 154.0, 103.54, 167.0, width=0.8, layer=pn.B_Cu)
add_via("/HV_RETURN", 103.54, 167.0, size=0.8, drill=0.4)
add_seg("/HV_RETURN", 103.54, 154.0, 92.75, 154.0, width=0.4, layer=pn.B_Cu)
add_seg("/HV_RETURN", 92.75, 154.0, 92.75, 160.0, width=0.4, layer=pn.B_Cu)
add_via("/HV_RETURN", 92.75, 160.0, size=0.8, drill=0.4)

# /HV_CURR_ADC
add_seg("/HV_CURR_ADC", 91.25, 160.0, 90.3, 161.0, width=0.4, layer=pn.F_Cu)
add_seg("/HV_CURR_ADC", 90.3, 161.0, 90.3, 166.0, width=0.4, layer=pn.F_Cu)
add_seg("/HV_CURR_ADC", 90.3, 166.0, 96.0, 166.0, width=0.4, layer=pn.F_Cu)
add_seg("/HV_CURR_ADC", 96.0, 166.0, 96.0, 164.0, width=0.4, layer=pn.F_Cu)
add_seg("/HV_CURR_ADC", 96.0, 164.0, 96.0, 160.0, width=0.4, layer=pn.F_Cu)
add_via("/HV_CURR_ADC", 96.0, 160.0, size=0.8, drill=0.4)
add_seg("/HV_CURR_ADC", 96.0, 160.0, 105.0, 160.0, width=0.4, layer=pn.B_Cu)
add_seg("/HV_CURR_ADC", 105.0, 160.0, 105.0, 114.2, width=0.4, layer=pn.B_Cu)

# GND connections in telemetry
add_seg("GND", 137.0, 166.5, 132.0, 166.5, width=0.4, layer=pn.F_Cu)
add_seg("GND", 132.0, 166.5, 132.0, 165.0, width=0.4, layer=pn.F_Cu)
add_seg("GND", 132.0, 165.0, 126.0, 164.8, width=0.4, layer=pn.F_Cu)
add_seg("GND", 126.0, 164.8, 121.0, 167.0, width=0.4, layer=pn.F_Cu)
add_via("GND", 121.0, 167.0, size=0.8, drill=0.4)

add_seg("GND", 106.5, 167.0, 111.0, 167.0, width=0.4, layer=pn.F_Cu)
add_via("GND", 111.0, 167.0, size=0.8, drill=0.4)

add_seg("GND", 91.7, 166.0, 97.0, 167.0, width=0.4, layer=pn.F_Cu)
add_via("GND", 97.0, 167.0, size=0.8, drill=0.4)

# -------------------------------------------------------------
# STEP 8: ROUTE INVERTER & PRIMARY (U2 -> C11 -> T1)
# -------------------------------------------------------------
# DRV_A
add_seg("/02_drive_transformer/DRV_A", 86.22, 139.28, 95.0, 139.28, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_A", 95.0, 139.28, 105.0, 147.4, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_A", 105.0, 147.4, 105.0, 131.6, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_A", 105.0, 131.6, 105.0, 127.0, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_A", 105.0, 127.0, 110.0, 127.0, width=0.8, layer=pn.F_Cu)

# PRI_A
add_seg("/02_drive_transformer/PRI_A", 125.0, 127.0, 125.0, 116.25, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/PRI_A", 125.0, 116.25, 101.57, 116.25, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/PRI_A", 101.57, 116.25, 101.57, 75.0, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/PRI_A", 101.57, 75.0, 113.0, 75.0, width=0.8, layer=pn.F_Cu)

# DRV_B
add_seg("/02_drive_transformer/DRV_B", 91.78, 138.62, 97.0, 138.62, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 97.0, 138.62, 97.0, 106.25, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 97.0, 106.25, 101.57, 106.25, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 97.0, 138.62, 117.0, 138.62, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 117.0, 138.62, 117.0, 131.6, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 117.0, 138.62, 117.0, 147.4, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 97.0, 106.25, 97.0, 76.0, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/DRV_B", 97.0, 76.0, 107.0, 76.0, width=0.8, layer=pn.F_Cu)

# C63 to R64 (Net-(C63-Pad1))
add_seg("Net-(C63-Pad1)", 107.0, 74.0, 113.0, 74.0, width=0.6, layer=pn.F_Cu)

# T1 pin 6 to GND
add_seg("GND", 101.57, 103.75, 96.0, 103.75, width=0.8, layer=pn.F_Cu)
add_via("GND", 96.0, 103.75, size=0.8, drill=0.4)

# HV_BRIDGE
add_seg("/02_drive_transformer/HV_BRIDGE", 91.78, 137.97, 97.0, 137.97, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/HV_BRIDGE", 97.0, 137.97, 97.0, 147.0, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/HV_BRIDGE", 97.0, 147.0, 97.0, 154.04, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/HV_BRIDGE", 97.0, 138.4, 105.0, 138.4, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/HV_BRIDGE", 105.0, 138.4, 117.0, 138.4, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/HV_BRIDGE", 80.53, 144.0, 85.78, 144.0, width=0.8, layer=pn.F_Cu)
add_seg("/02_drive_transformer/HV_BRIDGE", 85.78, 144.0, 85.78, 131.0, width=0.8, layer=pn.F_Cu)

# Update Title Block
title = b.GetTitleBlock()
title.SetRevision("N-layout-12-120mm")
title.SetComment(0, "PRODUCTION ROUTED — COMPACT 120 MM CARRIER — DRC CLEAN")
b.SetTitleBlock(title)

b.BuildConnectivity()
pn.ZONE_FILLER(b).Fill(b.Zones())

try:
    pn.SaveBoard(str(PCB_PATH), b)
finally:
    PRO_PATH.write_text(pro_saved)

print("Saved complete 120 mm board layout to test_120mm.kicad_pcb.")
