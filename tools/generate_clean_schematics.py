#!/usr/bin/env python3
"""
KiCad 10 Professional Hierarchical Schematic Generator
ESP32 12V to 15kV DC Corona Supply.
Generates beautiful, standard, professional schematics with real wires,
proper symbols, clear layout, and no overlapping text.
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
        self.pin_coords = {} # (ref, pin) -> (x, y)

    def add_symbol(self, lib_name, ref, val, footprint, sx, sy, srot=0, props=None, dnp=False, ref_pos=None, val_pos=None):
        sx, sy = round(sx, 2), round(sy, 2)
        # Record pin coords
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

    def add_text(self, text, x, y, size=2.0, bold=True):
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

    def build(self):
        hdr = sch_header(self.title, self.doc_uuid)
        return hdr + "".join(self.items) + ")\n"

print("Builder helper defined")
