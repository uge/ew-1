"""Use KiCadRoutingTools for LV-only routing trials, preserving KiCad rules.

Never autoroute multiplier, HV sense/return or transformer power nodes here.
Run with /usr/bin/python3. Native KiCad DRC remains the acceptance check.
"""
from pathlib import Path
import json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
TOOLS=Path.home()/'.local/share/KiCadRoutingTools'
trial=ROOT/'layout/routing-trials';trial.mkdir(exist_ok=True)
source=ROOT/'pi5_corona_hv'
for ext in ['.kicad_pcb','.kicad_pro','.kicad_dru']:
 shutil.copy2(source.with_suffix(ext),trial/('control-input'+ext))
(trial/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "ionic_thrust_hv") (type "KiCad") (uri "${KIPRJMOD}/../../ionic_thrust_hv.pretty") (options "") (descr "Project footprints")))\n')
# Exact names rather than wildcards prevent accidental HV routing.
names=['/01_power_mcu/SDA','/01_power_mcu/SCL','/DRV_IN1',
       '/DRV_IN2','/01_power_mcu/BULK_EN',
       '/02_drive_transformer/DRV_nFAULT','/DRV_nSLEEP']
data=json.loads((ROOT/'layout/schematic-connectivity.json').read_text())
existing={n['name'] for n in data['nets']}; names=[n for n in names if n in existing]
if not names:raise RuntimeError('No requested control nets found')
clear={a['pattern']:10 if a['netclass']=='HV_OUT' else 4 for a in json.loads((ROOT/'layout/hv-netclass-assignments.json').read_text())}
clear['/HV_RETURN']=4
(trial/'net-clearances.json').write_text(json.dumps(clear,indent=2)+'\n')
for ext in ['.kicad_pro','.kicad_dru']:
 shutil.copy2(source.with_suffix(ext),trial/('control-routed'+ext))
cmd=['/usr/bin/python3',str(TOOLS/'py_router/route.py'),str(trial/'control-input.kicad_pcb'),str(trial/'control-routed.kicad_pcb'),
     '--nets',*names,'--layers','F.Cu','B.Cu','--track-width','0.2',
     '--clearance','0.2','--net-clearances',str(trial/'net-clearances.json'),
     '--via-size','0.6','--via-drill','0.3','--escalation','off',
     '--no-fix-drc-settings','--no-crossing-layer-check','--no-stub-layer-swap',
     '--same-net-pad-clearance','0.2','--write-fill','--max-ripup','2','--max-iterations','100000','--json-out',str(trial/'router-result.json')]
(trial/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
with (trial/'router.log').open('w') as log:
 result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
print('Route tool exit:',result.returncode,'nets:',names)
# Keep the project constraints intact even if the tool changes defaults.
for name in ['control-input','control-routed']:
 shutil.copy2(source.with_suffix('.kicad_pro'),trial/(name+'.kicad_pro'))
print('Test routes:',trial/'control-routed.kicad_pcb')
raise SystemExit(result.returncode)
