#!/usr/bin/env python3
"""
apply_cw_stages.py
Applies verified Cockcroft-Walton 10-stage multiplier routing, SEC_A, Net-(D20-K),
HV_RAW, and HV_OUT to pi5_corona_hv.kicad_pcb.
Preserves pi5_corona_hv.kicad_pro verbatim.
"""

import sys
import os
import pcbnew as p
import subprocess
import json

BOARD_PATH = "pi5_corona_hv.kicad_pcb"
PRO_PATH = "pi5_corona_hv.kicad_pro"
DRC_REPORT = "exports/current_drc.json"

def main():
    # 1. Backup .kicad_pro text
    with open(PRO_PATH, "r") as f:
        pro_text = f.read()

    # 2. Load board
    b = p.LoadBoard(BOARD_PATH)

    # Clean existing tracks on these target nets if any
    target_nets = [
        f"/03_multiplier/CW_P{k}" for k in range(1, 6)
    ] + [
        f"/03_multiplier/CW_S{k}" for k in range(1, 6)
    ] + [
        "/SEC_A", "Net-(D20-K)", "/HV_RAW", "/04_sense_safety/HV_OUT"
    ]

    for t in list(b.GetTracks()):
        if t.GetNetname() in target_nets:
            b.Remove(t)
            t.thisown = False

    def add_seg(netname, x1, y1, x2, y2, width=0.8, layer=p.B_Cu):
        net = b.FindNet(netname)
        if not net:
            print(f"Warning: net {netname} not found!")
            return
        t = p.PCB_TRACK(b)
        t.SetStart(p.VECTOR2I(p.FromMM(x1), p.FromMM(y1)))
        t.SetEnd(p.VECTOR2I(p.FromMM(x2), p.FromMM(y2)))
        t.SetWidth(p.FromMM(width))
        t.SetLayer(layer)
        t.SetNet(net)
        b.Add(t)

    def add_via(netname, x, y, size=0.8, drill=0.4):
        net = b.FindNet(netname)
        if not net:
            return
        v = p.PCB_VIA(b)
        v.SetPosition(p.VECTOR2I(p.FromMM(x), p.FromMM(y)))
        v.SetWidth(p.FromMM(size))
        v.SetDrill(p.FromMM(drill))
        v.SetNet(net)
        b.Add(v)

    # 3. Route CW_P1 to CW_P5 (Pump stages)
    for k in range(1, 6):
        netname = f"/03_multiplier/CW_P{k}"
        dx = (k - 1) * 16.0
        c_l_x, c_l_y = 134.25 + dx, 102.0
        c_r_x, c_r_y = 140.25 + dx, 102.0
        d_l_x, d_l_y = 136.0 + dx, 112.0
        d_r_x, d_r_y = 144.0 + dx, 112.0

        add_seg(netname, c_l_x, c_l_y, c_r_x, c_r_y, width=0.8, layer=p.B_Cu)
        add_seg(netname, c_l_x, c_l_y, d_l_x, d_l_y, width=0.8, layer=p.B_Cu)
        add_seg(netname, c_r_x, c_r_y, d_r_x, d_r_y, width=0.8, layer=p.B_Cu)

        if k % 2 == 1:
            b_95_x = 132.29 + dx
            b_87_x = 142.21 + dx
            add_seg(netname, b_95_x, 95.0, c_l_x, c_l_y, width=0.8, layer=p.F_Cu)
            add_seg(netname, b_87_x, 87.0, b_87_x, 84.5, width=0.8, layer=p.F_Cu)
            add_via(netname, b_87_x, 84.5, size=0.8, drill=0.4)
            add_seg(netname, b_87_x, 84.5, c_r_x, c_r_y, width=0.8, layer=p.B_Cu)
        else:
            b_87_x = 148.29 + (k - 2) * 16.0
            b_95_x = 158.21 + (k - 2) * 16.0
            add_seg(netname, b_87_x, 87.0, b_87_x, 84.5, width=0.8, layer=p.F_Cu)
            add_via(netname, b_87_x, 84.5, size=0.8, drill=0.4)
            add_seg(netname, b_87_x, 84.5, c_l_x, c_l_y, width=0.8, layer=p.B_Cu)
            add_seg(netname, b_95_x, 95.0, c_r_x, c_r_y, width=0.8, layer=p.F_Cu)

    # 4. Route CW_S1 to CW_S5 (Series stages)
    for k in range(1, 6):
        netname = f"/03_multiplier/CW_S{k}"
        dx = (k - 1) * 16.0
        c_l_x, c_l_y = 141.0 + dx, 156.0
        c_r_x, c_r_y = 147.0 + dx, 156.0
        d_l_x, d_l_y = 144.0 + dx, 138.0
        d_r_x, d_r_y = 152.0 + dx, 138.0

        add_seg(netname, c_l_x, c_l_y, c_r_x, c_r_y, width=0.8, layer=p.B_Cu)
        add_seg(netname, c_l_x, c_l_y, d_l_x, d_l_y, width=0.8, layer=p.B_Cu)
        add_seg(netname, c_r_x, c_r_y, d_r_x, d_r_y, width=0.8, layer=p.B_Cu)

        if k % 2 == 1:
            b_169_x = 139.04 + dx
            b_177_x = 148.96 + dx
            add_seg(netname, b_169_x, 169.0, c_l_x, c_l_y, width=0.8, layer=p.F_Cu)
            add_seg(netname, b_177_x, 177.0, b_177_x, 180.0, width=0.8, layer=p.F_Cu)
            add_via(netname, b_177_x, 180.0, size=0.8, drill=0.4)
            add_seg(netname, b_177_x, 180.0, c_r_x, c_r_y, width=0.8, layer=p.B_Cu)
        else:
            b_177_x = 155.04 + (k - 2) * 16.0
            b_169_x = 164.96 + (k - 2) * 16.0
            add_seg(netname, b_177_x, 177.0, b_177_x, 180.0, width=0.8, layer=p.F_Cu)
            add_via(netname, b_177_x, 180.0, size=0.8, drill=0.4)
            add_seg(netname, b_177_x, 180.0, c_l_x, c_l_y, width=0.8, layer=p.B_Cu)
            add_seg(netname, b_169_x, 169.0, c_r_x, c_r_y, width=0.8, layer=p.F_Cu)

    # 5. Route /SEC_A:
    add_seg("/SEC_A", 123.43, 131.25, 123.43, 128.75, width=0.8, layer=p.F_Cu)
    add_seg("/SEC_A", 123.43, 131.25, 123.43, 134.0, width=0.8, layer=p.F_Cu)
    add_via("/SEC_A", 123.43, 134.0, size=0.8, drill=0.4)
    add_seg("/SEC_A", 123.43, 134.0, 127.5, 134.0, width=0.8, layer=p.B_Cu)
    add_seg("/SEC_A", 127.5, 134.0, 127.5, 102.0, width=0.8, layer=p.B_Cu)
    add_seg("/SEC_A", 127.5, 102.0, 124.25, 102.0, width=0.8, layer=p.B_Cu)
    add_seg("/SEC_A", 124.25, 102.0, 116.29, 102.0, width=0.8, layer=p.F_Cu)
    add_seg("/SEC_A", 116.29, 102.0, 116.29, 87.0, width=0.8, layer=p.F_Cu)

    # 6. Route Net-(D20-K):
    add_seg("Net-(D20-K)", 214.25, 102.0, 216.0, 112.0, width=0.8, layer=p.B_Cu)
    add_seg("Net-(D20-K)", 214.25, 102.0, 224.0, 102.0, width=0.8, layer=p.B_Cu)
    add_seg("Net-(D20-K)", 224.0, 102.0, 228.0, 112.0, width=0.8, layer=p.B_Cu)
    add_seg("Net-(D20-K)", 222.21, 95.0, 224.5, 95.0, width=0.8, layer=p.F_Cu)
    add_seg("Net-(D20-K)", 224.5, 95.0, 224.5, 102.0, width=0.8, layer=p.F_Cu)
    add_seg("Net-(D20-K)", 224.5, 102.0, 214.25, 102.0, width=0.8, layer=p.F_Cu)

    # 7. Route /HV_RAW:
    add_seg("/HV_RAW", 221.0, 156.0, 228.0, 138.0, width=0.8, layer=p.B_Cu)
    add_seg("/HV_RAW", 228.0, 138.0, 228.9625, 169.0, width=0.6, layer=p.F_Cu)
    add_seg("/HV_RAW", 228.0, 138.0, 235.0, 138.0, width=0.6, layer=p.B_Cu)
    add_seg("/HV_RAW", 235.0, 138.0, 235.0, 98.0, width=0.6, layer=p.B_Cu)
    add_seg("/HV_RAW", 235.0, 98.0, 226.6, 91.0, width=0.6, layer=p.B_Cu)
    add_seg("/HV_RAW", 226.6, 91.0, 226.6, 75.0, width=0.6, layer=p.B_Cu)
    add_seg("/HV_RAW", 226.6, 75.0, 234.75, 68.0, width=0.6, layer=p.B_Cu)
    add_seg("/HV_RAW", 234.75, 68.0, 234.75, 63.0, width=0.6, layer=p.B_Cu)

    # 8. Route /04_sense_safety/HV_OUT:
    # R29.2 to J60.1
    add_seg("/04_sense_safety/HV_OUT", 234.75, 78.0, 233.5, 84.0, width=0.8, layer=p.F_Cu)
    # J60.1 to R30.1:
    add_seg("/04_sense_safety/HV_OUT", 233.5, 84.0, 234.75, 84.0, width=0.6, layer=p.F_Cu)
    add_seg("/04_sense_safety/HV_OUT", 234.75, 84.0, 234.75, 187.0, width=0.6, layer=p.F_Cu)
    add_seg("/04_sense_safety/HV_OUT", 234.75, 187.0, 230.9625, 187.0, width=0.6, layer=p.F_Cu)

    # 9. Route /HV_RETURN:
    # 1. T1.10 to T1.9 on F.Cu:
    add_seg("/HV_RETURN", 123.43, 118.75, 123.43, 121.25, width=0.8, layer=p.F_Cu)
    # 2. T1.9 to D10.2 on F.Cu:
    add_seg("/HV_RETURN", 123.43, 121.25, 136.0, 121.25, width=0.8, layer=p.F_Cu)
    add_seg("/HV_RETURN", 136.0, 121.25, 136.0, 138.0, width=0.8, layer=p.F_Cu)
    # 3. D10.2 to C101.1 on B.Cu:
    add_seg("/HV_RETURN", 136.0, 138.0, 131.0, 143.0, width=0.8, layer=p.B_Cu)
    add_seg("/HV_RETURN", 131.0, 143.0, 131.0, 156.0, width=0.8, layer=p.B_Cu)
    # 4. C101.1 to J61.1 on B.Cu:
    add_seg("/HV_RETURN", 131.0, 156.0, 131.0, 196.0, width=0.8, layer=p.B_Cu)
    # 5. R142.1 tap:
    add_seg("/HV_RETURN", 123.04, 177.0, 121.0, 177.0, width=0.6, layer=p.F_Cu)
    add_via("/HV_RETURN", 121.0, 177.0)
    add_seg("/HV_RETURN", 121.0, 177.0, 121.0, 185.0, width=0.6, layer=p.B_Cu)
    add_seg("/HV_RETURN", 121.0, 185.0, 131.0, 185.0, width=0.6, layer=p.B_Cu)
    # 6. Bottom trunk from J61.1 on B.Cu:
    add_seg("/HV_RETURN", 131.0, 196.0, 131.0, 196.8, width=0.8, layer=p.B_Cu)
    add_seg("/HV_RETURN", 131.0, 196.8, 94.0, 196.8, width=0.8, layer=p.B_Cu)
    # R91.1 tap at (92.75, 180.0):
    add_seg("/HV_RETURN", 94.0, 196.8, 94.0, 180.0, width=0.6, layer=p.B_Cu)
    add_via("/HV_RETURN", 94.0, 180.0)
    add_seg("/HV_RETURN", 94.0, 180.0, 92.75, 180.0, width=0.6, layer=p.F_Cu)
    # R90.1 tap at (102.54, 192.0):
    add_seg("/HV_RETURN", 102.54, 196.8, 102.54, 193.5, width=0.6, layer=p.B_Cu)
    add_via("/HV_RETURN", 102.54, 193.5)
    add_seg("/HV_RETURN", 102.54, 193.5, 102.54, 192.0, width=0.6, layer=p.F_Cu)
    # D5.1 to R90.1 on F.Cu:
    add_seg("/HV_RETURN", 104.0, 183.15, 104.0, 192.0, width=0.6, layer=p.F_Cu)
    add_seg("/HV_RETURN", 104.0, 192.0, 102.54, 192.0, width=0.6, layer=p.F_Cu)

    # 10. Refill zones
    filler = p.ZONE_FILLER(b)
    filler.Fill(b.Zones())

    # 11. Save board and restore .kicad_pro
    b.BuildConnectivity()
    p.SaveBoard(BOARD_PATH, b)
    with open(PRO_PATH, "w") as f:
        f.write(pro_text)
    print("Successfully saved board and restored .kicad_pro.")

    # 10. Run DRC
    res = subprocess.run([
        "kicad-cli", "pcb", "drc",
        "--format", "json",
        "-o", DRC_REPORT,
        BOARD_PATH
    ], capture_output=True, text=True)

    d = json.load(open(DRC_REPORT))
    clearance_v = [v for v in d.get("violations", []) if v["type"] == "clearance"]
    other_v = [v for v in d.get("violations", []) if v["type"] not in ["clearance", "lib_footprint_issues"]]
    unc = d.get("unconnected_items", [])

    print(f"DRC Clearance Violations: {len(clearance_v)}")
    print(f"DRC Other Violations:     {len(other_v)}")
    print(f"Unconnected Items:        {len(unc)}")
    for v in clearance_v:
        print("  Clearance:", v.get("description"))
    for v in other_v:
        print("  Other:", v.get("type"), v.get("description"))

if __name__ == "__main__":
    main()
