#!/usr/bin/env python3
"""
Generate a two-piece snap-together FreeCAD enclosure for the High Voltage (HV)
section of the pi5_corona_hv board.

Coordinate system matches the native KiCad 10 3D STEP export of `pi5_corona_hv.kicad_pcb`:
  - Main carrier PCB: X in [50.0, 246.0] mm, Y in [-171.0, -51.0] mm, Z in [0.0, 1.6] mm
  - Low-voltage (LV) section: X in [50.0, 100.8] mm (left uncovered)
  - High-voltage (HV) section: X in [100.8, 246.0] mm (enclosed)
  - HV wire connectors:
      * J60 (HV_OUT_WIRE):    X = 233.25 mm, Y = -63.50 mm
      * J61 (HV_RETURN_WIRE): X = 126.00 mm, Y = -156.00 mm
  - Mounting hole in HV section:
      * H3 (M2.5, 2.7 mm drill): X = 105.00 mm, Y = -55.00 mm

Key design parameters:
  - Wall thickness: 3.0 mm on all walls, roof, and floor
  - Two halves (Top Half + Bottom Half) with a stepped rabbet overlap along the
    mating surface and integrated cylindrical snap-fit beads/detents
  - Small wire escape holes (Ø 5.0 mm with protective collars) directly above J60 and J61
"""

import os
import sys
import FreeCAD as App
import Part

# ---------------------------------------------------------------------------
# 1. Board & Enclosure Parameters (mm)
# ---------------------------------------------------------------------------
PCB_X_MIN_LV = 50.0
PCB_X_DIV = 100.80       # Outer X face of the West (LV/HV dividing) wall
PCB_X_MAX = 246.00       # East edge of PCB
PCB_Y_MIN = -171.00      # South edge of PCB (KiCad Y = +171.0)
PCB_Y_MAX = -51.00       # North edge of PCB (KiCad Y = +51.0)
PCB_Z_BOT = 0.00
PCB_Z_TOP = 1.60

EDGE_CLEARANCE = 0.30    # Radial clearance between PCB outer edge and inner wall
WALL_THICKNESS = 3.00    # 3.0 mm nominal wall thickness everywhere

# Inner cavity bounds (where N, S, E walls wrap around outside of PCB edge)
CAV_X_MIN = PCB_X_DIV + WALL_THICKNESS          # 103.80 mm
CAV_X_MAX = PCB_X_MAX + EDGE_CLEARANCE          # 246.30 mm
CAV_Y_MIN = PCB_Y_MIN - EDGE_CLEARANCE          # -171.30 mm
CAV_Y_MAX = PCB_Y_MAX + EDGE_CLEARANCE          # -50.70 mm

# Outer bounds of enclosure
OUT_X_MIN = PCB_X_DIV                           # 100.80 mm
OUT_X_MAX = CAV_X_MAX + WALL_THICKNESS          # 249.30 mm
OUT_Y_MIN = CAV_Y_MIN - WALL_THICKNESS          # -174.30 mm
OUT_Y_MAX = CAV_Y_MAX + WALL_THICKNESS          # -47.70 mm

# Vertical (Z) bounds
# Tallest HV parts: C11 (Z=17.4 mm), C100-C111 6kV discs (Z~16.1 mm)
CAV_Z_TOP = 23.60                               # 22.0 mm above PCB top face
OUT_Z_TOP = CAV_Z_TOP + WALL_THICKNESS          # 26.60 mm (3.0 mm roof thickness)

# Underside THT leads protrude ~2.5 mm below Z=0
CAV_Z_BOT = -8.00                               # 8.0 mm below PCB bottom face
OUT_Z_BOT = CAV_Z_BOT - WALL_THICKNESS          # -11.00 mm (3.0 mm floor thickness)

# Mating plane and overlapping rabbet (stepped lip) parameters
SPLIT_Z = 0.80                                  # Mid-plane of the 1.6 mm PCB
OVERLAP_HEIGHT = 3.00                           # 3.0 mm vertical overlap at mating seam
LIP_Z_TOP = SPLIT_Z + OVERLAP_HEIGHT            # 3.80 mm
LIP_THICKNESS = 1.50                            # Half of the 3.0 mm wall thickness
LIP_CLEARANCE = 0.12                            # Radial mating clearance for 3D printing / assembly
SNAP_RADIUS = 0.45                              # Snap bead radius along the overlapping lip
SNAP_Z = SPLIT_Z + OVERLAP_HEIGHT * 0.55        # Z = 2.45 mm (center of overlap)

# Wire escape holes above HV wire connectors (J60 and J61)
J60_POS = (233.25, -63.50)                      # HV_OUT_WIRE
J61_POS = (126.00, -156.00)                     # HV_RETURN_WIRE
WIRE_HOLE_DIA = 5.00                            # 5.0 mm escape hole diameter
COLLAR_WALL = 3.00                              # 3.0 mm wall around collar
COLLAR_HEIGHT = 2.50                            # 2.5 mm raised boss above roof

# Mounting hole H3 in HV section
H3_POS = (105.00, -55.00)
H3_PIN_DIA = 2.30                               # Locator pin for 2.7 mm hole H3
H3_BOSS_DIA = 5.20


def make_box(xmin, xmax, ymin, ymax, zmin, zmax):
    return Part.makeBox(
        xmax - xmin,
        ymax - ymin,
        zmax - zmin,
        App.Vector(xmin, ymin, zmin),
    )


def build_top_half():
    """
    Build the Top Half (Upper Shell / Lid) of the HV enclosure:
      - 3.0 mm roof (Z = 23.6 to 26.6)
      - 3.0 mm walls on North, South, East, and West (LV/HV divider)
      - Outer overlapping skirt from Z = 3.8 down to Z = 0.8 around N, E, S walls
        (and N/S ends of West wall outside the PCB)
      - Snap-fit detent grooves on the inside of the outer skirt
      - West wall lower edge stops at Z = 1.90 mm above PCB top face (0.3 mm clearance)
        with local relief slots over T1 primary pins and D52/D53
      - Internal PCB hold-down ribs along safe copper-free N/E/S edges (Z = 1.75 mm)
      - Small wire escape holes (Ø 5.0 mm) + protective collars directly above J60 and J61
    """
    # 1. Main outer block from LIP_Z_TOP (3.80) to OUT_Z_TOP (26.60)
    outer_upper = make_box(OUT_X_MIN, OUT_X_MAX, OUT_Y_MIN, OUT_Y_MAX, LIP_Z_TOP, OUT_Z_TOP)
    inner_upper = make_box(CAV_X_MIN, CAV_X_MAX, CAV_Y_MIN, CAV_Y_MAX, LIP_Z_TOP, CAV_Z_TOP)
    shell = outer_upper.cut(inner_upper)

    # 2. Outer overlapping skirt from SPLIT_Z (0.80) to LIP_Z_TOP (3.80)
    #    Along North, East, South walls, the outer half of the 3 mm wall (thickness 1.50 mm)
    #    projects down to SPLIT_Z (0.80 mm), overlapping the Bottom Half's inner lip.
    skirt_outer = make_box(OUT_X_MIN, OUT_X_MAX, OUT_Y_MIN, OUT_Y_MAX, SPLIT_Z, LIP_Z_TOP)
    skirt_inner_cut = make_box(
        OUT_X_MIN,
        OUT_X_MAX - LIP_THICKNESS,
        OUT_Y_MIN + LIP_THICKNESS,
        OUT_Y_MAX - LIP_THICKNESS,
        SPLIT_Z,
        LIP_Z_TOP,
    )
    skirt = skirt_outer.cut(skirt_inner_cut)
    shell = shell.fuse(skirt)

    # 3. West (LV/HV dividing) wall extension down to PCB top surface (Z = 1.90 mm)
    #    Across the PCB width [PCB_Y_MIN, PCB_Y_MAX], the 3.0 mm thick West wall
    #    comes down to Z = 1.90 mm (0.30 mm above the 1.60 mm PCB surface).
    #    Outside the PCB width (in the North/South wall zones), it joins the skirt.
    PCB_TOP_CLEAR_Z = PCB_Z_TOP + 0.30  # 1.90 mm
    west_wall_lower = make_box(
        OUT_X_MIN,
        CAV_X_MIN,
        CAV_Y_MIN,
        CAV_Y_MAX,
        PCB_TOP_CLEAR_Z,
        LIP_Z_TOP,
    )
    shell = shell.fuse(west_wall_lower)

    # 4. Local component relief cutouts on the bottom of the West wall:
    #    a) T1 primary leads at X in [102.0, 104.1], Y in [-121.5, -106.5], Z up to 2.50 mm
    t1_relief = make_box(
        OUT_X_MIN - 0.5,
        CAV_X_MIN + 0.5,
        -122.5,
        -105.5,
        PCB_Z_TOP,
        2.80,
    )
    #    b) D52 & D53 recirculation diodes at X in [102.0, 108.0], Y in [-160.5, -139.5], Z up to 3.91 mm
    d52_d53_relief = make_box(
        OUT_X_MIN + 1.00,  # Keep 1.0 mm outer skin where D52/D53 start at X=102.05
        CAV_X_MIN + 0.5,
        -161.2,
        -138.8,
        PCB_Z_TOP,
        4.35,
    )
    shell = shell.cut(t1_relief).cut(d52_d53_relief)

    # 5. Upper PCB hold-down ribs (presses down gently to Z = 1.75 mm on safe PCB border
    #    and overlaps 1.0 mm into the main 3.0 mm wall above LIP_Z_TOP so it forms a single solid)
    HOLD_Z = PCB_Z_TOP + 0.15  # 1.75 mm
    TAB_W = 1.35
    hold_tabs = [
        # North edge ribs (copper-free border is 12 mm wide)
        make_box(112.0, 145.0, CAV_Y_MAX - TAB_W, CAV_Y_MAX + 1.0, HOLD_Z, LIP_Z_TOP + 2.5),
        make_box(185.0, 240.0, CAV_Y_MAX - TAB_W, CAV_Y_MAX + 1.0, HOLD_Z, LIP_Z_TOP + 2.5),
        # South edge ribs (avoid X=118..138 where D1/U4/sense tracks are near South edge)
        make_box(148.0, 240.0, CAV_Y_MIN - 1.0, CAV_Y_MIN + TAB_W, HOLD_Z, LIP_Z_TOP + 2.5),
        # East edge ribs (copper-free border is 12.25 mm wide)
        make_box(CAV_X_MAX - TAB_W, CAV_X_MAX + 1.0, -155.0, -70.0, HOLD_Z, LIP_Z_TOP + 2.5),
    ]
    for tab in hold_tabs:
        shell = shell.fuse(tab)
    # Trim any part of hold_tabs that entered the Bottom Half's lip slot (with 0.15 mm inner clearance) below LIP_Z_TOP
    slot_clear = make_box(
        OUT_X_MIN,
        OUT_X_MAX - LIP_THICKNESS,
        OUT_Y_MIN + LIP_THICKNESS,
        OUT_Y_MAX - LIP_THICKNESS,
        SPLIT_Z,
        LIP_Z_TOP,
    ).cut(
        make_box(
            CAV_X_MIN,
            CAV_X_MAX - 0.15,
            CAV_Y_MIN + 0.15,
            CAV_Y_MAX - 0.15,
            SPLIT_Z,
            LIP_Z_TOP,
        )
    )
    shell = shell.cut(slot_clear)

    # 6. Snap-fit detent grooves on the inside face of the outer overlapping skirt
    #    North skirt inner face is at Y = OUT_Y_MAX - LIP_THICKNESS (-49.20 mm)
    #    South skirt inner face is at Y = OUT_Y_MIN + LIP_THICKNESS (-172.80 mm)
    #    East skirt inner face is at  X = OUT_X_MAX - LIP_THICKNESS (247.80 mm)
    detent_r = SNAP_RADIUS + 0.05
    for x_start, x_end in [(125.0, 160.0), (190.0, 225.0)]:
        # North detent cylinder
        cyl_n = Part.makeCylinder(
            detent_r,
            x_end - x_start,
            App.Vector(x_start, OUT_Y_MAX - LIP_THICKNESS, SNAP_Z),
            App.Vector(1, 0, 0),
        )
        # South detent cylinder
        cyl_s = Part.makeCylinder(
            detent_r,
            x_end - x_start,
            App.Vector(x_start, OUT_Y_MIN + LIP_THICKNESS, SNAP_Z),
            App.Vector(1, 0, 0),
        )
        shell = shell.cut(cyl_n).cut(cyl_s)

    # East detent cylinder
    cyl_e = Part.makeCylinder(
        detent_r,
        50.0,
        App.Vector(OUT_X_MAX - LIP_THICKNESS, -136.0, SNAP_Z),
        App.Vector(0, 1, 0),
    )
    shell = shell.cut(cyl_e)

    # 7. Raised protective collars + wire escape holes directly above J60 and J61
    collar_od = WIRE_HOLE_DIA + 2.0 * COLLAR_WALL  # 11.0 mm OD (3.0 mm wall)
    for cx, cy in [J60_POS, J61_POS]:
        collar = Part.makeCylinder(
            collar_od / 2.0,
            COLLAR_HEIGHT,
            App.Vector(cx, cy, OUT_Z_TOP),
            App.Vector(0, 0, 1),
        )
        shell = shell.fuse(collar)

    for cx, cy in [J60_POS, J61_POS]:
        hole = Part.makeCylinder(
            WIRE_HOLE_DIA / 2.0,
            WALL_THICKNESS + COLLAR_HEIGHT + 4.0,
            App.Vector(cx, cy, CAV_Z_TOP - 2.0),
            App.Vector(0, 0, 1),
        )
        shell = shell.cut(hole)

    shell = shell.removeSplitter()
    return shell


def build_bottom_half():
    """
    Build the Bottom Half (Lower Shell / Base) of the HV enclosure:
      - 3.0 mm floor (Z = -11.0 to -8.0)
      - 3.0 mm walls on North, South, East, and West (LV/HV divider)
      - Inner upward-projecting overlapping mating lip from Z = 0.8 to Z = 3.8
        along N, E, S walls (thickness = 1.50 - 0.12 = 1.38 mm)
      - Snap-fit beads (ridges) on the outer face of the upward mating lip
      - West wall rises to Z = -0.20 mm (0.20 mm clearance below PCB bottom face Z=0)
      - Internal PCB support ledges up to Z = 0.00 mm along N, E, S borders
      - H3 PCB alignment boss + locator pin at (105.0, -55.0)
    """
    # 1. Main lower shell from OUT_Z_BOT (-11.00) to SPLIT_Z (0.80)
    outer_lower = make_box(OUT_X_MIN, OUT_X_MAX, OUT_Y_MIN, OUT_Y_MAX, OUT_Z_BOT, SPLIT_Z)
    inner_lower = make_box(CAV_X_MIN, CAV_X_MAX, CAV_Y_MIN, CAV_Y_MAX, CAV_Z_BOT, SPLIT_Z)
    shell = outer_lower.cut(inner_lower)

    # 2. Trim the West wall between [PCB_Y_MIN - 0.3, PCB_Y_MAX + 0.3] down to Z = -0.20 mm
    #    so the continuous PCB (Z = 0.0 to 1.6 mm) passes unobstructed into the LV section!
    PCB_BOT_CLEAR_Z = PCB_Z_BOT - 0.20  # -0.20 mm
    west_pcb_slot = make_box(
        OUT_X_MIN - 1.0,
        CAV_X_MIN + 1.0,
        CAV_Y_MIN,
        CAV_Y_MAX,
        PCB_BOT_CLEAR_Z,
        SPLIT_Z + 1.0,
    )
    shell = shell.cut(west_pcb_slot)

    # 3. Inner upward-projecting overlapping lip from SPLIT_Z (0.80) to LIP_Z_TOP (3.80)
    #    along the North, East, and South walls (thickness = LIP_THICKNESS - LIP_CLEARANCE = 1.38 mm)
    eff_lip_t = LIP_THICKNESS - LIP_CLEARANCE  # 1.38 mm
    lip_outer = make_box(
        OUT_X_MIN,
        CAV_X_MAX + eff_lip_t,
        CAV_Y_MIN - eff_lip_t,
        CAV_Y_MAX + eff_lip_t,
        SPLIT_Z,
        LIP_Z_TOP - 0.15,  # 0.15 mm vertical top clearance in step
    )
    lip_inner = make_box(
        OUT_X_MIN - 1.0,  # Open on the West side where the PCB passes through
        CAV_X_MAX,
        CAV_Y_MIN,
        CAV_Y_MAX,
        SPLIT_Z,
        LIP_Z_TOP,
    )
    lip = lip_outer.cut(lip_inner)
    shell = shell.fuse(lip)

    # 4. Snap-fit beads (ridges) on the outer face of the Bottom Half's upward lip
    bead_r = SNAP_RADIUS - 0.05  # 0.40 mm protrusion for crisp snap engagement
    for x_start, x_end in [(126.0, 159.0), (191.0, 224.0)]:
        # North bead
        cyl_n = Part.makeCylinder(
            bead_r,
            x_end - x_start,
            App.Vector(x_start, CAV_Y_MAX + eff_lip_t, SNAP_Z),
            App.Vector(1, 0, 0),
        )
        # South bead
        cyl_s = Part.makeCylinder(
            bead_r,
            x_end - x_start,
            App.Vector(x_start, CAV_Y_MIN - eff_lip_t, SNAP_Z),
            App.Vector(1, 0, 0),
        )
        shell = shell.fuse(cyl_n).fuse(cyl_s)

    # East bead
    cyl_e = Part.makeCylinder(
        bead_r,
        48.0,
        App.Vector(CAV_X_MAX + eff_lip_t, -135.0, SNAP_Z),
        App.Vector(0, 1, 0),
    )
    shell = shell.fuse(cyl_e)

    # Keep snap beads strictly within the outer wall envelope and above SPLIT_Z
    trim_inner = make_box(OUT_X_MIN - 1.0, CAV_X_MAX, CAV_Y_MIN, CAV_Y_MAX, SPLIT_Z, LIP_Z_TOP)
    shell = shell.cut(trim_inner)

    # 5. Internal PCB support ledges rising from CAV_Z_BOT (-8.0) to PCB_Z_BOT (0.0)
    #    Supports the PCB around the North, East, and South edges.
    LEDGE_W = 1.50  # Projects 1.20 mm under the PCB edge (since EDGE_CLEARANCE = 0.30 mm)
    ledges = [
        # North support ledge
        make_box(112.0, 244.0, CAV_Y_MAX - LEDGE_W, CAV_Y_MAX, CAV_Z_BOT, PCB_Z_BOT),
        # South support ledge (starts at X=142 to stay well clear of B.Cu sense tracks at X=119..135)
        make_box(142.0, 244.0, CAV_Y_MIN, CAV_Y_MIN + LEDGE_W, CAV_Z_BOT, PCB_Z_BOT),
        # East support ledge
        make_box(CAV_X_MAX - LEDGE_W, CAV_X_MAX, -168.0, -54.0, CAV_Z_BOT, PCB_Z_BOT),
    ]
    for ldg in ledges:
        shell = shell.fuse(ldg)

    # 6. Mounting hole H3 (105.0, -55.0) support standoff + locator pin
    h3_boss = Part.makeCylinder(
        H3_BOSS_DIA / 2.0,
        PCB_Z_BOT - CAV_Z_BOT,
        App.Vector(H3_POS[0], H3_POS[1], CAV_Z_BOT),
        App.Vector(0, 0, 1),
    )
    h3_pin = Part.makeCylinder(
        H3_PIN_DIA / 2.0,
        (PCB_Z_TOP + 0.60) - PCB_Z_BOT,
        App.Vector(H3_POS[0], H3_POS[1], PCB_Z_BOT),
        App.Vector(0, 0, 1),
    )
    shell = shell.fuse(h3_boss).fuse(h3_pin)

    shell = shell.removeSplitter()
    return shell


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out_dir, exist_ok=True)

    doc = App.newDocument("HV_Enclosure")

    top_shape = build_top_half()
    bot_shape = build_bottom_half()

    top_obj = doc.addObject("Part::Feature", "HV_Enclosure_Top_Half")
    top_obj.Label = "HV_Enclosure_Top_Half"
    top_obj.Shape = top_shape

    bot_obj = doc.addObject("Part::Feature", "HV_Enclosure_Bottom_Half")
    bot_obj.Label = "HV_Enclosure_Bottom_Half"
    bot_obj.Shape = bot_shape

    doc.recompute()

    # Save native FreeCAD file (.FCStd)
    fcstd_path = os.path.join(out_dir, "hv_enclosure.FCStd")
    doc.saveAs(fcstd_path)
    print(f"Saved FreeCAD document: {fcstd_path}")

    # Export STEP and STL deliverables
    top_step = os.path.join(out_dir, "hv_enclosure_top.step")
    bot_step = os.path.join(out_dir, "hv_enclosure_bottom.step")
    asm_step = os.path.join(out_dir, "hv_enclosure_assembly.step")
    top_stl = os.path.join(out_dir, "hv_enclosure_top.stl")
    bot_stl = os.path.join(out_dir, "hv_enclosure_bottom.stl")

    top_shape.exportStep(top_step)
    bot_shape.exportStep(bot_step)
    Part.Compound([top_shape, bot_shape]).exportStep(asm_step)
    top_shape.exportStl(top_stl)
    bot_shape.exportStl(bot_stl)
    print("Exported STEP and STL files.")

    # Verification checks
    print("=== Geometry Verification ===")
    for name, sh in [("Top Half", top_shape), ("Bottom Half", bot_shape)]:
        bb = sh.BoundBox
        print(
            f"{name:12s}: valid={sh.isValid()}, solids={len(sh.Solids)}, "
            f"vol={sh.Volume:.1f} mm^3, "
            f"X=[{bb.XMin:.2f}, {bb.XMax:.2f}], Y=[{bb.YMin:.2f}, {bb.YMax:.2f}], Z=[{bb.ZMin:.2f}, {bb.ZMax:.2f}]"
        )
        assert sh.isValid(), f"{name} is not a valid solid!"
        assert len(sh.Solids) == 1, f"{name} has {len(sh.Solids)} solids instead of 1!"

    # Check overlap between Top Half and Bottom Half (should have zero interference)
    inter = top_shape.common(bot_shape)
    print(f"Top/Bottom interference volume: {inter.Volume:.4f} mm^3")
    assert inter.Volume < 1e-3, f"Top and Bottom halves collide: {inter.Volume} mm^3"

    # Check wire escape holes above J60 and J61 are unobstructed vertical rays
    for label, (wx, wy) in [("J60 (HV_OUT)", J60_POS), ("J61 (HV_RETURN)", J61_POS)]:
        ray_cyl = Part.makeCylinder(
            WIRE_HOLE_DIA * 0.48,
            50.0,
            App.Vector(wx, wy, PCB_Z_TOP),
            App.Vector(0, 0, 1),
        )
        hit = top_shape.common(ray_cyl)
        print(f"Wire escape hole check above {label} at ({wx}, {wy}): obstruction={hit.Volume:.4f} mm^3")
        assert hit.Volume < 1e-3, f"Wire hole above {label} is obstructed!"

    # Check collision against exported PCB STEP if present
    if os.path.exists("/tmp/board_only.step"):
        pcb_sh = Part.Shape()
        pcb_sh.read("/tmp/board_only.step")
        top_pcb_hit = top_shape.common(pcb_sh).Volume
        bot_pcb_hit = bot_shape.common(pcb_sh).Volume
        print(f"PCB substrate collision check: Top={top_pcb_hit:.4f} mm^3, Bottom={bot_pcb_hit:.4f} mm^3")
        assert top_pcb_hit < 1e-3 and bot_pcb_hit < 1e-3, "Enclosure collides with PCB substrate!"


if __name__ in ("__main__", "generate_hv_enclosure"):
    main()

