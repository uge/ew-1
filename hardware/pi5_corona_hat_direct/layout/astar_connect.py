#!/usr/bin/env python3
"""
astar_connect.py
Routes a net from a start point (or disconnected sub-tree) to the rest of the net
using 2-layer grid search (A*/Dijkstra).
"""

import math
import heapq
import numpy as np
import pcbnew
from pathlib import Path

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

def route_net_connection(board_path, target_net, start_pt, start_layer=0, goal_pts=None, goal_layer=None):
    b = pcbnew.LoadBoard(str(board_path))
    
    # Bounding box around relevant region
    # Low-voltage control area is roughly [65, 125] x [50, 195]
    X_MIN, X_MAX = 65.0, 125.0
    Y_MIN, Y_MAX = 50.0, 195.0
    STEP = 0.1  # 0.1 mm
    
    NX = int(math.ceil((X_MAX - X_MIN) / STEP))
    NY = int(math.ceil((Y_MAX - Y_MIN) / STEP))
    
    def to_grid(x, y):
        gx = int(round((x - X_MIN) / STEP))
        gy = int(round((y - Y_MIN) / STEP))
        return max(0, min(NX - 1, gx)), max(0, min(NY - 1, gy))
    
    def to_coord(gx, gy):
        return X_MIN + gx * STEP, Y_MIN + gy * STEP
    
    occupied = np.zeros((2, NX, NY), dtype=bool)
    
    def mark_circle(layer, x, y, radius):
        r_cells = int(math.ceil(radius / STEP))
        gx, gy = to_grid(x, y)
        for dx in range(-r_cells, r_cells + 1):
            for dy in range(-r_cells, r_cells + 1):
                if dx*dx + dy*dy <= (radius/STEP)**2:
                    cx, cy = gx + dx, gy + dy
                    if 0 <= cx < NX and 0 <= cy < NY:
                        occupied[layer, cx, cy] = True
                        
    def mark_rect(layer, x1, y1, x2, y2):
        gx1, gy1 = to_grid(min(x1, x2), min(y1, y2))
        gx2, gy2 = to_grid(max(x1, x2), max(y1, y2))
        occupied[layer, gx1:gx2+1, gy1:gy2+1] = True
        
    def mark_segment(layer, x1, y1, x2, y2, radius):
        length = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, int(math.ceil(length / (STEP * 0.5))))
        for i in range(steps + 1):
            t = i / steps
            px = x1 + t * (x2 - x1)
            py = y1 + t * (y2 - y1)
            mark_circle(layer, px, py, radius)
            
    print(f"Building obstacle map for {target_net}...")
    # 1. Pads
    for p in b.GetPads():
        pnet = p.GetNetname()
        if pnet == target_net:
            continue
        pos = p.GetPosition()
        px, py = pos.x / 1e6, pos.y / 1e6
        sz = p.GetSize()
        sx, sy = sz.x / 1e6, sz.y / 1e6
        clr = 4.0 if is_hv_net(pnet) else 0.20
        pl = p.GetLayerSet()
        if pl.Contains(pcbnew.F_Cu):
            mark_rect(0, px - sx/2 - clr, py - sy/2 - clr, px + sx/2 + clr, py + sy/2 + clr)
        if pl.Contains(pcbnew.B_Cu):
            mark_rect(1, px - sx/2 - clr, py - sy/2 - clr, px + sx/2 + clr, py + sy/2 + clr)
            
    # 2. Tracks & Vias
    for t in b.GetTracks():
        tnet = t.GetNetname()
        if tnet == target_net:
            continue
        clr = 4.0 if is_hv_net(tnet) else 0.20
        if isinstance(t, pcbnew.PCB_VIA):
            pos = t.GetPosition()
            vx, vy = pos.x / 1e6, pos.y / 1e6
            vr = (t.GetWidth() / 1e6) / 2 + clr
            mark_circle(0, vx, vy, vr)
            mark_circle(1, vx, vy, vr)
        else:
            s, e = t.GetStart(), t.GetEnd()
            sx, sy = s.x / 1e6, s.y / 1e6
            ex, ey = e.x / 1e6, e.y / 1e6
            tr = (t.GetWidth() / 1e6) / 2 + clr
            tl = 0 if t.GetLayer() == pcbnew.F_Cu else 1
            mark_segment(tl, sx, sy, ex, ey, tr)
            
    # Target goals
    # If goal_pts not specified, collect all existing tracks/pads of target_net except start component
    is_goal = np.zeros((2, NX, NY), dtype=bool)
    if goal_pts:
        for gl, gx_coord, gy_coord in goal_pts:
            gx, gy = to_grid(gx_coord, gy_coord)
            is_goal[gl, gx, gy] = True
    else:
        # Auto-detect target net pads/tracks not connected to start_pt
        for p in b.GetPads():
            if p.GetNetname() == target_net:
                pos = p.GetPosition()
                px, py = pos.x / 1e6, pos.y / 1e6
                if math.hypot(px - start_pt[0], py - start_pt[1]) > 2.0:
                    gx, gy = to_grid(px, py)
                    pl = p.GetLayerSet()
                    if pl.Contains(pcbnew.F_Cu): is_goal[0, gx, gy] = True
                    if pl.Contains(pcbnew.B_Cu): is_goal[1, gx, gy] = True
        for t in b.GetTracks():
            if t.GetNetname() == target_net:
                s, e = t.GetStart(), t.GetEnd()
                sx, sy = s.x / 1e6, s.y / 1e6
                ex, ey = e.x / 1e6, e.y / 1e6
                if math.hypot(sx - start_pt[0], sy - start_pt[1]) > 2.0 and math.hypot(ex - start_pt[0], ey - start_pt[1]) > 2.0:
                    tl = 0 if (isinstance(t, pcbnew.PCB_VIA) or t.GetLayer() == pcbnew.F_Cu) else 1
                    gx1, gy1 = to_grid(sx, sy)
                    gx2, gy2 = to_grid(ex, ey)
                    # mark line in is_goal
                    steps = max(1, int(math.hypot(gx2 - gx1, gy2 - gy1)))
                    for step in range(steps + 1):
                        cur_gx = int(round(gx1 + step/steps * (gx2 - gx1)))
                        cur_gy = int(round(gy1 + step/steps * (gy2 - gy1)))
                        is_goal[tl, cur_gx, cur_gy] = True
                        if isinstance(t, pcbnew.PCB_VIA):
                            is_goal[1, cur_gx, cur_gy] = True
                            
    VIA_RAD_CELLS = int(math.ceil((0.30 + 0.20) / STEP))  # 0.5mm
    def can_place_via(x, y):
        for dx in range(-VIA_RAD_CELLS, VIA_RAD_CELLS + 1):
            for dy in range(-VIA_RAD_CELLS, VIA_RAD_CELLS + 1):
                if dx*dx + dy*dy <= VIA_RAD_CELLS**2:
                    cx, cy = x + dx, y + dy
                    if not (0 <= cx < NX and 0 <= cy < NY):
                        return False
                    if occupied[0, cx, cy] or occupied[1, cx, cy]:
                        return False
        return True
        
    start_gx, start_gy = to_grid(start_pt[0], start_pt[1])
    pq = []
    dist = {}
    parent = {}
    
    start_node = (start_layer, start_gx, start_gy)
    dist[start_node] = 0.0
    heapq.heappush(pq, (0.0, 0.0, start_layer, start_gx, start_gy))
    
    found_node = None
    iterations = 0
    while pq:
        iterations += 1
        f, c, layer, x, y = heapq.heappop(pq)
        
        if is_goal[layer, x, y]:
            found_node = (layer, x, y)
            print(f"Goal reached at {layer}, grid ({x}, {y}) after {iterations} iterations, cost {c:.2f}")
            break
            
        if iterations > 300000:
            print("Iteration limit reached")
            break
            
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < NX and 0 <= ny < NY:
                if occupied[layer, nx, ny] and not is_goal[layer, nx, ny]:
                    continue
                step_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
                nc = c + step_cost
                next_node = (layer, nx, ny)
                if nc < dist.get(next_node, float('inf')):
                    dist[next_node] = nc
                    parent[next_node] = (layer, x, y)
                    heapq.heappush(pq, (nc, nc, layer, nx, ny))
                    
        # Via transition
        other_layer = 1 - layer
        next_node = (other_layer, x, y)
        if can_place_via(x, y):
            nc = c + 15.0  # via penalty
            if nc < dist.get(next_node, float('inf')):
                dist[next_node] = nc
                parent[next_node] = (layer, x, y)
                heapq.heappush(pq, (nc, nc, other_layer, x, y))
                
    if not found_node:
        print("No route found!")
        return None
        
    path = [found_node]
    curr = found_node
    while curr in parent:
        curr = parent[curr]
        path.append(curr)
    path.reverse()
    
    # Simplify path into straight segments
    simplified = [path[0]]
    for i in range(1, len(path) - 1):
        prev_l, prev_x, prev_y = simplified[-1]
        curr_l, curr_x, curr_y = path[i]
        next_l, next_x, next_y = path[i+1]
        if curr_l != prev_l or curr_l != next_l:
            simplified.append((curr_l, curr_x, curr_y))
            continue
        d1x, d1y = curr_x - prev_x, curr_y - prev_y
        d2x, d2y = next_x - curr_x, next_y - curr_y
        if (d1x, d1y) != (d2x, d2y):
            simplified.append((curr_l, curr_x, curr_y))
    simplified.append(path[-1])
    
    print(f"Path has {len(simplified)} waypoints:")
    waypoint_coords = []
    for l, gx, gy in simplified:
        layer_name = "F.Cu" if l == 0 else "B.Cu"
        x, y = to_coord(gx, gy)
        print(f"  {layer_name}: ({x:.2f}, {y:.2f})")
        waypoint_coords.append((layer_name, x, y))
        
    return waypoint_coords

if __name__ == "__main__":
    import sys
    board = "layout/routing-trials/test_rip_reroute.kicad_pcb"
    net = sys.argv[1] if len(sys.argv) > 1 else "/02_drive_transformer/DRV_B"
    sx = float(sys.argv[2]) if len(sys.argv) > 2 else 92.4
    sy = float(sys.argv[3]) if len(sys.argv) > 3 else 138.7
    sl = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    route_net_connection(board, net, (sx, sy), sl)
