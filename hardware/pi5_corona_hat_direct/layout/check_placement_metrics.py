"""Compare straight-line HV net trees; these are placement proxies, not routes."""
from pathlib import Path
import json,math
import pcbnew as p
ROOT=Path(__file__).resolve().parents[1]
def measure(path):
 board=p.LoadBoard(str(path));nets={};connections=[]
 for f in board.GetFootprints():
  r=f.GetReference()
  if not (r in ['T1','J60','J61'] or r in [f'D{i}' for i in range(10,22)] or r in [f'C{i}' for i in range(100,112)] or r in [f'R{i}' for i in list(range(20,52))+list(range(140,164))]):continue
  for pad in f.Pads():
   if pad.GetNetCode():nets.setdefault(pad.GetNetname(),[]).append((p.ToMM(pad.GetPosition().x),p.ToMM(pad.GetPosition().y)))
 for net,pts in nets.items():
  done={0}
  while len(done)<len(pts):
   dist,i,j=min((math.dist(pts[i],pts[j]),i,j) for i in done for j in range(len(pts)) if j not in done)
   done.add(j)
   if dist>0:connections.append((net,pts[i],pts[j],dist))
 def orient(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
 cross=0
 for i,(n,a,b,_) in enumerate(connections):
  for m,c,d,_ in connections[i+1:]:
   if n!=m and orient(a,b,c)*orient(a,b,d)<-1e-8 and orient(c,d,a)*orient(c,d,b)<-1e-8:cross+=1
 return {'hv_minimum_spanning_tree_length_mm':round(sum(e[3] for e in connections),2),'hv_straight_tree_crossings':cross,'pad_net_map':sorted((f.GetReference(),q.GetNumber(),q.GetNetname()) for f in board.GetFootprints() for q in f.Pads()),'diode_positions':{f.GetReference():[p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y),f.GetOrientationDegrees()] for f in board.GetFootprints() if f.GetReference() in [f'D{i}' for i in range(10,22)]}}
a=measure(ROOT/'revisions/M-layout-8/pi5_corona_hv.kicad_pcb');b=measure(ROOT/'pi5_corona_hv.kicad_pcb')
same=a.pop('pad_net_map')==b.pop('pad_net_map')
r={'revision':'N-layout-9','before':a,'after':b,'all_pad_net_assignments_preserved':same,'method':'Euclidean per-net minimum spanning trees across HV footprints; strict segment crossings between different nets. Excludes trace clearance, obstacle avoidance and vias. Not completed routing.'}
(ROOT/'exports/placement-optimization.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='method'},indent=2))
assert same
