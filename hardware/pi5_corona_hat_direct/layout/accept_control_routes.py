"""Accept LV trial after native refill, dangling-copper cleanup and neck checks."""
from pathlib import Path
import json,subprocess
import pcbnew as p
R=Path(__file__).resolve().parents[1];pro=R/'pi5_corona_hv.kicad_pro';saved=pro.read_bytes()
b=p.LoadBoard(str(R/'layout/routing-trials/control-routed.kicad_pcb'))
native=R/'layout/routing-trials/route-drc.json'
subprocess.run(['kicad-cli','pcb','drc','--format','json','--output',str(native),str(R/'layout/routing-trials/control-routed.kicad_pcb')],check=True)
report=json.loads(native.read_text())
allowed={'hole_clearance','track_dangling','via_dangling','starved_thermal'}
assert all(v['type'] in allowed for v in report['violations']), 'Resolve other route defects before accepting'
ids={v['items'][0]['uuid'] for v in report['violations'] if v['type'] in ['track_dangling','via_dangling']}
tracks=list(b.GetTracks())
removed=[]
for t in tracks:
 if t.m_Uuid.AsString() in ids:
  b.Remove(t);t.thisown=False;removed.append(t)
for z in b.Zones():
 if not z.GetIsRuleArea():z.SetLocalClearance(p.FromMM(.3))
rows=[(120,{'GND','3V3','/01_power_mcu/SDA','/01_power_mcu/SCL'}),
      (136,{'COIL_3V','/04_sense_safety/LID_INT'}),
      (152,{'/04_sense_safety/LID_INT','/04_sense_safety/LID_2'}),
      (168,{'/04_sense_safety/LID_2','/04_sense_safety/LID_3'}),
      (184,{'/04_sense_safety/LID_3','/04_sense_safety/RELAY_COIL_POS'})]
crossings=[]
for t in b.GetTracks():
 if isinstance(t,p.PCB_VIA):continue
 a=t.GetStart();c=t.GetEnd();x1,x2=p.ToMM(a.x),p.ToMM(c.x);y1,y2=p.ToMM(a.y),p.ToMM(c.y)
 if min(x1,x2)<=47.5<=max(x1,x2) and x1!=x2:
  y=y1+(y2-y1)*(47.5-x1)/(x2-x1)
  matches=[(top,nets) for top,nets in rows if top+4<=y<=top+10]
  assert matches, f'Copper crosses absent tab substrate at {y}'
  top,nets=matches[0];assert t.GetNetname() in nets,f'Unexpected neck net {t.GetNetname()} at {top}'
  crossings.append({'top_mm':top,'net':t.GetNetname(),'y_mm':round(y,4),'layer':b.GetLayerName(t.GetLayer())})
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones())
try:p.SaveBoard(str(R/'pi5_corona_hv.kicad_pcb'),b)
finally:pro.write_bytes(saved)
subprocess.run(['kicad-cli','pcb','drc','--format','json','--output',str(R/'exports/compact-pcb-drc.json'),str(R/'pi5_corona_hv.kicad_pcb')],check=True)
for attempt in range(15):
 d=json.loads((R/'exports/compact-pcb-drc.json').read_text())
 if not d['violations']:break
 assert all(v['type'] in ['track_dangling','via_dangling','starved_thermal'] for v in d['violations'])
 for violation in d['violations']:
  if violation['type']=='starved_thermal':
   pad_id=violation['items'][1]['uuid']
   for fp in b.GetFootprints():
    for pad in fp.Pads():
     if pad.m_Uuid.AsString()==pad_id:
      assert pad.GetNetname()=='GND'
      pad.SetLocalZoneConnection(p.ZONE_CONNECTION_FULL)
 ids={v['items'][0]['uuid'] for v in d['violations']}
 pending=list(b.GetTracks());tracks.extend(pending)
 for t in pending:
  if t.m_Uuid.AsString() in ids:b.Remove(t);t.thisown=False;removed.append(t)
 b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones())
 try:p.SaveBoard(str(R/'pi5_corona_hv.kicad_pcb'),b)
 finally:pro.write_bytes(saved)
 subprocess.run(['kicad-cli','pcb','drc','--format','json','--output',str(R/'exports/compact-pcb-drc.json'),str(R/'pi5_corona_hv.kicad_pcb')],check=True)
d=json.loads((R/'exports/compact-pcb-drc.json').read_text());assert not d['violations'] and not d['schematic_parity']
(R/'exports/breakoff-neck-validation.json').write_text(json.dumps({'layout_revision':b.GetTitleBlock().GetRevision(),'unexpected_neck_nets':[],'crossings':crossings,'routing_complete':False,'unconnected_items':len(d['unconnected_items'])},indent=2)+'\n')
print('Accepted partial routing:',len(d['unconnected_items']),'unconnected items;',len(crossings),'valid neck crossings')
