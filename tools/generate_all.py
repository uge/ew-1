#!/usr/bin/env python3
"""
KiCad 10 Complete Hierarchical Schematic Generator - Clean, Professional Edition
Generates:
  - hardware/ionic_thrust_hv.kicad_sch (Root hierarchical sheet)
  - hardware/01_power_mcu.kicad_sch
  - hardware/02_drive_transformer.kicad_sch
  - hardware/03_multiplier.kicad_sch
  - hardware/04_sense_safety.kicad_sch
"""

import os
import re
import json
import uuid

def gen_uuid():
    return str(uuid.uuid4())

# Load pin database
with open("/home/uge/Development/ew-1/tools/sym_pins.json") as f:
    SYM_PINS = json.load(f)

# Load symbol library content to embed in lib_symbols
with open("/home/uge/Development/ew-1/hardware/ionic_thrust_hv.kicad_sym") as f:
    raw_sym_text = f.read()

lines = raw_sym_text.splitlines(keepends=True)
symbols = []
current = []
depth = 0
in_sym = False
for line in lines:
    if line.startswith("  (symbol \""):
        in_sym = True
        depth = 0
        current = []
    if in_sym:
        current.append(line)
        depth += line.count("(") - line.count(")")
        if depth == 0:
            symbols.append("".join(current))
            in_sym = False

cleaned = []
for s in symbols:
    s = re.sub(r'^\s*\(symbol "([^":]+)"', '    (symbol "ionic_thrust_hv:\\1"', s)
    cleaned.append(s)

EMBEDDED_LIB_SYMBOLS = "\n".join(cleaned)

def sch_header(title, doc_uuid=None):
    if not doc_uuid:
        doc_uuid = gen_uuid()
    return f"""(kicad_sch
	(version 20250114)
	(generator "eeschema")
	(generator_version "10.0")
	(uuid "{doc_uuid}")
	(paper "A3")
	(title_block
		(title "{title}")
		(company "Antigravity Engineering")
		(rev "B")
		(date "2026-10-01")
	)
	(lib_symbols
{EMBEDDED_LIB_SYMBOLS}
	)
"""

def get_pin_pos(sym_name, pnum, sx, sy, srot=0):
    pin = SYM_PINS[sym_name][str(pnum)]
    px, py = pin["x"], pin["y"]
    if srot == 0:
        wx, wy = sx + px, sy - py
    elif srot == 90:
        wx, wy = sx - py, sy - px
    elif srot == 180:
        wx, wy = sx - px, sy + py
    elif srot == 270:
        wx, wy = sx + py, sy + px
    return round(wx, 2), round(wy, 2)

class SchematicBuilder:
    def __init__(self, title, doc_uuid=None):
        self.title = title
        self.doc_uuid = doc_uuid or gen_uuid()
        self.items = []
        self.pin_coords = {}

    def add_symbol(self, lib_name, ref, val, footprint, sx, sy, srot=0, props=None, dnp=False, ref_pos=None, val_pos=None):
        sx, sy = round(sx, 2), round(sy, 2)
        for p in SYM_PINS[lib_name].keys():
            wx, wy = get_pin_pos(lib_name, p, sx, sy, srot)
            self.pin_coords[(ref, str(p))] = (wx, wy)

        rx, ry = (sx, sy - 3.81) if ref_pos is None else ref_pos
        vx, vy = (sx, sy + 3.81) if val_pos is None else val_pos

        prop_str = f"""		(property "Reference" "{ref}" (at {rx:.2f} {ry:.2f} 0) (effects (font (size 1.27 1.27))))
		(property "Value" "{val}" (at {vx:.2f} {vy:.2f} 0) (effects (font (size 1.27 1.27))))
		(property "Footprint" "{footprint}" (at {sx:.2f} {sy:.2f} 0) (effects (font (size 1.27 1.27)) hide))
"""
        if props:
            offset = 2.54
            for k, v in props.items():
                prop_str += f"""		(property "{k}" "{v}" (at {sx:.2f} {sy+offset:.2f} 0) (effects (font (size 1.27 1.27)) hide))\n"""
                offset += 2.54

        dnp_str = "yes" if dnp else "no"
        pin_str = ""
        for p in SYM_PINS[lib_name].keys():
            pin_str += f"""		(pin "{p}" (uuid "{gen_uuid()}"))\n"""

        sym_output = f"""	(symbol
		(lib_id "ionic_thrust_hv:{lib_name}")
		(at {sx:.2f} {sy:.2f} {srot})
		(unit 1)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(dnp {dnp_str})
		(uuid "{gen_uuid()}")
{prop_str}{pin_str}	)
"""
        self.items.append(sym_output)

    def add_wire(self, x1, y1, x2, y2):
        x1, y1, x2, y2 = round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)
        if x1 == x2 and y1 == y2:
            return
        w = f"""	(wire
		(pts (xy {x1:.2f} {y1:.2f}) (xy {x2:.2f} {y2:.2f}))
		(stroke (width 0) (type default))
		(uuid "{gen_uuid()}")
	)
"""
        self.items.append(w)

    def add_wire_path(self, pts):
        for i in range(len(pts) - 1):
            self.add_wire(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])

    def add_junction(self, x, y):
        x, y = round(x, 2), round(y, 2)
        j = f"""	(junction
		(at {x:.2f} {y:.2f})
		(diameter 0)
		(color 0 0 0 0)
		(uuid "{gen_uuid()}")
	)
"""
        self.items.append(j)

    def add_no_connect(self, x, y):
        x, y = round(x, 2), round(y, 2)
        self.items.append(f"""	(no_connect (at {x:.2f} {y:.2f}) (uuid "{gen_uuid()}"))\n""")

    def add_no_connect_pin(self, ref, pin):
        wx, wy = self.pin_coords[(ref, str(pin))]
        self.add_no_connect(wx, wy)

    def add_label(self, name, x, y, angle=0, justify=None):
        x, y = round(x, 2), round(y, 2)
        effects = f"(effects (font (size 1.27 1.27))"
        if justify:
            effects += f" (justify {justify})"
        effects += ")"
        lbl = f"""	(label "{name}"
		(at {x:.2f} {y:.2f} {angle})
		{effects}
		(uuid "{gen_uuid()}")
	)
"""
        self.items.append(lbl)

    def add_hier_label(self, name, shape, x, y, angle=0):
        x, y = round(x, 2), round(y, 2)
        lbl = f"""	(hierarchical_label "{name}"
		(shape {shape})
		(at {x:.2f} {y:.2f} {angle})
		(effects (font (size 1.27 1.27)))
		(uuid "{gen_uuid()}")
	)
"""
        self.items.append(lbl)

    def add_text(self, text, x, y, size=2.54, bold=True):
        x, y = round(x, 2), round(y, 2)
        b_str = " (bold yes)" if bold else ""
        t = f"""	(text "{text}"
		(at {x:.2f} {y:.2f} 0)
		(effects (font (size {size} {size}){b_str}) (justify left))
		(uuid "{gen_uuid()}")
	)
"""
        self.items.append(t)

    def add_rect(self, x1, y1, x2, y2, stroke_type="dash", stroke_width=0.254):
        x1, y1, x2, y2 = round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)
        r = f"""	(rectangle
		(start {x1:.2f} {y1:.2f})
		(end {x2:.2f} {y2:.2f})
		(stroke (width {stroke_width}) (type {stroke_type}))
		(fill (type none))
		(uuid "{gen_uuid()}")
	)
"""
        self.items.append(r)

    def get_pin(self, ref, pin):
        return self.pin_coords[(ref, str(pin))]

    def build(self):
        hdr = sch_header(self.title, self.doc_uuid)
        return hdr + "".join(self.items) + ")\n"

# ==============================================================================
# 1. ROOT SCHEMATIC
# ==============================================================================
def generate_root_sch():
    content = sch_header("ESP32 12V to 15kV DC Corona Supply - System Overview")

    # Sheet 1: Power & MCU (Left)
    content += f"""	(sheet
		(at 35.56 50.80)
		(size 63.50 114.30)
		(fields_autoplaced yes)
		(stroke (width 0.1524) (type solid))
		(fill (color 0 0 0 0.0000))
		(uuid "{gen_uuid()}")
		(property "Sheetname" "01_power_mcu" (at 35.56 46.99 0) (effects (font (size 1.524 1.524) (bold yes)) (justify left bottom)))
		(property "Sheetfile" "01_power_mcu.kicad_sch" (at 35.56 167.64 0) (effects (font (size 1.27 1.27)) (justify left top)))
		(pin "VIN_PROTECTED" output (at 99.06 60.96 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "3V3" output (at 99.06 71.12 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "GND" bidirectional (at 99.06 81.28 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "DRV_IN1" output (at 99.06 96.52 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "DRV_IN2" output (at 99.06 106.68 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "INTERLOCK_OK" input (at 99.06 121.92 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_SENSE_ADC" input (at 99.06 137.16 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_CURR_ADC" input (at 99.06 147.32 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
	)
"""

    # Sheet 4: Sense & Safety (Middle Left)
    content += f"""	(sheet
		(at 132.08 50.80)
		(size 63.50 114.30)
		(fields_autoplaced yes)
		(stroke (width 0.1524) (type solid))
		(fill (color 0 0 0 0.0000))
		(uuid "{gen_uuid()}")
		(property "Sheetname" "04_sense_safety" (at 132.08 46.99 0) (effects (font (size 1.524 1.524) (bold yes)) (justify left bottom)))
		(property "Sheetfile" "04_sense_safety.kicad_sch" (at 132.08 167.64 0) (effects (font (size 1.27 1.27)) (justify left top)))
		(pin "VIN_PROTECTED" input (at 132.08 60.96 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "3V3" input (at 132.08 71.12 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "GND" bidirectional (at 132.08 81.28 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "INTERLOCK_OK" output (at 132.08 121.92 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_SENSE_ADC" output (at 132.08 137.16 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_CURR_ADC" output (at 132.08 147.32 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_VM" output (at 195.58 60.96 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "GND" bidirectional (at 195.58 81.28 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_RAW" input (at 195.58 121.92 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_RETURN" input (at 195.58 137.16 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
	)
"""

    # Sheet 2: Driver & Transformer (Middle Right)
    content += f"""	(sheet
		(at 228.60 50.80)
		(size 63.50 81.28)
		(fields_autoplaced yes)
		(stroke (width 0.1524) (type solid))
		(fill (color 0 0 0 0.0000))
		(uuid "{gen_uuid()}")
		(property "Sheetname" "02_drive_transformer" (at 228.60 46.99 0) (effects (font (size 1.524 1.524) (bold yes)) (justify left bottom)))
		(property "Sheetfile" "02_drive_transformer.kicad_sch" (at 228.60 134.62 0) (effects (font (size 1.27 1.27)) (justify left top)))
		(pin "HV_VM" input (at 228.60 60.96 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "DRV_nSLEEP" input (at 228.60 71.12 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "GND" bidirectional (at 228.60 81.28 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "DRV_IN1" input (at 228.60 96.52 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "DRV_IN2" input (at 228.60 106.68 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "SEC_A" output (at 292.10 71.12 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_RETURN" output (at 292.10 91.44 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
	)
"""

    # Sheet 3: Multiplier (Right)
    content += f"""	(sheet
		(at 325.12 50.80)
		(size 63.50 81.28)
		(fields_autoplaced yes)
		(stroke (width 0.1524) (type solid))
		(fill (color 0 0 0 0.0000))
		(uuid "{gen_uuid()}")
		(property "Sheetname" "03_multiplier" (at 325.12 46.99 0) (effects (font (size 1.524 1.524) (bold yes)) (justify left bottom)))
		(property "Sheetfile" "03_multiplier.kicad_sch" (at 325.12 134.62 0) (effects (font (size 1.27 1.27)) (justify left top)))
		(pin "SEC_A" input (at 325.12 71.12 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_RETURN" input (at 325.12 91.44 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_RAW" output (at 388.62 71.12 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_RETURN" output (at 388.62 91.44 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
	)
"""

    def wire(x1, y1, x2, y2):
        return f"""	(wire (pts (xy {x1:.2f} {y1:.2f}) (xy {x2:.2f} {y2:.2f})) (stroke (width 0) (type default)) (uuid "{gen_uuid()}"))\n"""

    def junc(x, y):
        return f"""	(junction (at {x:.2f} {y:.2f}) (diameter 0) (color 0 0 0 0) (uuid "{gen_uuid()}"))\n"""

    # Direct horizontal wires between Sheet 1 & Sheet 4:
    content += wire(99.06, 60.96, 132.08, 60.96) # VIN_PROTECTED
    content += wire(99.06, 71.12, 132.08, 71.12) # 3V3
    content += wire(99.06, 81.28, 132.08, 81.28) # GND
    content += wire(99.06, 121.92, 132.08, 121.92) # INTERLOCK_OK
    content += wire(99.06, 137.16, 132.08, 137.16) # HV_SENSE_ADC
    content += wire(99.06, 147.32, 132.08, 147.32) # HV_CURR_ADC

    # Connections to Sheet 2:
    # HV_VM from Sheet 4 to Sheet 2
    content += wire(195.58, 60.96, 228.60, 60.96)
    # GND to Sheet 2
    content += wire(195.58, 81.28, 228.60, 81.28)

    # DRV_IN1 from Sheet 1 across to Sheet 2
    content += wire(99.06, 96.52, 104.14, 96.52)
    content += wire(104.14, 96.52, 104.14, 185.42)
    content += wire(104.14, 185.42, 218.44, 185.42)
    content += wire(218.44, 185.42, 218.44, 96.52)
    content += wire(218.44, 96.52, 228.60, 96.52)

    # DRV_IN2 from Sheet 1 across to Sheet 2
    content += wire(99.06, 106.68, 106.68, 106.68)
    content += wire(106.68, 106.68, 106.68, 190.50)
    content += wire(106.68, 190.50, 220.98, 190.50)
    content += wire(220.98, 190.50, 220.98, 106.68)
    content += wire(220.98, 106.68, 228.60, 106.68)

    # INTERLOCK_OK branched to DRV_nSLEEP on Sheet 2
    content += junc(116.84, 121.92)
    content += wire(116.84, 121.92, 116.84, 175.26)
    content += wire(116.84, 175.26, 213.36, 175.26)
    content += wire(213.36, 175.26, 213.36, 71.12)
    content += wire(213.36, 71.12, 228.60, 71.12)

    # Direct horizontal wires from Sheet 2 to Sheet 3:
    content += wire(292.10, 71.12, 325.12, 71.12) # SEC_A
    content += wire(292.10, 91.44, 325.12, 91.44) # HV_RETURN

    # HV_RAW from Sheet 3 loopback to Sheet 4:
    content += wire(388.62, 71.12, 396.24, 71.12)
    content += wire(396.24, 71.12, 396.24, 203.20)
    content += wire(396.24, 203.20, 200.66, 203.20)
    content += wire(200.66, 203.20, 200.66, 121.92)
    content += wire(200.66, 121.92, 195.58, 121.92)

    # HV_RETURN from Sheet 3 loopback to Sheet 4:
    content += wire(388.62, 91.44, 401.32, 91.44)
    content += wire(401.32, 91.44, 401.32, 208.28)
    content += wire(401.32, 208.28, 205.74, 208.28)
    content += wire(205.74, 208.28, 205.74, 137.16)
    content += wire(205.74, 137.16, 195.58, 137.16)

    # Domain Boundaries
    content += f"""	(rectangle (start 27.94 38.10) (end 299.72 215.90) (stroke (width 0.381) (type dash)) (fill (type none)) (uuid "{gen_uuid()}"))
	(text "LOW-VOLTAGE DOMAIN (JLCPCB 4-LAYER: F.Cu, In1.Cu GND, In2.Cu Power, B.Cu)" (at 30.48 43.18 0) (effects (font (size 2.0 2.0) (bold yes)) (justify left)) (uuid "{gen_uuid()}"))
	(rectangle (start 314.96 38.10) (end 408.94 215.90) (stroke (width 0.381) (type dash)) (fill (type none)) (uuid "{gen_uuid()}"))
	(text "HIGH-VOLTAGE MULTIPLIER DOMAIN (STRICT MULTI-LAYER KEEPOUT: >=20mm ISOLATION)" (at 317.50 43.18 0) (effects (font (size 2.0 2.0) (bold yes)) (justify left)) (uuid "{gen_uuid()}"))
"""
    content += ")\n"
    return content

# ==============================================================================
# 2. SHEET 01: POWER & MCU
# ==============================================================================
def generate_power_mcu_sch():
    b = SchematicBuilder("01 Power Supply & ESP32-C3 Microcontroller")

    # Section 1: 12V Power Input & TVS Protection
    b.add_text("12V DC INPUT & OVERVOLTAGE PROTECTION", 33.02, 38.10, size=2.54, bold=True)
    b.add_rect(30.48, 33.02, 132.08, 93.98)

    # J1 Screw Terminal
    b.add_symbol("WJ500V-5.08-2P-14-00A", "J1", "12V_IN", "ionic_thrust_hv:CONN-TH_2P-P5.00_WJ500V-5.08-2P",
        45.72, 55.88, srot=0, props={"LCSC Part": "C8465", "MPN": "WJ500V-5.08-2P"}, dnp=True)

    # F1 PTC Fuse 1A 1206
    b.add_symbol("nSMD100-16V", "F1", "1A PTC", "ionic_thrust_hv:F1206",
        78.74, 54.61, srot=0, props={"LCSC Part": "C70082", "MPN": "nSMD100-16V"})

    # Connect J1 pin 1 to F1 pin 1
    j1_p1 = b.get_pin("J1", 1) # (44.45, 60.96)
    f1_p1 = b.get_pin("F1", 1) # (69.85, 55.88)
    b.add_wire_path([j1_p1, (44.45, 55.88), f1_p1])
    b.add_label("VIN_12", 55.88, 55.88)
    b.add_symbol("PWR_FLAG", "#FLG1", "PWR_FLAG", "", 55.88, 50.80, srot=0)
    b.add_wire(55.88, 50.80, 55.88, 55.88)
    b.add_junction(55.88, 55.88)

    # F1 pin 2 to VIN_PROTECTED bus
    f1_p2 = b.get_pin("F1", 2) # (87.63, 55.88)
    b.add_wire(f1_p2[0], f1_p2[1], 106.68, 55.88)
    b.add_junction(106.68, 55.88)
    b.add_label("VIN_PROTECTED", 106.68, 55.88)
    b.add_symbol("PWR_FLAG", "#FLG5", "PWR_FLAG", "", 106.68, 48.26, srot=0)
    b.add_wire(106.68, 48.26, 106.68, 55.88)
    b.add_hier_label("VIN_PROTECTED", "output", 127.00, 55.88)
    b.add_wire(106.68, 55.88, 127.00, 55.88)

    # TVS Diode D2 across VIN_PROTECTED and GND (Cathode=1, Anode=2; rot=90)
    b.add_symbol("SMAJ18A_C173513", "D2", "SMAJ18A", "ionic_thrust_hv:SMA_L4.4-W2.6-LS5.0-RD",
        106.68, 66.04, srot=90, props={"LCSC Part": "C173513", "MPN": "SMAJ18A"})
    d2_p1 = b.get_pin("D2", 1)
    d2_p2 = b.get_pin("D2", 2)
    b.add_wire(d2_p1[0], d2_p1[1], 106.68, 55.88)

    # J1 pin 2 to GND bus
    j1_p2 = b.get_pin("J1", 2) # (46.99, 60.96)
    b.add_wire_path([j1_p2, (46.99, 76.20), (127.00, 76.20)])
    b.add_wire(d2_p2[0], d2_p2[1], 106.68, 76.20)
    b.add_junction(106.68, 76.20)
    b.add_label("GND", 55.88, 76.20)
    b.add_symbol("PWR_FLAG", "#FLG2", "PWR_FLAG", "", 55.88, 83.82, srot=180)
    b.add_wire(55.88, 83.82, 55.88, 76.20)
    b.add_junction(55.88, 76.20)
    b.add_hier_label("GND", "bidirectional", 127.00, 76.20)

    # Section 2: 3.3V Synchronous Buck Converter (AP63203)
    b.add_text("3.3V SYNCHRONOUS BUCK REGULATOR (AP63203WU-7)", 33.02, 106.68, size=2.54, bold=True)
    b.add_rect(30.48, 101.60, 157.48, 228.60)

    # Feed VIN_PROTECTED from top section
    b.add_wire_path([(106.68, 55.88), (114.30, 55.88), (114.30, 119.38), (38.10, 119.38)])
    b.add_junction(106.68, 55.88)
    b.add_label("VIN_PROTECTED", 38.10, 119.38)

    # Input Capacitors C1, C2 (10uF 0805, srot=90)
    b.add_symbol("CC0805KKX5R8BB106", "C1", "10uF", "ionic_thrust_hv:C0805", 50.80, 137.16, srot=90, props={"LCSC Part": "C89831"})
    b.add_symbol("CC0805KKX5R8BB106", "C2", "10uF", "ionic_thrust_hv:C0805", 63.50, 137.16, srot=90, props={"LCSC Part": "C89831"})
    c1_p1 = b.get_pin("C1", 1) # top
    c1_p2 = b.get_pin("C1", 2) # bottom
    c2_p1 = b.get_pin("C2", 1)
    c2_p2 = b.get_pin("C2", 2)
    b.add_wire(c1_p1[0], c1_p1[1], 50.80, 119.38)
    b.add_junction(50.80, 119.38)
    b.add_wire(c2_p1[0], c2_p1[1], 63.50, 119.38)
    b.add_junction(63.50, 119.38)

    # GND rail for Buck connected to top GND
    b.add_wire_path([(127.00, 76.20), (127.00, 104.14), (38.10, 104.14), (38.10, 162.56), (147.32, 162.56)])
    b.add_junction(127.00, 76.20)
    b.add_label("GND", 43.18, 162.56)
    b.add_wire(c1_p2[0], c1_p2[1], 50.80, 162.56)
    b.add_junction(50.80, 162.56)
    b.add_wire(c2_p2[0], c2_p2[1], 63.50, 162.56)
    b.add_junction(63.50, 162.56)

    # Buck IC U3 (AP63203WU-7) at (81.28, 142.24)
    b.add_symbol("AP63203WU-7", "U3", "AP63203", "ionic_thrust_hv:TSOT-26_L2.9-W1.6-P0.95-LS2.8-BL",
        81.28, 142.24, srot=0, props={"LCSC Part": "C780769", "MPN": "AP63203WU-7"})
    u3_vin = b.get_pin("U3", 3)
    u3_en = b.get_pin("U3", 2)
    u3_fb = b.get_pin("U3", 1)
    u3_gnd = b.get_pin("U3", 4)
    u3_sw = b.get_pin("U3", 5)
    u3_bst = b.get_pin("U3", 6)

    # Connect VIN and EN to VIN_PROTECTED
    b.add_wire_path([u3_vin, (72.39, 119.38)])
    b.add_junction(72.39, 119.38)
    b.add_wire_path([u3_en, (72.39, u3_en[1])])
    b.add_junction(72.39, u3_en[1])

    # Connect U3 GND to GND rail
    b.add_wire(u3_gnd[0], u3_gnd[1], u3_gnd[0], 162.56)
    b.add_junction(u3_gnd[0], 162.56)

    # Inductor L1 (3.9uH) at (114.30, 142.24)
    b.add_symbol("SRN6028-3R9M", "L1", "3.9uH", "ionic_thrust_hv:Inductor_SMD_6.0x6.0mm",
        114.30, 142.24, srot=0, props={"LCSC Part": "C2046441", "MPN": "SRN6028-3R9M"})
    l1_p1 = b.get_pin("L1", 1)
    l1_p2 = b.get_pin("L1", 2)
    b.add_wire(u3_sw[0], u3_sw[1], l1_p1[0], l1_p1[1])
    b.add_junction(96.52, 142.24)

    # Bootstrap capacitor C5 (100nF) between BST and SW
    b.add_symbol("CC0603KRX7R9BB104", "C5", "100nF", "ionic_thrust_hv:C0603",
        96.52, 132.08, srot=90, props={"LCSC Part": "C14663"})
    c5_p1 = b.get_pin("C5", 1)
    c5_p2 = b.get_pin("C5", 2)
    b.add_wire_path([u3_bst, (96.52, u3_bst[1]), c5_p1])
    b.add_wire(c5_p2[0], c5_p2[1], 96.52, 142.24)

    # L1 pin 2 to 3V3 rail at Y=142.24
    b.add_wire(l1_p2[0], l1_p2[1], 152.40, 142.24)
    b.add_junction(129.54, 142.24)
    b.add_junction(142.24, 142.24)
    b.add_label("3V3", 152.40, 142.24)
    b.add_hier_label("3V3", "output", 152.40, 137.16)
    b.add_wire(152.40, 142.24, 152.40, 137.16)
    b.add_symbol("PWR_FLAG", "#FLG3", "PWR_FLAG", "", 152.40, 132.08, srot=0)
    b.add_wire(152.40, 132.08, 152.40, 137.16)
    b.add_junction(152.40, 137.16)

    # Feedback loop: U3 FB to 3V3
    b.add_wire_path([u3_fb, (72.39, 127.00), (124.46, 127.00), (124.46, 142.24)])
    b.add_junction(124.46, 142.24)

    # Output Capacitors C3, C4 (22uF 0805, srot=0: pin 2 is TOP, pin 1 is BOTTOM)
    b.add_symbol("TCC0805X5R226M100FT", "C3", "22uF", "ionic_thrust_hv:C0805", 129.54, 152.40, srot=0, props={"LCSC Part": "C380338"})
    b.add_symbol("TCC0805X5R226M100FT", "C4", "22uF", "ionic_thrust_hv:C0805", 142.24, 152.40, srot=0, props={"LCSC Part": "C380338"})
    c3_top = b.get_pin("C3", 2)
    c3_bot = b.get_pin("C3", 1)
    c4_top = b.get_pin("C4", 2)
    c4_bot = b.get_pin("C4", 1)

    b.add_wire(c3_top[0], c3_top[1], 129.54, 142.24)
    b.add_wire(c4_top[0], c4_top[1], 142.24, 142.24)
    b.add_wire(c3_bot[0], c3_bot[1], 129.54, 162.56)
    b.add_junction(129.54, 162.56)
    b.add_wire(c4_bot[0], c4_bot[1], 142.24, 162.56)
    b.add_junction(142.24, 162.56)

    # Section 3: ESP32-C3 Microcontroller & Peripherals
    b.add_text("ESP32-C3 CONTROLLER & USER INTERFACE", 175.26, 38.10, size=2.54, bold=True)
    b.add_rect(170.18, 33.02, 396.24, 256.54)

    # Place U1 at (266.70, 137.16)
    b.add_symbol("ESP32-C3-WROOM-02-H4", "U1", "ESP32-C3-WROOM-02", "ionic_thrust_hv:WIFIM-SMD_18P-L20.0-W18.0-P1.50",
        266.70, 137.16, srot=0, props={"LCSC Part": "C2944070", "MPN": "ESP32-C3-WROOM-02-H4"})

    # Power rail 3V3 for U1 at Y=116.84
    b.add_wire(223.52, 116.84, 255.27, 116.84)
    b.add_label("3V3", 223.52, 116.84)
    u1_p1 = b.get_pin("U1", 1) # 3V3 @ (255.27, 125.73)
    b.add_wire_path([u1_p1, (255.27, 116.84)])
    b.add_junction(255.27, 116.84)

    # Decoupling Caps C7, C8, C9 (100nF)
    b.add_symbol("CC0603KRX7R9BB104", "C7", "100nF", "ionic_thrust_hv:C0603", 228.60, 124.46, srot=90, props={"LCSC Part": "C14663"})
    b.add_symbol("CC0603KRX7R9BB104", "C8", "100nF", "ionic_thrust_hv:C0603", 236.22, 124.46, srot=90, props={"LCSC Part": "C14663"})
    b.add_symbol("CC0603KRX7R9BB104", "C9", "100nF", "ionic_thrust_hv:C0603", 243.84, 124.46, srot=90, props={"LCSC Part": "C14663"})
    for cap_ref, cx in [("C7", 228.60), ("C8", 236.22), ("C9", 243.84)]:
        cp1 = b.get_pin(cap_ref, 1)
        cp2 = b.get_pin(cap_ref, 2)
        b.add_wire(cp1[0], cp1[1], cx, 116.84)
        b.add_junction(cx, 116.84)
        b.add_wire(cp2[0], cp2[1], cx, 132.08)
        b.add_junction(cx, 132.08)

    # Ground bus for decoupling caps
    b.add_wire(228.60, 132.08, 243.84, 132.08)
    b.add_label("GND", 228.60, 132.08)

    # U1 Ground pins (9 and 19)
    u1_p9 = b.get_pin("U1", 9)
    u1_p19 = b.get_pin("U1", 19)
    b.add_wire(u1_p9[0], u1_p9[1], u1_p9[0] - 5.08, u1_p9[1])
    b.add_label("GND", u1_p9[0] - 5.08, u1_p9[1])
    b.add_wire(u1_p19[0], u1_p19[1], u1_p19[0] + 5.08, u1_p19[1])
    b.add_label("GND", u1_p19[0] + 5.08, u1_p19[1])

    # Helper function for tactile pushbutton connection
    def wire_button(sw_ref, net_name, y_sig):
        # Tie pin 1 & 2 together, tie pin 3 & 4 together
        p1 = b.get_pin(sw_ref, 1)
        p2 = b.get_pin(sw_ref, 2)
        p3 = b.get_pin(sw_ref, 3)
        p4 = b.get_pin(sw_ref, 4)
        b.add_wire(p1[0], p1[1], p2[0], p2[1]) # top terminals
        b.add_wire(p3[0], p3[1], p4[0], p4[1]) # bottom terminals
        b.add_wire_path([p1, (p1[0], y_sig), (208.28, y_sig)])
        b.add_wire(p3[0], p3[1], p3[0], p3[1] + 5.08)
        b.add_label("GND", p3[0], p3[1] + 5.08)

    # Reset circuit: Pin 2 (EN), R1 pullup to 3V3, C6 filter to GND, SW1 to GND
    u1_en = b.get_pin("U1", 2)
    b.add_wire(u1_en[0], u1_en[1], 208.28, u1_en[1])
    b.add_junction(208.28, u1_en[1])
    b.add_label("MCU_EN", 208.28, u1_en[1])

    # R1 (10k pullup)
    b.add_symbol("0603WAF1002T5E", "R1", "10k", "ionic_thrust_hv:R0603", 208.28, 116.84, srot=90, props={"LCSC Part": "C25804"})
    r1_p1 = b.get_pin("R1", 1)
    r1_p2 = b.get_pin("R1", 2)
    b.add_wire(r1_p1[0], r1_p1[1], 208.28, 106.68)
    b.add_label("3V3", 208.28, 106.68)
    b.add_wire(r1_p2[0], r1_p2[1], 208.28, u1_en[1])

    # C6 (100nF reset cap)
    b.add_symbol("CC0603KRX7R9BB104", "C6", "100nF", "ionic_thrust_hv:C0603", 208.28, 137.16, srot=90, props={"LCSC Part": "C14663"})
    c6_p1 = b.get_pin("C6", 1)
    c6_p2 = b.get_pin("C6", 2)
    b.add_wire(c6_p1[0], c6_p1[1], 208.28, u1_en[1])
    b.add_wire(c6_p2[0], c6_p2[1], 208.28, 147.32)
    b.add_label("GND", 208.28, 147.32)

    # SW1 Reset Switch at (187.96, 128.27)
    b.add_symbol("TS-1187A-B-A-B", "SW1", "RESET", "ionic_thrust_hv:SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5",
        187.96, 128.27, srot=0, props={"LCSC Part": "C318884"})
    wire_button("SW1", "MCU_EN", u1_en[1])

    # Boot circuit: Pin 8 (IO9), R2 pullup to 3V3, SW2 to GND
    u1_io9 = b.get_pin("U1", 8)
    b.add_wire(u1_io9[0], u1_io9[1], 208.28, u1_io9[1])
    b.add_junction(208.28, u1_io9[1])
    b.add_label("MCU_BOOT", 208.28, u1_io9[1])

    b.add_symbol("0603WAF1002T5E", "R2", "10k", "ionic_thrust_hv:R0603", 208.28, 154.94, srot=90, props={"LCSC Part": "C25804"})
    r2_p1 = b.get_pin("R2", 1)
    r2_p2 = b.get_pin("R2", 2)
    b.add_wire(r2_p1[0], r2_p1[1], 208.28, u1_io9[1])
    b.add_wire(r2_p2[0], r2_p2[1], 208.28, 165.10)
    b.add_label("3V3", 208.28, 165.10)

    # SW2 Boot Switch at (187.96, 154.94)
    b.add_symbol("TS-1187A-B-A-B", "SW2", "BOOT", "ionic_thrust_hv:SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5",
        187.96, 154.94, srot=0, props={"LCSC Part": "C318884"})
    wire_button("SW2", "MCU_BOOT", u1_io9[1])

    # ARM Switch Circuit: Pin 5 (IO6), R4 pullup to 3V3, S6 to GND
    u1_io6 = b.get_pin("U1", 5)
    b.add_wire(u1_io6[0], u1_io6[1], 208.28, u1_io6[1])
    b.add_junction(208.28, u1_io6[1])
    b.add_label("ARM_SW", 208.28, u1_io6[1])

    b.add_symbol("0603WAF1002T5E", "R4", "10k", "ionic_thrust_hv:R0603", 208.28, 180.34, srot=90, props={"LCSC Part": "C25804"})
    r4_p1 = b.get_pin("R4", 1)
    r4_p2 = b.get_pin("R4", 2)
    b.add_wire(r4_p1[0], r4_p1[1], 208.28, u1_io6[1])
    b.add_wire(r4_p2[0], r4_p2[1], 208.28, 190.50)
    b.add_label("3V3", 208.28, 190.50)

    # S6 ARM Switch at (187.96, 180.34)
    b.add_symbol("TS-1187A-B-A-B", "S6", "ARM", "ionic_thrust_hv:SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5",
        187.96, 180.34, srot=0, props={"LCSC Part": "C318884"})
    wire_button("S6", "ARM_SW", u1_io6[1])

    # High Voltage Driver PWM Outputs: Pin 3 (IO4) and Pin 4 (IO5)
    # Route cleanly below everything at X=251.46 and X=248.92
    u1_io4 = b.get_pin("U1", 3)
    u1_io5 = b.get_pin("U1", 4)
    b.add_wire_path([u1_io4, (251.46, u1_io4[1]), (251.46, 208.28), (381.00, 208.28)])
    b.add_hier_label("DRV_IN1", "output", 381.00, 208.28)
    b.add_wire_path([u1_io5, (248.92, u1_io5[1]), (248.92, 218.44), (381.00, 218.44)])
    b.add_hier_label("DRV_IN2", "output", 381.00, 218.44)

    # High Voltage Sense Inputs: Pin 18 (IO0) and Pin 17 (IO1)
    u1_io0 = b.get_pin("U1", 18)
    u1_io1 = b.get_pin("U1", 17)
    b.add_wire(u1_io0[0], u1_io0[1], 381.00, u1_io0[1])
    b.add_hier_label("HV_SENSE_ADC", "input", 381.00, u1_io0[1])
    b.add_wire(u1_io1[0], u1_io1[1], 381.00, u1_io1[1])
    b.add_hier_label("HV_CURR_ADC", "input", 381.00, u1_io1[1])

    # Interlock Status Input: Pin 15 (IO3) with R3 (10k pulldown)
    u1_io3 = b.get_pin("U1", 15)
    b.add_wire(u1_io3[0], u1_io3[1], 342.90, u1_io3[1])
    b.add_junction(342.90, u1_io3[1])
    b.add_hier_label("INTERLOCK_OK", "input", 381.00, u1_io3[1])
    b.add_wire(342.90, u1_io3[1], 381.00, u1_io3[1])

    b.add_symbol("0603WAF1002T5E", "R3", "10k", "ionic_thrust_hv:R0603", 342.90, 152.40, srot=90, props={"LCSC Part": "C25804"})
    r3_p1 = b.get_pin("R3", 1)
    r3_p2 = b.get_pin("R3", 2)
    b.add_wire(r3_p1[0], r3_p1[1], 342.90, u1_io3[1])
    b.add_wire(r3_p2[0], r3_p2[1], 342.90, 165.10)
    b.add_label("GND", 342.90, 165.10)

    # Status LED on Pin 6 (IO7)
    u1_io7 = b.get_pin("U1", 6)
    b.add_wire_path([u1_io7, (246.38, u1_io7[1]), (246.38, 198.12), (304.80, 198.12)])
    b.add_symbol("0603WAF1001T5E", "R6", "1k", "ionic_thrust_hv:R0603", 314.96, 198.12, srot=0, props={"LCSC Part": "C21190"})
    r6_p1 = b.get_pin("R6", 1)
    r6_p2 = b.get_pin("R6", 2)
    b.add_wire(304.80, 198.12, r6_p1[0], r6_p1[1])

    b.add_symbol("19-217_GHC-YR1S2_3T", "LED1", "STATUS", "ionic_thrust_hv:LED0603-RD",
        335.28, 198.12, srot=90, props={"LCSC Part": "C72043"})
    led1_a = b.get_pin("LED1", 2)
    led1_c = b.get_pin("LED1", 1)
    b.add_wire(r6_p2[0], r6_p2[1], led1_a[0], led1_a[1])
    b.add_wire(led1_c[0], led1_c[1], 345.44, 198.12)
    b.add_label("GND", 345.44, 198.12)

    # Programming Header J2 (1x6 2.54mm)
    b.add_symbol("DS1021-1X6SF11-B", "J2", "UART_PROG", "ionic_thrust_hv:CONN-TH_DS1021-1X6SF11-B",
        314.96, 236.22, srot=0, props={"LCSC Part": "C7430362"}, dnp=True)
    j2_pins = {
        1: "3V3",
        2: "GND",
        3: "UART_TX",
        4: "UART_RX",
        5: "MCU_EN",
        6: "MCU_BOOT"
    }
    for p, net in j2_pins.items():
        jp = b.get_pin("J2", p)
        b.add_wire(jp[0], jp[1], jp[0] - 7.62, jp[1])
        b.add_label(net, jp[0] - 7.62, jp[1], justify="right")

    # Connect U1 TXD & RXD to labels
    u1_txd = b.get_pin("U1", 12)
    u1_rxd = b.get_pin("U1", 11)
    b.add_wire(u1_txd[0], u1_txd[1], u1_txd[0] + 5.08, u1_txd[1])
    b.add_label("UART_TX", u1_txd[0] + 5.08, u1_txd[1])
    b.add_wire(u1_rxd[0], u1_rxd[1], u1_rxd[0] + 5.08, u1_rxd[1])
    b.add_label("UART_RX", u1_rxd[0] + 5.08, u1_rxd[1])

    # Unused U1 pins with no-connect
    for p in [7, 10, 13, 14, 16]:
        b.add_no_connect_pin("U1", p)

    return b.build()

# ==============================================================================
# 3. SHEET 02: DRIVE & TRANSFORMER
# ==============================================================================
def generate_drive_transformer_sch():
    b = SchematicBuilder("02 Isolated AC Generation & Resonance Tank")

    b.add_text("FULL-BRIDGE DRIVER & SERIES RESONANT STEP-UP TRANSFORMER", 33.02, 38.10, size=2.54, bold=True)
    b.add_rect(30.48, 33.02, 391.16, 243.84)

    # Power & Control Inputs on Left
    b.add_hier_label("HV_VM", "input", 45.72, 60.96)
    b.add_symbol("PWR_FLAG", "#FLG4", "PWR_FLAG", "", 45.72, 53.34, srot=0)
    b.add_wire(45.72, 53.34, 45.72, 60.96)
    b.add_junction(45.72, 60.96)

    b.add_hier_label("DRV_nSLEEP", "input", 45.72, 86.36)
    b.add_hier_label("DRV_IN1", "input", 45.72, 106.68)
    b.add_hier_label("DRV_IN2", "input", 45.72, 116.84)
    b.add_hier_label("GND", "bidirectional", 45.72, 147.32)

    # Driver U2 (DRV8220DSGR) placed at (114.30, 96.52)
    b.add_symbol("DRV8220DSGR_C3681269", "U2", "DRV8220DSGR", "ionic_thrust_hv:WSON-8_L2.0-W2.0-P0.50-TL-EP",
        114.30, 96.52, srot=0, props={"LCSC Part": "C3681269", "MPN": "DRV8220DSGR"})

    u2_vm = b.get_pin("U2", 1)
    u2_out1 = b.get_pin("U2", 2)
    u2_out2 = b.get_pin("U2", 3)
    u2_gnd = b.get_pin("U2", 4)
    u2_in2 = b.get_pin("U2", 5)
    u2_in1 = b.get_pin("U2", 6)
    u2_mode = b.get_pin("U2", 7)
    u2_nsleep = b.get_pin("U2", 8)
    u2_ep = b.get_pin("U2", 9)

    # VM feed and bypass capacitors C10 (100nF) and C12 (10uF)
    b.add_wire(45.72, 60.96, u2_vm[0] - 10.16, 60.96)
    b.add_wire(u2_vm[0] - 10.16, 60.96, u2_vm[0], u2_vm[1])
    b.add_junction(66.04, 60.96)
    b.add_junction(78.74, 60.96)

    b.add_symbol("CC0603KRX7R9BB104", "C10", "100nF", "ionic_thrust_hv:C0603", 66.04, 76.20, srot=90, props={"LCSC Part": "C14663"})
    b.add_symbol("CC0805KKX5R8BB106", "C12", "10uF", "ionic_thrust_hv:C0805", 78.74, 76.20, srot=90, props={"LCSC Part": "C89831"})
    c10_p1 = b.get_pin("C10", 1)
    c10_p2 = b.get_pin("C10", 2)
    c12_p1 = b.get_pin("C12", 1)
    c12_p2 = b.get_pin("C12", 2)
    b.add_wire(c10_p1[0], c10_p1[1], 66.04, 60.96)
    b.add_wire(c12_p1[0], c12_p1[1], 78.74, 60.96)

    # Ground bus for driver
    b.add_wire(45.72, 147.32, 147.32, 147.32)
    b.add_wire(c10_p2[0], c10_p2[1], 66.04, 147.32)
    b.add_junction(66.04, 147.32)
    b.add_wire(c12_p2[0], c12_p2[1], 78.74, 147.32)
    b.add_junction(78.74, 147.32)
    b.add_wire_path([u2_gnd, (u2_gnd[0] - 5.08, u2_gnd[1]), (u2_gnd[0] - 5.08, 147.32)])
    b.add_junction(u2_gnd[0] - 5.08, 147.32)

    # Inputs to U2:
    # DRV_IN1 -> Pin 6
    b.add_wire(45.72, 106.68, 55.88, 106.68)
    b.add_wire_path([(55.88, 106.68), (55.88, 160.02), (134.62, 160.02), (134.62, u2_in1[1]), u2_in1])

    # DRV_IN2 -> Pin 5
    b.add_wire(45.72, 116.84, 53.34, 116.84)
    b.add_wire_path([(53.34, 116.84), (53.34, 165.10), (137.16, 165.10), (137.16, u2_in2[1]), u2_in2])

    # DRV_nSLEEP -> Pin 8 with R5 (10k) pulldown to GND
    # Route via Y=86.36 directly across to U2 nSLEEP at X=142.24 without crossing GND!
    b.add_wire(45.72, 86.36, 142.24, 86.36)
    b.add_wire_path([(142.24, 86.36), (142.24, u2_nsleep[1]), u2_nsleep])
    b.add_junction(58.42, 86.36)

    b.add_symbol("0603WAF1002T5E", "R5", "10k", "ionic_thrust_hv:R0603", 58.42, 101.60, srot=90, props={"LCSC Part": "C25804"})
    r5_p1 = b.get_pin("R5", 1)
    r5_p2 = b.get_pin("R5", 2)
    b.add_wire(r5_p1[0], r5_p1[1], 58.42, 86.36)
    b.add_wire(r5_p2[0], r5_p2[1], 58.42, 147.32)
    b.add_junction(58.42, 147.32)

    # U2 MODE (Pin 7) and EP (Pin 9) tied to GND
    b.add_wire_path([u2_mode, (129.54, u2_mode[1]), (129.54, 147.32)])
    b.add_junction(129.54, 147.32)
    b.add_wire_path([u2_ep, (129.54, u2_ep[1])])
    b.add_junction(129.54, u2_ep[1])

    # Driver Outputs: OUT1 (pin 2 / DRV_A) and OUT2 (pin 3 / DRV_B)
    # Resonant Capacitor C11 (120nF 100V film) at (165.10, 96.52)
    b.add_symbol("BFC236821124", "C11", "120nF 100V", "ionic_thrust_hv:C_Radial_P10.0mm",
        165.10, 96.52, srot=0, props={"LCSC Part": "C3771644", "MPN": "BFC236821124"}, dnp=True)
    c11_p1 = b.get_pin("C11", 1)
    c11_p2 = b.get_pin("C11", 2)

    b.add_wire_path([u2_out1, (u2_out1[0] - 5.08, u2_out1[1]), (u2_out1[0] - 5.08, 96.52), c11_p1])

    # Transformer T1 (FL2015-4LD) at (228.60, 101.60)
    b.add_symbol("FL2015-4LD", "T1", "FL2015-4LD", "ionic_thrust_hv:Coilcraft_FL2015-4L",
        228.60, 101.60, srot=0, props={"MPN": "FL2015-4LD", "Manufacturer": "Coilcraft"}, dnp=True)
    t1_p1 = b.get_pin("T1", 1) # PRI_A
    t1_p2 = b.get_pin("T1", 2) # PRI_CT
    t1_p3 = b.get_pin("T1", 3) # PRI_B
    t1_p5 = b.get_pin("T1", 5) # SEC_A
    t1_p8 = b.get_pin("T1", 8) # SEC_B (HV_RETURN)

    # C11 pin 2 to T1 pin 1 (PRI_A)
    b.add_wire(c11_p2[0], c11_p2[1], t1_p1[0], t1_p1[1])
    b.add_label("PRI_A", round((c11_p2[0] + t1_p1[0])/2, 2), 96.52)

    # U2 OUT2 to T1 pin 3 (PRI_B)
    b.add_wire_path([u2_out2, (u2_out2[0] - 7.62, u2_out2[1]), (u2_out2[0] - 7.62, 106.68), t1_p3])
    b.add_label("DRV_B", 165.10, 106.68)

    # T1 Pin 2 NC
    b.add_no_connect_pin("T1", 2)
    b.add_no_connect_pin("T1", 4)
    b.add_no_connect_pin("T1", 9)

    # Secondary Outputs to Hierarchical Labels
    b.add_wire(t1_p5[0], t1_p5[1], 355.60, t1_p5[1])
    b.add_hier_label("SEC_A", "output", 355.60, t1_p5[1])
    b.add_label("SEC_A", 280.00, t1_p5[1])

    b.add_wire(t1_p8[0], t1_p8[1], 355.60, t1_p8[1])
    b.add_hier_label("HV_RETURN", "output", 355.60, t1_p8[1])
    b.add_label("HV_RETURN", 280.00, t1_p8[1])

    # Design Notes Block
    b.add_text("RESONANT TANK SPECIFICATIONS:", 35.56, 182.88, size=1.778, bold=True)
    b.add_text("1. Resonant frequency fr ≈ 69.3 kHz (L_pri ≈ 44 uH, C11 = 120 nF 100V film).", 38.10, 190.50, size=1.524, bold=False)
    b.add_text("2. Transformer ratio: ~1:100 step-up, delivering ~1.4 kV AC peak to Cockcroft-Walton ladder.", 38.10, 196.85, size=1.524, bold=False)
    b.add_text("3. HV_RETURN is isolated from low-voltage GND; connects via 10k current shunt on Sheet 4.", 38.10, 203.20, size=1.524, bold=False)

    return b.build()

# ==============================================================================
# 4. SHEET 03: MULTIPLIER
# ==============================================================================
def generate_multiplier_sch():
    b = SchematicBuilder("03 6-Stage Positive Cockcroft-Walton Multiplier & Bleeders")

    b.add_text("6-STAGE POSITIVE COCKCROFT-WALTON VOLTAGE MULTIPLIER & PASSIVE BLEEDERS", 33.02, 35.56, size=2.54, bold=True)
    b.add_rect(30.48, 30.48, 396.24, 254.00)

    # Inputs from Transformer Secondary
    b.add_hier_label("SEC_A", "input", 45.72, 86.36)
    b.add_hier_label("HV_RETURN", "input", 45.72, 172.72)

    Y_pump_r = 71.12
    Y_pump_c = 86.36
    Y_stack_c = 172.72
    Y_stack_r = 187.96

    # Input feed wires
    b.add_wire(45.72, 86.36, 68.58, 86.36)
    b.add_wire(45.72, 172.72, 68.58, 172.72)

    for stage in range(1, 7):
        x_center = 83.82 + (stage - 1) * 48.26
        x_left = x_center - 15.24
        x_right = x_center + 15.24

        d_pump_ref = f"D{10 + (stage-1)*2}"
        d_stack_ref = f"D{11 + (stage-1)*2}"
        c_pump_ref = f"C{20 + (stage-1)*2}"
        c_stack_ref = f"C{21 + (stage-1)*2}"
        r_pump_ref = f"R{40 + (stage-1)*2}"
        r_stack_ref = f"R{41 + (stage-1)*2}"

        # Stage Header
        b.add_text(f"STAGE {stage} (+{stage*2.8:.1f} kV)", x_center - 15.24, 53.34, size=1.778, bold=True)

        # 1. Pump Capacitor and Bleeder Resistor (Top Rail)
        b.add_symbol("S102M59Z5UU83L0R", c_pump_ref, "1nF 6kV", "ionic_thrust_hv:CAP-TH_L15.0-W4.0-P10.00-D0.6",
            x_center, Y_pump_c, srot=0, props={"LCSC Part": "C1620009"}, dnp=True)
        b.add_symbol("MGR0W2J0107A10", r_pump_ref, "100M 3.5kV", "ionic_thrust_hv:RES-TH_BD3.5-L9.5-P13.50-D0.6",
            x_center, Y_pump_r, srot=0, props={"LCSC Part": "C51904773"}, dnp=True)

        cp_p1 = b.get_pin(c_pump_ref, 1)
        cp_p2 = b.get_pin(c_pump_ref, 2)
        rp_p1 = b.get_pin(r_pump_ref, 1)
        rp_p2 = b.get_pin(r_pump_ref, 2)

        # Wire pump cap and bleeder in parallel
        b.add_wire(x_left, Y_pump_c, cp_p1[0], cp_p1[1])
        b.add_junction(x_left, Y_pump_c)
        b.add_wire_path([(x_left, Y_pump_c), (x_left, Y_pump_r), rp_p1])

        b.add_wire(cp_p2[0], cp_p2[1], x_right, Y_pump_c)
        b.add_junction(x_right, Y_pump_c)
        b.add_wire_path([rp_p2, (x_right, Y_pump_r), (x_right, Y_pump_c)])

        # 2. Stack Capacitor and Bleeder Resistor (Bottom Rail)
        b.add_symbol("S102M59Z5UU83L0R", c_stack_ref, "1nF 6kV", "ionic_thrust_hv:CAP-TH_L15.0-W4.0-P10.00-D0.6",
            x_center, Y_stack_c, srot=0, props={"LCSC Part": "C1620009"}, dnp=True)
        b.add_symbol("MGR0W2J0107A10", r_stack_ref, "100M 3.5kV", "ionic_thrust_hv:RES-TH_BD3.5-L9.5-P13.50-D0.6",
            x_center, Y_stack_r, srot=0, props={"LCSC Part": "C51904773"}, dnp=True)

        cs_p1 = b.get_pin(c_stack_ref, 1)
        cs_p2 = b.get_pin(c_stack_ref, 2)
        rs_p1 = b.get_pin(r_stack_ref, 1)
        rs_p2 = b.get_pin(r_stack_ref, 2)

        # Wire stack cap and bleeder in parallel
        b.add_wire(x_left, Y_stack_c, cs_p1[0], cs_p1[1])
        b.add_junction(x_left, Y_stack_c)
        b.add_wire_path([(x_left, Y_stack_c), (x_left, Y_stack_r), rs_p1])

        b.add_wire(cs_p2[0], cs_p2[1], x_right, Y_stack_c)
        b.add_junction(x_right, Y_stack_c)
        b.add_wire_path([rs_p2, (x_right, Y_stack_r), (x_right, Y_stack_c)])

        # 3. Diodes
        # d_pump points UP: Anode (pin 2) at stack rail, Cathode (pin 1) at pump rail. rot=270
        b.add_symbol("HVM12", d_pump_ref, "HVM12", "ionic_thrust_hv:DO-722_BD7.5-L22.0-P26.00-D1.2-RD",
            x_center - 7.62, 129.54, srot=270, props={"LCSC Part": "C7436450", "MPN": "HVM12"}, dnp=True)
        dp_k = b.get_pin(d_pump_ref, 1)
        dp_a = b.get_pin(d_pump_ref, 2)

        b.add_wire_path([dp_k, (dp_k[0], Y_pump_c), (x_right, Y_pump_c)])
        b.add_wire_path([dp_a, (dp_a[0], Y_stack_c), (x_left, Y_stack_c)])

        # d_stack points DOWN: Anode (pin 2) at pump rail, Cathode (pin 1) at stack rail. rot=90
        b.add_symbol("HVM12", d_stack_ref, "HVM12", "ionic_thrust_hv:DO-722_BD7.5-L22.0-P26.00-D1.2-RD",
            x_center + 7.62, 129.54, srot=90, props={"LCSC Part": "C7436450", "MPN": "HVM12"}, dnp=True)
        ds_k = b.get_pin(d_stack_ref, 1)
        ds_a = b.get_pin(d_stack_ref, 2)

        b.add_wire_path([ds_a, (ds_a[0], Y_pump_c), (x_right, Y_pump_c)])
        b.add_wire_path([ds_k, (ds_k[0], Y_stack_c), (x_right, Y_stack_c)])

        # Inter-stage horizontal connection to next stage
        if stage < 6:
            next_x_left = (x_center + 48.26) - 15.24
            b.add_wire(x_right, Y_pump_c, next_x_left, Y_pump_c)
            # Label placed EXACTLY on the wire at Y_pump_c!
            b.add_label(f"CW_P{stage}", round((x_right + next_x_left)/2, 2), Y_pump_c)

            b.add_wire(x_right, Y_stack_c, next_x_left, Y_stack_c)
            # Label placed EXACTLY on the wire at Y_stack_c!
            b.add_label(f"CW_S{stage}", round((x_right + next_x_left)/2, 2), Y_stack_c)

    # Final Stage Outputs
    final_x = 83.82 + 5 * 48.26 + 15.24 # 340.36
    b.add_wire(final_x, Y_stack_c, 375.92, Y_stack_c)
    b.add_label("HV_RAW", 360.68, Y_stack_c)
    b.add_hier_label("HV_RAW", "output", 375.92, Y_stack_c)

    # HV_RETURN line continues along bottom
    b.add_wire_path([(68.58, 172.72), (68.58, 203.20), (375.92, 203.20)])
    b.add_junction(68.58, 172.72)
    b.add_label("HV_RETURN", 220.00, 203.20)
    b.add_hier_label("HV_RETURN", "output", 375.92, 203.20)

    # Multiplier Safety & Design Notes
    b.add_text("SAFETY & DISCHARGE SPECIFICATIONS:", 35.56, 218.44, size=1.778, bold=True)
    b.add_text("1. Nominal open-circuit output voltage: ~17 kV DC (regulated by MCU PWM duty cycle to +10 kV .. +15 kV DC).", 38.10, 226.06, size=1.524, bold=False)
    b.add_text("2. PASSIVE DISCHARGE: 12x 100M 3.5kV bleeder resistors discharge all capacitors to < 50V within 5 seconds of shutdown.", 38.10, 232.41, size=1.524, bold=False)
    b.add_text("3. CLEARANCE: Minimum 4.0 mm clearance maintained between adjacent stages; all inner copper planes removed beneath ladder.", 38.10, 238.76, size=1.524, bold=False)

    return b.build()

# ==============================================================================
# 5. SHEET 04: SENSE, SAFETY & INTERLOCK
# ==============================================================================
def generate_sense_safety_sch():
    b = SchematicBuilder("04 Ballast, Divider, Sensing & Hardware Interlock")

    # Section 1: Output Ballast String & Terminal J3
    b.add_text("OUTPUT BALLAST STRING (100 M-OHM TOTAL, 150 uA SHORT-CIRCUIT LIMIT)", 33.02, 38.10, size=2.54, bold=True)
    b.add_rect(30.48, 33.02, 391.16, 83.82)

    b.add_hier_label("HV_RAW", "input", 40.64, 53.34)

    # 10 Ballast Resistors R20..R29 (10M 3.5kV each) in series
    b.add_wire(40.64, 53.34, 48.26, 53.34)
    prev_x = 48.26
    for i in range(10):
        ref = f"R{20 + i}"
        rx = 58.42 + i * 25.40
        b.add_symbol("MGR0W2J0106A10", ref, "10M 3.5kV", "ionic_thrust_hv:RES-TH_BD3.5-L9.5-P13.50-D0.6",
            rx, 53.34, srot=0, props={"LCSC Part": "C51904770"}, dnp=True)
        rp1 = b.get_pin(ref, 1)
        rp2 = b.get_pin(ref, 2)
        b.add_wire(prev_x, 53.34, rp1[0], rp1[1])
        prev_x = rp2[0]

    # After R29: net is HV_OUT
    b.add_wire(prev_x, 53.34, 320.04, 53.34)
    b.add_junction(320.04, 53.34)
    b.add_label("HV_OUT", 320.04, 53.34)

    # High Voltage Output Terminal J3 (WJ500V-5.08-2P) at (350.52, 58.42)
    b.add_symbol("WJ500V-5.08-2P-14-00A", "J3", "HV_OUT_TERMINAL", "ionic_thrust_hv:CONN-TH_2P-P5.00_WJ500V-5.08-2P",
        350.52, 58.42, srot=0, props={"LCSC Part": "C8465"}, dnp=True)
    j3_p1 = b.get_pin("J3", 1) # (349.25, 63.50)
    j3_p2 = b.get_pin("J3", 2) # (351.79, 63.50)
    b.add_wire_path([j3_p1, (349.25, 53.34), (320.04, 53.34)])

    # HV_RETURN input and connection to J3
    b.add_hier_label("HV_RETURN", "input", 40.64, 76.20)
    b.add_wire(40.64, 76.20, 360.00, 76.20)
    b.add_junction(101.60, 76.20)
    b.add_junction(351.79, 76.20)
    b.add_label("HV_RETURN", 180.00, 76.20)
    b.add_wire_path([j3_p2, (351.79, 76.20)])

    # Section 2: 1 G-ohm Divider & TLV9001 Buffer
    b.add_text("1 G-OHM HIGH VOLTAGE DIVIDER (RATIO 6098:1) & BUFFER", 33.02, 93.98, size=2.54, bold=True)
    b.add_rect(30.48, 88.90, 391.16, 160.02)

    # Branch from HV_OUT to divider string
    b.add_wire_path([(320.04, 53.34), (320.04, 96.52), (48.26, 96.52), (48.26, 106.68)])

    # 10 Divider Resistors R30..R39 (100M 3.5kV each) in series
    prev_x = 48.26
    for i in range(10):
        ref = f"R{30 + i}"
        rx = 58.42 + i * 25.40
        b.add_symbol("MGR0W2J0107A10", ref, "100M 3.5kV", "ionic_thrust_hv:RES-TH_BD3.5-L9.5-P13.50-D0.6",
            rx, 106.68, srot=0, props={"LCSC Part": "C51904773"}, dnp=True)
        rp1 = b.get_pin(ref, 1)
        rp2 = b.get_pin(ref, 2)
        b.add_wire(prev_x, 106.68, rp1[0], rp1[1])
        prev_x = rp2[0]

    # After R39: net is HV_SENSE_RAW
    b.add_wire(prev_x, 106.68, 304.80, 106.68)
    b.add_junction(304.80, 106.68)
    b.add_label("HV_SENSE_RAW", 304.80, 106.68)

    # Low leg: R8 (82k), R9 (82k), C13 (100nF) to GND
    b.add_symbol("0603WAF8202T5E", "R8", "82k", "ionic_thrust_hv:R0603", 264.16, 124.46, srot=90, props={"LCSC Part": "C23254"})
    b.add_symbol("0603WAF8202T5E", "R9", "82k", "ionic_thrust_hv:R0603", 264.16, 142.24, srot=90, props={"LCSC Part": "C23254"})
    b.add_symbol("CC0603KRX7R9BB104", "C13", "100nF", "ionic_thrust_hv:C0603", 276.86, 124.46, srot=90, props={"LCSC Part": "C14663"})

    r8_p1 = b.get_pin("R8", 1)
    r8_p2 = b.get_pin("R8", 2)
    r9_p1 = b.get_pin("R9", 1)
    r9_p2 = b.get_pin("R9", 2)
    c13_p1 = b.get_pin("C13", 1)
    c13_p2 = b.get_pin("C13", 2)

    b.add_wire_path([(304.80, 106.68), (264.16, 106.68), r8_p1])
    b.add_junction(264.16, 106.68)
    b.add_wire(r8_p2[0], r8_p2[1], r9_p1[0], r9_p1[1])
    b.add_wire(r9_p2[0], r9_p2[1], 264.16, 152.40)
    b.add_label("GND", 264.16, 152.40)

    # C13 in parallel
    b.add_wire_path([c13_p1, (276.86, 106.68), (304.80, 106.68)])
    b.add_junction(276.86, 106.68)
    b.add_wire(c13_p2[0], c13_p2[1], 276.86, 152.40)
    b.add_label("GND", 276.86, 152.40)

    # Buffer U4 (TLV9001IDBVR) at (314.96, 124.46)
    b.add_symbol("TLV9001IDBVR", "U4", "TLV9001", "ionic_thrust_hv:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR",
        314.96, 124.46, srot=0, props={"LCSC Part": "C398363", "MPN": "TLV9001IDBVR"})
    u4_out = b.get_pin("U4", 1)
    u4_vm = b.get_pin("U4", 2)
    u4_inp = b.get_pin("U4", 3)
    u4_inm = b.get_pin("U4", 4)
    u4_vp = b.get_pin("U4", 5)

    # IN+ from HV_SENSE_RAW
    b.add_wire_path([(304.80, 106.68), (304.80, u4_inp[1]), u4_inp])

    # Unity-gain feedback: OUT (pin 1) to IN- (pin 4)
    b.add_wire_path([u4_out, (302.26, u4_out[1]), (302.26, 114.30), (327.66, 114.30), (327.66, u4_inm[1]), u4_inm])
    b.add_junction(302.26, u4_out[1])

    # Power for U4: V+ to 3V3, V- to GND
    b.add_wire(u4_vp[0], u4_vp[1], u4_vp[0] + 5.08, u4_vp[1])
    b.add_label("3V3", u4_vp[0] + 5.08, u4_vp[1])
    b.add_wire(u4_vm[0], u4_vm[1], u4_vm[0] - 5.08, u4_vm[1])
    b.add_label("GND", u4_vm[0] - 5.08, u4_vm[1])

    # Output protection: R7 (1k) and D1 (BAT54S) clamp
    b.add_symbol("0603WAF1001T5E", "R7", "1k", "ionic_thrust_hv:R0603", 340.36, 124.46, srot=0, props={"LCSC Part": "C21190"})
    r7_p1 = b.get_pin("R7", 1)
    r7_p2 = b.get_pin("R7", 2)
    b.add_wire_path([(302.26, u4_out[1]), (302.26, 124.46), r7_p1])

    # D1 BAT54S (1=A1 GND, 2=K2 3V3, 3=A/K)
    b.add_symbol("BAT54S", "D1", "BAT54S", "ionic_thrust_hv:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR",
        358.14, 124.46, srot=90, props={"LCSC Part": "C83935"})
    d1_p1 = b.get_pin("D1", 1) # GND
    d1_p2 = b.get_pin("D1", 2) # 3V3
    d1_p3 = b.get_pin("D1", 3) # HV_SENSE_ADC
    b.add_wire(d1_p1[0], d1_p1[1], d1_p1[0], 142.24)
    b.add_label("GND", d1_p1[0], 142.24)
    b.add_wire(d1_p2[0], d1_p2[1], d1_p2[0], 114.30)
    b.add_label("3V3", d1_p2[0], 114.30)

    b.add_wire(r7_p2[0], r7_p2[1], d1_p3[0], d1_p3[1])
    b.add_junction(d1_p3[0], d1_p3[1])
    b.add_wire(d1_p3[0], d1_p3[1], 375.92, d1_p3[1])
    b.add_hier_label("HV_SENSE_ADC", "output", 375.92, d1_p3[1])

    # Section 3: HV Return Current Sense Shunt
    b.add_text("HV RETURN CURRENT SHUNT (10 k-OHM, 1.5 V @ 150 uA)", 33.02, 172.72, size=2.54, bold=True)
    b.add_rect(30.48, 167.64, 182.88, 246.38)

    # Shunt R10 (10k 0603) from HV_RETURN to GND
    # rot=90: pin 1 is top at Y=187.96, pin 2 is bottom at Y=198.12
    b.add_symbol("0603WAF1002T5E", "R10", "10k Shunt", "ionic_thrust_hv:R0603", 55.88, 193.04, srot=90, props={"LCSC Part": "C25804"})
    r10_p1 = b.get_pin("R10", 1) # HV_RETURN @ (55.88, 187.96)
    r10_p2 = b.get_pin("R10", 2) # GND @ (55.88, 198.12)
    b.add_wire_path([(101.60, 76.20), (55.88, 76.20), r10_p1])
    b.add_wire(r10_p2[0], r10_p2[1], 55.88, 213.36)
    b.add_label("GND", 55.88, 213.36)

    # Filter R11 (1k) and C14 (100nF)
    b.add_symbol("0603WAF1001T5E", "R11", "1k", "ionic_thrust_hv:R0603", 83.82, 187.96, srot=0, props={"LCSC Part": "C21190"})
    r11_p1 = b.get_pin("R11", 1)
    r11_p2 = b.get_pin("R11", 2)
    b.add_wire(r10_p1[0], r10_p1[1], r11_p1[0], r11_p1[1])
    b.add_junction(55.88, 187.96)

    b.add_symbol("CC0603KRX7R9BB104", "C14", "100nF", "ionic_thrust_hv:C0603", 109.22, 198.12, srot=90, props={"LCSC Part": "C14663"})
    c14_p1 = b.get_pin("C14", 1)
    c14_p2 = b.get_pin("C14", 2)
    b.add_wire_path([r11_p2, (109.22, 187.96), c14_p1])
    b.add_junction(109.22, 187.96)
    b.add_wire(c14_p2[0], c14_p2[1], 109.22, 213.36)
    b.add_label("GND", 109.22, 213.36)

    # Clamp diode D4 (BAT54S)
    b.add_symbol("BAT54S", "D4", "BAT54S", "ionic_thrust_hv:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR",
        134.62, 187.96, srot=90, props={"LCSC Part": "C83935"})
    d4_p1 = b.get_pin("D4", 1) # GND
    d4_p2 = b.get_pin("D4", 2) # 3V3
    d4_p3 = b.get_pin("D4", 3) # HV_CURR_ADC
    b.add_wire(d4_p1[0], d4_p1[1], d4_p1[0], 213.36)
    b.add_label("GND", d4_p1[0], 213.36)
    b.add_wire(d4_p2[0], d4_p2[1], d4_p2[0], 175.26)
    b.add_label("3V3", d4_p2[0], 175.26)

    b.add_wire(109.22, 187.96, d4_p3[0], d4_p3[1])
    b.add_junction(d4_p3[0], d4_p3[1])
    b.add_wire(d4_p3[0], d4_p3[1], 167.64, d4_p3[1])
    b.add_hier_label("HV_CURR_ADC", "output", 167.64, d4_p3[1])

    # Section 4: Hardware Safety Interlock
    b.add_text("HARDWARE SAFETY INTERLOCK (DUAL REDUNDANT LID SWITCHES)", 198.12, 172.72, size=2.54, bold=True)
    b.add_rect(193.04, 167.64, 391.16, 246.38)

    b.add_label("VIN_PROTECTED", 203.20, 185.42)

    # Switch S3 (Omron D2F-L) at (220.98, 190.50)
    b.add_symbol("D2F-L", "S3", "LID_SW_1", "ionic_thrust_hv:SW-TH_D2F-L",
        220.98, 190.50, srot=0, props={"LCSC Part": "C231337", "MPN": "D2F-L"}, dnp=True)
    s3_com = b.get_pin("S3", 1)
    s3_no = b.get_pin("S3", 2)
    b.add_no_connect_pin("S3", 3)
    b.add_wire_path([(203.20, 185.42), (203.20, s3_com[1]), s3_com])

    # Switch S4 (Omron D2F-L) at (251.46, 190.50)
    b.add_symbol("D2F-L", "S4", "LID_SW_2", "ionic_thrust_hv:SW-TH_D2F-L",
        251.46, 190.50, srot=0, props={"LCSC Part": "C231337", "MPN": "D2F-L"}, dnp=True)
    s4_com = b.get_pin("S4", 1)
    s4_no = b.get_pin("S4", 2)
    b.add_no_connect_pin("S4", 3)

    # S3 NO to S4 COM
    b.add_wire_path([s3_no, (s3_no[0], 203.20), (s4_com[0], 203.20), s4_com])
    b.add_label("LID_INT", round((s3_no[0]+s4_com[0])/2, 2), 203.20)

    # Relay K1 (N4078-2C-12V) at (309.88, 203.20)
    b.add_symbol("N4078-2C-12V", "K1", "DPDT_RELAY", "ionic_thrust_hv:Relay_DPDT_N4078",
        309.88, 203.20, srot=0, props={"LCSC Part": "C52195125", "MPN": "N4078-2C-12V"}, dnp=True)
    k1_cp = b.get_pin("K1", 1)
    k1_cm = b.get_pin("K1", 16)
    k1_com1 = b.get_pin("K1", 4)
    k1_no1 = b.get_pin("K1", 8)
    k1_com2 = b.get_pin("K1", 13)
    k1_no2 = b.get_pin("K1", 9)

    b.add_no_connect_pin("K1", 6)
    b.add_no_connect_pin("K1", 11)

    # S4 NO to Relay COIL+
    b.add_wire_path([s4_no, (s4_no[0], 208.28), (284.48, 208.28), (284.48, k1_cp[1]), k1_cp])
    b.add_junction(284.48, k1_cp[1])
    b.add_label("RELAY_COIL_POS", 284.48, k1_cp[1])

    # Flyback Diode D3 (1N4148WS) across coil (Cathode=pin 1, Anode=pin 2)
    b.add_symbol("1N4148WS", "D3", "1N4148WS", "ionic_thrust_hv:D_SOD-323",
        284.48, 205.74, srot=90, props={"LCSC Part": "C81598"})
    d3_k = b.get_pin("D3", 1)
    d3_a = b.get_pin("D3", 2)
    b.add_wire(d3_k[0], d3_k[1], 284.48, k1_cp[1])
    b.add_wire(d3_a[0], d3_a[1], 284.48, k1_cm[1])
    b.add_junction(284.48, k1_cm[1])

    # Relay COIL- to GND
    b.add_wire(k1_cm[0], k1_cm[1], 284.48, k1_cm[1])
    b.add_wire(284.48, k1_cm[1], 284.48, 226.06)
    b.add_label("GND", 284.48, 226.06)

    # Pole 1: COM1 (pin 4) to VIN_PROTECTED, NO1 (pin 8) to HV_VM
    b.add_wire_path([(203.20, 185.42), (203.20, 180.34), (330.20, 180.34), (330.20, k1_com1[1]), k1_com1])
    b.add_junction(203.20, 185.42)
    b.add_wire(k1_no1[0], k1_no1[1], 375.92, k1_no1[1])
    b.add_hier_label("HV_VM", "output", 375.92, k1_no1[1])

    # Pole 2: COM2 (pin 13) to 3V3, NO2 (pin 9) to INTERLOCK_OK
    b.add_wire(k1_com2[0], k1_com2[1], k1_com2[0] + 7.62, k1_com2[1])
    b.add_label("3V3", k1_com2[0] + 7.62, k1_com2[1])
    b.add_wire(k1_no2[0], k1_no2[1], 375.92, k1_no2[1])
    b.add_hier_label("INTERLOCK_OK", "output", 375.92, k1_no2[1])

    # Sheet power & ground hierarchical ports
    b.add_hier_label("VIN_PROTECTED", "input", 35.56, 147.32)
    b.add_wire(35.56, 147.32, 45.72, 147.32)
    b.add_label("VIN_PROTECTED", 45.72, 147.32)

    b.add_hier_label("3V3", "input", 35.56, 154.94)
    b.add_wire(35.56, 154.94, 45.72, 154.94)
    b.add_label("3V3", 45.72, 154.94)

    b.add_hier_label("GND", "bidirectional", 35.56, 162.56)
    b.add_wire(35.56, 162.56, 45.72, 162.56)
    b.add_label("GND", 45.72, 162.56)

    return b.build()

# ==============================================================================
# MAIN
# ==============================================================================
def main():
    hw_dir = "/home/uge/Development/ew-1/hardware"
    os.makedirs(hw_dir, exist_ok=True)

    files = {
        "ionic_thrust_hv.kicad_sch": generate_root_sch(),
        "01_power_mcu.kicad_sch": generate_power_mcu_sch(),
        "02_drive_transformer.kicad_sch": generate_drive_transformer_sch(),
        "03_multiplier.kicad_sch": generate_multiplier_sch(),
        "04_sense_safety.kicad_sch": generate_sense_safety_sch()
    }

    for fname, data in files.items():
        path = os.path.join(hw_dir, fname)
        with open(path, "w") as f:
            f.write(data)
        print(f"Generated {path}")

if __name__ == "__main__":
    main()
