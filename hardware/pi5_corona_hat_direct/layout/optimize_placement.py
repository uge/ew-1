"""Optimize native PCB placement; no schematic generation.

Euclidean per-net MST is a ratsnest proxy, not routing or HV qualification.
Accept each proposed rotation/translation only after native KiCad DRC passes.
Run with /usr/bin/python3. Saves preserve the project settings verbatim.
"""
from pathlib import Path
import json,math,subprocess,shutil
import pcbnew as p
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'pi5_corona_hv.kicad_pcb'
PRO=ROOT/'pi5_corona_hv.kicad_pro'
project=PRO.read_bytes();board=p.LoadBoard(str(PATH))
fps={f.GetReference():f for f in board.GetFootprints()}
hv={f'R{i}' for i in list(range(20,52))+list(range(140,164))}|{f'D{i}' for i in range(10,22)}|{f'C{i}' for i in range(100,112)}|{'T1','J60','J61'}

def mst(pts):
 pts=list(set(pts))
 if len(pts)<2:return 0.0
 pending=pts[1:];dist=[math.dist(pts[0],q) for q in pending];total=0
 while pending:
  i=min(range(len(dist)),key=dist.__getitem__);total+=dist.pop(i);a=pending.pop(i)
  dist=[min(d,math.dist(a,q)) for d,q in zip(dist,pending)]
 return total

def measure():
 groups={};hgroups={}
 for r,f in fps.items():
  for pad in f.Pads():
   n=pad.GetNetname()
   if not n or n.startswith('unconnected-'):continue
   q=(p.ToMM(pad.GetPosition().x),p.ToMM(pad.GetPosition().y))
   groups.setdefault(n,[]).append(q)
   if r in hv:hgroups.setdefault(n,[]).append(q)
 return {'all_nets_mst_mm':round(sum(mst(q) for q in groups.values()),3),
         'hv_nets_mst_mm':round(sum(mst(q) for q in hgroups.values()),3)}

def save():
 try:p.SaveBoard(str(PATH),board)
 finally:PRO.write_bytes(project)

def drc():
 save();out=ROOT/'layout/placement-trial-drc.json'
 subprocess.run(['kicad-cli','pcb','drc','--format','json','--output',str(out),str(PATH)],stdout=subprocess.DEVNULL,check=True)
 d=json.loads(out.read_text());return len(d['violations'])==0 and len(d['schematic_parity'])==0

# Same four-switch circuit, with the previous HV placement as a fair baseline.
old=p.LoadBoard(str(ROOT/'revisions/J-layout-5/pi5_corona_hv.kicad_pcb'))
oldfps={f.GetReference():f for f in old.GetFootprints()}
state={r:(f.GetPosition(),f.GetOrientationDegrees()) for r,f in fps.items()}
for r in hv:
 f=fps[r];o=oldfps[r];f.SetPosition(o.GetPosition());f.SetOrientationDegrees(o.GetOrientationDegrees())
before=measure()
for r,(q,a) in state.items():fps[r].SetPosition(q);fps[r].SetOrientationDegrees(a)
start=measure();assert drc(),'Initial compact placement must pass DRC'
accepted=[];rejected=set()
# Keep connector, mini-board, transformer, diode and Pi mechanical poses fixed.
movable=[r for r in fps if (r.startswith('R') or r.startswith('C') or r in ['U4','U5','U6','U7','U9','U10','Q1','K1','D1','D3','D4','D5']) and r not in ['C11']]
for step in range(20):
 score=measure()['all_nets_mst_mm'];proposals=[]
 for r in movable:
  f=fps[r];q=f.GetPosition();a=f.GetOrientationDegrees()
  # Copper locations are preserved when testing 180 degree rotations.
  angles=[(a+180)%360] if r in hv else [(a+90)%360,(a+180)%360,(a+270)%360]
  for na in angles:
   key=(r,round(p.ToMM(q.x),3),round(p.ToMM(q.y),3),round(na,3))
   if key in rejected:continue
   f.SetOrientationDegrees(na);gain=score-measure()['all_nets_mst_mm']
   if gain>.5:proposals.append((gain,r,q,na,key))
  f.SetOrientationDegrees(a)
 proposals.sort(key=lambda t:t[0],reverse=True);found=False
 for gain,r,q,na,key in proposals[:12]:
  f=fps[r];a=f.GetOrientationDegrees();refpos=f.Reference().GetPosition();f.SetOrientationDegrees(na)
  # Keep references horizontal and place clear of copper before checking.
  f.Reference().SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
  if drc():
   accepted.append({'ref':r,'rotation_before':a,'rotation_after':na,'mst_gain_mm':round(gain,3)});print('Accepted',accepted[-1],flush=True);found=True;break
  rejected.add(key);f.SetOrientationDegrees(a);f.Reference().SetPosition(refpos)
 if not found:break
save();assert drc()
result={'revision':'J','layout_revision':board.GetTitleBlock().GetRevision(),'before':before,'compact_before_rotation_search':start,'after':measure(),'accepted_rotations':accepted,'method':'Euclidean per-net minimum spanning trees. Baseline uses the same four-switch netlist and mini boards, with original J-layout-5 HV component positions. Each accepted rotation passes native KiCad DRC. Not actual routed length.','global_optimum_claimed':False,'hv_rules_unchanged':True,'routing_complete':False}
(ROOT/'exports/four-switch-placement-optimization.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2),flush=True)
