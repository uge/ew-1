"""Complete the three LV neck links missed by the L-layout-7 route trial.

Requires the current trial placement; run native DRC after applying.
"""
from pathlib import Path
import pcbnew as p
r=Path(__file__).resolve().parents[1];pro=r/'pi5_corona_hv.kicad_pro';saved=pro.read_bytes();b=p.LoadBoard(str(r/'pi5_corona_hv.kicad_pcb'));assert all(f.GetFPID().GetLibItemName()=='SW-TH_D2F-L' for f in b.GetFootprints() if f.GetReference() in ['S3','S4','S5','S6']), 'Historical Omron routing helper; do not apply to TK-0013-R'
nets={n.GetNetname():n for n in b.GetNetsByNetcode().values()}
def pt(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
for y,net in [(146,'/04_sense_safety/LID_INT'),(162,'/04_sense_safety/LID_2'),(178,'/04_sense_safety/LID_3')]:
 offset=3.5 if y==146 else 2.5
 for a,c in [((30,y-6),(32.54,y)),((32.54,y),(35,y-.8)),((35,y-.8),(64,y-.8)),((64,y-.8),(64,y-offset)),((64,y-offset),(74.08,y-offset)),((74.08,y-offset),(74.08,y))]:
  existing=any(not isinstance(q,p.PCB_VIA) and q.GetNetname()==net and q.GetLayer()==p.B_Cu and {tuple(q.GetStart()),tuple(q.GetEnd())}=={tuple(pt(*a)),tuple(pt(*c))} for q in b.GetTracks())
  if existing:continue
  t=p.PCB_TRACK(b);t.SetStart(pt(*a));t.SetEnd(pt(*c));t.SetLayer(p.B_Cu);t.SetWidth(p.FromMM(.3));t.SetNet(nets[net]);b.Add(t)
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(r/'pi5_corona_hv.kicad_pcb'),b);pro.write_bytes(saved)
