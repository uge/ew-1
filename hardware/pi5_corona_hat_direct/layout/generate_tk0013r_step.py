import FreeCAD, Part, Import
from pathlib import Path
import math
import re

out_dirs = [
    Path("/home/uge/Development/ew-1/hardware/pi5_corona_hat_direct/ionic_thrust_hv.3dshapes"),
    Path("/home/uge/Development/ew-1/hardware/ionic_thrust_hv.3dshapes")
]

for d in out_dirs:
    d.mkdir(parents=True, exist_ok=True)

print("Generating high-fidelity DEALON TK-0013-R microswitch model...")
doc = FreeCAD.newDocument("TK0013R")

# 1. Main Body: 8.30mm (X) x 6.20mm (Y) x 2.70mm (Z)
# Standoff above PCB: Z = 1.10mm. So Z in [1.10, 3.80].
# Centered in X: [-4.15, 4.15].
# In KiCad 3D convention (Y_3D = -Y_fp): Body extends along -Y: [-8.90, -2.70].
body_box = Part.makeBox(8.30, 6.20, 2.70, FreeCAD.Vector(-4.15, -8.90, 1.10))

# Mounting holes: diameter 1.6mm at X = -2.50 and +2.50, Y = -4.30
hole1 = Part.makeCylinder(0.80, 3.5, FreeCAD.Vector(-2.50, -4.30, 0.8), FreeCAD.Vector(0, 0, 1))
hole2 = Part.makeCylinder(0.80, 3.5, FreeCAD.Vector(2.50, -4.30, 0.8), FreeCAD.Vector(0, 0, 1))

# Top recess between holes
recess = Part.makeBox(1.2, 0.8, 0.6, FreeCAD.Vector(-0.6, -4.4, 3.3))

body_shape = body_box.cut(hole1).cut(hole2).cut(recess)
body_obj = doc.addObject("Part::Feature", "SwitchBody")
body_obj.Shape = body_shape

# 2. Plunger Button (White PA66)
# Plunger extends in -Y direction from body edge (-8.80 to -9.90)
plunger_cyl = Part.makeCylinder(0.60, 1.10, FreeCAD.Vector(-1.50, -8.80, 2.45), FreeCAD.Vector(0, -1, 0))
plunger_sph = Part.makeSphere(0.60, FreeCAD.Vector(-1.50, -9.90, 2.45))
plunger_shape = plunger_cyl.fuse(plunger_sph)
plunger_obj = doc.addObject("Part::Feature", "Plunger")
plunger_obj.Shape = plunger_shape

# 3. Actuator Lever (Stainless Steel)
# Hinge barrel at (-3.35, -8.80)
hinge_barrel = Part.makeCylinder(0.70, 2.20, FreeCAD.Vector(-3.35, -8.80, 1.35), FreeCAD.Vector(0, 0, 1))
hinge_hole = Part.makeCylinder(0.35, 2.40, FreeCAD.Vector(-3.35, -8.80, 1.25), FreeCAD.Vector(0, 0, 1))
hinge = hinge_barrel.cut(hinge_hole)

# Lever arm blade:
# Free position extends to Y = -12.50mm at X = 2.65mm
w_points = [
    FreeCAD.Vector(-3.35, -8.80, 0),
    FreeCAD.Vector(-3.35, -8.50, 0),
    FreeCAD.Vector(2.55, -12.20, 0),
    FreeCAD.Vector(3.20, -11.10, 0),
    FreeCAD.Vector(3.40, -11.30, 0),
    FreeCAD.Vector(2.65, -12.50, 0),
    FreeCAD.Vector(-3.35, -8.80, 0)
]
poly = Part.makePolygon(w_points)
face = Part.Face(poly)
blade = face.extrude(FreeCAD.Vector(0, 0, 2.20))
blade.translate(FreeCAD.Vector(0, 0, 1.35))

crest = Part.makeCylinder(0.40, 2.20, FreeCAD.Vector(2.65, -12.35, 1.35), FreeCAD.Vector(0, 0, 1))
lever_shape = hinge.fuse(blade).fuse(crest)
lever_obj = doc.addObject("Part::Feature", "ActuatorLever")
lever_obj.Shape = lever_shape

# 4. Terminals (3 Pins)
pins_list = []
for px in [-2.5, 0.0, 2.5]:
    # Vertical pin into PCB through-hole
    pv = Part.makeBox(1.20, 0.40, 3.60, FreeCAD.Vector(px - 0.60, -0.20, -2.50))
    # Horizontal bridge to body extending from 0.10 to -2.70
    ph = Part.makeBox(1.20, 2.80, 0.40, FreeCAD.Vector(px - 0.60, -2.70, 0.90))
    pins_list.append(pv.fuse(ph))

pins_shape = pins_list[0].fuse(pins_list[1]).fuse(pins_list[2])
pins_obj = doc.addObject("Part::Feature", "Pins")
pins_obj.Shape = pins_shape

# Function to colorize STEP file
def colorize_step_file(step_path, product_colors):
    with open(step_path) as f:
        text = f.read()

    def find_solids_and_faces_for_product(prod_name):
        m_p = re.search(r"(#[0-9]+)\s*=\s*PRODUCT\s*\(\s*\x27" + re.escape(prod_name) + r"\x27", text)
        if not m_p:
            return [], []
        prod_id = m_p.group(1)
        pdf = re.search(r"(#[0-9]+)\s*=\s*PRODUCT_DEFINITION_FORMATION\s*\(\s*\x27[^\x27]*\x27\s*,\s*\x27[^\x27]*\x27\s*,\s*" + re.escape(prod_id), text)
        if not pdf: return [], []
        pdf_id = pdf.group(1)
        pd = re.search(r"(#[0-9]+)\s*=\s*PRODUCT_DEFINITION\s*\(\s*\x27[^\x27]*\x27\s*,\s*\x27[^\x27]*\x27\s*,\s*" + re.escape(pdf_id), text)
        if not pd: return [], []
        pd_id = pd.group(1)
        pds = re.search(r"(#[0-9]+)\s*=\s*PRODUCT_DEFINITION_SHAPE\s*\(\s*\x27[^\x27]*\x27\s*,\s*\x27[^\x27]*\x27\s*,\s*" + re.escape(pd_id), text)
        if not pds: return [], []
        pds_id = pds.group(1)
        sdr = re.search(r"SHAPE_DEFINITION_REPRESENTATION\s*\(\s*" + re.escape(pds_id) + r"\s*,\s*(#[0-9]+)\s*\)", text)
        if not sdr: return [], []
        sr_id = sdr.group(1)

        solids = []
        faces = []
        sr_match = re.search(re.escape(sr_id) + r"\s*=\s*(?:[A-Z_]*SHAPE_REPRESENTATION)\s*\(\s*\x27[^\x27]*\x27\s*,\s*\(([^)]+)\)", text)
        if sr_match:
            items = [item.strip() for item in sr_match.group(1).split(",")]
            for item in items:
                m_msb = re.search(re.escape(item) + r"\s*=\s*MANIFOLD_SOLID_BREP\s*\(\s*\x27[^\x27]*\x27\s*,\s*(#[0-9]+)\s*\)", text)
                if m_msb:
                    solids.append(item)
                    shell_id = m_msb.group(1)
                    m_cs = re.search(re.escape(shell_id) + r"\s*=\s*CLOSED_SHELL\s*\(\s*\x27[^\x27]*\x27\s*,\s*\(([^)]+)\)", text)
                    if m_cs:
                        for f_id in m_cs.group(1).split(","):
                            faces.append(f_id.strip())
        return solids, faces

    max_id = max([int(x) for x in re.findall(r"#([0-9]+)\s*=", text)])
    new_entries = []

    for prod_name, rgb in product_colors.items():
        solids, faces = find_solids_and_faces_for_product(prod_name)
        if not faces:
            continue
        max_id += 1; col_id = f"#{max_id}"
        max_id += 1; fsa_id = f"#{max_id}"
        max_id += 1; fstyle_id = f"#{max_id}"
        max_id += 1; ssfa_id = f"#{max_id}"
        max_id += 1; sss_id = f"#{max_id}"
        max_id += 1; ssu_id = f"#{max_id}"
        max_id += 1; pds_id = f"#{max_id}"

        new_entries.append(f"{col_id} = COLOUR_RGB('{prod_name}', {rgb[0]:.6f}, {rgb[1]:.6f}, {rgb[2]:.6f});\n")
        new_entries.append(f"{fsa_id} = FILL_AREA_STYLE_COLOUR('', {col_id});\n")
        new_entries.append(f"{fstyle_id} = FILL_AREA_STYLE('', ({fsa_id}));\n")
        new_entries.append(f"{ssfa_id} = SURFACE_STYLE_FILL_AREA({fstyle_id});\n")
        new_entries.append(f"{sss_id} = SURFACE_SIDE_STYLE('', ({ssfa_id}));\n")
        new_entries.append(f"{ssu_id} = SURFACE_STYLE_USAGE(.BOTH., {sss_id});\n")
        new_entries.append(f"{pds_id} = PRESENTATION_STYLE_ASSIGNMENT(({ssu_id}));\n")

        for f_id in faces:
            max_id += 1
            new_entries.append(f"#{max_id} = STYLED_ITEM('color', ({pds_id}), {f_id});\n")

    endsec_idx = text.rfind("ENDSEC;")
    if endsec_idx != -1:
        text = text[:endsec_idx] + "".join(new_entries) + text[endsec_idx:]
        with open(step_path, "w") as f:
            f.write(text)

colors = {
    "SwitchBody": (0.12, 0.12, 0.12),
    "Plunger": (0.95, 0.95, 0.95),
    "ActuatorLever": (0.85, 0.85, 0.88),
    "Pins": (0.82, 0.82, 0.85)
}

# Export and colorize for both output directories
for d in out_dirs:
    sp = str(d / "TK-0013-R.step")
    Import.export([body_obj, plunger_obj, lever_obj, pins_obj], sp)
    colorize_step_file(sp, colors)
    print(f"Exported & colorized STEP: {sp}")

# Generate matching VRML (.wrl) file
wrl_content = """#VRML V2.0 utf8
# DEALON TK-0013-R Right-Angle Detector Switch 3D Model
# Accurately aligned to footprint pads at (0, 0), positive Y_fp (negative Y_3D) actuation
Transform {
  scale 0.3937007874 0.3937007874 0.3937007874
  children [
    # Switch Body (Black PA66)
    Transform {
      translation 0.0 -5.80 2.45
      children [
        Shape {
          appearance Appearance {
            material Material {
              diffuseColor 0.12 0.12 0.12
              specularColor 0.25 0.25 0.25
              shininess 0.2
            }
          }
          geometry Box { size 8.30 6.20 2.70 }
        }
      ]
    }
    # White Plunger Button
    Transform {
      translation -1.50 -9.20 2.45
      children [
        Shape {
          appearance Appearance {
            material Material {
              diffuseColor 0.95 0.95 0.95
              specularColor 0.3 0.3 0.3
              shininess 0.3
            }
          }
          geometry Cylinder { radius 0.60 height 0.80 }
        }
      ]
    }
    # Stainless Steel Actuator Lever
    Transform {
      translation 0.0 -10.60 2.45
      rotation 0 0 1 -0.46
      children [
        Shape {
          appearance Appearance {
            material Material {
              diffuseColor 0.85 0.85 0.88
              specularColor 0.8 0.8 0.85
              shininess 0.7
            }
          }
          geometry Box { size 7.20 0.35 2.20 }
        }
      ]
    }
    # Pin 1 (COM)
    Transform {
      translation -2.50 -1.35 1.10
      children [
        Shape {
          appearance Appearance {
            material Material {
              diffuseColor 0.82 0.82 0.85
              specularColor 0.7 0.7 0.7
              shininess 0.6
            }
          }
          geometry Box { size 1.20 2.70 0.40 }
        }
      ]
    }
    # Pin 2 (NO)
    Transform {
      translation 0.0 -1.35 1.10
      children [
        Shape {
          appearance Appearance {
            material Material {
              diffuseColor 0.82 0.82 0.85
              specularColor 0.7 0.7 0.7
              shininess 0.6
            }
          }
          geometry Box { size 1.20 2.70 0.40 }
        }
      ]
    }
    # Pin 3 (NC)
    Transform {
      translation 2.50 -1.35 1.10
      children [
        Shape {
          appearance Appearance {
            material Material {
              diffuseColor 0.82 0.82 0.85
              specularColor 0.7 0.7 0.7
              shininess 0.6
            }
          }
          geometry Box { size 1.20 2.70 0.40 }
        }
      ]
    }
  ]
}
"""

for d in out_dirs:
    wp = d / "TK-0013-R.wrl"
    with open(wp, "w") as f:
        f.write(wrl_content)
    print(f"Exported VRML: {wp}")

print("All TK-0013-R STEP and WRL models successfully generated and verified.")
