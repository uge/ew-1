import FreeCAD, Part, Import
from pathlib import Path
import math

out_dir = Path("/home/uge/Development/ew-1/hardware/pi5_corona_hat_direct/ionic_thrust_hv.3dshapes")
out_dir.mkdir(parents=True, exist_ok=True)

print("Creating high-detail DEALON TK-0013-R STEP model...")
doc = FreeCAD.newDocument("TK0013R_Clean")

# 1. Main Body: 8.30mm (X) x 6.20mm (Y) x 2.70mm (Z)
# Located at X in [-4.15, 4.15], Y in [2.70, 8.90], Z in [1.10, 3.80]
body_raw = Part.makeBox(8.30, 6.20, 2.70, FreeCAD.Vector(-4.15, 2.70, 1.10))

# Mounting holes: diameter 1.6mm at X = -2.50 and +2.50, Y = 2.70 + 1.60 = 4.30
hole1 = Part.makeCylinder(0.80, 3.5, FreeCAD.Vector(-2.50, 4.30, 0.8), FreeCAD.Vector(0, 0, 1))
hole2 = Part.makeCylinder(0.80, 3.5, FreeCAD.Vector(2.50, 4.30, 0.8), FreeCAD.Vector(0, 0, 1))

# Cut holes from body
body_shape = body_raw.cut(hole1).cut(hole2)

# Small top locating recess between holes (X in [-0.6, 0.6], Y in [4.0, 4.6], Z in [3.4, 3.81])
recess = Part.makeBox(1.2, 0.6, 0.5, FreeCAD.Vector(-0.6, 4.0, 3.4))
body_shape = body_shape.cut(recess)

body_obj = doc.addObject("Part::Feature", "SwitchBody")
body_obj.Shape = body_shape

# 2. Push-button Plunger (white PA66)
# Sits at front face of body at X = -1.50, Y = 8.90 to 9.80, Z = 2.45
plunger_cyl = Part.makeCylinder(0.60, 1.10, FreeCAD.Vector(-1.50, 8.80, 2.45), FreeCAD.Vector(0, 1, 0))
plunger_sph = Part.makeSphere(0.60, FreeCAD.Vector(-1.50, 9.90, 2.45))
plunger_shape = plunger_cyl.fuse(plunger_sph)

plunger_obj = doc.addObject("Part::Feature", "Plunger")
plunger_obj.Shape = plunger_shape

# 3. Actuator Lever (stainless steel)
# Pivot hinge at X = -3.35, Y = 8.80, Z = 2.45
# Hinge barrel (cylinder along Z)
hinge_barrel = Part.makeCylinder(0.70, 2.20, FreeCAD.Vector(-3.35, 8.80, 1.35), FreeCAD.Vector(0, 0, 1))
hinge_hole = Part.makeCylinder(0.35, 2.40, FreeCAD.Vector(-3.35, 8.80, 1.25), FreeCAD.Vector(0, 0, 1))
hinge = hinge_barrel.cut(hinge_hole)

# Lever arm blade:
# Extends from (-3.35, 8.80) to contact crest at (+2.70, 12.50)
# Wire cross-section or thin polygon swept / extruded in Z:
p1 = FreeCAD.Vector(-3.35, 8.80, 0)
p2 = FreeCAD.Vector(2.70, 12.50, 0)
p3 = FreeCAD.Vector(3.35, 11.20, 0)

# Create 2D profile of lever in XY, then extrude in Z from 1.35 to 3.55 (height 2.20mm)
# Lever thickness 0.30mm
# Parallel offset vector for thickness:
dx = p2.x - p1.x
dy = p2.y - p1.y
length = math.sqrt(dx*dx + dy*dy)
nx = -dy / length * 0.30
ny = dx / length * 0.30

# Outer points
w_points = [
    FreeCAD.Vector(-3.35, 8.80, 0),
    FreeCAD.Vector(2.70, 12.50, 0),
    FreeCAD.Vector(3.40, 11.30, 0),
    FreeCAD.Vector(3.20, 11.10, 0),
    FreeCAD.Vector(2.55, 12.20, 0),
    FreeCAD.Vector(-3.35 + nx, 8.80 + ny, 0),
    FreeCAD.Vector(-3.35, 8.80, 0)
]
poly = Part.makePolygon(w_points)
face = Part.Face(poly)
blade = face.extrude(FreeCAD.Vector(0, 0, 2.20))
blade.translate(FreeCAD.Vector(0, 0, 1.35))

# Rounded crest at (+2.70, 12.50)
crest = Part.makeCylinder(0.40, 2.20, FreeCAD.Vector(2.65, 12.35, 1.35), FreeCAD.Vector(0, 0, 1))

lever_shape = hinge.fuse(blade).fuse(crest)
lever_obj = doc.addObject("Part::Feature", "ActuatorLever")
lever_obj.Shape = lever_shape

# 4. Terminals (Pins)
# 3 bent pins at px in [-2.5, 0.0, 2.5]
pins_list = []
for px in [-2.5, 0.0, 2.5]:
    # Vertical pin into PCB through-hole: from Z = -2.50 to Z = 1.10 at Y = 0.00
    # Width 1.20mm (X), thickness 0.40mm (Y)
    pv = Part.makeBox(1.20, 0.40, 3.60, FreeCAD.Vector(px - 0.60, -0.20, -2.50))
    # Horizontal lead from Y = 0.00 to Y = 2.70 at Z = 1.10
    # Width 1.20mm (X), length 2.80mm (Y), thickness 0.40mm (Z)
    ph = Part.makeBox(1.20, 2.80, 0.40, FreeCAD.Vector(px - 0.60, -0.10, 0.90))
    pins_list.append(pv.fuse(ph))

pins_shape = pins_list[0].fuse(pins_list[1]).fuse(pins_list[2])
pins_obj = doc.addObject("Part::Feature", "Pins")
pins_obj.Shape = pins_shape

# Export STEP model
step_path = str(out_dir / "TK-0013-R.step")
Import.export([body_obj, plunger_obj, lever_obj, pins_obj], step_path)
print(f"Exported STEP to {step_path}")
