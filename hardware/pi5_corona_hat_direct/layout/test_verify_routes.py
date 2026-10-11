#!/usr/bin/env python3
import math
import pcbnew

b = pcbnew.LoadBoard("layout/routing-trials/test_u6_unloop.kicad_pcb")

HV_EXACT_NETS = {
    "/04_sense_safety/HV_OUT", "/HV_RAW", "/SEC_A", "Net-(D20-K)"
}

def is_hv_net(netname):
    if netname in HV_EXACT_NETS:
        return True
    if "CW_P" in netname or "CW_S" in netname:
        return True
    if netname.startswith("Net-(R2") or netname.startswith("Net-(R3") or netname.startswith("Net-(R14") or netname.startswith("Net-(R15") or netname.startswith("Net-(R16"):
        return True
    return False

def get_req_clr(n1, n2, default_clr=0.20):
    if n1 == "/04_sense_safety/HV_OUT" or n1 == "/HV_RAW":
        return 4.0 if (n2 == "/04_sense_safety/HV_OUT" or n2 == "/HV_RAW") else 10.0
    if n2 == "/04_sense_safety/HV_OUT" or n2 == "/HV_RAW":
        return 4.0 if (n1 == "/04_sense_safety/HV_OUT" or n1 == "/HV_RAW") else 10.0
    if is_hv_net(n1) or is_hv_net(n2):
        return 4.0
    return default_clr

def dist_point_to_seg(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx*dx + dy*dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1)*dx + (py - y1)*dy) / L2))
    projx = x1 + t * dx
    projy = y1 + t * dy
    return math.hypot(px - projx, py - projy)

def dist_seg_to_seg(x1, y1, x2, y2, x3, y3, x4, y4):
    d1 = dist_point_to_seg(x1, y1, x3, y3, x4, y4)
    d2 = dist_point_to_seg(x2, y2, x3, y3, x4, y4)
    d3 = dist_point_to_seg(x3, y3, x1, y1, x2, y2)
    d4 = dist_point_to_seg(x4, y4, x1, y1, x2, y2)
    return min(d1, d2, d3, d4)

def dist_point_to_rect(px, py, rx, ry, sx, sy):
    # rx, ry is center of rect, sx, sy is full width/height
    half_x = sx / 2.0
    half_y = sy / 2.0
    dx = max(0.0, abs(px - rx) - half_x)
    dy = max(0.0, abs(py - ry) - half_y)
    return math.hypot(dx, dy)

def dist_seg_to_rect(x1, y1, x2, y2, rx, ry, sx, sy):
    # Sample along segment
    steps = max(2, int(math.ceil(math.hypot(x2 - x1, y2 - y1) / 0.05)))
    min_d = float('inf')
    for i in range(steps + 1):
        t = i / steps
        px = x1 + t * (x2 - x1)
        py = y1 + t * (y2 - y1)
        d = dist_point_to_rect(px, py, rx, ry, sx, sy)
        if d < min_d:
            min_d = d
    return min_d

def check_segment(layer_name, x1, y1, x2, y2, net_name, trace_w=0.20, min_clr=0.20):
    layer_num = pcbnew.F_Cu if layer_name == "F.Cu" else pcbnew.B_Cu
    collisions = []
    
    # 1. Pads
    for pad in b.GetPads():
        if pad.GetNetname() == net_name:
            continue
        if not pad.GetLayerSet().Contains(layer_num):
            continue
        bb = pad.GetBoundingBox()
        px = bb.GetCenter().x / 1e6
        py = bb.GetCenter().y / 1e6
        sx = bb.GetWidth() / 1e6
        sy = bb.GetHeight() / 1e6
        req_clr = get_req_clr(net_name, pad.GetNetname(), min_clr)
        d = dist_seg_to_rect(x1, y1, x2, y2, px, py, sx, sy)
        thresh = trace_w/2 + req_clr
        if d < thresh:
            ref = pad.GetParentFootprint().GetReference() if pad.GetParentFootprint() else "?"
            collisions.append(f"PAD {ref}.{pad.GetNumber()} ({pad.GetNetname()}) at ({px:.2f}, {py:.2f}) d={d:.3f} < {thresh:.3f}")
            
    # 2. Tracks & Vias
    for trk in b.GetTracks():
        if trk.GetNetname() == net_name:
            continue
        req_clr = get_req_clr(net_name, trk.GetNetname(), min_clr)
        if isinstance(trk, pcbnew.PCB_VIA):
            # Via exists on all layers
            pos = trk.GetPosition()
            vx, vy = pos.x / 1e6, pos.y / 1e6
            via_r = 0.30  # standard via diameter 0.6mm -> radius 0.3mm
            d = dist_point_to_seg(vx, vy, x1, y1, x2, y2)
            thresh = via_r + trace_w/2 + req_clr
            if d < thresh:
                collisions.append(f"VIA ({trk.GetNetname()}) at ({vx:.2f}, {vy:.2f}) d={d:.3f} < {thresh:.3f}")
        else:
            if trk.GetLayer() != layer_num:
                continue
            s = trk.GetStart()
            e = trk.GetEnd()
            sx, sy = s.x / 1e6, s.y / 1e6
            ex, ey = e.x / 1e6, e.y / 1e6
            trk_w = trk.GetWidth() / 1e6
            d = dist_seg_to_seg(x1, y1, x2, y2, sx, sy, ex, ey)
            thresh = trk_w/2 + trace_w/2 + req_clr
            if d < thresh:
                collisions.append(f"TRACK {layer_name} ({trk.GetNetname()}) [({sx:.2f},{sy:.2f})-({ex:.2f},{ey:.2f})] d={d:.3f} < {thresh:.3f}")
                
    return collisions

def check_via(x, y, net_name, via_dia=0.60, min_clr=0.20):
    via_r = via_dia / 2
    collisions = []
    # Check pads on F.Cu and B.Cu
    for pad in b.GetPads():
        if pad.GetNetname() == net_name:
            continue
        bb = pad.GetBoundingBox()
        px = bb.GetCenter().x / 1e6
        py = bb.GetCenter().y / 1e6
        sx = bb.GetWidth() / 1e6
        sy = bb.GetHeight() / 1e6
        req_clr = get_req_clr(net_name, pad.GetNetname(), min_clr)
        d = dist_point_to_rect(x, y, px, py, sx, sy)
        thresh = via_r + req_clr
        if d < thresh:
            ref = pad.GetParentFootprint().GetReference() if pad.GetParentFootprint() else "?"
            collisions.append(f"PAD {ref}.{pad.GetNumber()} ({pad.GetNetname()}) at ({px:.2f}, {py:.2f}) d={d:.3f} < {thresh:.3f}")
            
    # Check tracks and vias
    for trk in b.GetTracks():
        if trk.GetNetname() == net_name:
            continue
        req_clr = get_req_clr(net_name, trk.GetNetname(), min_clr)
        if isinstance(trk, pcbnew.PCB_VIA):
            pos = trk.GetPosition()
            vx, vy = pos.x / 1e6, pos.y / 1e6
            other_r = 0.30
            d = math.hypot(vx - x, vy - y)
            thresh = other_r + via_r + req_clr
            if d < thresh:
                collisions.append(f"VIA ({trk.GetNetname()}) at ({vx:.2f}, {vy:.2f}) d={d:.3f} < {thresh:.3f}")
        else:
            s = trk.GetStart()
            e = trk.GetEnd()
            sx, sy = s.x / 1e6, s.y / 1e6
            ex, ey = e.x / 1e6, e.y / 1e6
            trk_w = trk.GetWidth() / 1e6
            d = dist_point_to_seg(x, y, sx, sy, ex, ey)
            thresh = trk_w/2 + via_r + req_clr
            if d < thresh:
                layer_name = "F.Cu" if trk.GetLayer() == pcbnew.F_Cu else "B.Cu"
                collisions.append(f"TRACK {layer_name} ({trk.GetNetname()}) [({sx:.2f},{sy:.2f})-({ex:.2f},{ey:.2f})] d={d:.3f} < {thresh:.3f}")
                
    return collisions

print("Loaded checker module successfully.")
