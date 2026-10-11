"""Apply 42 collinear high-voltage string track segments to pi5_corona_hv.kicad_pcb.

Routes:
1. Ballast string R20-R29 (9 segments, 0.6 mm width on F.Cu)
2. 1G Divider string R30-R39 (9 segments, 0.6 mm width on F.Cu)
3. 6-Stage Bleeder intermediate pairs R140-R163 (24 segments, 0.6 mm width on F.Cu)
"""
from pathlib import Path
import pcbnew as p

ROOT = Path(__file__).resolve().parents[1]
pro = ROOT / 'pi5_corona_hv.kicad_pro'
pro_saved = pro.read_text()
pcb_path = str(ROOT / 'pi5_corona_hv.kicad_pcb')

b = p.LoadBoard(pcb_path)

def add_seg(netname, x1, y1, x2, y2, width=0.6, layer=p.F_Cu):
    net = b.FindNet(netname)
    if not net:
        raise RuntimeError(f'Net {netname} not found!')
    t = p.PCB_TRACK(b)
    t.SetStart(p.VECTOR2I(p.FromMM(x1), p.FromMM(y1)))
    t.SetEnd(p.VECTOR2I(p.FromMM(x2), p.FromMM(y2)))
    t.SetWidth(p.FromMM(width))
    t.SetLayer(layer)
    t.SetNet(net)
    b.Add(t)

# 1. Ballast string connections (9 segments):
add_seg('Net-(R20-Pad2)', 221.25, 63.0, 219.25, 63.0)
add_seg('Net-(R21-Pad2)', 205.75, 63.0, 203.75, 63.0)
add_seg('Net-(R22-Pad2)', 190.25, 63.0, 188.25, 63.0)
add_seg('Net-(R23-Pad2)', 174.75, 63.0, 172.75, 63.0)
add_seg('Net-(R24-Pad2)', 159.25, 63.0, 159.25, 78.0)
add_seg('Net-(R25-Pad2)', 172.75, 78.0, 174.75, 78.0)
add_seg('Net-(R26-Pad2)', 188.25, 78.0, 190.25, 78.0)
add_seg('Net-(R27-Pad2)', 203.75, 78.0, 205.75, 78.0)
add_seg('Net-(R28-Pad2)', 219.25, 78.0, 221.25, 78.0)

# 2. Divider string connections (9 segments):
add_seg('Net-(R30-Pad2)', 225.04, 187.0, 219.21, 187.0)
add_seg('Net-(R31-Pad2)', 213.29, 187.0, 210.21, 187.0)
add_seg('Net-(R32-Pad2)', 204.29, 187.0, 201.21, 187.0)
add_seg('Net-(R33-Pad2)', 195.29, 187.0, 192.21, 187.0)
add_seg('Net-(R34-Pad2)', 186.29, 187.0, 183.21, 187.0)
add_seg('Net-(R35-Pad2)', 177.29, 187.0, 174.21, 187.0)
add_seg('Net-(R36-Pad2)', 168.29, 187.0, 165.21, 187.0)
add_seg('Net-(R37-Pad2)', 159.29, 187.0, 156.21, 187.0)
add_seg('Net-(R38-Pad2)', 150.29, 187.0, 147.21, 187.0)

# 3. Bleeder intermediate connections (24 segments):
add_seg('Net-(R140-Pad2)', 122.21, 87.0, 126.29, 87.0)
add_seg('Net-(R141-Pad1)', 132.21, 87.0, 136.29, 87.0)
add_seg('Net-(R142-Pad2)', 128.96, 177.0, 133.04, 177.0)
add_seg('Net-(R143-Pad1)', 138.96, 177.0, 143.04, 177.0)

add_seg('Net-(R144-Pad2)', 138.21, 95.0, 142.29, 95.0)
add_seg('Net-(R145-Pad1)', 148.21, 95.0, 152.29, 95.0)
add_seg('Net-(R146-Pad2)', 144.96, 169.0, 149.04, 169.0)
add_seg('Net-(R147-Pad1)', 154.96, 169.0, 159.04, 169.0)

add_seg('Net-(R148-Pad2)', 154.21, 87.0, 158.29, 87.0)
add_seg('Net-(R149-Pad1)', 164.21, 87.0, 168.29, 87.0)
add_seg('Net-(R150-Pad2)', 160.96, 177.0, 165.04, 177.0)
add_seg('Net-(R151-Pad1)', 170.96, 177.0, 175.04, 177.0)

add_seg('Net-(R152-Pad2)', 170.21, 95.0, 174.29, 95.0)
add_seg('Net-(R153-Pad1)', 180.21, 95.0, 184.29, 95.0)
add_seg('Net-(R154-Pad2)', 176.96, 169.0, 181.04, 169.0)
add_seg('Net-(R155-Pad1)', 186.96, 169.0, 191.04, 169.0)

add_seg('Net-(R156-Pad2)', 186.21, 87.0, 190.29, 87.0)
add_seg('Net-(R157-Pad1)', 196.21, 87.0, 200.29, 87.0)
add_seg('Net-(R158-Pad2)', 192.96, 177.0, 197.04, 177.0)
add_seg('Net-(R159-Pad1)', 202.96, 177.0, 207.04, 177.0)

add_seg('Net-(R160-Pad2)', 202.21, 95.0, 206.29, 95.0)
add_seg('Net-(R161-Pad1)', 212.21, 95.0, 216.29, 95.0)
add_seg('Net-(R162-Pad2)', 208.96, 169.0, 213.04, 169.0)
add_seg('Net-(R163-Pad1)', 218.96, 169.0, 223.04, 169.0)

b.BuildConnectivity()
try:
    p.SaveBoard(pcb_path, b)
finally:
    pro.write_text(pro_saved)

print('Applied 42 HV string segments.')
