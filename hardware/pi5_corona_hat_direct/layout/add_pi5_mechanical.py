"""Add/update only the board-only DNP Pi 5 fit-check model; preserve routing."""
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[1]
board_path=ROOT/'pi5_corona_hv.kicad_pcb'
project_path=ROOT/'pi5_corona_hv.kicad_pro'
project_text=project_path.read_text()
b=p.LoadBoard(str(board_path))
socket=next(f for f in b.GetFootprints() if f.GetReference()=='J2')
if socket.GetLayer()!=p.F_Cu: socket.Flip(socket.GetPosition(),False)
socket.SetOrientationDegrees(180)
socket.SetPosition(p.VECTOR2I(p.FromMM(54.23),p.FromMM(106.63)))
f=next((fp for fp in b.GetFootprints() if fp.GetReference()=='MP1'),None)
if f is None:
 f=p.FootprintLoad(str(ROOT/'ionic_thrust_hv.pretty'),'Raspberry_Pi_5_Mechanical')
 b.Add(f)
f.SetFPID(p.LIB_ID('ionic_thrust_hv','Raspberry_Pi_5_Mechanical'))
f.SetReference('MP1');f.SetDNP(True)
f.SetPosition(p.VECTOR2I(p.FromMM(3),p.FromMM(115)))
f.SetOrientationDegrees(90)
# Update the model transform even on an existing mechanical instance.
for model in f.Models():
 model.m_Offset.z=13.306
 model.m_Rotation.x=180
f.SetLocked(True)
b.BuildConnectivity()
p.ZONE_FILLER(b).Fill(b.Zones())
p.SaveBoard(str(board_path),b)
project_path.write_text(project_text)
print('Added MP1: DNP, board-only, excluded from BOM and position files, locked.')
