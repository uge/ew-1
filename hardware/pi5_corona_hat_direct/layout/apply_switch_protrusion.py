import pcbnew as pn
from pathlib import Path
import re

pcb_path = Path("/home/uge/Development/ew-1/hardware/pi5_corona_hat_direct/pi5_corona_hv.kicad_pcb")
b = pn.LoadBoard(str(pcb_path))

# 1. Update S3, S4, S5, S6 footprint positions (+1.4mm in Y)
# S3: 75.6 -> 77.0
# S4: 91.6 -> 93.0
# S5: 107.6 -> 109.0
# S6: 123.6 -> 125.0
shift_pairs = [
    ("S3", 75.6, 77.0),
    ("S4", 91.6, 93.0),
    ("S5", 107.6, 109.0),
    ("S6", 123.6, 125.0),
]

for ref, old_y, new_y in shift_pairs:
    f = b.FindFootprintByReference(ref)
    pos = f.GetPosition()
    f.SetPosition(pn.VECTOR2I(pos.x, int(new_y * 1e6)))
    print(f"Shifted {ref} to ({pos.x / 1e6:.2f}, {new_y:.2f})")

# 2. Update track endpoints connecting to switch pads
for t in list(b.GetTracks()):
    if isinstance(t, pn.PCB_TRACK):
        s = t.GetStart()
        e = t.GetEnd()
        sx, sy = s.x / 1e6, s.y / 1e6
        ex, ey = e.x / 1e6, e.y / 1e6

        for ref, old_y, new_y in shift_pairs:
            # Pad 1 at X = 36.5
            if abs(sx - 36.5) < 0.1 and abs(sy - old_y) < 0.1:
                t.SetStart(pn.VECTOR2I(int(sx * 1e6), int(new_y * 1e6)))
            elif abs(ex - 36.5) < 0.1 and abs(ey - old_y) < 0.1:
                t.SetEnd(pn.VECTOR2I(int(ex * 1e6), int(new_y * 1e6)))

            # Pad 2 at X = 39.0
            if abs(sx - 39.0) < 0.1 and abs(sy - old_y) < 0.1:
                t.SetStart(pn.VECTOR2I(int(sx * 1e6), int(new_y * 1e6)))
            elif abs(ex - 39.0) < 0.1 and abs(ey - old_y) < 0.1:
                t.SetEnd(pn.VECTOR2I(int(ex * 1e6), int(new_y * 1e6)))

# Rebuild connectivity
b.BuildConnectivity()
pn.SaveBoard(str(pcb_path), b)

# 3. Update 3D model link in text file to TK-0013-R.step
text = pcb_path.read_text()
text = text.replace("TK-0013-R.wrl", "TK-0013-R.step")
pcb_path.write_text(text)

# 4. Reload and refill zones
b = pn.LoadBoard(str(pcb_path))
pn.ZONE_FILLER(b).Fill(b.Zones())
pn.SaveBoard(str(pcb_path), b)

print("Applied switch protrusion and STEP model updates successfully.")
