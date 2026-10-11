#!/usr/bin/env python3
"""
Clean migration script for HUSB238A & AO4407A.
"""
import re, json, subprocess, uuid
from pathlib import Path

ROOT = Path("/home/uge/Development/ew-1/hardware/pi5_corona_hat_direct")
PCB_IN = ROOT / "pi5_corona_hv.kicad_pcb.bak"
PCB_OUT = ROOT / "pi5_corona_hv.kicad_pcb"
REPORT_JSON = ROOT / "drc_clean.json"

text = PCB_IN.read_text()

def find_footprint_by_ref(t, ref):
    ref_str = f'(property "Reference" "{ref}"'
    idx = t.find(ref_str)
    assert idx != -1, f"Reference {ref} not found!"
    start = t.rfind("\t(footprint ", 0, idx)
    assert start != -1, f"Start of footprint for {ref} not found!"
    end = t.find("\n\t)", idx) + 3
    assert end != -1, f"End of footprint for {ref} not found!"
    return start, end, t[start:end]

def replace_footprint(t, ref, new_fp):
    s, e, _ = find_footprint_by_ref(t, ref)
    return t[:s] + new_fp + t[e:]

# ---------------------------------------------------------
# Step 1: Footprints
# ---------------------------------------------------------

# 1. U7 (QFN-16 3x3mm)
qfn16_template = (ROOT / "ionic_thrust_hv.pretty/QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm.kicad_mod").read_text()

u7_props = """
		(layer "F.Cu")
		(uuid "9c001a06-7c4c-4800-ad13-4c508cc0c143")
		(at 82 72 0)
		(descr "QFN, 16 Pin 3x3mm, 0.5mm pitch")
		(tags "QFN NoLead")
		(property "Reference" "U7"
			(at 0 -2.83 0)
			(layer "F.SilkS")
			(uuid "1d972e51-ec43-4cfb-a3b4-72a24624feb7")
			(effects (font (size 0.9 0.9) (thickness 0.15)))
		)
		(property "Value" "HUSB238A"
			(at 0 2.83 0)
			(layer "F.Fab")
			(hide yes)
			(uuid "9424541e-9f69-48c9-becb-5ebaf32f8988")
			(effects (font (size 1 1) (thickness 0.15)))
		)
		(property "Datasheet" "https://datasheet.lcsc.com/lcsc/2309131604_Hynetek-Semiconductor-HUSB238A-BB001-QN16R_C24833806.pdf"
			(at 0 0 0) (layer "F.Fab") (hide yes) (uuid "faca062f-cd2b-4b99-ab44-74974b8a85bb")
			(effects (font (size 1.27 1.27)))
		)
		(property "Description" "USB-PD Sink Controller with PPS, QFN-16 3x3mm"
			(at 0 0 0) (layer "F.Fab") (hide yes) (uuid "d6403911-3cbc-40ca-9f7b-374a0d26b9be")
			(effects (font (size 1.27 1.27)))
		)
		(property "LCSC" "C24833806"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "4e04be65-badd-4263-9cc7-5c9463244b91")
			(effects (font (size 1.27 1.27) (thickness 0.15)))
		)
		(property "JLCPCB Part #" "C24833806"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "1712e982-1b39-4998-a3da-9e987a296652")
			(effects (font (size 1.27 1.27) (thickness 0.15)))
		)
		(property "Manufacturer" "Hynetek Semiconductor"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "dbea364a-a4dc-4fda-82da-b757d49f6051")
			(effects (font (size 1.27 1.27) (thickness 0.15)))
		)
		(property "MPN" "HUSB238A-BB001-QN16R"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "1f2b1617-3364-40c2-8505-d33661f8c128")
			(effects (font (size 1.27 1.27) (thickness 0.15)))
		)
		(property "JLCPCB Library" "Extended"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "3a1700e0-bdc1-4679-9732-5aafee3d7404")
			(effects (font (size 1.27 1.27) (thickness 0.15)))
		)
		(property "Procurement Status" "CATALOG_MATCH"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "9fbb59d1-3f27-4f23-b121-70cf2dd17f80")
			(effects (font (size 1.27 1.27) (thickness 0.15)))
		)
		(property "Procurement Notes" "HUSB238A-BB001-QN16R QFN-16 (3x3mm) USB PD Sink Controller with PPS"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "4aa2bee9-e0ce-4102-8b3e-b77d68a9acd5")
			(effects (font (size 1.27 1.27) (thickness 0.15)))
		)
		(property "Catalog URL" "https://jlcpcb.com/partdetail/C24833806"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "7e4804b6-2241-410c-9b0f-f21235134336")
			(effects (font (size 1.27 1.27)))
		)
		(property "Catalog Checked" "2026-10-10"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "0da063f5-9627-4d24-ab83-19aa7e11f02f")
			(effects (font (size 1.27 1.27)))
		)
		(property "Assembly Process" "smtWeld"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "e130bea1-9088-4b0b-8872-55f75c7a6518")
			(effects (font (size 1.27 1.27) (thickness 0.15)))
		)
		(property "LCSC Part" "C24833806"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "810ea532-baf0-4c52-a2c1-1416b679c6cd")
			(effects (font (size 1.27 1.27) (thickness 0.15)))
		)
		(property "Sheetname" "01_power_mcu"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "c4c1ffc7-2196-42d6-ad75-b1cca4b2bf66")
			(effects (font (size 1.27 1.27) (thickness 0.15)))
		)
		(property "Sheetfile" "01_power_mcu.kicad_sch"
			(at 0 0 0) (layer "F.SilkS") (hide yes) (uuid "8be80ee6-0209-4994-bae1-1fb3c66379c4")
			(effects (font (size 1.27 1.27) (thickness 0.15)))
		)
		(path "/1709378f-a8a2-4798-b42d-99352f87d149/45bed891-6b2c-4ccd-b433-046c9ecf22ab")
		(attr smd)
		(duplicate_pad_numbers_are_jumpers no)
"""

lines = qfn16_template.splitlines()
fp_start = [i for i, l in enumerate(lines) if l.strip().startswith("(fp_line")][0]
qfn16_core = "\n".join(lines[fp_start:-1])

pad_nets = {
    "1": "/01_power_mcu/USB_DP",
    "2": "/01_power_mcu/USB_DN",
    "3": "/01_power_mcu/CC1",
    "4": "/01_power_mcu/CC2",
    "5": "3V3",
    "6": "/01_power_mcu/DEBUG_N",
    "7": "unconnected-(U7-EN_HVDCP-Pad7)",
    "8": "/01_power_mcu/ADDR",
    "9": "/01_power_mcu/SDA",
    "10": "/01_power_mcu/SCL",
    "11": "unconnected-(U7-INT_N-Pad11)",
    "12": "GND",
    "13": "unconnected-(U7-FAULT-Pad13)",
    "14": "GND",
    "15": "/01_power_mcu/EN_DRV",
    "16": "/01_power_mcu/VBUS_IN",
    "17": "GND",
}

for pad_num, net_name in pad_nets.items():
    if pad_num == "17":
        pattern = rf'(\(pad "17" smd rect\n\s*\(at 0 0\)\n\s*\(size 1.7 1.7\)\n\s*\(property pad_prop_heatsink\)\n\s*\(layers "F.Cu" "F.Mask"\)\n\s*\(zone_connect 2\))'
        repl = rf'\1\n\t\t(net "{net_name}")'
        qfn16_core = re.sub(pattern, repl, qfn16_core)
    else:
        pattern = rf'(\(pad "{pad_num}" smd roundrect[\s\S]*?\(roundrect_rratio [0-9.]+\))'
        repl = rf'\1\n\t\t(net "{net_name}")'
        qfn16_core = re.sub(pattern, repl, qfn16_core)

new_u7_footprint = f'\t(footprint "ionic_thrust_hv:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm"{u7_props}\n{qfn16_core}\n\t)'
text = replace_footprint(text, "U7", new_u7_footprint)

# 2. Q1 (AO4407A)
_, _, q1_str = find_footprint_by_ref(text, "Q1")
q1_str = re.sub(r'\(property "Value" "[^"]*"', '(property "Value" "AO4407A"', q1_str)
q1_str = re.sub(r'\(property "Datasheet" "[^"]*"', '(property "Datasheet" "https://jlcpcb.com/partdetail/C16072"', q1_str)
q1_str = re.sub(r'\(property "Description" "[^"]*"', '(property "Description" "P-MOSFET transistor, -30V, -12A, SO-8"', q1_str)
q1_str = re.sub(r'\(property "LCSC" "[^"]*"', '(property "LCSC" "C16072"', q1_str)
q1_str = re.sub(r'\(property "LCSC Part" "[^"]*"', '(property "LCSC Part" "C16072"', q1_str)
q1_str = re.sub(r'\(property "JLCPCB Part #" "[^"]*"', '(property "JLCPCB Part #" "C16072"', q1_str)
q1_str = re.sub(r'\(property "Manufacturer" "[^"]*"', '(property "Manufacturer" "Alpha & Omega Semicon"', q1_str)
q1_str = re.sub(r'\(property "MPN" "[^"]*"', '(property "MPN" "AO4407A"', q1_str)
q1_str = re.sub(r'\(property "JLCPCB Library" "[^"]*"', '(property "JLCPCB Library" "Basic"', q1_str)
q1_str = re.sub(r'\(property "Procurement Notes" "[^"]*"', '(property "Procurement Notes" "AO4407A P-MOSFET: S=1/2/3 on VBUS_IN, G=4 on GATE, D=5/6/7/8 on VIN_PD."', q1_str)
q1_str = re.sub(r'\(property "Catalog URL" "[^"]*"', '(property "Catalog URL" "https://jlcpcb.com/partdetail/C16072"', q1_str)
q1_str = re.sub(r'\(property "Catalog Checked" "[^"]*"', '(property "Catalog Checked" "2026-10-10"', q1_str)

q1_pad_nets = {
    "1": "/01_power_mcu/VBUS_IN",
    "2": "/01_power_mcu/VBUS_IN",
    "3": "/01_power_mcu/VBUS_IN",
    "4": "/01_power_mcu/GATE",
    "5": "/01_power_mcu/VIN_PD",
    "6": "/01_power_mcu/VIN_PD",
    "7": "/01_power_mcu/VIN_PD",
    "8": "/01_power_mcu/VIN_PD",
}
for p_num, net_name in q1_pad_nets.items():
    q1_str = re.sub(rf'(\(pad "{p_num}" smd roundrect[\s\S]*?\(net ")[^"]*("\))', rf'\1{net_name}\2', q1_str)
text = replace_footprint(text, "Q1", q1_str)

# 3. C18 (1uF 16V 0603) at (79.3 75.0 180) using proven C17 template
# Rotation 180 places Pad 1 (3V3) on the right at (80.075, 75.0) directly facing U7 Pin 5
# Pad 2 (GND) is on the left at (78.525, 75.0)
_, _, c17_orig = find_footprint_by_ref(text, "C17")
c18_fp = c17_orig
c18_fp = re.sub(r'\(uuid "[^"]*"', lambda m: f'(uuid "{uuid.uuid4()}"', c18_fp)
c18_fp = re.sub(r'\(at [0-9.-]+ [0-9.-]+(?: [0-9.-]+)?\)', '(at 79.3 75.0 180)', c18_fp, count=1)
c18_fp = c18_fp.replace(' 90)', ' 180)')
c18_fp = re.sub(r'\(property "Reference" "C17"[\s\S]*?\(at [^)]+\)', '(property "Reference" "C18"\n\t\t\t(at 0 -1.5 180)', c18_fp)
c18_fp = re.sub(r'\(property "Value" "[^"]*"', '(property "Value" "1uF 16V 10%"', c18_fp)
c18_fp = re.sub(r'\(property "Datasheet" "[^"]*"', '(property "Datasheet" "https://jlcpcb.com/partdetail/C15849"', c18_fp)
c18_fp = re.sub(r'\(property "Description" "[^"]*"', '(property "Description" "1uF 16V X7R 10% 0603"', c18_fp)
c18_fp = re.sub(r'\(property "LCSC" "[^"]*"', '(property "LCSC" "C15849"', c18_fp)
c18_fp = re.sub(r'\(property "LCSC Part" "[^"]*"', '(property "LCSC Part" "C15849"', c18_fp)
c18_fp = re.sub(r'\(property "JLCPCB Part #" "[^"]*"', '(property "JLCPCB Part #" "C15849"', c18_fp)
c18_fp = re.sub(r'\(property "Manufacturer" "[^"]*"', '(property "Manufacturer" "Samsung Electro-Mechanics"', c18_fp)
c18_fp = re.sub(r'\(property "MPN" "[^"]*"', '(property "MPN" "CL10B105KO8NNNC"', c18_fp)
c18_fp = re.sub(r'\(property "Catalog URL" "[^"]*"', '(property "Catalog URL" "https://jlcpcb.com/partdetail/C15849"', c18_fp)
c18_fp = re.sub(r'\(property "Catalog Checked" "[^"]*"', '(property "Catalog Checked" "2026-10-10"', c18_fp)
c18_fp = re.sub(r'\(path "/1709378f-a8a2-4798-b42d-99352f87d149/[^"]*"',
                '(path "/1709378f-a8a2-4798-b42d-99352f87d149/eadbe6f4-2abc-4675-81f7-984adf77948c"', c18_fp)
c18_fp = re.sub(r'(\(pad "1" smd roundrect[\s\S]*?\(net ")[^"]*("\))', r'\g<1>3V3\g<2>', c18_fp)
c18_fp = re.sub(r'(\(pad "2" smd roundrect[\s\S]*?\(net ")[^"]*("\))', r'\g<1>GND\g<2>', c18_fp)
text = replace_footprint(text, "C18", c18_fp)

# 4. R0603 helper for R14, R15, R16 (rotation 0)
_, _, r14_template = find_footprint_by_ref(text, "R14")

def make_r0603_rot0(ref, val, lcsc, mpn, desc, at_str, p1_net, p2_net, sym_uuid):
    fp = r14_template
    fp = re.sub(r'\(uuid "[^"]*"', lambda m: f'(uuid "{uuid.uuid4()}"', fp)
    fp = re.sub(r'\(at [0-9.-]+ [0-9.-]+(?: [0-9.-]+)?\)', f'(at {at_str})', fp, count=1)
    fp = re.sub(r'\(property "Reference" "[^"]*"', f'(property "Reference" "{ref}"', fp)
    fp = re.sub(r'\(property "Value" "[^"]*"', f'(property "Value" "{val}"', fp)
    fp = re.sub(r'\(property "Datasheet" "[^"]*"', f'(property "Datasheet" "https://jlcpcb.com/partdetail/{lcsc}"', fp)
    fp = re.sub(r'\(property "Description" "[^"]*"', f'(property "Description" "{desc}"', fp)
    fp = re.sub(r'\(property "LCSC" "[^"]*"', f'(property "LCSC" "{lcsc}"', fp)
    fp = re.sub(r'\(property "LCSC Part" "[^"]*"', f'(property "LCSC Part" "{lcsc}"', fp)
    fp = re.sub(r'\(property "JLCPCB Part #" "[^"]*"', f'(property "JLCPCB Part #" "{lcsc}"', fp)
    fp = re.sub(r'\(property "Manufacturer" "[^"]*"', '(property "Manufacturer" "UNI-ROYAL(Uniroyal Elec)"', fp)
    fp = re.sub(r'\(property "MPN" "[^"]*"', f'(property "MPN" "{mpn}"', fp)
    fp = re.sub(r'\(property "Catalog URL" "[^"]*"', f'(property "Catalog URL" "https://jlcpcb.com/partdetail/{lcsc}"', fp)
    fp = re.sub(r'\(property "Catalog Checked" "[^"]*"', '(property "Catalog Checked" "2026-10-10"', fp)
    fp = re.sub(r'\(path "/1709378f-a8a2-4798-b42d-99352f87d149/[^"]*"',
                f'(path "/1709378f-a8a2-4798-b42d-99352f87d149/{sym_uuid}"', fp)
    fp = re.sub(r'(\(pad "1" smd roundrect[\s\S]*?\(net ")[^"]*("\))', rf'\g<1>{p1_net}\g<2>', fp)
    fp = re.sub(r'(\(pad "2" smd roundrect[\s\S]*?\(net ")[^"]*("\))', rf'\g<1>{p2_net}\g<2>', fp)
    return fp

# R15 at (86 77 0)
r15_fp = make_r0603_rot0("R15", "1M 1%", "C22935", "0603WAF1004T5E", "1M 1% 0603 resistor",
                         "86 77 0", "/01_power_mcu/ADDR", "GND", "8b78c2a0-9975-4f9c-a94a-4426fbc0e344")
text = replace_footprint(text, "C19", r15_fp)

# R16 at (82 77 0)
r16_fp = make_r0603_rot0("R16", "1M 1%", "C22935", "0603WAF1004T5E", "1M 1% 0603 resistor",
                         "82 77 0", "/01_power_mcu/DEBUG_N", "GND", "154464fc-3f38-4753-a3b4-72cc88f9f2b6")
text = replace_footprint(text, "C20", r16_fp)

# R14 at (76 77 0)
r14_fp = make_r0603_rot0("R14", "47k 1%", "C25816", "0603WAF4702T5E", "47k 1% 0603 resistor",
                         "76 77 0", "/01_power_mcu/EN_DRV", "/01_power_mcu/GATE", "436cf7f5-c2bc-4182-9b73-f900d4256869")
text = replace_footprint(text, "R14", r14_fp)

# 5. R12 at (88.5 77.27 90) using R70 (proven 90-degree 0603 template with 0 lib mismatch)
_, _, r70_template = find_footprint_by_ref(text, "R70")
r12_fp = r70_template
r12_fp = re.sub(r'\(uuid "[^"]*"', lambda m: f'(uuid "{uuid.uuid4()}"', r12_fp)
r12_fp = re.sub(r'\(at 85 91 90\)', '(at 88.5 77.27 90)', r12_fp)
r12_fp = re.sub(r'\(property "Reference" "R70"[\s\S]*?\(effects',
                '(property "Reference" "R12"\n\t\t\t(at -2.8 0 0)\n\t\t\t(layer "F.SilkS")\n\t\t\t(uuid "' + str(uuid.uuid4()) + '")\n\t\t\t(effects', r12_fp)
r12_fp = re.sub(r'\(property "Value" "[^"]*"', '(property "Value" "100k 1%"', r12_fp)
r12_fp = re.sub(r'\(property "Description" "[^"]*"', '(property "Description" "100k 1% 0603 gate pullup resistor"', r12_fp)
r12_fp = re.sub(r'\(path "[^"]*"', '(path "/1709378f-a8a2-4798-b42d-99352f87d149/2d65ce2e-712a-420b-bc16-09faedef7afd"', r12_fp)
r12_fp = re.sub(r'(\(pad "1" smd roundrect[\s\S]*?\(net ")[^"]*("\))', r'\g<1>/01_power_mcu/GATE\g<2>', r12_fp)
r12_fp = re.sub(r'(\(pad "2" smd roundrect[\s\S]*?\(net ")[^"]*("\))', r'\g<1>/01_power_mcu/VBUS_IN\g<2>', r12_fp)
text = replace_footprint(text, "R12", r12_fp)

# 6. NTC1
_, _, ntc1_str = find_footprint_by_ref(text, "NTC1")
ntc1_str = re.sub(r'(\(pad "1" smd roundrect[\s\S]*?\(net ")[^"]*("\))', r'\g<1>unconnected-(NTC1-Pad1)\g<2>', ntc1_str)
text = replace_footprint(text, "NTC1", ntc1_str)

print("Step 1: Footprints updated.")

# ---------------------------------------------------------
# Step 2: Purge obsolete tracks & vias
# ---------------------------------------------------------
purge_nets = {
    "/01_power_mcu/V18",
    "/01_power_mcu/V5V",
    "/01_power_mcu/IFB",
    "/01_power_mcu/OTP_NTC",
}

seg_pattern = re.compile(r'\t\(segment\s+\(start\s+([0-9.-]+)\s+([0-9.-]+)\)\s+\(end\s+([0-9.-]+)\s+([0-9.-]+)\)\s+\(width\s+([0-9.-]+)\)\s+\(layer\s+"([^"]+)"\)\s+\(net\s+"([^"]+)"\)\s+\(uuid\s+"([^"]+)"\)\s+\)\n')
via_pattern = re.compile(r'\t\(via\s+\(at\s+([0-9.-]+)\s+([0-9.-]+)\)\s+\(size\s+([0-9.-]+)\)\s+\(drill\s+([0-9.-]+)\)\s+\(layers\s+"([^"]+)"\s+"([^"]+)"\)\s+\(net\s+"([^"]+)"\)\s+\(uuid\s+"([^"]+)"\)\s+\)\n')

removed_segs = 0
def seg_filter(m):
    global removed_segs
    x1, y1, x2, y2, w, layer, net, uid = m.groups()
    x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
    min_x, max_x = min(x1, x2), max(x1, x2)
    min_y, max_y = min(y1, y2), max(y1, y2)

    if net in purge_nets:
        removed_segs += 1
        return ""

    if net == "/01_power_mcu/VIN_PD":
        # Remove tracks connecting to old Q1 pads 1, 2, 3
        if (abs(min_x - 90.4) < 0.1 and min_y >= 74.0 and max_y <= 77.0) or \
           (abs(min_x - 90.75) < 0.1 and abs(max_x - 91.8) < 0.1) or \
           (abs(min_x - 91.8) < 0.1 and abs(min_y - 77.7) < 0.1):
            removed_segs += 1
            return ""
        if abs(min_x - 90.55) < 0.1 and abs(max_x - 91.80) < 0.1 and min_y >= 78.4:
            removed_segs += 1
            return ""
        if min_y < 79.0 and max_x < 85.0:
            removed_segs += 1
            return ""
        if min_y >= 76.5 and max_y <= 79.8 and min_x >= 84.0 and max_x <= 90.6:
            removed_segs += 1
            return ""

    if net == "/01_power_mcu/VBUS_IN":
        # Remove tracks connecting to old Q1 pads 5, 6, 7, 8
        if abs(min_x - 95.60) < 0.1 and min_y >= 74.0 and max_y <= 78.0:
            removed_segs += 1
            return ""
        if abs(max_x - 95.60) < 0.1 and abs(min_x - 90.35) < 0.1:
            removed_segs += 1
            return ""
        if min_y > 73.5 and max_x < 85.0:
            removed_segs += 1
            return ""
        # Remove old stub from (86.2, 73.0) to (84.4, 74.8)
        if abs(min_x - 84.40) < 0.1 and abs(max_x - 86.20) < 0.1:
            removed_segs += 1
            return ""
        # Remove old stub (79.475, 67.5) -> (86.2, 67.5) and (79.475, 67.0) -> (79.475, 67.5)
        if layer == "F.Cu" and abs(min_x - 79.475) < 0.05:
            removed_segs += 1
            return ""
        if layer == "F.Cu" and min_y >= 67.4 and max_y <= 67.6 and min_x >= 79.4 and max_x <= 86.3:
            removed_segs += 1
            return ""

    if net == "/01_power_mcu/ISENP":
        if max_y > 65.5:
            removed_segs += 1
            return ""

    if net == "/01_power_mcu/GATE":
        # Remove old south branches south of y=79.1
        if max_y > 79.1:
            removed_segs += 1
            return ""

    if net == "GND":
        # Purge old manual tracks around U7 and C19 (82 <= x <= 88.5, 71.5 <= y <= 77.5)
        if min_x >= 82.0 and max_x <= 88.5 and min_y >= 71.5 and max_y <= 77.5:
            removed_segs += 1
            return ""
        # Purge old GND track near old R12 at y=112
        if abs(min_x - 87.8) < 0.1 and min_y >= 110.8 and max_y <= 112.2:
            removed_segs += 1
            return ""
        # Purge old GND fragments around (73.5..78.5, 67.5..75.5) on both layers
        if min_x >= 73.5 and max_x <= 78.5 and min_y >= 67.5 and max_y <= 75.5:
            removed_segs += 1
            return ""

    if net == "/01_power_mcu/USB_DP":
        # Remove old tracks south of y=64.30
        if max_y > 64.30:
            removed_segs += 1
            return ""

    if net == "/01_power_mcu/USB_DN":
        # Remove old tracks near U7 in range x >= 77.5 and 70.0 <= y <= 75.8
        if min_x >= 77.5 and min_y >= 70.0 and max_y <= 75.8:
            removed_segs += 1
            return ""
        if layer == "B.Cu" and min_x >= 77.5 and min_y >= 70.0:
            removed_segs += 1
            return ""

    if net == "/01_power_mcu/CC1":
        # Remove old CC1 routing south of y=58.5
        if max_y > 58.5:
            removed_segs += 1
            return ""

    if net == "/01_power_mcu/CC2":
        # Remove old segments connecting south of y=66.15 on B.Cu
        if layer == "B.Cu" and min_y >= 66.15:
            removed_segs += 1
            return ""
        # Remove old segments on F.Cu near U7
        if layer == "F.Cu" and min_y >= 71.5:
            removed_segs += 1
            return ""

    if net == "/01_power_mcu/EN_DRV":
        # Remove old F.Cu track from old U7
        if layer == "F.Cu" and min_x > 80.0:
            removed_segs += 1
            return ""

    if net == "/01_power_mcu/SDA":
        # Remove old convoluted loop
        if (min_x >= 71.2 and max_x <= 85.5 and min_y >= 68.6 and max_y <= 78.9):
            if max_x > 71.2 and min_y < 78.6:
                removed_segs += 1
                return ""

    if net == "/01_power_mcu/SCL":
        # Remove old stub from old U7 (83.963, 71.25) -> (84.7, 71.25) -> (84.7, 70.0)
        if layer == "F.Cu" and min_x >= 83.5 and max_x <= 84.8 and min_y >= 69.9 and max_y <= 71.4:
            removed_segs += 1
            return ""

    return m.group(0)

text = seg_pattern.sub(seg_filter, text)
print(f"Step 2: Removed {removed_segs} obsolete segments.")

removed_vias = 0
def via_filter(m):
    global removed_vias
    x, y, s, d, l1, l2, net, uid = m.groups()
    x, y = float(x), float(y)

    if net in purge_nets:
        removed_vias += 1
        return ""

    if net == "/01_power_mcu/ISENP" and ((abs(x - 83.80) < 0.1 and abs(y - 66.60) < 0.1) or (abs(x - 83.95) < 0.1 and abs(y - 73.85) < 0.1)):
        removed_vias += 1
        return ""

    if net == "/01_power_mcu/VIN_PD" and ((abs(x - 84.10) < 0.1 and abs(y - 76.70) < 0.1) or (abs(x - 91.80) < 0.1 and abs(y - 78.45) < 0.1)):
        removed_vias += 1
        return ""

    if net == "/01_power_mcu/USB_DP" and abs(x - 80.60) < 0.1 and abs(y - 75.20) < 0.1:
        removed_vias += 1
        return ""

    if net == "/01_power_mcu/USB_DN" and (
        (abs(x - 78.85) < 0.1 and abs(y - 74.55) < 0.1) or
        (abs(x - 77.575) < 0.1 and abs(y - 75.825) < 0.1)
    ):
        removed_vias += 1
        return ""

    if net == "/01_power_mcu/CC1" and ((abs(x - 77.425) < 0.1 and abs(y - 74.825) < 0.1) or (abs(x - 78.275) < 0.1 and abs(y - 73.975) < 0.1)):
        removed_vias += 1
        return ""

    if net == "/01_power_mcu/CC2" and abs(x - 76.95) < 0.1 and abs(y - 72.50) < 0.1:
        removed_vias += 1
        return ""

    if net == "GND" and (
        (abs(x - 84.90) < 0.1 and abs(y - 72.60) < 0.1) or
        (abs(x - 87.80) < 0.1 and abs(y - 110.90) < 0.1) or
        (abs(x - 73.80) < 0.1 and abs(y - 75.10) < 0.1)
    ):
        removed_vias += 1
        return ""

    if net == "/01_power_mcu/EN_DRV" and abs(x - 82.55) < 0.1 and abs(y - 76.00) < 0.1:
        removed_vias += 1
        return ""

    # Old SDA loop vias: (73.45, 76.7), (78.7, 72.6), (79.55, 69.15)
    if net == "/01_power_mcu/SDA" and (
        (abs(x - 73.45) < 0.1 and abs(y - 76.70) < 0.1) or
        (abs(x - 78.70) < 0.1 and abs(y - 72.60) < 0.1) or
        (abs(x - 79.55) < 0.1 and abs(y - 69.15) < 0.1)
    ):
        removed_vias += 1
        return ""

    return m.group(0)

text = via_pattern.sub(via_filter, text)
print(f"Step 2: Removed {removed_vias} obsolete vias.")

# ---------------------------------------------------------
# Step 3: Add new clean tracks & vias
# ---------------------------------------------------------
new_tracks = []
def add_track(layer, x1, y1, x2, y2, net, width=0.2):
    uid = str(uuid.uuid4())
    s = f"""\t(segment
\t\t(start {x1:.4f} {y1:.4f})
\t\t(end {x2:.4f} {y2:.4f})
\t\t(width {width})
\t\t(layer "{layer}")
\t\t(net "{net}")
\t\t(uuid "{uid}")
\t)
"""
    new_tracks.append(s)

def add_via(x, y, net, dia=0.6, drill=0.3):
    uid = str(uuid.uuid4())
    s = f"""\t(via
\t\t(at {x:.4f} {y:.4f})
\t\t(size {dia})
\t\t(drill {drill})
\t\t(layers "F.Cu" "B.Cu")
\t\t(net "{net}")
\t\t(uuid "{uid}")
\t)
"""
    new_tracks.append(s)

# --- 1. Q1 power tracks ---
# VBUS_IN (wide 1.2mm)
add_track("F.Cu", 90.425, 74.095, 90.425, 76.635, "/01_power_mcu/VBUS_IN", width=1.2)
add_track("F.Cu", 90.950, 68.250, 90.425, 74.095, "/01_power_mcu/VBUS_IN", width=1.2)

# VIN_PD (wide 1.2mm)
add_track("F.Cu", 95.575, 74.095, 95.575, 77.905, "/01_power_mcu/VIN_PD", width=1.2)
add_track("F.Cu", 95.575, 77.905, 93.800, 79.680, "/01_power_mcu/VIN_PD", width=1.2)
add_track("F.Cu", 93.800, 79.680, 90.550, 79.680, "/01_power_mcu/VIN_PD", width=1.2)
add_track("F.Cu", 90.550, 79.680, 90.550, 79.700, "/01_power_mcu/VIN_PD", width=1.2)
add_via(90.550, 79.700, "/01_power_mcu/VIN_PD", dia=0.8, drill=0.4)

# --- 2. Q1 gate & R12 tracks ---
# R12 Pad 2 (VBUS_IN) at (88.5, 76.445) -> connects to Q1 Pad 3 at (90.425, 76.445)
add_track("F.Cu", 88.500, 76.445, 90.425, 76.445, "/01_power_mcu/VBUS_IN", width=0.3)
add_track("F.Cu", 90.425, 76.445, 90.425, 76.635, "/01_power_mcu/VBUS_IN", width=0.3)

# R12 Pad 1 (GATE) at (88.5, 78.095) -> connects to Q1 Pad 4 at (90.425, 77.905)
add_track("F.Cu", 88.500, 78.095, 90.425, 77.905, "/01_power_mcu/GATE", width=0.3)
add_track("F.Cu", 88.500, 78.095, 88.500, 79.000, "/01_power_mcu/GATE", width=0.3)
add_track("F.Cu", 88.500, 79.000, 89.325, 79.000, "/01_power_mcu/GATE", width=0.2)
add_track("F.Cu", 88.500, 79.000, 78.825, 79.000, "/01_power_mcu/GATE", width=0.2)

# --- 3. West USB signals Fanout (DP, DN, CC1, CC2) ---
# Lane 1: USB_DP (U7 Pin 1 at 80.5375, 71.250)
add_track("F.Cu", 80.5375, 71.2500, 79.5000, 70.2125, "/01_power_mcu/USB_DP", width=0.2)
add_track("F.Cu", 79.5000, 70.2125, 79.5000, 69.2000, "/01_power_mcu/USB_DP", width=0.2)
add_via(79.5000, 69.2000, "/01_power_mcu/USB_DP", dia=0.6, drill=0.3)
add_track("B.Cu", 79.5000, 69.2000, 81.5500, 69.2000, "/01_power_mcu/USB_DP", width=0.2)
add_track("B.Cu", 81.5500, 69.2000, 81.5500, 64.3000, "/01_power_mcu/USB_DP", width=0.2)

# Lane 2: USB_DN (U7 Pin 2 at 80.5375, 71.750)
add_track("F.Cu", 80.5375, 71.7500, 78.5000, 71.7500, "/01_power_mcu/USB_DN", width=0.2)
add_track("F.Cu", 78.5000, 71.7500, 78.0000, 71.2500, "/01_power_mcu/USB_DN", width=0.2)
add_via(78.0000, 71.2500, "/01_power_mcu/USB_DN", dia=0.6, drill=0.3)
add_track("B.Cu", 78.0000, 71.2500, 78.0000, 74.0000, "/01_power_mcu/USB_DN", width=0.2)
add_track("B.Cu", 78.0000, 74.0000, 77.5750, 74.4250, "/01_power_mcu/USB_DN", width=0.2)
add_track("B.Cu", 77.5750, 74.4250, 77.5750, 75.8250, "/01_power_mcu/USB_DN", width=0.2)
add_via(77.5750, 75.8250, "/01_power_mcu/USB_DN", dia=0.6, drill=0.3)

# Lane 3: CC1 (U7 Pin 3 at 80.5375, 72.250)
add_track("F.Cu", 80.5375, 72.2500, 75.5000, 72.2500, "/01_power_mcu/CC1", width=0.2)
add_via(75.5000, 72.2500, "/01_power_mcu/CC1", dia=0.6, drill=0.3)
add_track("B.Cu", 75.5000, 72.2500, 75.5000, 60.5000, "/01_power_mcu/CC1", width=0.2)
add_track("B.Cu", 75.5000, 60.5000, 89.2500, 60.5000, "/01_power_mcu/CC1", width=0.2)
add_via(89.2500, 60.5000, "/01_power_mcu/CC1", dia=0.6, drill=0.3)
add_track("F.Cu", 89.2500, 60.5000, 89.2500, 58.4250, "/01_power_mcu/CC1", width=0.2)

# Lane 4: CC2 (U7 Pin 4 at 80.5375, 72.750)
# Slant south to y=73.55 to achieve >0.9mm clearance to CC1
add_track("F.Cu", 80.5375, 72.7500, 79.5000, 72.7500, "/01_power_mcu/CC2", width=0.2)
add_track("F.Cu", 79.5000, 72.7500, 78.7000, 73.5500, "/01_power_mcu/CC2", width=0.2)
add_track("F.Cu", 78.7000, 73.5500, 76.9500, 73.5500, "/01_power_mcu/CC2", width=0.2)
add_via(76.9500, 73.5500, "/01_power_mcu/CC2", dia=0.6, drill=0.3)
add_track("B.Cu", 76.9500, 73.5500, 76.9500, 66.1500, "/01_power_mcu/CC2", width=0.2)

# --- 4. East I2C signals: SDA, SCL ---
# SCL (Pin 10 at 83.4625, 72.25)
add_track("F.Cu", 83.4625, 72.2500, 84.7000, 72.2500, "/01_power_mcu/SCL", width=0.2)
add_track("F.Cu", 84.7000, 72.2500, 84.7000, 70.0000, "/01_power_mcu/SCL", width=0.2)

# SDA (Pin 9 at 83.4625, 72.75)
add_track("F.Cu", 83.4625, 72.7500, 84.5000, 73.7875, "/01_power_mcu/SDA", width=0.2)
add_track("F.Cu", 84.5000, 73.7875, 84.5000, 74.5000, "/01_power_mcu/SDA", width=0.2)
add_via(84.5000, 74.5000, "/01_power_mcu/SDA", dia=0.6, drill=0.3)
add_track("B.Cu", 84.5000, 74.5000, 84.5000, 80.5000, "/01_power_mcu/SDA", width=0.2)
add_track("B.Cu", 84.5000, 80.5000, 71.3000, 80.5000, "/01_power_mcu/SDA", width=0.2)
add_track("B.Cu", 71.3000, 80.5000, 71.3000, 78.8500, "/01_power_mcu/SDA", width=0.2)

# --- 5. South Passives: R16 (DEBUG_N) & R15 (ADDR) ---
# U7 Pin 6 (DEBUG_N) at (81.750, 73.4625) -> R16 pad 1 at (81.175, 77.000)
add_track("F.Cu", 81.7500, 73.4625, 81.7500, 75.5000, "/01_power_mcu/DEBUG_N", width=0.2)
add_track("F.Cu", 81.7500, 75.5000, 81.1750, 76.0750, "/01_power_mcu/DEBUG_N", width=0.2)
add_track("F.Cu", 81.1750, 76.0750, 81.1750, 77.0000, "/01_power_mcu/DEBUG_N", width=0.2)

# U7 Pin 8 (ADDR) at (82.750, 73.4625) -> R15 pad 1 at (85.175, 77.000)
add_track("F.Cu", 82.7500, 73.4625, 82.7500, 75.5000, "/01_power_mcu/ADDR", width=0.2)
add_track("F.Cu", 82.7500, 75.5000, 85.1750, 75.5000, "/01_power_mcu/ADDR", width=0.2)
add_track("F.Cu", 85.1750, 75.5000, 85.1750, 77.0000, "/01_power_mcu/ADDR", width=0.2)

# --- 6. North Signals: VBUS_IN, EN_DRV, GND ---
# U7 Pin 16 (VBUS_IN) at (81.250, 70.5375) -> runs along y=67.5 on F.Cu
add_track("F.Cu", 81.2500, 70.5375, 81.2500, 69.0000, "/01_power_mcu/VBUS_IN", width=0.2)
add_track("F.Cu", 81.2500, 69.0000, 80.5000, 68.2500, "/01_power_mcu/VBUS_IN", width=0.2)
add_track("F.Cu", 80.5000, 68.2500, 80.5000, 67.5000, "/01_power_mcu/VBUS_IN", width=0.2)
add_track("F.Cu", 80.5000, 67.5000, 86.2000, 67.5000, "/01_power_mcu/VBUS_IN", width=0.25)

# C21 pad 1 (79.475, 67.0) to VBUS_IN trace at (80.5, 67.5)
add_track("F.Cu", 79.4750, 67.0000, 79.4750, 67.5000, "/01_power_mcu/VBUS_IN", width=0.2)
add_track("F.Cu", 79.4750, 67.5000, 80.5000, 67.5000, "/01_power_mcu/VBUS_IN", width=0.2)

# U7 Pin 15 (EN_DRV) at (81.750, 70.5375) -> fan out north-east to via at (82.5, 69.0)
add_track("F.Cu", 81.7500, 70.5375, 81.7500, 69.7500, "/01_power_mcu/EN_DRV", width=0.2)
add_track("F.Cu", 81.7500, 69.7500, 82.5000, 69.0000, "/01_power_mcu/EN_DRV", width=0.2)
add_via(82.5000, 69.0000, "/01_power_mcu/EN_DRV", dia=0.6, drill=0.3)
add_track("B.Cu", 82.5000, 69.0000, 82.5500, 69.0500, "/01_power_mcu/EN_DRV", width=0.2)
add_track("B.Cu", 82.5500, 69.0500, 82.5500, 76.0000, "/01_power_mcu/EN_DRV", width=0.2)

# GND Connections: direct to solid B.Cu ground plane
# U7 Pin 12 (GND) & Pin 14 (GND) -> connect to Pad 17 (EP)
add_track("F.Cu", 83.4625, 71.2500, 82.8500, 71.2500, "GND", width=0.2)
add_track("F.Cu", 82.2500, 70.5375, 82.2500, 71.1500, "GND", width=0.2)
# U7 Thermal pad (EP) GND via at (81.5, 72.0)
add_via(81.5000, 72.0000, "GND", dia=0.6, drill=0.3)

# C17 pad 2 (GND) direct via to B.Cu ground plane at (88.5, 72.225)
add_track("F.Cu", 87.0000, 72.2250, 88.5000, 72.2250, "GND", width=0.3)
add_via(88.5000, 72.2250, "GND", dia=0.6, drill=0.3)

# R15 pad 2 (GND at 86.825, 77.0) direct via to B.Cu ground plane
add_track("F.Cu", 86.8250, 77.0000, 86.8250, 78.2000, "GND", width=0.3)
add_via(86.8250, 78.2000, "GND", dia=0.6, drill=0.3)

# R16 pad 2 (GND at 82.825, 77.0) direct via to B.Cu ground plane
add_track("F.Cu", 82.8250, 77.0000, 82.8250, 78.2000, "GND", width=0.3)
add_via(82.8250, 78.2000, "GND", dia=0.6, drill=0.3)

# C73 pad 2 (GND at 73.775, 68.0) direct via to B.Cu ground plane
add_track("F.Cu", 73.7750, 68.0000, 74.5000, 68.0000, "GND", width=0.3)
add_via(74.5000, 68.0000, "GND", dia=0.6, drill=0.3)

# NTC1 pad 2 (GND at 73.825, 74.0) direct via to B.Cu ground plane
add_via(73.8250, 74.0000, "GND", dia=0.6, drill=0.3)

# --- 7. C18 & 3V3 path ---
# In (at 79.3 75.0 180):
# Pad 1 (3V3) is at (80.075, 75.0) - right pad, closer to U7 Pin 5 (81.25, 73.4625)
# Pad 2 (GND) is at (78.525, 75.0) - left pad

# C18 Pad 2 (GND at 78.525, 75.0) -> direct via to B.Cu ground plane at (78.525, 76.0)
add_track("F.Cu", 78.5250, 75.0000, 78.5250, 76.0000, "GND", width=0.3)
add_via(78.5250, 76.0000, "GND", dia=0.6, drill=0.3)

# C18 Pad 1 (3V3 at 80.075, 75.0) -> U7 Pin 5 at (81.25, 73.4625)
add_track("F.Cu", 80.0750, 75.0000, 81.2500, 75.0000, "3V3", width=0.25)
add_track("F.Cu", 81.2500, 75.0000, 81.2500, 73.4625, "3V3", width=0.25)

# 3V3 feed from U5 at (66.1, 76.9):
# Via at (66.1, 76.9) -> B.Cu north to y=59.0 -> east to x=73.0 -> south to y=76.2 -> east to x=80.075 -> via to F.Cu
add_via(66.1000, 76.9000, "3V3", dia=0.6, drill=0.3)
add_track("B.Cu", 66.1000, 76.9000, 66.1000, 59.0000, "3V3", width=0.3)
add_track("B.Cu", 66.1000, 59.0000, 73.0000, 59.0000, "3V3", width=0.3)
add_track("B.Cu", 73.0000, 59.0000, 73.0000, 76.8500, "3V3", width=0.2)
add_track("B.Cu", 73.0000, 76.8500, 80.0750, 76.8500, "3V3", width=0.2)
add_via(80.0750, 76.8500, "3V3", dia=0.6, drill=0.3)
add_track("F.Cu", 80.0750, 76.8500, 80.0750, 75.0000, "3V3", width=0.25)

# Insert new tracks before final closing paren
new_tracks_str = "".join(new_tracks)
last_paren_idx = text.rfind(")")
assert last_paren_idx != -1
text = text[:last_paren_idx] + new_tracks_str + ")\n"

# Write out updated PCB
PCB_OUT.write_text(text)
print("Step 3: New tracks & vias added. PCB written.")

# Refill zones with pcbnew
import pcbnew
pro_file = ROOT / "pi5_corona_hv.kicad_pro"
saved_pro = pro_file.read_bytes()
try:
    board = pcbnew.LoadBoard(str(PCB_OUT))
    board.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(str(PCB_OUT), board)
finally:
    pro_file.write_bytes(saved_pro)

print("Step 4: Zones refilled and board saved. Running DRC...")

# Run DRC
res = subprocess.run([
    "kicad-cli", "pcb", "drc",
    "--severity-all",
    "--format", "json",
    "--output", str(REPORT_JSON),
    str(PCB_OUT)
], capture_output=True, text=True)

print("DRC returncode:", res.returncode)
print("DRC stdout:\n", res.stdout)
