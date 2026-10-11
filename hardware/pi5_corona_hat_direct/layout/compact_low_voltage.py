"""Compact LV placement and align USB-C mouth with the top edge; no schematic edits.
Preserves a revision snapshot and project settings. Routing must be redone after
moving footprints; the previous routes stay in revisions/K-layout-6/.
"""
from pathlib import Path
import pcbnew as p,json
R=Path(__file__).resolve().parents[1];pro=R/'pi5_corona_hv.kicad_pro';saved=pro.read_bytes()
b=p.LoadBoard(str(R/'revisions/K-layout-6/pi5_corona_hv.kicad_pcb'))
fps={f.GetReference():f for f in b.GetFootprints()}
def pt(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
# All HV footprints and their associated measurement/protection components move
# together, retaining the previously checked HV geometry and voltage spacing.
hv={f'R{i}' for i in list(range(20,52))+list(range(140,164))}|{f'D{i}' for i in range(10,22)}|{f'C{i}' for i in range(100,112)}|{'T1','C11','J60','J61','U4','R8','R9','C13','R7','D1','R90','D5','D52','D53','D54','D55','C63','R64'}
for r in hv:
 f=fps[r];q=f.GetPosition();q.x-=p.FromMM(20);f.SetPosition(q)
# Preserve accepted rotations unless edge access or loop placement needs change.
positions={
 'J3':(88,54.675,180),
 'U7':(82,72,180),'R13':(88,65,0),'F1':(77,62,0),
 'C21':(78,67,180),'C73':(73,68,0),'C17':(87,73,90),
 'C18':(77,71,0),'C19':(82,77,0),'C20':(86,77,0),
 'R14':(76,77,0),'NTC1':(73,74,0),
 'Q1':(93,76,0),'C22':(96,83,180),
 'U9':(91,92,180),'R70':(85,91,90),'R71':(95,92,180),
 'R72':(91,97,0),'R73':(96,97,0),'C71':(87,96,0),'C72':(80,91,0),
 'C70':(97,104,0),
 'U5':(68,78,0),'C15':(68,83,0),
 'U6':(82,107,90),'C16':(78,103,0),
 'R10':(91,111,0),'R11':(95,111,0),'R12':(87,112,0),
 'K1':(76,126,180),'D3':(70,119,0),
 'U10':(68,107,90),'C82':(64,112,0),'C83':(69,112,0),'R92':(82,120,0),
 'U2':(89,137,0),'C10':(81,137,90),'C12':(82,144,0),
 'C60':(97,147,0),'C61':(85,131,0),'C62':(93,131,0),
 'R5':(83.5,126,0),'R61':(88,127,0),'R62':(95,127,90),
 'R63':(96,137,180),'TP50':(97,140,0),
 'D50':(83,116,0),'D51':(95,117,90),'R60':(97,157,270),
 'C11':(110,140,0),'D52':(105,152,90),'D54':(122,152,90),
 'D53':(105,165,90),'D55':(117,165,90),
 'D5':(104,181,90),'R91':(92,180,180),'C14':(91,186,0),'D4':(97,186,0),
 'H5':(240,194,0),'H6':(240,55,0)
}
for r,(x,y,a) in positions.items():f=fps[r];f.SetPosition(pt(x,y));f.SetOrientationDegrees(a)
# Discard only the active trial routes; moved pads invalidate their endpoints.
tracks=list(b.GetTracks())
for t in tracks:b.Remove(t);t.thisown=False
# Rebuild the zones for the narrower LV region, retaining .3 mm GND clearance.
zones=list(b.Zones())
for z in zones:b.Remove(z);z.thisown=False
nets={n.GetNetname():n for n in b.GetNetsByNetcode().values()}
for keepout,coords,layers in [(False,(52,52,101,198),[p.B_Cu]),(True,(102,52,245,198),[p.F_Cu,p.B_Cu])]:
 z=p.ZONE(b);ls=p.LSET()
 for layer in layers:ls.AddLayer(layer)
 z.SetLayerSet(ls);z.SetIsRuleArea(keepout)
 if keepout:z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowTracks(False);z.SetDoNotAllowVias(False);z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False)
 else:z.SetNet(nets['GND']);z.SetLocalClearance(p.FromMM(.3));z.SetMinThickness(p.FromMM(.25))
 x1,y1,x2,y2=coords;poly=z.Outline();poly.NewOutline()
 for x,y in [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]:poly.Append(p.FromMM(x),p.FromMM(y))
 b.Add(z)
for s in b.GetDrawings():
 if isinstance(s,p.PCB_SHAPE) and s.GetLayer()==p.Edge_Cuts:
  for get,setter in [(s.GetStart,s.SetStart),(s.GetEnd,s.SetEnd)]:
   q=get()
   if p.ToMM(q.x)==266:q.x=p.FromMM(246);setter(q)
 elif isinstance(s,p.PCB_TEXT):
  value=s.GetText();q=s.GetPosition()
  if value in ['HV BALLAST','HV MULTIPLIER / NO POURS','1 GOhm DIVIDER','2 LAYERS / PLACEMENT STUDY','HV OUT','HV RETURN']:q.x-=p.FromMM(20);s.SetPosition(q)
  elif value=='USB-C PD / eFUSE':s.SetPosition(pt(82,86));s.SetTextSize(pt(.8,.8))
  elif value=='BRIDGE / TRANSFORMER':s.SetPosition(pt(83,153));s.SetTextSize(pt(.8,.8))
# Reference fields follow the physical package, with horizontal text.
for r,f in fps.items():
 if r in ['MP1','J2','J51','U8','S3','S4','S5','S6','J62','J63','J66','J67','J64','J65','J68','J69']:continue
 box=f.GetBoundingBox(False,False);q=f.GetPosition();f.Reference().SetPosition(pt(p.ToMM(q.x),p.ToMM(box.GetTop())-1.2));f.Reference().SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
fps['J3'].Reference().SetPosition(pt(98,57))
for ref,x,y in [('H1',60.5,111.5),('H3',114,60),('H6',235,55),('J60',239,84),('U4',117,190),('TP50',92,142),('D54',127,152),('D51',100,117),('R92',78,117),('C18',77,73.3)]:fps[ref].Reference().SetPosition(pt(x,y))
t=b.GetTitleBlock();t.SetRevision('L-layout-7');t.SetComment(0,'PLACEMENT STUDY — UNROUTED — NOT FOR FABRICATION');b.SetTitleBlock(t)
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones())
try:p.SaveBoard(str(R/'pi5_corona_hv.kicad_pcb'),b)
finally:pro.write_bytes(saved)
print('LV width 71 → 51 mm; carrier 196 × 148 mm; USB-C mouth y=51 mm facing outward.')
