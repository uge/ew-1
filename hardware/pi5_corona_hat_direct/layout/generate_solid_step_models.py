import FreeCAD, Part, Import
from pathlib import Path
import re, shutil

out_dir = Path("/home/uge/Development/ew-1/hardware/pi5_corona_hat_direct/ionic_thrust_hv.3dshapes")
root_3d_dir = Path("/home/uge/Development/ew-1/hardware/ionic_thrust_hv.3dshapes")

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
        sr = re.search(re.escape(sr_id) + r"\s*=\s*[A-Z_]+\s*\(\s*\x27[^\x27]*\x27\s*,\s*\((.*?)\)\s*,", text, re.DOTALL)
        items = [it.strip() for it in sr.group(1).split(",")]
        
        solids = []
        faces = []
        for it in items:
            if re.search(re.escape(it) + r"\s*=\s*MANIFOLD_SOLID_BREP", text):
                solids.append(it)
                m = re.search(re.escape(it) + r"\s*=\s*MANIFOLD_SOLID_BREP\s*\(\s*\x27[^\x27]*\x27\s*,\s*(#[0-9]+)\s*\);", text)
                if m:
                    shell = m.group(1)
                    sm = re.search(re.escape(shell) + r"\s*=\s*CLOSED_SHELL\s*\(\s*\x27[^\x27]*\x27\s*,\s*\((.*?)\)\s*\);", text, re.DOTALL)
                    if sm:
                        faces.extend([f.strip() for f in sm.group(1).split(",")])
        return solids, faces

    all_ids = [int(x) for x in re.findall(r"#([0-9]+)", text)]
    next_id = max(all_ids) + 1

    def make_style(name, r, g, b):
        nonlocal next_id
        col_id = f"#{next_id}"; next_id += 1
        fasc_id = f"#{next_id}"; next_id += 1
        fas_id = f"#{next_id}"; next_id += 1
        ssfa_id = f"#{next_id}"; next_id += 1
        sss_id = f"#{next_id}"; next_id += 1
        ssu_id = f"#{next_id}"; next_id += 1
        psa_id = f"#{next_id}"; next_id += 1
        
        lines = [
            f"{col_id} = COLOUR_RGB(\x27{name}\x27, {r:.6f}, {g:.6f}, {b:.6f});",
            f"{fasc_id} = FILL_AREA_STYLE_COLOUR(\x27\x27, {col_id});",
            f"{fas_id} = FILL_AREA_STYLE(\x27\x27, ({fasc_id}));",
            f"{ssfa_id} = SURFACE_STYLE_FILL_AREA({fas_id});",
            f"{sss_id} = SURFACE_SIDE_STYLE(\x27\x27, ({ssfa_id}));",
            f"{ssu_id} = SURFACE_STYLE_USAGE(.BOTH., {sss_id});",
            f"{psa_id} = PRESENTATION_STYLE_ASSIGNMENT(({ssu_id}));",
        ]
        return psa_id, lines

    new_lines = []
    for prod_name, (r, g, b) in product_colors.items():
        solids, faces = find_solids_and_faces_for_product(prod_name)
        if not solids and not faces:
            continue
        psa_id, lines = make_style(prod_name, r, g, b)
        new_lines.extend(lines)
        for item in solids + faces:
            si_id = f"#{next_id}"; next_id += 1
            new_lines.append(f"{si_id} = STYLED_ITEM(\x27color\x27, ({psa_id}), {item});")

    endsec_pos = text.rfind("ENDSEC;")
    colored_step = text[:endsec_pos] + "\n".join(new_lines) + "\n" + text[endsec_pos:]

    with open(step_path, "w") as f:
        f.write(colored_step)


# ==========================================
# 1. Sunmate 2CL75 Axial Diode with Cathode Orientation Bar
# ==========================================
print("Generating detailed solid Sunmate 2CL75 with Cathode Orientation Bar...")
doc_diode = FreeCAD.newDocument("Sunmate2CL75")

# Body cylinder with chamfered ends
b_main = Part.makeCylinder(1.5, 9.8, FreeCAD.Vector(-4.0, 0, 1.8), FreeCAD.Vector(1, 0, 0))
b_cone_pos = Part.makeCone(1.5, 1.3, 0.2, FreeCAD.Vector(5.8, 0, 1.8), FreeCAD.Vector(1, 0, 0))
b_end = Part.makeCylinder(1.5, 0.4, FreeCAD.Vector(-5.8, 0, 1.8), FreeCAD.Vector(1, 0, 0))
b_cone_neg = Part.makeCone(1.3, 1.5, 0.2, FreeCAD.Vector(-6.0, 0, 1.8), FreeCAD.Vector(1, 0, 0))
body_shape = b_main.fuse(b_cone_pos).fuse(b_end).fuse(b_cone_neg)
body_obj = doc_diode.addObject("Part::Feature", "Body")
body_obj.Shape = body_shape

# Cathode Orientation Bar: 1.4mm wide, 1.53mm radius (0.03mm raised ridge) at X = -5.4 to -4.0
band_shape = Part.makeCylinder(1.53, 1.4, FreeCAD.Vector(-5.4, 0, 1.8), FreeCAD.Vector(1, 0, 0))
band_obj = doc_diode.addObject("Part::Feature", "CathodeBand")
band_obj.Shape = band_shape

# Leads: r = 0.3mm wire with smooth formed corners
l_horiz = Part.makeCylinder(0.3, 6.2, FreeCAD.Vector(-12.2, 0, 1.8), FreeCAD.Vector(1, 0, 0))
r_horiz = Part.makeCylinder(0.3, 6.2, FreeCAD.Vector(6.0, 0, 1.8), FreeCAD.Vector(1, 0, 0))
l_vert = Part.makeCylinder(0.3, 3.5, FreeCAD.Vector(-13.0, 0, -2.5), FreeCAD.Vector(0, 0, 1))
r_vert = Part.makeCylinder(0.3, 3.5, FreeCAD.Vector(13.0, 0, -2.5), FreeCAD.Vector(0, 0, 1))
l_corner = Part.makeSphere(0.32, FreeCAD.Vector(-13.0, 0, 1.8))
r_corner = Part.makeSphere(0.32, FreeCAD.Vector(13.0, 0, 1.8))
l_h_ext = Part.makeCylinder(0.3, 0.8, FreeCAD.Vector(-13.0, 0, 1.8), FreeCAD.Vector(1, 0, 0))
r_h_ext = Part.makeCylinder(0.3, 0.8, FreeCAD.Vector(12.2, 0, 1.8), FreeCAD.Vector(1, 0, 0))
l_v_ext = Part.makeCylinder(0.3, 0.8, FreeCAD.Vector(-13.0, 0, 1.0), FreeCAD.Vector(0, 0, 1))
r_v_ext = Part.makeCylinder(0.3, 0.8, FreeCAD.Vector(13.0, 0, 1.0), FreeCAD.Vector(0, 0, 1))
leads_shape = l_horiz.fuse(r_horiz).fuse(l_vert).fuse(r_vert).fuse(l_corner).fuse(r_corner).fuse(l_h_ext).fuse(r_h_ext).fuse(l_v_ext).fuse(r_v_ext)
leads_obj = doc_diode.addObject("Part::Feature", "Leads")
leads_obj.Shape = leads_shape

diode_file = str(out_dir / "Sunmate_2CL75_D3_L12_P26.step")
Import.export([body_obj, band_obj, leads_obj], diode_file)
colorize_step_file(diode_file, {
    "Body": (0.10, 0.10, 0.10),
    "CathodeBand": (0.98, 0.98, 0.98),
    "Leads": (0.82, 0.82, 0.85)
})
print("Sunmate 2CL75 exported with Cathode Orientation Bar.")

# ==========================================
# 2. DEALON TK-0013-R Switch
# ==========================================
print("Generating solid TK-0013-R...")
doc_sw = FreeCAD.newDocument("TK0013R")
sw_body = Part.makeBox(8.3, 6.2, 2.7, FreeCAD.Vector(-4.15, 2.7, 0.1))
body_sw = doc_sw.addObject("Part::Feature", "SwitchBody")
body_sw.Shape = sw_body

sw_lever = Part.makeBox(7.0, 3.6, 0.3, FreeCAD.Vector(-3.5, 8.9, 1.0))
lever_obj = doc_sw.addObject("Part::Feature", "ActuatorLever")
lever_obj.Shape = sw_lever

pins = []
for px in [-2.5, 0.0, 2.5]:
    ph = Part.makeBox(0.6, 2.7, 0.3, FreeCAD.Vector(px - 0.3, 0.0, 0.5))
    pv = Part.makeBox(0.6, 0.6, 2.5, FreeCAD.Vector(px - 0.3, -0.3, -2.0))
    pins.append(ph.fuse(pv))

all_pins = pins[0].fuse(pins[1]).fuse(pins[2])
pins_obj = doc_sw.addObject("Part::Feature", "Pins")
pins_obj.Shape = all_pins

sw_file = str(out_dir / "TK-0013-R.step")
Import.export([body_sw, lever_obj, pins_obj], sw_file)
colorize_step_file(sw_file, {
    "SwitchBody": (0.12, 0.12, 0.12),
    "ActuatorLever": (0.85, 0.85, 0.88),
    "Pins": (0.80, 0.82, 0.85)
})
print("TK-0013-R exported.")

# ==========================================
# 3. Coilcraft FL2015 Package 1
# ==========================================
print("Generating solid Coilcraft FL2015...")
doc_fl = FreeCAD.newDocument("CoilcraftFL2015")
core_box = Part.makeBox(20.96, 15.49, 6.5, FreeCAD.Vector(-10.48, -7.745, 1.2))
core_obj = doc_fl.addObject("Part::Feature", "FerriteCore")
core_obj.Shape = core_box

base_box = Part.makeBox(21.4, 15.6, 1.0, FreeCAD.Vector(-10.7, -7.8, 0.2))
base_obj = doc_fl.addObject("Part::Feature", "PlasticBase")
base_obj.Shape = base_box

coil_cyl = Part.makeCylinder(4.5, 14.0, FreeCAD.Vector(0, -7.0, 4.0), FreeCAD.Vector(0, 1, 0))
coil_obj = doc_fl.addObject("Part::Feature", "CopperCoil")
coil_obj.Shape = coil_cyl

pads = []
for py in [-6.25, -3.75, -1.25, 1.25, 3.75, 6.25]:
    foot = Part.makeBox(1.905, 1.27, 0.2, FreeCAD.Vector(11.4325 - 0.9525, py - 0.635, 0.0))
    leg = Part.makeBox(0.8, 0.8, 0.6, FreeCAD.Vector(10.7 - 0.2, py - 0.4, 0.1))
    pads.append(foot.fuse(leg))

for py in [-6.25, -3.75, 3.75, 6.25]:
    foot = Part.makeBox(1.905, 1.27, 0.2, FreeCAD.Vector(-11.4325 - 0.9525, py - 0.635, 0.0))
    leg = Part.makeBox(0.8, 0.8, 0.6, FreeCAD.Vector(-10.7 - 0.6, py - 0.4, 0.1))
    pads.append(foot.fuse(leg))

all_pads = pads[0]
for p in pads[1:]:
    all_pads = all_pads.fuse(p)
pads_obj = doc_fl.addObject("Part::Feature", "TerminalPads")
pads_obj.Shape = all_pads

fl_file = str(out_dir / "Coilcraft_FL2015_Package1_SMT.step")
Import.export([core_obj, base_obj, coil_obj, pads_obj], fl_file)
colorize_step_file(fl_file, {
    "FerriteCore": (0.18, 0.18, 0.20),
    "PlasticBase": (0.10, 0.10, 0.10),
    "CopperCoil": (0.72, 0.35, 0.05),
    "TerminalPads": (0.82, 0.82, 0.85)
})
print("Coilcraft FL2015 exported.")

# ==========================================
# 4. DFN-6 2x2.4mm P0.65mm (TSL2591)
# ==========================================
print("Generating solid DFN-6 for TSL2591...")
doc_dfn = FreeCAD.newDocument("DFN6")
dfn_body = Part.makeBox(2.0, 2.4, 0.65, FreeCAD.Vector(-1.0, -1.2, 0.0))
body_dfn_obj = doc_dfn.addObject("Part::Feature", "ICBody")
body_dfn_obj.Shape = dfn_body

opt_window = Part.makeCylinder(0.45, 0.1, FreeCAD.Vector(0, 0, 0.56), FreeCAD.Vector(0, 0, 1))
opt_obj = doc_dfn.addObject("Part::Feature", "OpticWindow")
opt_obj.Shape = opt_window

dfn_pads = []
for px in [-0.85, 0.85]:
    for py in [-0.65, 0.0, 0.65]:
        p = Part.makeBox(0.3, 0.4, 0.05, FreeCAD.Vector(px - 0.15, py - 0.2, 0.0))
        dfn_pads.append(p)

all_dfn_pads = dfn_pads[0]
for p in dfn_pads[1:]:
    all_dfn_pads = all_dfn_pads.fuse(p)
dfn_pads_obj = doc_dfn.addObject("Part::Feature", "DFNPads")
dfn_pads_obj.Shape = all_dfn_pads

dfn_file = str(out_dir / "DFN-6_2x2.4mm_P0.65mm.step")
Import.export([body_dfn_obj, opt_obj, dfn_pads_obj], dfn_file)
colorize_step_file(dfn_file, {
    "ICBody": (0.10, 0.10, 0.10),
    "OpticWindow": (0.05, 0.45, 0.70),
    "DFNPads": (0.92, 0.85, 0.50)
})
print("DFN-6 exported.")

# Sync all to root
for fname in ["Sunmate_2CL75_D3_L12_P26.step", "TK-0013-R.step", "Coilcraft_FL2015_Package1_SMT.step", "DFN-6_2x2.4mm_P0.65mm.step"]:
    src = out_dir / fname
    dst = root_3d_dir / fname
    shutil.copyfile(src, dst)
    print(f"Synced {fname} to {root_3d_dir}")

print("ALL SOLID STEP MODELS CREATED & COLORIZED WITH DETAILS!")
