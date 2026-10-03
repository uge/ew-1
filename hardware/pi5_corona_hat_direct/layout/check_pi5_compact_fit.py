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
pcb = Part.makeBox(281,150,1.6,App.Vector(50,-200,0))

candidates=[]
collisions=[]
for index,solid in enumerate(shape.Solids):
    box=solid.BoundBox
    # Rotation 180 degrees about X, then translation to assembly coordinates.
    xmin,xmax=3+box.YMin,3+box.YMax
    ymin,ymax=115-box.XMax,115-box.XMin  # PCB drawing Y, downward
    zmin,zmax=14.906-box.ZMax,14.906-box.ZMin
    if xmax<=50 or xmin>=331 or ymax<=50 or ymin>=200 or zmax<=0 or zmin>=1.6:
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
        'substrate_collisions':collisions,'carrier_dimensions_mm':[281,150,1.6],
        'pi_native_rotation_deg':[180,0,90],
        'pi_assembly_translation_mm':[3,-115,14.906],
        'carrier_usb_relief_mm':None,
        'pi_gpio_overlap_only_assumption':True,
        'excludes':['Cooler','Enclosure','Cables','Complete carrier component collision test',
                    'Connector mating tolerance validation']}
(root/'exports/compact-pi5-substrate-fit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
assert not collisions, 'Pi model collides with carrier substrate'
