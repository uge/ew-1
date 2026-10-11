#!/usr/bin/env python3
"""
test_astar_router.py
Tests the 2-layer A* grid router on a single net.
"""

from pathlib import Path
import math
import heapq
import numpy as np
import pcbnew
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
trial = ROOT / "layout/routing-trials"
pcb_in = trial / "test_rip_reroute.kicad_pcb"

b = pcbnew.LoadBoard(str(pcb_in))

# Grid parameters
X_MIN, X_MAX = 65.0, 132.0
Y_MIN, Y_MAX = 50.0, 196.0
STEP = 0.1  # 0.1 mm per cell

NX = int(math.ceil((X_MAX - X_MIN) / STEP))
NY = int(math.ceil((Y_MAX - Y_MIN) / STEP))

print(f"Grid size: {NX} x {NY} x 2 layers ({NX*NY*2} cells)")

def to_grid(x, y):
    gx = int(round((x - X_MIN) / STEP))
    gy = int(round((y - Y_MIN) / STEP))
    return max(0, min(NX - 1, gx)), max(0, min(NY - 1, gy))

def to_coord(gx, gy):
    return X_MIN + gx * STEP, Y_MIN + gy * STEP

# Build obstacle map
# 0: F.Cu, 1: B.Cu
occupied = np.zeros((2, NX, NY), dtype=bool)

def mark_rect(layer, x1, y1, x2, y2):
    gx1, gy1 = to_grid(min(x1, x2), min(y1, y2))
    gx2, gy2 = to_grid(max(x1, x2), max(y1, y2))
    occupied[layer, gx1:gx2+1, gy1:gy2+1] = True

def mark_circle(layer, x, y, radius):
    r_cells = int(math.ceil(radius / STEP))
    gx, gy = to_grid(x, y)
    for dx in range(-r_cells, r_cells + 1):
        for dy in range(-r_cells, r_cells + 1):
            if dx*dx + dy*dy <= (radius/STEP)**2:
                cx, cy = gx + dx, gy + dy
                if 0 <= cx < NX and 0 <= cy < NY:
                    occupied[layer, cx, cy] = True

def mark_segment(layer, x1, y1, x2, y2, radius):
    # Capsule around segment
    length = math.hypot(x2 - x1, y2 - y1)
    steps = max(1, int(math.ceil(length / (STEP * 0.5))))
    for i in range(steps + 1):
        t = i / steps
        px = x1 + t * (x2 - x1)
        py = y1 + t * (y2 - y1)
        mark_circle(layer, px, py, radius)

target_net = "/01_power_mcu/V18"
print(f"Populating obstacles for target net {target_net}...")

# 1. Pads
for fp in b.GetFootprints():
    for p in fp.Pads():
        pnet = p.GetNetname()
        if pnet == target_net:
            continue
        pos = p.GetPosition()
        px, py = pos.x / 1e6, pos.y / 1e6
        size = p.GetSize()
        sx, sy = size.x / 1e6, size.y / 1e6
        
        # Clearance depends on net
        clr = 0.20
        if any(h in pnet for h in ["CW_", "HV_", "SEC_"]):
            clr = 4.0
        
        # Check layer
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
    
    clr = 0.20
    if any(h in tnet for h in ["CW_", "HV_", "SEC_"]):
        clr = 4.0
    
    if isinstance(t, pcbnew.PCB_VIA):
        pos = t.GetPosition()
        vx, vy = pos.x / 1e6, pos.y / 1e6
        vr = (t.GetWidth() / 1e6) / 2 + clr
        mark_circle(0, vx, vy, vr)
        mark_circle(1, vx, vy, vr)
    else:
        s = t.GetStart()
        e = t.GetEnd()
        sx, sy = s.x / 1e6, s.y / 1e6
        ex, ey = e.x / 1e6, e.y / 1e6
        tr = (t.GetWidth() / 1e6) / 2 + clr
        tl = 0 if t.GetLayer() == pcbnew.F_Cu else 1
        mark_segment(tl, sx, sy, ex, ey, tr)

print("Obstacle map built.")

# Find start and goal for target_net
pads = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname() == target_net:
            pos = p.GetPosition()
            pads.append((fp.GetReference(), p.GetNumber(), pos.x/1e6, pos.y/1e6))

print("Target pads:", pads)
# V18 connects U7.12 at (80.75, 70.037) and C18.1 at (76.225, 71.0)
start_pos = (80.75, 70.037)
goal_pos = (76.225, 71.0)

start_gx, start_gy = to_grid(*start_pos)
goal_gx, goal_gy = to_grid(*goal_pos)

print(f"Start: {start_pos} -> grid ({start_gx}, {start_gy})")
print(f"Goal:  {goal_pos} -> grid ({goal_gx}, {goal_gy})")

# A* search
def astar(start_layer, sx, sy, goal_layer, gx, gy):
    # pq: (f_score, cost, layer, x, y)
    pq = []
    dist = {}
    parent = {}
    
    start_node = (start_layer, sx, sy)
    dist[start_node] = 0.0
    h0 = math.hypot(sx - gx, sy - gy) + (0 if start_layer == goal_layer else 5.0)
    heapq.heappush(pq, (h0, 0.0, start_layer, sx, sy))
    
    VIA_RAD_CELLS = int(math.ceil((0.3 + 0.2) / STEP))  # 0.5mm
    
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
    
    iterations = 0
    while pq:
        iterations += 1
        f, c, layer, x, y = heapq.heappop(pq)
        
        if (layer, x, y) == (goal_layer, gx, gy) or (math.hypot(x - gx, y - gy) <= 1 and layer == goal_layer):
            print(f"Found path in {iterations} iterations, cost = {c:.2f}")
            # Reconstruct
            path = [(layer, x, y)]
            curr = (layer, x, y)
            while curr in parent:
                curr = parent[curr]
                path.append(curr)
            path.reverse()
            return path
        
        if c > dist.get((layer, x, y), float('inf')):
            continue
        
        # 1. Same layer neighbors
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < NX and 0 <= ny < NY:
                if occupied[layer, nx, ny] and (nx, ny) != (gx, gy) and (nx, ny) != (sx, sy):
                    continue
                step_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
                nc = c + step_cost
                next_node = (layer, nx, ny)
                if nc < dist.get(next_node, float('inf')):
                    dist[next_node] = nc
                    parent[next_node] = (layer, x, y)
                    h = math.hypot(nx - gx, ny - gy) + (0 if layer == goal_layer else 5.0)
                    heapq.heappush(pq, (nc + h, nc, layer, nx, ny))
        
        # 2. Via transition (layer swap)
        other_layer = 1 - layer
        next_node = (other_layer, x, y)
        if can_place_via(x, y):
            nc = c + 8.0  # via penalty
            if nc < dist.get(next_node, float('inf')):
                dist[next_node] = nc
                parent[next_node] = (layer, x, y)
                h = math.hypot(x - gx, y - gy) + (0 if other_layer == goal_layer else 5.0)
                heapq.heappush(pq, (nc + h, nc, other_layer, x, y))
                
    print(f"No path found after {iterations} iterations")
    return None

path = astar(0, start_gx, start_gy, 0, goal_gx, goal_gy)
if path:
    print(f"Path length: {len(path)} points")
    # Simplify path
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
    print(f"Simplified to {len(simplified)} points:")
    for l, gx, gy in simplified:
        layer_name = "F.Cu" if l == 0 else "B.Cu"
        x, y = to_coord(gx, gy)
        print(f"  {layer_name}: ({x:.2f}, {y:.2f})")
