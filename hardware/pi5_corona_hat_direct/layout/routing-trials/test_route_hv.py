#!/usr/bin/env python3
"""test_route_hv.py
Routes CW multiplier, bleeders, ballast, and 1G divider on test_120mm.kicad_pcb.
"""
import sys
from pathlib import Path
import pcbnew as pn

PCB_PATH = Path(__file__).resolve().parent / "test_120mm.kicad_pcb"
PRO_PATH = Path(__file__).resolve().parent / "test_120mm.kicad_pro"

pro_saved = PRO_PATH.read_text()
b = pn.LoadBoard(str(PCB_PATH))

def pt(x, y):
    return pn.VECTOR2I(pn.FromMM(x), pn.FromMM(y))

def add_seg(netname, x1, y1, x2, y2, width=0.8, layer=pn.B_Cu):
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

def add_via(netname, x, y, size=1.2, drill=0.6):
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

# 1. Remove old tracks on target nets
target_nets = [
    f"/03_multiplier/CW_P{k}" for k in range(1, 6)
] + [
    f"/03_multiplier/CW_S{k}" for k in range(1, 6)
] + [
    "/SEC_A", "Net-(D20-K)", "/HV_RAW", "/04_sense_safety/HV_OUT"
] + [f"Net-(R{i}-Pad2)" for i in range(20, 29)] + [f"Net-(R{i}-Pad2)" for i in range(30, 39)] + [
    f"Net-(R{i}-Pad2)" for i in range(140, 164, 2)
]

to_remove = []
for t in b.GetTracks():
    if t.GetNetname() in target_nets:
        to_remove.append(t)

for t in to_remove:
    b.Remove(t)
    t.thisown = False

print(f"Removed {len(to_remove)} old HV tracks.")

# 2. Route CW_P1 to CW_P5 (Pump stages)
# Top Caps at Y = 76.0 mm (pads at X +- 5.0 mm)
# Diodes at Y = 99.0 mm (top pads at Y = 99.0 - 13.0 = 86.0 mm)
# Bleeders Row 1 at Y = 61.0 mm (taps at X +- 2.9625)
# Bleeders Row 2 at Y = 69.0 mm (taps at X +- 2.9625)
for k in range(1, 6):
    netname = f"/03_multiplier/CW_P{k}"
    dx = (k - 1) * 16.0
    c_l_x, c_l_y = 134.25 + dx, 76.0
    c_r_x, c_r_y = 140.25 + dx, 76.0
    d_l_x, d_l_y = 136.0 + dx, 86.0
    d_r_x, d_r_y = 144.0 + dx, 86.0

    # Capacitor and Diode interconnects on B.Cu
    add_seg(netname, c_l_x, c_l_y, c_r_x, c_r_y, width=0.8, layer=pn.B_Cu)
    add_seg(netname, c_l_x, c_l_y, d_l_x, d_l_y, width=0.8, layer=pn.B_Cu)
    add_seg(netname, c_r_x, c_r_y, d_r_x, d_r_y, width=0.8, layer=pn.B_Cu)

    # Bleeder taps
    if k % 2 == 1:
        # Odd pump stage: tap Row 2 (Y=69) to c_l, tap Row 1 (Y=61) to c_r
        b_69_x = 137.2875 + dx - 5.0 # R144.1 at 137.2875 + dx
        b_61_x = 137.2125 + dx       # R141.2 at 137.2125 + dx
        add_seg(netname, 137.2875 + dx, 69.0, c_l_x, c_l_y, width=0.8, layer=pn.F_Cu)
        add_seg(netname, 137.2125 + dx, 61.0, 137.2125 + dx, 58.5, width=0.8, layer=pn.F_Cu)
        add_via(netname, 137.2125 + dx, 58.5, size=0.8, drill=0.4)
        add_seg(netname, 137.2125 + dx, 58.5, c_r_x, c_r_y, width=0.8, layer=pn.B_Cu)
    else:
        # Even pump stage: tap Row 1 to c_l, tap Row 2 to c_r
        b_61_x = 153.2875 + (k - 2) * 16.0 # R148.1
        b_69_x = 153.2125 + (k - 2) * 16.0 # R145.2
        add_seg(netname, b_61_x, 61.0, b_61_x, 58.5, width=0.8, layer=pn.F_Cu)
        add_via(netname, b_61_x, 58.5, size=0.8, drill=0.4)
        add_seg(netname, b_61_x, 58.5, c_l_x, c_l_y, width=0.8, layer=pn.B_Cu)
        add_seg(netname, b_69_x, 69.0, c_r_x, c_r_y, width=0.8, layer=pn.F_Cu)

# 3. Route CW_S1 to CW_S5 (Series stages)
# Bottom Caps at Y = 126.0 mm
# Diodes at Y = 99.0 mm (bottom pads at Y = 99.0 + 13.0 = 112.0 mm)
# Bleeders Row 1 at Y = 139.0 mm
# Bleeders Row 2 at Y = 148.0 mm
for k in range(1, 6):
    netname = f"/03_multiplier/CW_S{k}"
    dx = (k - 1) * 16.0
    c_l_x, c_l_y = 141.0 + dx, 126.0
    c_r_x, c_r_y = 147.0 + dx, 126.0
    d_l_x, d_l_y = 144.0 + dx, 112.0
    d_r_x, d_r_y = 152.0 + dx, 112.0

    # Interconnects on B.Cu
    add_seg(netname, c_l_x, c_l_y, c_r_x, c_r_y, width=0.8, layer=pn.B_Cu)
    add_seg(netname, c_l_x, c_l_y, d_l_x, d_l_y, width=0.8, layer=pn.B_Cu)
    add_seg(netname, c_r_x, c_r_y, d_r_x, d_r_y, width=0.8, layer=pn.B_Cu)

    # Bleeder taps
    if k % 2 == 1:
        # Odd series stage: tap Row 1 (Y=139) to c_l, tap Row 2 (Y=148) to c_r
        b_139_x = 144.0375 + dx # R146.1
        b_148_x = 143.9625 + dx # R143.2
        add_seg(netname, b_139_x, 139.0, c_l_x, c_l_y, width=0.8, layer=pn.F_Cu)
        add_seg(netname, b_148_x, 148.0, b_148_x, 151.0, width=0.8, layer=pn.F_Cu)
        add_via(netname, b_148_x, 151.0, size=0.8, drill=0.4)
        add_seg(netname, b_148_x, 151.0, c_r_x, c_r_y, width=0.8, layer=pn.B_Cu)
    else:
        # Even series stage
        b_148_x = 160.0375 + (k - 2) * 16.0 # R150.1
        b_139_x = 159.9625 + (k - 2) * 16.0 # R147.2
        add_seg(netname, b_148_x, 148.0, b_148_x, 151.0, width=0.8, layer=pn.F_Cu)
        add_via(netname, b_148_x, 151.0, size=0.8, drill=0.4)
        add_seg(netname, b_148_x, 151.0, c_l_x, c_l_y, width=0.8, layer=pn.B_Cu)
        add_seg(netname, b_139_x, 139.0, c_r_x, c_r_y, width=0.8, layer=pn.F_Cu)

# 4. Route Net-(D20-K) (Stage 6 pump)
add_seg("Net-(D20-K)", 214.25, 76.0, 216.0, 86.0, width=0.8, layer=pn.B_Cu)
add_seg("Net-(D20-K)", 214.25, 76.0, 224.0, 76.0, width=0.8, layer=pn.B_Cu)
add_seg("Net-(D20-K)", 224.0, 76.0, 228.0, 86.0, width=0.8, layer=pn.B_Cu)
add_seg("Net-(D20-K)", 217.2125, 69.0, 224.5, 69.0, width=0.8, layer=pn.F_Cu)
add_seg("Net-(D20-K)", 224.5, 69.0, 224.5, 76.0, width=0.8, layer=pn.F_Cu)
add_seg("Net-(D20-K)", 224.5, 76.0, 214.25, 76.0, width=0.8, layer=pn.F_Cu)

# 5. Route Series Connections within each bleeder pair (12 pairs):
bleeder_pairs = [
    # Top Row 1 (Y=61.0)
    ("R140", "R141", 61.0, "Net-(R140-Pad2)"),
    ("R148", "R149", 61.0, "Net-(R148-Pad2)"),
    ("R156", "R157", 61.0, "Net-(R156-Pad2)"),
    # Top Row 2 (Y=69.0)
    ("R144", "R145", 69.0, "Net-(R144-Pad2)"),
    ("R152", "R153", 69.0, "Net-(R152-Pad2)"),
    ("R160", "R161", 69.0, "Net-(R160-Pad2)"),
    # Bottom Row 1 (Y=139.0)
    ("R146", "R147", 139.0, "Net-(R146-Pad2)"),
    ("R154", "R155", 139.0, "Net-(R154-Pad2)"),
    ("R162", "R163", 139.0, "Net-(R162-Pad2)"),
    # Bottom Row 2 (Y=148.0)
    ("R142", "R143", 148.0, "Net-(R142-Pad2)"),
    ("R150", "R151", 148.0, "Net-(R150-Pad2)"),
    ("R158", "R159", 148.0, "Net-(R158-Pad2)"),
]

for r_l, r_r, y_val, netname in bleeder_pairs:
    f_l = b.FindFootprintByReference(r_l)
    f_r = b.FindFootprintByReference(r_r)
    # Pad 2 of left is at x_l + 2.9625, Pad 1 of right is at x_r - 2.9625
    x1 = f_l.GetPosition().x/1e6 + 2.9625
    x2 = f_r.GetPosition().x/1e6 - 2.9625
    add_seg(netname, x1, y_val, x2, y_val, width=0.6, layer=pn.F_Cu)

# 6. Route /SEC_A:
# T1 secondary pins 7, 8 at (124.43, 113.75) and (124.43, 116.25)
# C100 pad 1 at (124.25, 76.0)
# R140 pad 1 at (121.2875, 61.0)
add_seg("/SEC_A", 124.43, 113.75, 124.43, 116.25, width=0.8, layer=pn.F_Cu)
add_seg("/SEC_A", 124.43, 113.75, 124.43, 118.0, width=0.8, layer=pn.F_Cu)
add_via("/SEC_A", 124.43, 118.0, size=0.8, drill=0.4)
add_seg("/SEC_A", 124.43, 118.0, 124.25, 118.0, width=0.8, layer=pn.B_Cu)
add_seg("/SEC_A", 124.25, 118.0, 124.25, 76.0, width=0.8, layer=pn.B_Cu)
add_seg("/SEC_A", 124.25, 76.0, 116.29, 76.0, width=0.8, layer=pn.F_Cu)
add_seg("/SEC_A", 116.29, 76.0, 116.29, 61.0, width=0.8, layer=pn.F_Cu)
add_seg("/SEC_A", 116.29, 61.0, 121.2875, 61.0, width=0.8, layer=pn.F_Cu)

# 7. Route Ballast Series Resistors (R29 down to R20) at X = 233.75:
xc = 233.75
ballast_ys = {
    "R29": 71.0, "R28": 78.5, "R27": 99.0, "R26": 120.0, "R25": 126.0,
    "R24": 132.0, "R23": 138.0, "R22": 144.0, "R21": 150.0, "R20": 156.0,
}
ballast_pairs = [
    ("R29", "R28", "Net-(R28-Pad2)"),
    ("R28", "R27", "Net-(R27-Pad2)"),
    ("R27", "R26", "Net-(R26-Pad2)"),
    ("R26", "R25", "Net-(R25-Pad2)"),
    ("R25", "R24", "Net-(R24-Pad2)"),
    ("R24", "R23", "Net-(R23-Pad2)"),
    ("R23", "R22", "Net-(R22-Pad2)"),
    ("R22", "R21", "Net-(R21-Pad2)"),
    ("R21", "R20", "Net-(R20-Pad2)"),
]

for r_up, r_dn, netname in ballast_pairs:
    y_up = ballast_ys[r_up]
    y_dn = ballast_ys[r_dn]
    pad1_up_y = y_up + 2.9625
    pad2_dn_y = y_dn - 2.9625
    add_seg(netname, xc, pad1_up_y, xc, pad2_dn_y, width=0.6, layer=pn.F_Cu)

# 8. Route /04_sense_safety/HV_OUT:
# Connect J60 at (xc, 63.5) to R29 pad 2 at (xc, 71.0 - 2.9625) = (xc, 68.0375) on F.Cu:
add_seg("/04_sense_safety/HV_OUT", xc, 63.5, xc, 68.0375, width=0.8, layer=pn.F_Cu)
# From J60 straight down on B.Cu to R30 via at (xc, 159.0):
add_seg("/04_sense_safety/HV_OUT", xc, 63.5, xc, 159.0, width=0.8, layer=pn.B_Cu)
add_via("/04_sense_safety/HV_OUT", xc, 159.0, size=1.2, drill=0.6)
# Connect from via to R30 pad 1 at (230.9625, 159.0) on F.Cu:
add_seg("/04_sense_safety/HV_OUT", xc, 159.0, 230.9625, 159.0, width=0.8, layer=pn.F_Cu)

# 9. Route /HV_RAW:
# D21 cathode at (228.0, 112.0)
# C111 pad 2 at (221.0, 126.0)
# R163 pad 2 at (223.9625, 139.0)
# R20 pad 1 at (xc, 158.9625)
add_seg("/HV_RAW", 228.0, 112.0, 221.0, 126.0, width=0.8, layer=pn.B_Cu)
add_seg("/HV_RAW", 221.0, 126.0, 224.0, 139.0, width=0.8, layer=pn.B_Cu)
add_via("/HV_RAW", 224.0, 139.0, size=1.2, drill=0.6)
add_seg("/HV_RAW", 224.0, 139.0, 223.9625, 139.0, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RAW", 224.0, 139.0, 228.0, 158.9625, width=0.8, layer=pn.F_Cu)
add_seg("/HV_RAW", 228.0, 158.9625, xc, 158.9625, width=0.8, layer=pn.F_Cu)

# 10. Route 1G Divider Series Resistors (R30 down to R39) at Y = 159.0 mm on F.Cu:
divider_refs = [f"R{i}" for i in range(30, 40)]
for i in range(len(divider_refs) - 1):
    r_r = divider_refs[i]
    r_l = divider_refs[i + 1]
    netname = f"Net-({r_r}-Pad2)"
    f_r = b.FindFootprintByReference(r_r)
    f_l = b.FindFootprintByReference(r_l)
    # rot = 180: pad 1 is on the RIGHT (+2.9625), pad 2 is on the LEFT (-2.9625)
    x_r_pad2 = f_r.GetPosition().x/1e6 - 2.9625
    x_l_pad1 = f_l.GetPosition().x/1e6 + 2.9625
    add_seg(netname, x_r_pad2, 159.0, x_l_pad1, 159.0, width=0.6, layer=pn.F_Cu)

b.BuildConnectivity()
pn.ZONE_FILLER(b).Fill(b.Zones())

try:
    pn.SaveBoard(str(PCB_PATH), b)
finally:
    PRO_PATH.write_text(pro_saved)

print("Applied HV multiplier, bleeders, ballast, and divider routing.")
