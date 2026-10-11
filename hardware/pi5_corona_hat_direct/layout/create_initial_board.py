"""Initial KiCad 10 PCB placement using pcbnew; never generates schematics.

Run with /usr/bin/python3. This deliberately leaves routing for the next pass.
"""
import json
from pathlib import Path
import pcbnew as p

ROOT = Path(__file__).resolve().parents[1]
project_path = ROOT/'pi5_corona_hv.kicad_pro'
project_text = project_path.read_text()
data = json.loads((ROOT / 'layout/schematic-connectivity.json').read_text())
board = p.BOARD()
board.SetCopperLayerCount(2)
board.GetDesignSettings().SetBoardThickness(p.FromMM(1.6))
title = board.GetTitleBlock()
title.SetTitle('Pi 5 Corona Supply — Compact two-layer placement')
title.SetRevision('M-layout-8')
title.SetComment(0, 'PLACEMENT STUDY — PARTIAL ROUTING — NOT FOR FABRICATION')
board.SetTitleBlock(title)

def point(x, y):
    return p.VECTOR2I(p.FromMM(x), p.FromMM(y))

def line(a, b, layer=p.Edge_Cuts, width=.05):
    s = p.PCB_SHAPE(board)
    s.SetShape(p.SHAPE_T_SEGMENT)
    s.SetStart(point(*a)); s.SetEnd(point(*b))
    s.SetLayer(layer); s.SetWidth(p.FromMM(width)); board.Add(s)

def text(value, x, y, size=1.2, layer=p.F_SilkS):
    t = p.PCB_TEXT(board); t.SetText(value); t.SetPosition(point(x, y))
    t.SetTextSize(point(size, size)); t.SetTextThickness(p.FromMM(.18))
    t.SetLayer(layer); board.Add(t)

# Carrier 196 x 148 mm, detachable boards on the left below the Pi.
outline = [(50,51),(246,51),(246,199),(50,199)]
for top in reversed([120,136,152,168,184]):
    outline += [(50,top+10),(45,top+10),(45,top+14),(15,top+14),
                (15,top),(45,top),(45,top+4),(50,top+4)]
for a,b in zip(outline, outline[1:]+outline[:1]): line(a,b)

selected=json.loads((ROOT/'layout/optimized-placement.json').read_text())
assert selected['revision']=='M-layout-8'
positions=selected['positions']

net_objects={}
pin_nets={}
for n in data['nets']:
    net=p.NETINFO_ITEM(board,n['name'],n['code']); board.Add(net)
    net_objects[n['name']]=net
    for ref,pin in n['nodes']: pin_nets[(ref,pin)]=net

placed={}
for c in data['components']:
    ref=c['ref']; lib,name=c['footprint'].split(':',1)
    folder=ROOT/'ionic_thrust_hv.pretty' if lib=='ionic_thrust_hv' else Path('/usr/share/kicad/footprints')/(lib+'.pretty')
    fp=p.FootprintLoad(str(folder),name)
    if fp is None: raise RuntimeError(f'Missing footprint: {ref} {c["footprint"]}')
    board.Add(fp)
    fp.SetFPID(p.LIB_ID(lib,name))
    fp.SetReference(ref); fp.SetValue(c['value'])
    fp.SetAttributes(fp.GetAttributes() & ~p.FP_EXCLUDE_FROM_BOM)
    for key,value in c['properties'].items():
        if key in ('dnp','exclude_from_bom','exclude_from_board'): continue
        fp.SetField(key,value); fp.GetField(key).SetVisible(False)
    path=p.KIID_PATH()
    for uid in c['path'].split('/'):
        if uid: path.push_back(p.KIID(uid))
    fp.SetPath(path); fp.SetDNP(ref in ('C63','R64'))
    x,y,angle=positions[ref]
    fp.SetPosition(point(x,y)); fp.SetOrientationDegrees(angle)
    for pad in fp.Pads():
        net=pin_nets.get((ref,pad.GetNumber()))
        if net: pad.SetNet(net)
    fp.Reference().SetTextSize(point(.9,.9))
    fp.Reference().SetTextThickness(p.FromMM(.15))
    fp.Reference().SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
    # Field above the actual physical bounding box, rather than library anchors.
    box=fp.GetBoundingBox(False,False)
    fp.Reference().SetPosition(point(x,p.ToMM(box.GetTop())-1.3))
    if ref=='J60': fp.Reference().SetPosition(point(259,84))
    if ref=='J51': fp.Reference().SetPosition(point(39,124))
    if ref in ['S3','S4','S5','S6']: fp.Reference().SetPosition(point(20,y+6))
    if ref in ['J62','J63','J66','J67']: fp.Reference().SetPosition(point(39,y))
    if ref=='J2': fp.Reference().SetPosition(point(64,60))
    if ref=='U10': fp.Reference().SetPosition(point(80,167))
    if ref=='U8': fp.Reference().SetPosition(point(30,132.4))
    if ref=='U4': fp.Reference().SetPosition(point(137,190.5))
    fp.Value().SetVisible(False)
    placed[ref]=fp

# Four Pi mounting holes at 58 x 49 mm pitch. Additional carrier supports.
for i,(x,y) in enumerate([(55.5,111.5),(55.5,53.5),(114,55),
                          (55,194),(240,194),(240,55)],1):
    fp=p.FootprintLoad('/usr/share/kicad/footprints/MountingHole.pretty','MountingHole_2.7mm_M2.5')
    fp.SetReference(f'H{i}'); fp.SetPosition(point(x,y))
    fp.SetAttributes(fp.GetAttributes() | p.FP_BOARD_ONLY)
    fp.Reference().SetPosition(point(x+5,y))
    if i in (5,6): fp.Reference().SetPosition(point(x-5,y))
    fp.Value().SetVisible(False); board.Add(fp)

def region(x1,y1,x2,y2,layers,keepout=False,net='GND'):
    z=p.ZONE(board); ls=p.LSET()
    for layer in layers: ls.AddLayer(layer)
    z.SetLayerSet(ls)
    z.SetIsRuleArea(keepout)
    if keepout:
        z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowTracks(False)
        z.SetDoNotAllowVias(False); z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
    else:
        z.SetNet(net_objects[net]); z.SetLocalClearance(p.FromMM(.3))
        z.SetMinThickness(p.FromMM(.25))
    poly=z.Outline(); poly.NewOutline()
    for x,y in [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]: poly.Append(int(p.FromMM(x)),int(p.FromMM(y)))
    board.Add(z)

# On two layers the ground pour moves to the bottom, only in the LV region.
# HV tracks remain routable, but continuous pours on either side are forbidden.
region(52,52,101,198,[p.B_Cu])
region(102,52,245,198,[p.F_Cu,p.B_Cu],True)

text('PI GPIO',65,69,.9)
text('USB-C PD / eFUSE',82,86,.8)
text('BRIDGE / TRANSFORMER',83,153,.8)
text('HV BALLAST',180,53,.8)
text('HV MULTIPLIER / NO POURS',180,147,.8)
text('1 GOhm DIVIDER',180,195,1)
text('2 LAYERS / PLACEMENT STUDY',180,160,.8)
text('HV OUT',234,99,.8)
text('HV RETURN',146,196,.8)
for top,label in [(120,'ILLUMINATION'),(136,'S3'),(152,'S4'),(168,'S5'),(184,'S6')]:
    text(label,20 if top==120 else 30,top+3 if top==120 else top+13,.8)
    line((47.5,top+4),(47.5,top+10),p.Dwgs_User,.15)
    text('CUT',47.5,top+2,.7,p.Dwgs_User)
# Neck copper is routed in a separate pass; no dangling fixed stubs.
for fp in board.GetFootprints():
    ref=fp.GetReference()
    if ref in selected['reference_positions']:
        fp.Reference().SetPosition(point(*selected['reference_positions'][ref]))
        fp.Reference().SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
board.BuildConnectivity()
p.ZONE_FILLER(board).Fill(board.Zones())
p.SaveBoard(str(ROOT/'pi5_corona_hv.kicad_pcb'),board)
# pcbnew's legacy file API may save a default project alongside the board.
# Preserve the real project's netclasses, variables and design constraints.
project_path.write_text(project_text)
(ROOT/'layout/initial-placement.json').write_text(json.dumps({
    'revision':'M-layout-8','copper_layers':2,'board_thickness_mm':1.6,
    'main_board_mm':[196,148],'overall_mm':[231,148],
    'footprints_from_schematic':len(placed),'mounting_holes':6,
    'routing_complete':False,'production_release':False,
    'positions':{k:list(v) for k,v in positions.items()},
    'holds':['HV solder-wire insulation and strain-relief validation','Interlock timing and contact release verification',
             'Pi 5 cooler/enclosure interference','HV creepage and clearance review',
             'Transformer footprint manufacturer verification',
             'Break-off neck routing and cutting process','Complete routing and DRC']
},indent=2)+'\n')
print(f'Placed {len(placed)} schematic footprints on two copper layers.')
if (ROOT/'layout/add_pi5_mechanical.py').exists():
    import runpy
    runpy.run_path(str(ROOT/'layout/add_pi5_mechanical.py'),run_name='__main__')
