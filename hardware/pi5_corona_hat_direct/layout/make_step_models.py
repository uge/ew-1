import FreeCAD, Part, math
from pathlib import Path

out_dir = Path("/home/uge/Development/ew-1/hardware/pi5_corona_hat_direct/ionic_thrust_hv.3dshapes")

# ==========================================
# 1. Sunmate 2CL75 Axial Diode
# ==========================================
print("Building Sunmate 2CL75...")
# Body: Cylinder along X axis, diameter 3.0mm, length 12.0mm (-6 to +6)
body_cyl = Part.makeCylinder(1.5, 12.0, FreeCAD.Vector(-6.0, 0, 1.7), FreeCAD.Vector(1, 0, 0))
band_cyl = Part.makeCylinder(1.52, 1.2, FreeCAD.Vector(-5.0, 0, 1.7), FreeCAD.Vector(1, 0, 0))

# Leads: wire r = 0.3mm
l_horiz = Part.makeCylinder(0.3, 7.0, FreeCAD.Vector(-13.0, 0, 1.7), FreeCAD.Vector(1, 0, 0))
l_vert = Part.makeCylinder(0.3, 4.2, FreeCAD.Vector(-13.0, 0, -2.5), FreeCAD.Vector(0, 0, 1))
r_horiz = Part.makeCylinder(0.3, 7.0, FreeCAD.Vector(6.0, 0, 1.7), FreeCAD.Vector(1, 0, 0))
r_vert = Part.makeCylinder(0.3, 4.2, FreeCAD.Vector(13.0, 0, -2.5), FreeCAD.Vector(0, 0, 1))
l_corner = Part.makeSphere(0.35, FreeCAD.Vector(-13.0, 0, 1.7))
r_corner = Part.makeSphere(0.35, FreeCAD.Vector(13.0, 0, 1.7))

diode_compound = Part.Compound([body_cyl, band_cyl, l_horiz, l_vert, l_corner, r_horiz, r_vert, r_corner])
Part.export([diode_compound], str(out_dir / "Sunmate_2CL75_D3_L12_P26.step"))
print("Sunmate 2CL75 exported.")

# ==========================================
# 2. DEALON TK-0013-R Switch
# ==========================================
print("Building TK-0013-R...")
sw_body = Part.makeBox(8.3, 6.2, 2.7, FreeCAD.Vector(-4.15, 2.7, 0.1))
sw_lever = Part.makeBox(7.0, 3.6, 0.3, FreeCAD.Vector(-3.5, 8.9, 1.0))
pins = []
for px in [-2.5, 0.0, 2.5]:
    ph = Part.makeBox(0.6, 2.7, 0.3, FreeCAD.Vector(px - 0.3, 0.0, 0.5))
    pv = Part.makeBox(0.6, 0.6, 2.5, FreeCAD.Vector(px - 0.3, -0.3, -2.0))
    pins.extend([ph, pv])

sw_compound = Part.Compound([sw_body, sw_lever] + pins)
Part.export([sw_compound], str(out_dir / "TK-0013-R.step"))
print("TK-0013-R exported.")

# ==========================================
# 3. Coilcraft FL2015 Package 1
# ==========================================
print("Building Coilcraft FL2015...")
core_box = Part.makeBox(20.96, 15.49, 6.5, FreeCAD.Vector(-10.48, -7.745, 1.2))
base_box = Part.makeBox(21.4, 15.6, 1.0, FreeCAD.Vector(-10.7, -7.8, 0.2))
coil_cyl = Part.makeCylinder(4.5, 14.0, FreeCAD.Vector(0, -7.0, 4.0), FreeCAD.Vector(0, 1, 0))

pads = []
for py in [-6.25, -3.75, -1.25, 1.25, 3.75, 6.25]:
    foot = Part.makeBox(1.905, 1.27, 0.2, FreeCAD.Vector(11.4325 - 0.9525, py - 0.635, 0.0))
    leg = Part.makeBox(0.8, 0.8, 0.6, FreeCAD.Vector(10.7 - 0.2, py - 0.4, 0.1))
    pads.extend([foot, leg])

for py in [-6.25, -3.75, 3.75, 6.25]:
    foot = Part.makeBox(1.905, 1.27, 0.2, FreeCAD.Vector(-11.4325 - 0.9525, py - 0.635, 0.0))
    leg = Part.makeBox(0.8, 0.8, 0.6, FreeCAD.Vector(-10.7 - 0.6, py - 0.4, 0.1))
    pads.extend([foot, leg])

fl_compound = Part.Compound([core_box, base_box, coil_cyl] + pads)
Part.export([fl_compound], str(out_dir / "Coilcraft_FL2015_Package1_SMT.step"))
print("Coilcraft FL2015 exported.")

# ==========================================
# 4. DFN-6 2x2.4mm P0.65mm (TSL2591)
# ==========================================
print("Building DFN-6 for TSL2591...")
dfn_body = Part.makeBox(2.0, 2.4, 0.65, FreeCAD.Vector(-1.0, -1.2, 0.0))
opt_window = Part.makeCylinder(0.45, 0.1, FreeCAD.Vector(0, 0, 0.56), FreeCAD.Vector(0, 0, 1))

dfn_pads = []
for px in [-0.85, 0.85]:
    for py in [-0.65, 0.0, 0.65]:
        p = Part.makeBox(0.3, 0.4, 0.05, FreeCAD.Vector(px - 0.15, py - 0.2, 0.0))
        dfn_pads.append(p)

tsl_compound = Part.Compound([dfn_body, opt_window] + dfn_pads)
Part.export([tsl_compound], str(out_dir / "DFN-6_2x2.4mm_P0.65mm.step"))
print("DFN-6 exported.")

print("ALL 4 3D STEP MODELS CREATED SUCCESSFULLY!")
