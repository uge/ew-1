#!/usr/bin/env python3
import sys
import os
import shutil
import re
import pcbnew
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pcb_file = ROOT / "pi5_corona_hv.kicad_pcb"
pro_file = ROOT / "pi5_corona_hv.kicad_pro"
pro_bak = ROOT / "pi5_corona_hv.kicad_pro.bak"
pretty_dir = ROOT / "ionic_thrust_hv.pretty"

STEP_MAPPING = {
    # 1. HV Disc Capacitors C100-C111: Z offset +6.8mm to raise body above board surface
    "CAP-TH_L15.0-W4.0-P10.00-D0.6": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/CAP-TH_L15.0-W4.0-P10.00-D0.6.step",
        "offset": (0.0, 0.0, 6.8),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
    # 2. HV Ballast Resistors R20-R29: Z offset +2.25mm to raise body above board surface
    "RES-TH_BD3.5-L9.5-P13.50-D0.6": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/RES-TH_BD3.5-L9.5-P13.50-D0.6.step",
        "offset": (0.0, 0.0, 2.25),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
    # 3. Resonant Film Capacitor C11: X +7.5, Y -5.0, Z +7.9mm to sit flush on board surface
    "Film_KYET_18x10mm_P15mm": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/Film_KYET_18x10mm_P15mm.step",
        "offset": (7.5, -5.0, 7.9),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
    # 4. Sunmate 2CL75 HV Diodes D10-D21: True solid STEP model (body sits at Z=1.8mm, 0.3mm above PCB)
    "Sunmate_2CL75_D3_L12_P26": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/Sunmate_2CL75_D3_L12_P26.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
    # 5. 0603 Capacitors C13-C16: Official KiCad 10 0603 model (Z sits flush on pads)
    "C0603": {
        "step": "${KICAD10_3DMODEL_DIR}/Capacitor_SMD.3dshapes/C_0603_1608Metric.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
    # 6. 0603 Resistors R7-R9, R91, R92
    "R0603": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/R0603.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 270.0),
    },
    # 7. SOT-23-3 D1, D4
    "SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/SOT-23-3P_L2.9-W1.3-H1.0-LS2.4-P0.95.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 180.0),
    },
    # 8. SOT-23-5 U4
    "SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/SOT-23-5_L2.9-W1.6-H1.1-LS2.8-P0.95.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 180.0),
    },
    # 9. DEALON TK-0013-R Switch S3-S6
    "SW_TK-0013-R": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/TK-0013-R.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
    # 10. Coilcraft FL2015 Package 1 T1
    "Coilcraft_FL2015_Package1_SMT": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/Coilcraft_FL2015_Package1_SMT.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
    # 11. D_SOD-323 D3
    "D_SOD-323": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/D_SOD-323.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
    # 12. Texas_RPW0010A U9
    "Texas_RPW0010A_VQFN-HR-10_2x2mm": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/Texas_RPW0010A_VQFN-HR-10_2x2mm.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
    # 13. USB-C J3
    "USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
    # 14. HTSSOP-16 U2
    "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask3x3mm_ThermalVias": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
    # 15. AMS TSL2591 U8
    "AMS_TSL25911FN": {
        "step": "${KIPRJMOD}/ionic_thrust_hv.3dshapes/DFN-6_2x2.4mm_P0.65mm.step",
        "offset": (0.0, 0.0, 0.0),
        "scale": (1.0, 1.0, 1.0),
        "rotate": (0.0, 0.0, 0.0),
    },
}

print(f"Loading {pcb_file}...")
b = pcbnew.LoadBoard(str(pcb_file))

updated_refs = []
total_fp = 0

for fp in b.GetFootprints():
    total_fp += 1
    ref = fp.GetReference()
    fpid_name = fp.GetFPID().GetUniStringLibItemName()
    
    mapping = None
    for k, v in STEP_MAPPING.items():
        if k in fpid_name:
            mapping = v
            break
            
    if mapping:
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = mapping["step"]
        m.m_Offset = pcbnew.VECTOR3D(*mapping["offset"])
        m.m_Scale = pcbnew.VECTOR3D(*mapping["scale"])
        m.m_Rotation = pcbnew.VECTOR3D(*mapping["rotate"])
        
        fp.Models().clear()
        fp.Models().push_back(m)
        updated_refs.append(ref)

print(f"Updated 3D models for {len(updated_refs)} footprints (out of {total_fp}):")
print(f"  {', '.join(sorted(updated_refs))}")

# Backup kicad_pro verbatim before save
shutil.copy2(str(pro_file), str(pro_bak))
pcbnew.SaveBoard(str(pcb_file), b)
# Restore kicad_pro verbatim
shutil.copy2(str(pro_bak), str(pro_file))
pro_bak.unlink()

print("Board successfully updated and saved with verbatim kicad_pro!")

# Also sync ionic_thrust_hv.pretty footprint files
print("\nSyncing library .kicad_mod files in ionic_thrust_hv.pretty...")
for k, mapping in STEP_MAPPING.items():
    mod_name = k if k.endswith(".kicad_mod") else f"{k}.kicad_mod"
    fpath = pretty_dir / mod_name
    if not fpath.exists():
        continue
    content = fpath.read_text()
    content_clean = re.sub(r"\s*\(model\s+[^\)]*(\([^\)]*\)\s*)*\)", "", content)
    content_clean = content_clean.rstrip()
    if content_clean.endswith(")"):
        content_clean = content_clean[:-1].rstrip()
    
    offset, scale, rotate = mapping["offset"], mapping["scale"], mapping["rotate"]
    model_sexpr = f"""  (model "{mapping['step']}"
    (offset (xyz {offset[0]} {offset[1]} {offset[2]}))
    (scale (xyz {scale[0]} {scale[1]} {scale[2]}))
    (rotate (xyz {rotate[0]} {rotate[1]} {rotate[2]}))
  )
)
"""
    fpath.write_text(content_clean + "\n" + model_sexpr)
    print(f"  Synced {mod_name}")

print("Library sync complete!")
