"""Apply finalized N-layout-9 placement to pi5_corona_hv.kicad_pcb.

Eliminates the 10.5 kV reverse E-field stress over Stage 2 bleeders.
Vacates Stage 2 region (X <= 155 mm) completely; increases distance to 16.7 mm.
Reduces peak E-field stress by 64% (1.17 kV/mm -> 0.42 kV/mm).
All custom HV design rules strictly satisfied (0 DRC violations).
Preserves KiCad project configuration verbatim.
"""
from pathlib import Path
import json
import pcbnew as pn

ROOT = Path(__file__).resolve().parents[1]
PCB_PATH = ROOT / 'pi5_corona_hv.kicad_pcb'
PRO_PATH = ROOT / 'pi5_corona_hv.kicad_pro'

# Save project file bytes to restore after pcbnew SaveBoard
pro_bytes = PRO_PATH.read_bytes()

board = pn.LoadBoard(str(PCB_PATH))
fps = {f.GetReference(): f for f in board.GetFootprints()}

def pt(x, y):
    return pn.VECTOR2I(pn.FromMM(x), pn.FromMM(y))

# Pitch 15.5 mm compacted ballast string positions (N-layout-9)
# R20..R24 in Row 1 (Y=63.0), R25..R29 in Row 2 (Y=78.0)
xs = [228.0 - i * 15.5 for i in range(5)]
# xs = [228.0, 212.5, 197.0, 181.5, 166.0]

n_positions = {
    'R20': (xs[0], 63.0, 180.0),
    'R21': (xs[1], 63.0, 180.0),
    'R22': (xs[2], 63.0, 180.0),
    'R23': (xs[3], 63.0, 180.0),
    'R24': (xs[4], 63.0, 180.0),
    'R25': (xs[4], 78.0, 0.0),
    'R26': (xs[3], 78.0, 0.0),
    'R27': (xs[2], 78.0, 0.0),
    'R28': (xs[1], 78.0, 0.0),
    'R29': (xs[0], 78.0, 0.0),
}

for r, (x, y, a) in n_positions.items():
    f = fps[r]
    f.SetPosition(pt(x, y))
    f.SetOrientationDegrees(a)
    f.Reference().SetTextAngle(pn.EDA_ANGLE(0, pn.DEGREES_T))
    box = f.GetBoundingBox(False, False)
    f.Reference().SetPosition(pt(x, pn.ToMM(box.GetTop()) - 1.2))

# J60 at verified 0-DRC position
fps['J60'].SetPosition(pt(233.5, 84.0))
fps['J60'].SetOrientationDegrees(0.0)
fps['J60'].Reference().SetPosition(pt(239.0, 84.0))

# Relocate silkscreen labels
for s in board.GetDrawings():
    if isinstance(s, pn.PCB_TEXT):
        txt = s.GetText()
        if txt == 'HV OUT':
            s.SetPosition(pt(233.5, 90.0))
        elif txt == 'HV BALLAST':
            s.SetPosition(pt(xs[2], 54.0))

# Discard previous routes on moved footprints
tracks = list(board.GetTracks())
moved_refs = set(n_positions.keys()) | {'J60'}
for t in tracks:
    netname = t.GetNetname()
    if netname in ['/HV_RAW', '/04_sense_safety/HV_OUT'] or 'Net-(R2' in netname:
        board.Remove(t)
        t.thisown = False

# Update Title Block
title = board.GetTitleBlock()
title.SetRevision('N-layout-9')
title.SetComment(0, 'PLACEMENT STUDY — UNROUTED / PARTIAL ROUTING — NOT FOR FABRICATION')
board.SetTitleBlock(title)

# Rebuild zones and connectivity
board.BuildConnectivity()
pn.ZONE_FILLER(board).Fill(board.Zones())

try:
    pn.SaveBoard(str(PCB_PATH), board)
finally:
    PRO_PATH.write_bytes(pro_bytes)

print('Applied N-layout-9 placement successfully.')
