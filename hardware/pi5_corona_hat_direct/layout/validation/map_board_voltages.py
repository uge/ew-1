#!/usr/bin/env python3
"""
map_board_voltages.py - PCB Voltage Mapping & Insulation Geometry Screening

Performs spatial voltage mapping, all-net voltage differential proximity analysis,
electric field screening (V/mm), and project clearance screening
across the Raspberry Pi 5 Corona Supply / Ionic Thrust HV PCB.

Uses native KiCad 10 copper polygons, in-memory zone refill and actual board
outlines. Reports conservative geometry screening; does not certify insulation,
creepage, material withstand or safety. Run with /usr/bin/python3 (pcbnew).
"""

import os
import sys
import re
import math
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from scipy.interpolate import griddata

# Headless matplotlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap

# ==============================================================================
# 1. Electrical Model: Net Operating Voltage Table
# ==============================================================================

def get_net_voltage(net_name: str, worst_case_open_circuit: bool = True) -> float:
    """
    Returns the maximum expected operating voltage (in Volts) for a given net.
    
    If worst_case_open_circuit is True (default), ballast resistors are evaluated
    at 15 kV open-circuit (prior to corona discharge ignition), representing the
    most severe arcing condition.
    """
    if not net_name:
        return 0.0

    # 15 kV Maximum HV Rails
    if net_name in ["/HV_RAW", "/04_sense_safety/HV_OUT", "Net-(D20-K)"]:
        return 15000.0

    # Cockcroft-Walton Multiplier Series & Pump Nodes
    if "CW_S5" in net_name or "CW_P5" in net_name:
        return 12500.0
    if "CW_S4" in net_name or "CW_P4" in net_name:
        return 10000.0
    if "CW_S3" in net_name or "CW_P3" in net_name:
        return 7500.0
    if "CW_S2" in net_name or "CW_P2" in net_name:
        return 5000.0
    if "CW_S1" in net_name or "CW_P1" in net_name:
        return 2500.0
    if "SEC_A" in net_name:
        return 2500.0

    # Ballast Resistor String (R20 - R29)
    if "Net-(R2" in net_name:
        if worst_case_open_circuit:
            return 15000.0
        else:
            ballast_loaded = {
                "Net-(R20-Pad2)": 13500.0,
                "Net-(R21-Pad2)": 12000.0,
                "Net-(R22-Pad2)": 10500.0,
                "Net-(R23-Pad2)": 9000.0,
                "Net-(R24-Pad2)": 7500.0,
                "Net-(R25-Pad2)": 6000.0,
                "Net-(R26-Pad2)": 4500.0,
                "Net-(R27-Pad2)": 3000.0,
                "Net-(R28-Pad2)": 1500.0,
            }
            return ballast_loaded.get(net_name, 15000.0)

    # 1 GΩ High-Voltage Sense Divider (R30 - R39)
    divider_map = {
        "Net-(R30-Pad2)": 13500.0,
        "Net-(R31-Pad2)": 12000.0,
        "Net-(R32-Pad2)": 10500.0,
        "Net-(R33-Pad2)": 9000.0,
        "Net-(R34-Pad2)": 7500.0,
        "Net-(R35-Pad2)": 6000.0,
        "Net-(R36-Pad2)": 4500.0,
        "Net-(R37-Pad2)": 3000.0,
        "Net-(R38-Pad2)": 1500.0,
        "/04_sense_safety/HV_SENSE_RAW": 1.5,
    }
    if net_name in divider_map:
        return divider_map[net_name]

    # Multiplier Inter-Stage Bleeder Resistor Midpoints
    bleeder_map = {
        "Net-(R140-Pad2)": 3750.0,
        "Net-(R144-Pad2)": 6250.0,
        "Net-(R148-Pad2)": 8750.0,
        "Net-(R152-Pad2)": 11250.0,
        "Net-(R156-Pad2)": 13750.0,
        "Net-(R160-Pad2)": 14500.0,
        "Net-(R142-Pad2)": 1250.0,
        "Net-(R146-Pad2)": 3750.0,
        "Net-(R150-Pad2)": 6250.0,
        "Net-(R154-Pad2)": 8750.0,
        "Net-(R158-Pad2)": 11250.0,
        "Net-(R162-Pad2)": 13750.0,
    }
    if net_name in bleeder_map:
        return bleeder_map[net_name]

    # 24 V Drive & Switching Domain
    if any(k in net_name for k in ["HV_BRIDGE", "DRV_A", "DRV_B", "PRI_A", "DRV_VCP", "DRV_CPH", "DRV_CPL", "GATE"]):
        return 24.0

    # 20 V USB Power Delivery (PD) Domain
    if any(k in net_name for k in ["VBUS", "VIN_PD", "VIN_PROTECTED"]):
        return 20.0

    # 5 V / 3.3 V Logic, Relays, I2C, Telemetry
    if any(k in net_name for k in [
        "3V3", "V5V", "COIL_3V", "LID_", "RELAY", "BULK_", "INTERLOCK",
        "DRV_IN", "DRV_n", "SCL", "SDA", "ADC", "Net-(C63", "Net-(R8-",
        "Net-(U4-", "/01_power_mcu", "/02_drive_transformer/DRV_I", "/DRV_SLEEP_CMD"
    ]):
        return 3.3

    # Ground & Zero-Volt Shunt Returns
    if net_name in ["GND", "/HV_RETURN"] or "unconnected" in net_name:
        return 0.0

    return 0.0


# ==============================================================================
# 2. PCB Geometry Parser: Tracks, Vias, Pads, Zones, Edge.Cuts
# ==============================================================================

def polygon_geometry(polyset):
    """Convert native KiCad polygons, retaining all contours and holes (mm)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    def ring(chain):
        return [(chain.CPoint(i).x / 1e6, chain.CPoint(i).y / 1e6)
                for i in range(chain.PointCount())]
    parts = [Polygon(ring(polyset.COutline(i)),
                     [ring(polyset.CHole(i, j)) for j in range(polyset.HoleCount(i))])
             for i in range(polyset.OutlineCount())]
    # KiCad fractured zone outlines can contain touching hole bridges.
    # make_valid retains their area rather than silently dropping a contour.
    from shapely.validation import make_valid
    return unary_union([make_valid(p) for p in parts])


def voltage_bounds(net, worst_case=True):
    """Conservative independent phase envelopes; not a transient circuit solver."""
    v = get_net_voltage(net, worst_case)
    if net == '/SEC_A':
        return (-1250., 1250.)
    if 'CW_P' in net:
        stage = int(net.split('CW_P')[1][0])
        return ((stage - 1) * 2500., stage * 2500.)
    if net == 'Net-(D20-K)':
        return (12500., 15000.)
    # First pump bleeder bridges SEC_A and CW_P1. Other pump midpoint
    # envelopes span the independently bounded capacitor terminals.
    if net == 'Net-(R140-Pad2)':
        return (-625., 1875.)
    for stage, ref in enumerate([144, 148, 152, 156, 160], 2):
        if net == f'Net-(R{ref}-Pad2)':
            return ((stage - 1.5) * 2500., (stage - .5) * 2500.)
    if net == '/04_sense_safety/HV_SENSE_RAW':
        return (0., 15000. * 164e3 / (1e9 + 164e3))
    return (min(0., v), v) if v <= 50 else (v, v)


def voltage_difference(a, b):
    return max(abs(a[0] - b[1]), abs(a[1] - b[0]))


# ==============================================================================
# 3. Functional Board Regions
# ==============================================================================

REGIONS = [
    {
        "id": "R1_PI5_TABS",
        "name": "Pi 5 Interface & Break-off Tabs",
        "bbox": (15.0, 50.0, 58.0, 138.0),
        "desc": "Raspberry Pi 5 40-pin GPIO header, Type-C PD, Qwiic I2C, S3-S6 interlock switches, TSL2591 optical sensor"
    },
    {
        "id": "R2_POWER_COND",
        "name": "Power Conditioning & eFuse",
        "bbox": (55.0, 51.0, 115.0, 110.0),
        "desc": "TPS25947 eFuse protection, 3.3V LDO, USB-PD controller, power switching"
    },
    {
        "id": "R3_BRIDGE_DRV",
        "name": "Full-Bridge Driver & Relay",
        "bbox": (55.0, 110.0, 115.0, 155.0),
        "desc": "DRV8434S/DRV8874 H-bridge MOSFET driver, G6K safety relay K1, coil regulation"
    },
    {
        "id": "R4_TANK_XFRM",
        "name": "Resonant Tank & Transformer T1",
        "bbox": (115.0, 75.0, 140.0, 135.0),
        "desc": "Resonant capacitor C11, Coilcraft step-up transformer T1 (primary 24V, secondary 2.5kV AC)"
    },
    {
        "id": "R5_CW_MULT",
        "name": "Cockcroft-Walton Multiplier (1-6)",
        "bbox": (140.0, 52.0, 230.0, 155.0),
        "desc": "6-stage CW cascade (C100-C111, D10-D21), inter-stage bleeders R140-R163 (2.5kV to 15kV)"
    },
    {
        "id": "R6_BALLAST_COL",
        "name": "Vertical Ballast Resistor Column",
        "bbox": (230.0, 52.0, 246.0, 155.0),
        "desc": "1x10 vertical 100M column (R20-R29), far eastern safety edge corridor"
    },
    {
        "id": "R7_SENSE_DIV",
        "name": "1 GΩ High-Voltage Sense Divider",
        "bbox": (140.0, 155.0, 235.0, 171.0),
        "desc": "10x 100M divider string (R30-R39) stepping down 15kV to ~1.5V telemetry"
    },
    {
        "id": "R8_LV_TELEM",
        "name": "Low-Voltage Telemetry Corridor",
        "bbox": (55.0, 155.0, 140.0, 171.0),
        "desc": "TLV9001 precision op-amp buffers, ADS1115 16-bit I2C ADC, current return shunt"
    }
]


# ==============================================================================
# 4. Proximity & Creepage/Clearance Audit Engine
# ==============================================================================

def analyze_board(pcb_path: str, worst_case=True, min_hv=500., max_lv=50.):
    import pcbnew
    if not pcbnew.Version().startswith("10."):
        raise RuntimeError("KiCad 10 is required")
    from shapely.ops import unary_union, nearest_points
    board = pcbnew.LoadBoard(pcb_path)
    # Refill in memory so zone geometry cannot silently lag the tracks.
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    copper = {}
    features = []
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        groups = {}
        items = list(board.GetTracks()) + [p for f in board.GetFootprints() for p in f.Pads()]
        for item in items:
            if not item.IsOnLayer(layer):
                continue
            if isinstance(item, pcbnew.PAD) and not item.FlashLayer(layer):
                continue
            poly = pcbnew.SHAPE_POLY_SET()
            item.TransformShapeToPolygon(poly, layer, 0, 1000, pcbnew.ERROR_OUTSIDE)
            geom = polygon_geometry(poly)
            if geom.is_empty:
                continue
            net = item.GetNetname() or '<unconnected copper>'
            groups.setdefault(net, []).append(geom.buffer(.001))
        for zone in board.Zones():
            if zone.GetIsRuleArea() or not zone.IsOnLayer(layer):
                continue
            geom = polygon_geometry(zone.GetFilledPolysList(layer))
            if not geom.is_empty:
                groups.setdefault(zone.GetNetname(), []).append(geom.buffer(.001))
        copper[layer] = {n: unary_union(g) for n, g in groups.items()}
        for n, g in copper[layer].items():
            pos = g.representative_point()
            features.append(dict(x=pos.x, y=pos.y, net=n, v=voltage_bounds(n, worst_case)[1],
                                 on_f=layer == 0, on_b=layer == 31, type='copper', ref=''))
    outline = pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(outline, False, None, False, True):
        raise ValueError('Board outline is not closed')
    boundary = polygon_geometry(outline).boundary
    edges = []
    for line in getattr(boundary, 'geoms', [boundary]):
        coords = list(line.coords)
        edges.extend(zip(coords, coords[1:]))
    surface = []
    for layer, nets in copper.items():
        names = sorted(nets)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                av, bv = voltage_bounds(a, worst_case), voltage_bounds(b, worst_case)
                dv = voltage_difference(av, bv)
                if dv < min_hv:
                    continue
                ga, gb = nets[a], nets[b]
                d = ga.distance(gb)
                pa, pb = nearest_points(ga, gb)
                # Legacy project screening coefficients, not a claim of compliance.
                coated, bare = .00305 * dv, .005 * dv
                surface.append(dict(layer=board.GetLayerName(layer), distance_mm=d,
                    delta_v=dv, efield_v_mm=dv / max(d, .001), hv_net=a, lv_net=b,
                    hv_feature=a, lv_feature=b, hv_ref='', lv_ref='',
                    hv_coord=(pa.x, pa.y), lv_coord=(pb.x, pb.y), ipc_req_mm=coated,
                    margin_pct=100 * (d - coated) / coated, category='EXTERNAL_SURFACE',
                    status='CRITICAL' if d < coated else ('CAUTION' if d < bare else 'SAFE')))
    surface.sort(key=lambda p: p['margin_pct'])
    edge_audit = []
    for layer, nets in copper.items():
        for net, geom in nets.items():
            if max(map(abs, voltage_bounds(net, worst_case))) < min_hv:
                continue
            d = geom.distance(boundary)
            edge_audit.append(dict(edge=f'{board.GetLayerName(layer)} {net} to actual Edge.Cuts',
                clearance_mm=d, ipc_limit_mm=10., status='PASS' if d >= 10 else 'FAIL'))
    # Opposite-layer geometry is reported without an unqualified material withstand PASS.
    core = []
    for a, ga in copper[pcbnew.F_Cu].items():
        for b, gb in copper[pcbnew.B_Cu].items():
            if a == b:
                continue
            dv = voltage_difference(voltage_bounds(a, worst_case), voltage_bounds(b, worst_case))
            if dv < min_hv:
                continue
            d = ga.distance(gb)
            core.append(dict(hv_net=a, lv_net=b, planar_distance_mm=d,
                effective_3d_distance_mm=math.hypot(d, 1.6), delta_v=dv,
                efield_fr4_v_mm=dv / math.hypot(d, 1.6), status='REQUIRES_MATERIAL_QUALIFICATION'))
    core.sort(key=lambda p: -p['efield_fr4_v_mm'])
    return dict(all_features=features, edge_cuts=edges, top_surface=surface,
                top_through_core=core, edge_audit=edge_audit, regional_summary=[])


# ==============================================================================
# 5. Visual Heatmap & Arcing Hazard Plot Generation
# ==============================================================================

def generate_visual_maps(analysis_data, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    all_features = analysis_data["all_features"]
    edge_cuts = analysis_data["edge_cuts"]
    top_surface = analysis_data["top_surface"]

    xs = np.array([f["x"] for f in all_features])
    ys = np.array([f["y"] for f in all_features])
    vs = np.array([f["v"] for f in all_features])

    # Board grid interpolation
    grid_x, grid_y = np.mgrid[15:250:500j, 50:175:300j]
    grid_v = griddata((xs, ys), vs, (grid_x, grid_y), method="linear", fill_value=0.0)

    # Custom colormap
    colors = [
        (0.000, "#081d58"),   # 0V (GND)
        (0.002, "#1d91c0"),   # 24V (Bridge/Logic)
        (0.166, "#41b6c4"),   # 2.5 kV (Stage 1 / SEC)
        (0.333, "#7fcdbb"),   # 5.0 kV (Stage 2)
        (0.500, "#fed976"),   # 7.5 kV (Stage 3)
        (0.666, "#fd8d3c"),   # 10.0 kV (Stage 4)
        (0.833, "#e31a1c"),   # 12.5 kV (Stage 5)
        (1.000, "#800026")    # 15.0 kV (Stage 6 / HV_OUT)
    ]
    cmap_voltage = LinearSegmentedColormap.from_list("voltage_cmap", [c[1] for c in colors], N=256)

    # --------------------------------------------------------------------------
    # MAP 1: 2D Spatial Voltage Heatmap
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 9), dpi=300)
    fig.patch.set_facecolor("#0f111a")
    ax.set_facecolor("#1a1c23")

    im = ax.imshow(
        grid_v.T,
        extent=(15, 250, 175, 50),
        origin="upper",
        cmap=cmap_voltage,
        vmin=0,
        vmax=15000,
        alpha=0.75,
        interpolation="bicubic"
    )

    for p1, p2 in edge_cuts:
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#ffffff", lw=1.2, alpha=0.9, zorder=5)

    ax.scatter(xs, ys, c=vs, cmap=cmap_voltage, vmin=0, vmax=15000, s=4, alpha=0.85, zorder=4)

    for r in REGIONS:
        rx1, ry1, rx2, ry2 = r["bbox"]
        rect = patches.Rectangle(
            (rx1, ry1), rx2 - rx1, ry2 - ry1,
            linewidth=1.0, edgecolor="#00ffff", facecolor="none",
            linestyle="--", alpha=0.5, zorder=6
        )
        ax.add_patch(rect)
        ax.text(
            rx1 + 2.0, ry1 + 4.0, r["name"],
            color="#ffffff", fontsize=7.5, weight="bold",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#000000", alpha=0.7, edgecolor="#00ffff", lw=0.5),
            zorder=7
        )

    cbar = plt.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Operating Potential [Volts (DC/Peak)]", color="#ffffff", fontsize=11, weight="bold")
    cbar.ax.yaxis.set_tick_params(color="#ffffff")
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color="#ffffff", fontsize=9)

    ax.set_title("Raspberry Pi 5 Corona Supply — Spatial Voltage Distribution Map", color="#ffffff", fontsize=14, weight="bold", pad=12)
    ax.set_xlabel("X Coordinate [mm]", color="#ffffff", fontsize=10)
    ax.set_ylabel("Y Coordinate [mm]", color="#ffffff", fontsize=10)
    ax.tick_params(colors="#ffffff")
    ax.grid(color="#444444", linestyle=":", alpha=0.4)

    voltage_map_path = os.path.join(out_dir, "voltage_map_heatmap.png")
    plt.tight_layout()
    plt.savefig(voltage_map_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close()

    # --------------------------------------------------------------------------
    # MAP 2: Surface Arcing Hazard & Clearance Vector Map
    # --------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 9), dpi=300)
    fig.patch.set_facecolor("#0a0a0f")
    ax.set_facecolor("#14141e")

    for p1, p2 in edge_cuts:
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#aaaaaa", lw=1.2, zorder=3)

    # Plot low-voltage copper points
    lv_feats = [f for f in all_features if f["v"] <= 50.0]
    ax.scatter([f["x"] for f in lv_feats], [f["y"] for f in lv_feats], color="#00bcd4", s=3, alpha=0.25, label="Low Voltage Nodes (≤50 V / GND)", zorder=4)

    # Plot high-voltage copper points
    hv_feats = [f for f in all_features if f["v"] >= 500.0]
    ax.scatter([f["x"] for f in hv_feats], [f["y"] for f in hv_feats], c=[f["v"] for f in hv_feats], cmap="plasma", vmin=500, vmax=15000, s=6, alpha=0.85, label="High Voltage Nodes (≥500 V)", zorder=5)

    # Plot Top Proximity Vectors
    external_pairs = [p for p in top_surface if p["category"] in ["EXTERNAL_SURFACE", "TRANSFORMER_BREAKOUT"]]
    for idx, pair in enumerate(external_pairs[:8]):
        hvx, hvy = pair["hv_coord"]
        lvx, lvy = pair["lv_coord"]
        d = pair["distance_mm"]
        dv = pair["delta_v"]
        efield = pair["efield_v_mm"]
        status = pair["status"]

        if status == "SAFE":
            color = "#00ff00"
        elif status == "PASS_BREAKOUT":
            color = "#00e5ff"
        elif status == "CAUTION":
            color = "#ffaa00"
        else:
            color = "#ff0000"

        ax.plot([hvx, lvx], [hvy, lvy], color=color, linestyle="--", lw=1.5, zorder=8)
        ax.scatter([hvx, lvx], [hvy, lvy], color=color, s=25, zorder=9)

        midx = (hvx + lvx) / 2.0
        midy = (hvy + lvy) / 2.0
        callout_text = f"#{idx+1}: ΔV={dv/1000:.1f}kV, d={d:.2f}mm\nE={efield:.0f} V/mm [{status}]"
        ax.annotate(
            callout_text,
            xy=(midx, midy),
            xytext=(midx + (10 if midx < 150 else -30), midy + (8 if idx % 2 == 0 else -8)),
            fontsize=7,
            color="#ffffff",
            weight="bold",
            arrowprops=dict(arrowstyle="->", color=color, lw=1.0),
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#1e1e28", edgecolor=color, lw=1.0, alpha=0.9),
            zorder=10
        )

    ax.set_title("Raspberry Pi 5 Corona Supply — Surface Arcing Risk & Clearance Vectors", color="#ffffff", fontsize=14, weight="bold", pad=12)
    ax.set_xlabel("X Coordinate [mm]", color="#ffffff", fontsize=10)
    ax.set_ylabel("Y Coordinate [mm]", color="#ffffff", fontsize=10)
    ax.tick_params(colors="#ffffff")
    ax.grid(color="#333333", linestyle=":", alpha=0.5)
    ax.legend(loc="upper left", facecolor="#1e1e28", edgecolor="#555555", labelcolor="#ffffff", fontsize=9)

    arcing_map_path = os.path.join(out_dir, "arcing_risk_map.png")
    plt.tight_layout()
    plt.savefig(arcing_map_path, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close()

    return voltage_map_path, arcing_map_path


# ==============================================================================
# 6. Report Formatting & Main Execution
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Map board operating voltages and audit HV/LV arcing risks.")
    parser.add_argument("--pcb", default="pi5_corona_hv.kicad_pcb", help="Path to KiCad PCB file")
    parser.add_argument("--output-dir", default="exports", help="Output directory for reports and charts")
    parser.add_argument("--loaded", action="store_true", help="Evaluate ballast under full corona load instead of worst-case open circuit")
    parser.add_argument("--min-hv", type=float, default=500.0, help="Minimum voltage threshold for HV classification (default: 500V)")
    parser.add_argument("--max-lv", type=float, default=50.0, help="Maximum voltage threshold for LV classification (default: 50V)")
    parser.add_argument("--no-plot", action="store_true", help="Skip graphical map generation")
    parser.add_argument("--json", action="store_true", help="Output full report as JSON to stdout")

    args = parser.parse_args()

    if not os.path.exists(args.pcb):
        sys.stderr.write(f"Error: PCB file not found: {args.pcb}\n")
        sys.exit(1)

    worst_case = not args.loaded
    data = analyze_board(args.pcb, worst_case=worst_case, min_hv=args.min_hv, max_lv=args.max_lv)

    print("=" * 115)
    print("RASPBERRY PI 5 CORONA SUPPLY — BOARD VOLTAGE MAPPING & ARCING HAZARD AUDIT")
    print(f"Target PCB: {args.pcb}")
    print(f"Analysis Mode: {'WORST-CASE OPEN-CIRCUIT (15 kV Pre-Strike Floating Ballast)' if worst_case else 'NORMAL LOADED OPERATION'}")
    print("=" * 115)

    print("\n1. FUNCTIONAL REGIONAL VOLTAGE SUMMARY")
    print("-" * 115)
    print(f"{'Region Name':<40} {'BBox (X1, Y1, X2, Y2)':<26} {'Max Potential':>14} {'Min Clearance to LV':>22}")
    print("-" * 115)
    for r in data["regional_summary"]:
        bbox_str = f"[{r['bbox'][0]:.0f}, {r['bbox'][1]:.0f}, {r['bbox'][2]:.0f}, {r['bbox'][3]:.0f}]"
        clr_str = f"{r['min_clearance_to_lv_mm']:.2f} mm" if r['min_clearance_to_lv_mm'] < 900 else "N/A (LV Region)"
        print(f"{r['name']:<40} {bbox_str:<26} {r['max_voltage']:>12.0f} V {clr_str:>22}")

    print("\n2. TOP SURFACE CLEARANCE AUDIT (SAME-LAYER AIR / CREEPAGE)")
    print("-" * 115)
    print(f"{'Layer':<10} {'Distance':>9} {'Delta V':>9} {'E-Field':>11} {'IPC Req':>9} {'Margin':>9} {'Status':<14} {'HV Node':<20} {'LV Node':<20}")
    print("-" * 115)
    for p in data["top_surface"][:20]:
        lay_abbr = "F.Cu" if "F.Cu" in p["layer"] else "B.Cu"
        hv_n = p["hv_net"].split("/")[-1][:19]
        lv_n = p["lv_net"].split("/")[-1][:19]
        print(
            f"{lay_abbr:<10} {p['distance_mm']:7.2f} mm {p['delta_v']:7.0f} V {p['efield_v_mm']:8.1f} V/mm "
            f"{p['ipc_req_mm']:7.2f} mm {p['margin_pct']:+7.1f}% {p['status']:<14} "
            f"{hv_n:<20} {lv_n:<20}"
        )

    critical_count = sum(p['status'] == 'CRITICAL' for p in data['top_surface'])
    caution_count = sum(p['status'] == 'CAUTION' for p in data['top_surface'])
    min_dist = min((p['distance_mm'] for p in data['top_surface']), default=None)
    max_efield = max((p['efield_v_mm'] for p in data['top_surface']), default=None)
    print(f"Screening failures: {critical_count}; cautions: {caution_count}")
    print("REVIEW REQUIRED: no component/breakout exemptions; insulation qualification remains external.")

    if not args.no_plot:
        print("\n6. GENERATING GRAPHICAL VISUALIZATIONS...")
        vmap, amap = generate_visual_maps(data, args.output_dir)
        print(f"• Voltage Heatmap: {vmap}")
        print(f"• Arcing Risk Map: {amap}")

    report_json_path = os.path.join(args.output_dir, "voltage_audit_report.json")
    json_payload = {
        "pcb": args.pcb,
        "verdict": "REVIEW_REQUIRED",
        "model": "Native copper polygons, 1 um outward geometry tolerance; independent voltage envelopes",
        "limitations": ["Legacy 0.00305/0.005 mm per volt screening coefficients, not standards compliance", "No package or breakout exemptions", "Voltage envelopes assume 15 kV maximum and 1250 V peak secondary", "Unknown nets conservatively treated as 0 V; review voltage assignments", "No creepage/material/coating/environment or transient qualification"],
        "edge_failures": sum(e['status'] == 'FAIL' for e in data['edge_audit']),
        "worst_case_open_circuit": worst_case,
        "absolute_min_surface_clearance_mm": min_dist,
        "peak_surface_efield_v_mm": max_efield,
        "critical_violations": critical_count,
        "caution_points": caution_count,
        "edge_audit": data["edge_audit"],
        "regional_summary": data["regional_summary"],
        "top_surface_clearances": data["top_surface"],
        "top_through_core": data["top_through_core"]
    }
    os.makedirs(args.output_dir, exist_ok=True)
    with open(report_json_path, "w", encoding="utf-8") as jf:
        json.dump(json_payload, jf, indent=2)
    print(f"Saved Machine-Readable Audit Report: {report_json_path}")

    if args.json:
        print(json.dumps(json_payload, indent=2))

if __name__ == "__main__":
    main()
