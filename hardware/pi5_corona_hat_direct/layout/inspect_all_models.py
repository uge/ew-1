import FreeCAD, Part, os
from pathlib import Path

shapes_dir = Path("ionic_thrust_hv.3dshapes")
kicad10_dir = Path("/usr/share/kicad/3dmodels")

models_to_check = [
    ("CAP-TH (C100-C111)", shapes_dir / "CAP-TH_L15.0-W4.0-P10.00-D0.6.step"),
    ("RES-TH (R20-R29)", shapes_dir / "RES-TH_BD3.5-L9.5-P13.50-D0.6.step"),
    ("Film_KYET (C11)", shapes_dir / "Film_KYET_18x10mm_P15mm.step"),
    ("Radial C60/C70", kicad10_dir / "Capacitor_THT.3dshapes/CP_Radial_D5.0mm_P2.00mm.step"),
    ("USB-C (J3)", shapes_dir / "USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A.step"),
    ("eFuse (U9)", shapes_dir / "Texas_RPW0010A_VQFN-HR-10_2x2mm.step"),
    ("HTSSOP-16 (U2)", shapes_dir / "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm.step"),
    ("SOD-323 (D3)", shapes_dir / "D_SOD-323.step"),
    ("C0603", shapes_dir / "C0603_L1.6-W0.8-H0.8.step"),
    ("R0603", shapes_dir / "R0603.step"),
    ("SOT-23-3 (D1/D4)", shapes_dir / "SOT-23-3P_L2.9-W1.3-H1.0-LS2.4-P0.95.step"),
    ("SOT-23-5 (U4)", shapes_dir / "SOT-23-5_L2.9-W1.6-H1.1-LS2.8-P0.95.step"),
    ("BME280 (U5)", kicad10_dir / "Package_LGA.3dshapes/Bosch_LGA-8_2.5x2.5mm_P0.65mm_ClockwisePinNumbering.step"),
    ("ADS1115 (U6)", kicad10_dir / "Package_SO.3dshapes/TSSOP-10_3x3mm_P0.5mm.step"),
    ("QFN-24 (U7)", kicad10_dir / "Package_DFN_QFN.3dshapes/QFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm.step"),
    ("AO4262E (Q1)", kicad10_dir / "Package_SO.3dshapes/SO-8_3.9x4.9mm_P1.27mm.step"),
    ("Relay G6K (K1)", kicad10_dir / "Relay_SMD.3dshapes/Relay_DPDT_Omron_G6K-2F-Y.step"),
    ("J2 40-pin", kicad10_dir / "Connector_PinSocket_2.54mm.3dshapes/PinSocket_2x20_P2.54mm_Vertical.step"),
]

for label, p in models_to_check:
    if not p.exists():
        print(f"[{label}] NOT FOUND: {p}")
        continue
    try:
        s = Part.read(str(p))
        b = s.BoundBox
        print(f"[{label}]: X=[{b.XMin:6.2f}, {b.XMax:6.2f}] Y=[{b.YMin:6.2f}, {b.YMax:6.2f}] Z=[{b.ZMin:6.2f}, {b.ZMax:6.2f}]")
    except Exception as e:
        print(f"[{label}] ERROR: {e}")
