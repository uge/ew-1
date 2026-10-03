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
title.SetRevision('G-layout-3')
title.SetComment(0, 'PLACEMENT STUDY — UNROUTED — NOT FOR FABRICATION')
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

# Main carrier 281 x 150 mm, with three independently detachable mini boards.
# Each 8 mm neck has a marked cut line; do not use a shared scoring line.
outline = [(50,50),(331,50),(331,200),
           (153,200),(153,205),(163,205),(163,225),(135,225),(135,205),(145,205),(145,200),
           (119,200),(119,205),(129,205),(129,225),(101,225),(101,205),(111,205),(111,200),
           (83,200),(83,205),(94,205),(94,225),(64,225),(64,205),(75,205),(75,200),
           (50,200)]
for a,b in zip(outline, outline[1:]+outline[:1]): line(a,b)

positions = {
    'J2':(54.23,106.63,180), 'J3':(60,125,90), 'J50':(79,193,180),
    'U7':(76,116,0), 'Q1':(89,116,0), 'F1':(66,139,0),
    'U9':(103,116,0), 'R13':(96,127,0), 'C70':(114,129,0),
    'C21':(70,130,0), 'C22':(83,130,0), 'C73':(94,139,0),
    'NTC1':(78,124,0), 'C17':(73,110,0), 'C18':(79,110,0),
    'R14':(73,122,0), 'C19':(87,109,0), 'C20':(93,109,0),
    'R70':(101,122,0), 'R71':(108,121,0), 'R72':(109,111,0),
    'R73':(103,109,0), 'C71':(114,116,0), 'C72':(99,111,0),
    'U5':(68,80,0), 'C15':(68,85,0), 'U6':(90,91,0),
    'C16':(90,86,0), 'R10':(99,89,0), 'R11':(104,89,0),
    'R12':(96,95,0), 'K1':(84,153,0),
    'S3':(115,211,0), 'S4':(149,211,0), 'D3':(85,166,0),
    'U2':(110,171,0), 'C10':(102,171,90), 'C12':(103,178,0),
    'C60':(118,180,0), 'C61':(108,164,0), 'C62':(115,164,0),
    'R5':(104,157,0), 'R61':(109,157,0), 'R62':(115,157,0),
    'R63':(119,164,0), 'TP50':(121,152,0),
    'D50':(105,144,0), 'D51':(116,144,90), 'R60':(120,190,90),
    'D52':(130,162,90), 'D53':(130,178,90),
    'D54':(142,162,90), 'D55':(137,178,90),
    'C11':(122,132,0), 'T1':(129,110,90),
    'C63':(130,188,0), 'R64':(141,188,0),
    'U4':(137,193,0), 'R8':(148,190,90), 'R9':(148,198,90),
    'C13':(141,201,0), 'R7':(130,200,0), 'D1':(130,193,0),
    'R90':(116,188,0), 'R91':(109,188,0),
    'C14':(105,196,0), 'D4':(112,196,0),
    'J60':(318,65,0), 'J61':(164,196,0),
    'J62':(112.46,219,0), 'J63':(146.46,219,0),
    'J64':(86,181,0), 'J65':(97,181,0),
    'U8':(79,217,0), 'J51':(79,210,180),
    'C80':(73,217,90), 'C81':(85,217,90),
}
for i in range(10):
    positions[f'R{20+i}']=(150+i*17,65,0)
    positions[f'R{30+i}']=(303-i*16,187,180)
for i in range(6):
    x=156+i*30
    for row,y in [(0,99),(1,151)]:
        idx=i*2+row
        positions[f'C{100+idx}']=(x,y,0)
        by=80 if row==0 else 171
        positions[f'R{140+2*idx}']=(x-10,by,0)
        positions[f'R{40+idx}']=(x,by,0)
        positions[f'R{141+2*idx}']=(x+10,by,0)
    positions[f'D{10+2*i}']=(x-8,125,90)
    positions[f'D{11+2*i}']=(x+8,125,270)

for ref in ['U2','C10','C12','C60','C61','C62','R5','R61','R62','R63','R60',
            'D52','D53','D54','D55','C63','R64','U4','R8','R9','C13','R7','D1',
            'R90','R91','C14','D4']:
    x,y,a=positions[ref]; positions[ref]=(x,y-6,a)

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
    if ref=='D3':
        for graphic in fp.GraphicalItems():
            if graphic.GetLayer()==p.F_SilkS: graphic.SetLayer(p.F_Fab)
    for pad in fp.Pads():
        net=pin_nets.get((ref,pad.GetNumber()))
        if net: pad.SetNet(net)
    fp.Reference().SetTextSize(point(.9,.9))
    fp.Reference().SetTextThickness(p.FromMM(.15))
    fp.Reference().SetTextAngle(p.EDA_ANGLE(0,p.DEGREES_T))
    # Field above the actual physical bounding box, rather than library anchors.
    box=fp.GetBoundingBox(False,False)
    fp.Reference().SetPosition(point(x,p.ToMM(box.GetTop())-1.3))
    if ref=='J2': fp.Reference().SetPosition(point(64,60))
    if ref=='U4': fp.Reference().SetPosition(point(137,190.5))
    fp.Value().SetVisible(False)
    placed[ref]=fp

# Four Pi mounting holes at 58 x 49 mm pitch. Additional carrier supports.
for i,(x,y) in enumerate([(55.5,111.5),(55.5,53.5),(114,55),
                          (55,194),(325,194),(325,55)],1):
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
region(52,52,121,198,[p.B_Cu])
region(122,52,330,199,[p.F_Cu,p.B_Cu],True)

text('PI GPIO',65,69,.9)
text('USB-C PD / eFUSE',82,135,1)
text('BRIDGE / TRANSFORMER',82,174,.8)
text('HV BALLAST',231,54)
text('HV MULTIPLIER / NO POURS',231,92,1)
text('1 GOhm DIVIDER',233,195,1)
text('2 LAYERS / PLACEMENT STUDY',236,160,.8)
text('HV OUT',318,58,.8)
text('HV RETURN',179,196,.8)
for x,label,width in [(79,'ILLUMINATION',30),(115,'S3 / COM-NO',28),(149,'S4 / COM-NO',28)]:
    text(label,x,224,.8)
    line((x-4,202.5),(x+4,202.5),p.Dwgs_User,.15)
    text('CUT',x+7,202.5,.7,p.Dwgs_User)
for ref in ['J62','J63','J64','J65']:
    x,y,_=positions[ref];text('1 COM    2 NO',x+2.54,y+3,.8)
# Only the intended cable nets cross each marked neck. These fixed stubs guide
# later routing and are severed when the mini boards are detached.
neck_nets=[(76.6,'GND'),(78.2,'3V3'),(79.8,'/01_power_mcu/SDA'),
           (81.4,'/01_power_mcu/SCL'),(113,'/VIN_PROTECTED'),
           (117,'/04_sense_safety/LID_INT'),(147,'/04_sense_safety/LID_INT'),
           (151,'/04_sense_safety/RELAY_COIL_POS')]
for x,name in neck_nets:
    t=p.PCB_TRACK(board);t.SetStart(point(x,199));t.SetEnd(point(x,207))
    t.SetWidth(p.FromMM(.3));t.SetLayer(p.F_Cu);t.SetNet(net_objects[name]);board.Add(t)
board.BuildConnectivity()
p.ZONE_FILLER(board).Fill(board.Zones())
p.SaveBoard(str(ROOT/'pi5_corona_hv.kicad_pcb'),board)
# pcbnew's legacy file API may save a default project alongside the board.
# Preserve the real project's netclasses, variables and design constraints.
project_path.write_text(project_text)
(ROOT/'layout/initial-placement.json').write_text(json.dumps({
    'revision':'G-layout-3','copper_layers':2,'board_thickness_mm':1.6,
    'main_board_mm':[281,150],'overall_mm':[281,175],
    'footprints_from_schematic':len(placed),'mounting_holes':6,
    'routing_complete':False,'production_release':False,
    'positions':{k:list(v) for k,v in positions.items()},
    'holds':['HV solder-wire insulation and strain-relief validation','K1 coil supply review',
             'Pi 5 cooler/enclosure interference','HV creepage and clearance review',
             'Transformer footprint manufacturer verification',
             'Break-off neck routing and cutting process','Complete routing and DRC']
},indent=2)+'\n')
print(f'Placed {len(placed)} schematic footprints on two copper layers.')
if (ROOT/'layout/add_pi5_mechanical.py').exists():
    import runpy
    runpy.run_path(str(ROOT/'layout/add_pi5_mechanical.py'),run_name='__main__')
