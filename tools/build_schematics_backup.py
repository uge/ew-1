#!/usr/bin/env python3
"""
KiCad 10 Complete Hierarchical Schematic Generator
ESP32 12V to 15kV DC Corona Supply.
Generates:
  - hardware/ionic_thrust_hv.kicad_sch (Root hierarchical sheet)
  - hardware/01_power_mcu.kicad_sch
  - hardware/02_drive_transformer.kicad_sch
  - hardware/03_multiplier.kicad_sch
  - hardware/04_sense_safety.kicad_sch
"""

import uuid
import os
import json
import re

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
    s = re.sub(r"^\s*\(symbol \"([^\":]+)\"", "    (symbol \"ionic_thrust_hv:\\1\"", s)
    s = re.sub(r"\s*\(id\s+\d+\)", "", s)
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
		(rev "A")
		(date "2026-09-27")
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

def make_hier_label(name, shape, x, y, angle=0):
    return f"""	(hierarchical_label "{name}"
		(shape {shape})
		(at {x:.2f} {y:.2f} {angle})
		(effects (font (size 1.27 1.27)))
		(uuid "{gen_uuid()}")
	)
	(label "{name}"
		(at {x:.2f} {y:.2f} {angle})
		(effects (font (size 1.27 1.27)))
		(uuid "{gen_uuid()}")
	)
"""

def make_label(name, x, y, angle=0):
    return f"""	(label "{name}"
		(at {x:.2f} {y:.2f} {angle})
		(effects (font (size 1.27 1.27)))
		(uuid "{gen_uuid()}")
	)
"""

def make_wire(x1, y1, x2, y2):
    return f"""	(wire
		(pts (xy {x1:.2f} {y1:.2f}) (xy {x2:.2f} {y2:.2f}))
		(stroke (width 0) (type default))
		(uuid "{gen_uuid()}")
	)
"""

def make_junction(x, y):
    return f"""	(junction
		(at {x:.2f} {y:.2f})
		(diameter 0)
		(color 0 0 0 0)
		(uuid "{gen_uuid()}")
	)
"""

def make_no_connect(x, y):
    return f"""	(no_connect (at {x:.2f} {y:.2f}) (uuid "{gen_uuid()}"))
"""

def make_symbol_with_connections(lib_name, ref, val, footprint, sx, sy, srot, connections, props=None, dnp=False):
    """
    connections: dict of {pin_num: net_name or None for no_connect}
    """
    prop_str = f"""		(property "Reference" "{ref}" (at {sx:.2f} {sy-2.54:.2f} 0) (effects (font (size 1.27 1.27))))
		(property "Value" "{val}" (at {sx:.2f} {sy+2.54:.2f} 0) (effects (font (size 1.27 1.27))))
		(property "Footprint" "{footprint}" (at {sx:.2f} {sy+5.08:.2f} 0) (effects (font (size 1.27 1.27)) hide))
"""
    if props:
        offset = 7.62
        for k, v in props.items():
            prop_str += f"""		(property "{k}" "{v}" (at {sx:.2f} {sy+offset:.2f} 0) (effects (font (size 1.27 1.27)) hide))\n"""
            offset += 2.54
    dnp_str = "yes" if dnp else "no"
    pin_str = ""
    for p in connections.keys():
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
    labels_output = ""
    for p, net in connections.items():
        wx, wy = get_pin_pos(lib_name, p, sx, sy, srot)
        if net is None or net == "NC":
            labels_output += make_no_connect(wx, wy)
        else:
            labels_output += make_label(net, wx, wy, 0)

    return sym_output + labels_output

# ==============================================================================
# 1. ROOT SCHEMATIC
# ==============================================================================
def generate_root_sch():
    content = sch_header("ESP32 12V to 15kV DC Corona Supply - Top Level")
    
    # Sheet 1: Power and MCU
    content += f"""	(sheet
		(at 25.40 38.10)
		(size 63.50 88.90)
		(fields_autoplaced yes)
		(stroke (width 0.1524) (type solid))
		(fill (color 0 0 0 0.0000))
		(uuid "{gen_uuid()}")
		(property "Sheetname" "01_power_mcu" (at 25.40 35.56 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
		(property "Sheetfile" "01_power_mcu.kicad_sch" (at 25.40 129.54 0) (effects (font (size 1.27 1.27)) (justify left top)))
		(pin "VIN_PROTECTED" output (at 88.90 50.80 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "DRV_IN1" output (at 88.90 58.42 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "DRV_IN2" output (at 88.90 66.04 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_SENSE_ADC" input (at 88.90 81.28 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_CURR_ADC" input (at 88.90 88.90 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "INTERLOCK_OK" input (at 88.90 96.52 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "3V3" output (at 88.90 104.14 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "GND" bidirectional (at 88.90 111.76 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
	)
"""

    # Sheet 2: Driver & Transformer
    content += f"""	(sheet
		(at 127.00 38.10)
		(size 63.50 76.20)
		(fields_autoplaced yes)
		(stroke (width 0.1524) (type solid))
		(fill (color 0 0 0 0.0000))
		(uuid "{gen_uuid()}")
		(property "Sheetname" "02_drive_transformer" (at 127.00 35.56 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
		(property "Sheetfile" "02_drive_transformer.kicad_sch" (at 127.00 116.84 0) (effects (font (size 1.27 1.27)) (justify left top)))
		(pin "HV_VM" input (at 127.00 50.80 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "DRV_IN1" input (at 127.00 58.42 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "DRV_IN2" input (at 127.00 66.04 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "DRV_nSLEEP" input (at 127.00 73.66 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "SEC_A" output (at 190.50 50.80 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_RETURN" output (at 190.50 66.04 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "GND" bidirectional (at 127.00 88.90 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
	)
"""

    # Sheet 3: Multiplier
    content += f"""	(sheet
		(at 228.60 38.10)
		(size 63.50 63.50)
		(fields_autoplaced yes)
		(stroke (width 0.1524) (type solid))
		(fill (color 0 0 0 0.0000))
		(uuid "{gen_uuid()}")
		(property "Sheetname" "03_multiplier" (at 228.60 35.56 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
		(property "Sheetfile" "03_multiplier.kicad_sch" (at 228.60 104.14 0) (effects (font (size 1.27 1.27)) (justify left top)))
		(pin "SEC_A" input (at 228.60 50.80 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_RETURN" input (at 228.60 66.04 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_RAW" output (at 292.10 50.80 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_RETURN" output (at 292.10 66.04 0) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
	)
"""

    # Sheet 4: Sense & Safety
    content += f"""	(sheet
		(at 330.20 38.10)
		(size 63.50 114.30)
		(fields_autoplaced yes)
		(stroke (width 0.1524) (type solid))
		(fill (color 0 0 0 0.0000))
		(uuid "{gen_uuid()}")
		(property "Sheetname" "04_sense_safety" (at 330.20 35.56 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
		(property "Sheetfile" "04_sense_safety.kicad_sch" (at 330.20 154.94 0) (effects (font (size 1.27 1.27)) (justify left top)))
		(pin "HV_RAW" input (at 330.20 50.80 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_RETURN" input (at 330.20 66.04 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "VIN_PROTECTED" input (at 330.20 78.74 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "3V3" input (at 330.20 86.36 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "GND" bidirectional (at 330.20 93.98 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_VM" output (at 330.20 104.14 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "INTERLOCK_OK" output (at 330.20 119.38 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_SENSE_ADC" output (at 330.20 127.00 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
		(pin "HV_CURR_ADC" output (at 330.20 134.62 180) (uuid "{gen_uuid()}") (effects (font (size 1.27 1.27))))
	)
"""

    # Inter-sheet connections:
    # Sheet 2 -> Sheet 3
    content += make_wire(190.50, 50.80, 228.60, 50.80) # SEC_A
    content += make_wire(190.50, 66.04, 228.60, 66.04) # HV_RETURN

    # Sheet 3 -> Sheet 4
    content += make_wire(292.10, 50.80, 330.20, 50.80) # HV_RAW
    content += make_wire(292.10, 66.04, 330.20, 66.04) # HV_RETURN

    # VIN_PROTECTED: Sheet 1 (88.9, 50.8) -> Sheet 4 (330.2, 78.74)
    content += make_wire(88.90, 50.80, 101.60, 50.80)
    content += make_wire(101.60, 50.80, 101.60, 142.24)
    content += make_wire(101.60, 142.24, 314.96, 142.24)
    content += make_wire(314.96, 142.24, 314.96, 78.74)
    content += make_wire(314.96, 78.74, 330.20, 78.74)

    # HV_VM: Sheet 4 (330.2, 104.14) -> Sheet 2 (127.0, 50.8)
    content += make_wire(330.20, 104.14, 317.50, 104.14)
    content += make_wire(317.50, 104.14, 317.50, 144.78)
    content += make_wire(317.50, 144.78, 114.30, 144.78)
    content += make_wire(114.30, 144.78, 114.30, 50.80)
    content += make_wire(114.30, 50.80, 127.00, 50.80)

    # DRV_IN1: Sheet 1 (88.9, 58.42) -> Sheet 2 (127.0, 58.42)
    content += make_wire(88.90, 58.42, 127.00, 58.42)

    # DRV_IN2: Sheet 1 (88.9, 66.04) -> Sheet 2 (127.0, 66.04)
    content += make_wire(88.90, 66.04, 127.00, 66.04)

    # INTERLOCK_OK: Sheet 4 (330.20, 119.38) -> Sheet 1 (88.90, 96.52) and Sheet 2 DRV_nSLEEP (127.00, 73.66)
    content += make_wire(330.20, 119.38, 312.42, 119.38)
    content += make_wire(312.42, 119.38, 312.42, 154.94)
    content += make_wire(312.42, 154.94, 91.44, 154.94)
    content += make_wire(91.44, 154.94, 91.44, 96.52)
    content += make_wire(91.44, 96.52, 88.90, 96.52)
    # Branch to Sheet 2 DRV_nSLEEP
    content += make_junction(121.92, 154.94)
    content += make_wire(121.92, 154.94, 121.92, 73.66)
    content += make_wire(121.92, 73.66, 127.00, 73.66)

    # HV_SENSE_ADC: Sheet 4 (330.2, 127.0) -> Sheet 1 (88.9, 81.28)
    content += make_wire(330.20, 127.00, 322.58, 127.00)
    content += make_wire(322.58, 127.00, 322.58, 149.86)
    content += make_wire(322.58, 149.86, 96.52, 149.86)
    content += make_wire(96.52, 149.86, 96.52, 81.28)
    content += make_wire(96.52, 81.28, 88.90, 81.28)

    # HV_CURR_ADC: Sheet 4 (330.2, 134.62) -> Sheet 1 (88.9, 88.90)
    content += make_wire(330.20, 134.62, 325.12, 134.62)
    content += make_wire(325.12, 134.62, 325.12, 152.40)
    content += make_wire(325.12, 152.40, 93.98, 152.40)
    content += make_wire(93.98, 152.40, 93.98, 88.90)
    content += make_wire(93.98, 88.90, 88.90, 88.90)

    # 3V3: Sheet 1 (88.9, 104.14) -> Sheet 4 (330.2, 86.36)
    content += make_wire(88.90, 104.14, 99.06, 104.14)
    content += make_wire(99.06, 104.14, 99.06, 157.48)
    content += make_wire(99.06, 157.48, 309.88, 157.48)
    content += make_wire(309.88, 157.48, 309.88, 86.36)
    content += make_wire(309.88, 86.36, 330.20, 86.36)

    # GND: Sheet 1 (88.9, 111.76) -> Sheet 2 (127.0, 88.90) and Sheet 4 (330.2, 93.98)
    content += make_wire(88.90, 111.76, 106.68, 111.76)
    content += make_wire(106.68, 111.76, 106.68, 88.90)
    content += make_wire(106.68, 88.90, 127.00, 88.90)
    content += make_junction(106.68, 111.76)
    content += make_wire(106.68, 111.76, 106.68, 160.02)
    content += make_wire(106.68, 160.02, 307.34, 160.02)
    content += make_wire(307.34, 160.02, 307.34, 93.98)
    content += make_wire(307.34, 93.98, 330.20, 93.98)

    content += ")\n"
    return content

# ==============================================================================
# 2. SHEET 01: POWER & MCU
# ==============================================================================
def generate_power_mcu_sch():
    content = sch_header("01 Power Supply & ESP32-C3 Microcontroller")

    # Hierarchical ports
    content += make_hier_label("VIN_PROTECTED", "output", 101.60, 38.10, 0)
    content += make_hier_label("DRV_IN1", "output", 101.60, 58.42, 0)
    content += make_hier_label("DRV_IN2", "output", 101.60, 66.04, 0)
    content += make_hier_label("HV_SENSE_ADC", "input", 101.60, 81.28, 0)
    content += make_hier_label("HV_CURR_ADC", "input", 101.60, 88.90, 0)
    content += make_hier_label("INTERLOCK_OK", "input", 101.60, 96.52, 0)
    content += make_hier_label("3V3", "output", 101.60, 104.14, 0)
    content += make_hier_label("GND", "bidirectional", 101.60, 111.76, 0)

    # Power Flags
    content += make_symbol_with_connections("PWR_FLAG", "#FLG1", "PWR_FLAG", "", 38.10, 25.40, 0, {"1": "VIN_12"})
    content += make_symbol_with_connections("PWR_FLAG", "#FLG2", "PWR_FLAG", "", 101.60, 119.38, 0, {"1": "GND"})
    content += make_symbol_with_connections("PWR_FLAG", "#FLG3", "PWR_FLAG", "", 88.90, 76.20, 0, {"1": "3V3"})
    content += make_symbol_with_connections("PWR_FLAG", "#FLG5", "PWR_FLAG", "", 63.50, 25.40, 0, {"1": "VIN_PROTECTED"})

    # J1: 12V Screw Terminal (2 pins: 1=VIN_12, 2=GND)
    content += make_symbol_with_connections("WJ500V-5.08-2P-14-00A", "J1", "12V_IN", 
        "ionic_thrust_hv:CONN-TH_2P-P5.00_WJ500V-5.08-2P", 38.10, 38.10, 0,
        {"1": "VIN_12", "2": "GND"}, props={"LCSC Part": "C8465", "MPN": "WJ500V-5.08-2P"}, dnp=True)

    # F1: PTC Fuse 1A 1206 (2 pins: 1=VIN_12, 2=VIN_PROTECTED)
    content += make_symbol_with_connections("nSMD100-16V", "F1", "1A PTC", 
        "ionic_thrust_hv:F1206", 63.50, 38.10, 0,
        {"1": "VIN_12", "2": "VIN_PROTECTED"}, props={"LCSC Part": "C70082", "MPN": "nSMD100-16V"})

    # D2: TVS SMAJ18A (2 pins: 1=Cathode VIN_PROTECTED, 2=Anode GND)
    content += make_symbol_with_connections("SMAJ18A_C173513", "D2", "SMAJ18A", 
        "ionic_thrust_hv:SMA_L4.4-W2.6-LS5.0-RD", 76.20, 50.80, 90,
        {"1": "VIN_PROTECTED", "2": "GND"}, props={"LCSC Part": "C173513", "MPN": "SMAJ18A"})

    # U3: AP63203WU-7 Buck Converter (3.3V)
    content += make_symbol_with_connections("AP63203WU-7", "U3", "AP63203", 
        "ionic_thrust_hv:TSOT-26_L2.9-W1.6-P0.95-LS2.8-BL", 50.80, 88.90, 0,
        {"1": "3V3", "2": "VIN_PROTECTED", "3": "VIN_PROTECTED", "4": "GND", "5": "SW_BUCK", "6": "BST_BUCK"},
        props={"LCSC Part": "C780769", "MPN": "AP63203WU-7"})

    # L1: 3.9uH Inductor (Pins: 1=SW_BUCK, 2=3V3)
    content += make_symbol_with_connections("SRN6028-3R9M", "L1", "3.9uH", 
        "ionic_thrust_hv:Inductor_SMD_6.0x6.0mm", 76.20, 88.90, 0,
        {"1": "SW_BUCK", "2": "3V3"}, props={"LCSC Part": "C2046441", "MPN": "SRN6028-3R9M"})

    # C1, C2: 10uF 0805 on VIN_PROTECTED
    content += make_symbol_with_connections("CC0805KKX5R8BB106", "C1", "10uF", "ionic_thrust_hv:C0805", 38.10, 88.90, 90,
        {"1": "VIN_PROTECTED", "2": "GND"}, props={"LCSC Part": "C89831"})
    content += make_symbol_with_connections("CC0805KKX5R8BB106", "C2", "10uF", "ionic_thrust_hv:C0805", 43.18, 88.90, 90,
        {"1": "VIN_PROTECTED", "2": "GND"}, props={"LCSC Part": "C89831"})

    # C3, C4: 22uF 0805 on 3V3
    content += make_symbol_with_connections("TCC0805X5R226M100FT", "C3", "22uF", "ionic_thrust_hv:C0805", 88.90, 88.90, 90,
        {"1": "3V3", "2": "GND"}, props={"LCSC Part": "C380338"})
    content += make_symbol_with_connections("TCC0805X5R226M100FT", "C4", "22uF", "ionic_thrust_hv:C0805", 93.98, 88.90, 90,
        {"1": "3V3", "2": "GND"}, props={"LCSC Part": "C380338"})

    # C5: 100nF BST cap (between BST_BUCK and SW_BUCK)
    content += make_symbol_with_connections("CC0603KRX7R9BB104", "C5", "100nF", "ionic_thrust_hv:C0603", 63.50, 78.74, 0,
        {"1": "BST_BUCK", "2": "SW_BUCK"}, props={"LCSC Part": "C14663"})

    # U1: ESP32-C3-WROOM-02-H4
    content += make_symbol_with_connections("ESP32-C3-WROOM-02-H4", "U1", "ESP32-C3-WROOM-02", 
        "ionic_thrust_hv:WIFIM-SMD_18P-L20.0-W18.0-P1.50", 177.80, 88.90, 0,
        {
            "1": "3V3", "2": "MCU_EN", "3": "DRV_IN1", "4": "DRV_IN2", "5": "ARM_SW", "6": "LED_STATUS",
            "7": "NC", "8": "MCU_BOOT", "9": "GND", "10": "NC", "11": "UART_RX", "12": "UART_TX",
            "13": "NC", "14": "NC", "15": "INTERLOCK_OK", "16": "NC", "17": "HV_CURR_ADC", "18": "HV_SENSE_ADC", "19": "GND"
        },
        props={"LCSC Part": "C2944070", "MPN": "ESP32-C3-WROOM-02-H4"})

    # Programming Header J2
    content += make_symbol_with_connections("DS1021-1X6SF11-B", "J2", "UART_PROG", 
        "ionic_thrust_hv:CONN-TH_DS1021-1X6SF11-B", 228.60, 63.50, 0,
        {"1": "3V3", "2": "GND", "3": "UART_TX", "4": "UART_RX", "5": "MCU_EN", "6": "MCU_BOOT"},
        props={"LCSC Part": "C7430362"}, dnp=True)

    # SW1 Reset
    content += make_symbol_with_connections("TS-1187A-B-A-B", "SW1", "RESET", 
        "ionic_thrust_hv:SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5", 139.70, 50.80, 0,
        {"1": "MCU_EN", "2": "MCU_EN", "3": "GND", "4": "GND"}, props={"LCSC Part": "C318884"})

    # SW2 Boot
    content += make_symbol_with_connections("TS-1187A-B-A-B", "SW2", "BOOT", 
        "ionic_thrust_hv:SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5", 139.70, 76.20, 0,
        {"1": "MCU_BOOT", "2": "MCU_BOOT", "3": "GND", "4": "GND"}, props={"LCSC Part": "C318884"})

    # S6 ARM
    content += make_symbol_with_connections("TS-1187A-B-A-B", "S6", "ARM", 
        "ionic_thrust_hv:SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5", 139.70, 101.60, 0,
        {"1": "ARM_SW", "2": "ARM_SW", "3": "GND", "4": "GND"}, props={"LCSC Part": "C318884"})

    # R1: 10k EN pullup
    content += make_symbol_with_connections("0603WAF1002T5E", "R1", "10k", "ionic_thrust_hv:R0603", 152.40, 43.18, 90,
        {"1": "3V3", "2": "MCU_EN"}, props={"LCSC Part": "C25804"})

    # R2: 10k BOOT pullup
    content += make_symbol_with_connections("0603WAF1002T5E", "R2", "10k", "ionic_thrust_hv:R0603", 152.40, 68.58, 90,
        {"1": "3V3", "2": "MCU_BOOT"}, props={"LCSC Part": "C25804"})

    # R4: 10k ARM pullup
    content += make_symbol_with_connections("0603WAF1002T5E", "R4", "10k", "ionic_thrust_hv:R0603", 152.40, 93.98, 90,
        {"1": "3V3", "2": "ARM_SW"}, props={"LCSC Part": "C25804"})

    # R3: 10k pulldown on INTERLOCK_OK
    content += make_symbol_with_connections("0603WAF1002T5E", "R3", "10k", "ionic_thrust_hv:R0603", 203.20, 76.20, 90,
        {"1": "INTERLOCK_OK", "2": "GND"}, props={"LCSC Part": "C25804"})

    # R6: 1k Status LED series resistor
    content += make_symbol_with_connections("0603WAF1001T5E", "R6", "1k", "ionic_thrust_hv:R0603", 215.90, 114.30, 0,
        {"1": "LED_STATUS", "2": "LED_ANODE"}, props={"LCSC Part": "C21190"})

    # LED1: Status LED
    content += make_symbol_with_connections("19-217_GHC-YR1S2_3T", "LED1", "STATUS", 
        "ionic_thrust_hv:LED0603-RD", 228.60, 114.30, 90,
        {"1": "LED_ANODE", "2": "GND"}, props={"LCSC Part": "C72043"})

    # Decoupling Caps C6..C9
    content += make_symbol_with_connections("CC0603KRX7R9BB104", "C6", "100nF", "ionic_thrust_hv:C0603", 160.02, 50.80, 90,
        {"1": "MCU_EN", "2": "GND"}, props={"LCSC Part": "C14663"})
    content += make_symbol_with_connections("CC0603KRX7R9BB104", "C7", "100nF", "ionic_thrust_hv:C0603", 170.18, 50.80, 90,
        {"1": "3V3", "2": "GND"}, props={"LCSC Part": "C14663"})
    content += make_symbol_with_connections("CC0603KRX7R9BB104", "C8", "100nF", "ionic_thrust_hv:C0603", 175.26, 50.80, 90,
        {"1": "3V3", "2": "GND"}, props={"LCSC Part": "C14663"})
    content += make_symbol_with_connections("CC0603KRX7R9BB104", "C9", "100nF", "ionic_thrust_hv:C0603", 180.34, 50.80, 90,
        {"1": "3V3", "2": "GND"}, props={"LCSC Part": "C14663"})

    content += ")\n"
    return content

# ==============================================================================
# 3. SHEET 02: DRIVE & TRANSFORMER
# ==============================================================================
def generate_drive_transformer_sch():
    content = sch_header("02 Isolated AC Generation & Resonance Tank")

    # Hierarchical ports
    content += make_hier_label("HV_VM", "input", 38.10, 38.10, 180)
    content += make_hier_label("DRV_IN1", "input", 38.10, 50.80, 180)
    content += make_hier_label("DRV_IN2", "input", 38.10, 58.42, 180)
    content += make_hier_label("DRV_nSLEEP", "input", 38.10, 66.04, 180)
    content += make_hier_label("GND", "bidirectional", 38.10, 76.20, 180)
    content += make_hier_label("SEC_A", "output", 215.90, 50.80, 0)
    content += make_hier_label("HV_RETURN", "output", 215.90, 66.04, 0)

    # Power Flag on HV_VM
    content += make_symbol_with_connections("PWR_FLAG", "#FLG4", "PWR_FLAG", "", 38.10, 25.40, 0, {"1": "HV_VM"})

    # U2: DRV8220DSGR WSON-8
    content += make_symbol_with_connections("DRV8220DSGR_C3681269", "U2", "DRV8220DSGR", 
        "ionic_thrust_hv:WSON-8_L2.0-W2.0-P0.50-TL-EP", 76.20, 58.42, 0,
        {
            "1": "HV_VM", "2": "DRV_A", "3": "DRV_B", "4": "GND",
            "5": "DRV_IN2", "6": "DRV_IN1", "7": "GND", "8": "DRV_nSLEEP", "9": "GND"
        },
        props={"LCSC Part": "C3681269", "MPN": "DRV8220DSGR"})

    # C10 (100nF) and C12 (10uF) bypass caps on VM
    content += make_symbol_with_connections("CC0603KRX7R9BB104", "C10", "100nF", "ionic_thrust_hv:C0603", 55.88, 38.10, 90,
        {"1": "HV_VM", "2": "GND"}, props={"LCSC Part": "C14663"})
    content += make_symbol_with_connections("CC0805KKX5R8BB106", "C12", "10uF", "ionic_thrust_hv:C0805", 63.50, 38.10, 90,
        {"1": "HV_VM", "2": "GND"}, props={"LCSC Part": "C89831"})

    # R5: 10k pulldown on nSLEEP
    content += make_symbol_with_connections("0603WAF1002T5E", "R5", "10k", "ionic_thrust_hv:R0603", 55.88, 66.04, 90,
        {"1": "DRV_nSLEEP", "2": "GND"}, props={"LCSC Part": "C25804"})

    # C11: Resonant Film Capacitor 120nF 100V (1=DRV_A, 2=PRI_A)
    content += make_symbol_with_connections("BFC236821124", "C11", "120nF 100V", 
        "ionic_thrust_hv:C_Radial_P10.0mm", 114.30, 50.80, 0,
        {"1": "DRV_A", "2": "PRI_A"}, props={"LCSC Part": "C3771644", "MPN": "BFC236821124"}, dnp=True)

    # T1: Coilcraft FL2015-4LD CCFL Transformer
    content += make_symbol_with_connections("FL2015-4LD", "T1", "FL2015-4LD", 
        "ionic_thrust_hv:Coilcraft_FL2015-4L", 165.10, 58.42, 0,
        {"1": "PRI_A", "2": "NC", "3": "DRV_B", "5": "SEC_A", "8": "HV_RETURN", "4": "NC", "9": "NC"},
        props={"MPN": "FL2015-4LD", "Manufacturer": "Coilcraft"}, dnp=True)

    content += ")\n"
    return content

# ==============================================================================
# 4. SHEET 03: MULTIPLIER
# ==============================================================================
def generate_multiplier_sch():
    content = sch_header("03 6-Stage Positive Cockcroft-Walton Multiplier & Bleeders")

    # Hierarchical ports
    content += make_hier_label("SEC_A", "input", 38.10, 50.80, 180)
    content += make_hier_label("HV_RETURN", "input", 38.10, 88.90, 180)
    content += make_hier_label("HV_RAW", "output", 355.60, 50.80, 0)
    content += make_hier_label("HV_RETURN", "output", 355.60, 88.90, 0)

    # 6 stages
    for stage in range(1, 7):
        x_base = 38.10 + stage * 45.72
        d_pump_ref = f"D{10 + (stage-1)*2}"
        d_stack_ref = f"D{11 + (stage-1)*2}"
        c_pump_ref = f"C{20 + (stage-1)*2}"
        c_stack_ref = f"C{21 + (stage-1)*2}"
        r_pump_ref = f"R{40 + (stage-1)*2}"
        r_stack_ref = f"R{41 + (stage-1)*2}"

        prev_pump_net = "SEC_A" if stage == 1 else f"CW_P{stage-1}"
        curr_pump_net = f"CW_P{stage}"
        prev_stack_net = "HV_RETURN" if stage == 1 else f"CW_S{stage-1}"
        curr_stack_net = "HV_RAW" if stage == 6 else f"CW_S{stage}"

        # Pump Cap & Bleeder Resistor (between prev_pump_net and curr_pump_net)
        content += make_symbol_with_connections("S102M59Z5UU83L0R", c_pump_ref, "1nF 6kV", 
            "ionic_thrust_hv:CAP-TH_L15.0-W4.0-P10.00-D0.6", x_base, 38.10, 0,
            {"1": prev_pump_net, "2": curr_pump_net}, props={"LCSC Part": "C1620009"}, dnp=True)
        content += make_symbol_with_connections("MGR0W2J0107A10", r_pump_ref, "100M 3.5kV", 
            "ionic_thrust_hv:RES-TH_BD3.5-L9.5-P13.50-D0.6", x_base, 25.40, 0,
            {"1": prev_pump_net, "2": curr_pump_net}, props={"LCSC Part": "C51904773"}, dnp=True)

        # D_pump: Anode (pin 2)=prev_stack_net, Cathode (pin 1)=curr_pump_net
        content += make_symbol_with_connections("HVM12", d_pump_ref, "HVM12", 
            "ionic_thrust_hv:DO-722_BD7.5-L22.0-P26.00-D1.2-RD", x_base, 63.50, 90,
            {"2": prev_stack_net, "1": curr_pump_net}, props={"LCSC Part": "C7436450", "MPN": "HVM12"}, dnp=True)

        # D_stack: Anode (pin 2)=curr_pump_net, Cathode (pin 1)=curr_stack_net
        content += make_symbol_with_connections("HVM12", d_stack_ref, "HVM12", 
            "ionic_thrust_hv:DO-722_BD7.5-L22.0-P26.00-D1.2-RD", x_base + 15.24, 76.20, 90,
            {"2": curr_pump_net, "1": curr_stack_net}, props={"LCSC Part": "C7436450", "MPN": "HVM12"}, dnp=True)

        # Stack Cap & Bleeder Resistor (between prev_stack_net and curr_stack_net)
        content += make_symbol_with_connections("S102M59Z5UU83L0R", c_stack_ref, "1nF 6kV", 
            "ionic_thrust_hv:CAP-TH_L15.0-W4.0-P10.00-D0.6", x_base + 15.24, 101.60, 0,
            {"1": prev_stack_net, "2": curr_stack_net}, props={"LCSC Part": "C1620009"}, dnp=True)
        content += make_symbol_with_connections("MGR0W2J0107A10", r_stack_ref, "100M 3.5kV", 
            "ionic_thrust_hv:RES-TH_BD3.5-L9.5-P13.50-D0.6", x_base + 15.24, 114.30, 0,
            {"1": prev_stack_net, "2": curr_stack_net}, props={"LCSC Part": "C51904773"}, dnp=True)

    content += ")\n"
    return content

# ==============================================================================
# 5. SHEET 04: SENSE, SAFETY & INTERLOCK
# ==============================================================================
def generate_sense_safety_sch():
    content = sch_header("04 Ballast, Divider, Sensing & Hardware Interlock")

    # Hierarchical ports
    content += make_hier_label("HV_RAW", "input", 38.10, 38.10, 180)
    content += make_hier_label("HV_RETURN", "input", 38.10, 114.30, 180)
    content += make_hier_label("VIN_PROTECTED", "input", 38.10, 152.40, 180)
    content += make_hier_label("3V3", "input", 38.10, 162.56, 180)
    content += make_hier_label("GND", "bidirectional", 38.10, 172.72, 180)

    content += make_hier_label("HV_VM", "output", 279.40, 152.40, 0)
    content += make_hier_label("INTERLOCK_OK", "output", 279.40, 172.72, 0)
    content += make_hier_label("HV_SENSE_ADC", "output", 279.40, 76.20, 0)
    content += make_hier_label("HV_CURR_ADC", "output", 279.40, 114.30, 0)

    # Ballast Resistor String: 10x 10M 3.5kV (R20..R29) from HV_RAW to HV_OUT
    for i in range(10):
        ref = f"R{20 + i}"
        x = 63.50 + i * 20.32
        prev_net = "HV_RAW" if i == 0 else f"BAL_{i}"
        next_net = "HV_OUT" if i == 9 else f"BAL_{i+1}"
        content += make_symbol_with_connections("MGR0W2J0106A10", ref, "10M 3.5kV", 
            "ionic_thrust_hv:RES-TH_BD3.5-L9.5-P13.50-D0.6", x, 38.10, 0,
            {"1": prev_net, "2": next_net}, props={"LCSC Part": "C51904770"}, dnp=True)

    # High Voltage Divider String: 10x 100M 3.5kV (R30..R39) from HV_OUT to HV_SENSE_RAW
    for i in range(10):
        ref = f"R{30 + i}"
        x = 63.50 + i * 20.32
        prev_net = "HV_OUT" if i == 0 else f"DIV_{i}"
        next_net = "HV_SENSE_RAW" if i == 9 else f"DIV_{i+1}"
        content += make_symbol_with_connections("MGR0W2J0107A10", ref, "100M 3.5kV", 
            "ionic_thrust_hv:RES-TH_BD3.5-L9.5-P13.50-D0.6", x, 63.50, 0,
            {"1": prev_net, "2": next_net}, props={"LCSC Part": "C51904773"}, dnp=True)

    # Low Leg of Divider: R8 (82k), R9 (82k), C13 (100nF)
    content += make_symbol_with_connections("0603WAF8202T5E", "R8", "82k", "ionic_thrust_hv:R0603", 63.50, 76.20, 90,
        {"1": "HV_SENSE_RAW", "2": "DIV_MID"}, props={"LCSC Part": "C23254"})
    content += make_symbol_with_connections("0603WAF8202T5E", "R9", "82k", "ionic_thrust_hv:R0603", 73.66, 76.20, 90,
        {"1": "DIV_MID", "2": "GND"}, props={"LCSC Part": "C23254"})
    content += make_symbol_with_connections("CC0603KRX7R9BB104", "C13", "100nF", "ionic_thrust_hv:C0603", 83.82, 76.20, 90,
        {"1": "HV_SENSE_RAW", "2": "GND"}, props={"LCSC Part": "C14663"})

    # Buffer U4: TLV9001IDBVR SOT-23-5
    content += make_symbol_with_connections("TLV9001IDBVR", "U4", "TLV9001", 
        "ionic_thrust_hv:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR", 114.30, 76.20, 0,
        {"1": "BUF_OUT", "2": "GND", "3": "HV_SENSE_RAW", "4": "BUF_OUT", "5": "3V3"},
        props={"LCSC Part": "C398363", "MPN": "TLV9001IDBVR"})

    # Isolation R7: 1k 0603 (1=BUF_OUT, 2=HV_SENSE_ADC)
    content += make_symbol_with_connections("0603WAF1001T5E", "R7", "1k", "ionic_thrust_hv:R0603", 127.00, 76.20, 0,
        {"1": "BUF_OUT", "2": "HV_SENSE_ADC"}, props={"LCSC Part": "C21190"})

    # Clamp D1: BAT54S (1=A1 GND, 2=K2 3V3, 3=A/K HV_SENSE_ADC)
    content += make_symbol_with_connections("BAT54S", "D1", "BAT54S", 
        "ionic_thrust_hv:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR", 139.70, 76.20, 90,
        {"1": "GND", "2": "3V3", "3": "HV_SENSE_ADC"}, props={"LCSC Part": "C83935"})

    # Current Sense Shunt: R10 (10k 0603) between HV_RETURN and GND
    content += make_symbol_with_connections("0603WAF1002T5E", "R10", "10k Shunt", "ionic_thrust_hv:R0603", 63.50, 114.30, 90,
        {"1": "HV_RETURN", "2": "GND"}, props={"LCSC Part": "C25804"})

    # Filter R11 (1k) and C14 (100nF)
    content += make_symbol_with_connections("0603WAF1001T5E", "R11", "1k", "ionic_thrust_hv:R0603", 83.82, 114.30, 0,
        {"1": "HV_RETURN", "2": "HV_CURR_ADC"}, props={"LCSC Part": "C21190"})
    content += make_symbol_with_connections("CC0603KRX7R9BB104", "C14", "100nF", "ionic_thrust_hv:C0603", 99.06, 114.30, 90,
        {"1": "HV_CURR_ADC", "2": "GND"}, props={"LCSC Part": "C14663"})

    # Current Clamp D4: BAT54S (1=GND, 2=3V3, 3=HV_CURR_ADC)
    content += make_symbol_with_connections("BAT54S", "D4", "BAT54S", 
        "ionic_thrust_hv:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR", 114.30, 114.30, 90,
        {"1": "GND", "2": "3V3", "3": "HV_CURR_ADC"}, props={"LCSC Part": "C83935"})

    # Hardware Interlock: S3, S4, K1, D3
    # S3 (Omron D2F-L, 1=COM VIN_PROTECTED, 2=NC no_connect, 3=NO LID_INT)
    content += make_symbol_with_connections("D2F-L", "S3", "LID_SW_1", 
        "ionic_thrust_hv:SW-TH_D2F-L", 63.50, 152.40, 0,
        {"1": "VIN_PROTECTED", "2": "NC", "3": "LID_INT"}, props={"LCSC Part": "C231337", "MPN": "D2F-L"}, dnp=True)

    # S4 (Omron D2F-L, 1=COM LID_INT, 2=NC no_connect, 3=NO RELAY_COIL_POS)
    content += make_symbol_with_connections("D2F-L", "S4", "LID_SW_2", 
        "ionic_thrust_hv:SW-TH_D2F-L", 88.90, 152.40, 0,
        {"1": "LID_INT", "2": "NC", "3": "RELAY_COIL_POS"}, props={"LCSC Part": "C231337", "MPN": "D2F-L"}, dnp=True)

    # Flyback Diode D3: 1N4148WS (1=Cathode RELAY_COIL_POS, 2=Anode GND)
    content += make_symbol_with_connections("1N4148WS", "D3", "1N4148WS", 
        "ionic_thrust_hv:D_SOD-323", 114.30, 152.40, 90,
        {"1": "RELAY_COIL_POS", "2": "GND"}, props={"LCSC Part": "C81598"})

    # K1: N4078-2C-12V DPDT Relay
    content += make_symbol_with_connections("N4078-2C-12V", "K1", "DPDT_RELAY", 
        "ionic_thrust_hv:Relay_DPDT_N4078", 139.70, 162.56, 0,
        {
            "1": "RELAY_COIL_POS", "16": "GND",
            "4": "VIN_PROTECTED", "8": "HV_VM", "6": "NC",
            "13": "3V3", "9": "INTERLOCK_OK", "11": "NC"
        },
        props={"LCSC Part": "C52195125", "MPN": "N4078-2C-12V"}, dnp=True)

    # High Voltage Output Terminal J3 (2 pins: 1=HV_OUT, 2=HV_RETURN)
    content += make_symbol_with_connections("WJ500V-5.08-2P-14-00A", "J3", "HV_OUT_TERMINAL", 
        "ionic_thrust_hv:CONN-TH_2P-P5.00_WJ500V-5.08-2P", 228.60, 38.10, 0,
        {"1": "HV_OUT", "2": "HV_RETURN"}, props={"LCSC Part": "C8465"}, dnp=True)

    content += ")\n"
    return content

# ==============================================================================
# MAIN EXECUTION
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
