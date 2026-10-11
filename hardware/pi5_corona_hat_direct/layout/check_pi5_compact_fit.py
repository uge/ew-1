"""Run with FreeCADCmd to check Pi solids against the carrier substrate.

This tests the selected pose and PCB material only, not the enclosure, cooler,
cables, socket mating tolerances or all carrier component bodies.
"""
import json
from pathlib import Path
import Part
import FreeCAD as App

root = Path(__file__).resolve().parents[1]
shape = Part.Shape()
shape.read(str(root/'ionic_thrust_hv.3dshapes/Raspberry_Pi_5_official.step'))
pieces=[Part.makeBox(196,148,1.6,App.Vector(50,-199,0))]
for top in [120,136,152,168,184]:
    pieces += [Part.makeBox(30,14,1.6,App.Vector(15,-(top+14),0)),
               Part.makeBox(5,6,1.6,App.Vector(45,-(top+10),0))]
pcb=Part.makeCompound(pieces)

candidates=[]
collisions=[]
for index,solid in enumerate(shape.Solids):
    box=solid.BoundBox
    # Rotation 180 degrees about X, then translation to assembly coordinates.
    xmin,xmax=3+box.YMin,3+box.YMax
    ymin,ymax=115-box.XMax,115-box.XMin  # PCB drawing Y, downward
    zmin,zmax=14.906-box.ZMax,14.906-box.ZMin
    if xmax<=15 or xmin>=246 or ymax<=51 or ymin>=199 or zmax<=0 or zmin>=1.6:
        continue
    candidates.append({'solid':index,'native_bounds':[
        box.XMin,box.XMax,box.YMin,box.YMax,box.ZMin,box.ZMax],
        'posed_bounds':[xmin,xmax,ymin,ymax,zmin,zmax]})
    posed=solid.copy()
    posed.rotate(App.Vector(0,0,0),App.Vector(1,0,0),180)
    posed.rotate(App.Vector(0,0,0),App.Vector(0,0,1),90)
    posed.translate(App.Vector(3,-115,14.906))
    volume=posed.common(pcb).Volume
    if volume>1e-6: collisions.append({'solid':index,'volume_mm3':volume})
report={'pi_solids':len(shape.Solids),'bbox_candidates':candidates,
        'substrate_collisions':collisions,'carrier_dimensions_mm':[196,148,1.6], 'overall_dimensions_mm':[231,148], 'side_mini_boards':True, 'mini_board_count':5, 'mini_board_dimensions_mm':[30,14], 'layout_revision':'M-layout-8',
        'pi_native_rotation_deg':[180,0,90],
        'pi_assembly_translation_mm':[3,-115,14.906],
        'carrier_usb_relief_mm':None,
        'pi_gpio_overlap_only_assumption':True,
        'excludes':['Cooler','Enclosure','Cables','Complete carrier component collision test',
                    'Connector mating tolerance validation']}
(root/'exports/compact-pi5-substrate-fit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
assert not collisions, 'Pi model collides with carrier substrate'
