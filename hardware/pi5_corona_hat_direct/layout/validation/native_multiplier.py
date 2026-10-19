"""Native schematic-derived passive multiplier and bounded shutdown scenarios."""
from pathlib import Path
from functools import lru_cache
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import re
import hashlib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]

@lru_cache(maxsize=1)
def circuit():
    with tempfile.TemporaryDirectory() as td:
        xml = Path(td) / 'net.xml'
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml',
                        '-o', str(xml), str(ROOT / 'pi5_corona_hv.kicad_sch')], check=True, capture_output=True)
        doc = ET.parse(xml).getroot()
        digest = hashlib.sha256(xml.read_bytes()).hexdigest()
    values = {c.get('ref'): c.findtext('value') for c in doc.findall('./components/comp')}
    aliases = {'GND': '0', '/SEC_A': 'SEC_IN', '/HV_RAW': 'HV_RAW',
               '/HV_RETURN': 'HV_RET', '/04_sense_safety/HV_OUT': 'HV_OUT',
               '/04_sense_safety/HV_SENSE_RAW': 'HV_SENSE'}
    for i in range(1, 6):
        for letter in 'PS':
            aliases[f'/03_multiplier/CW_{letter}{i}'] = f'CW_{letter}{i}'
    aliases['Net-(D20-K)'] = 'D20_K'
    pins = {}
    for i, net in enumerate(doc.findall('./nets/net')):
        name = aliases.get(net.get('name'), f'N{i}')
        for node in net.findall('node'):
            pins[(node.get('ref'), node.get('pin'))] = name
    refs = ([f'C{i}' for i in range(100,112)] + [f'R{i}' for i in range(140,164)] +
            [f'R{i}' for i in range(20,40)] + ['R8','R9','R90','C13'] + [f'D{i}' for i in range(10,22)])
    lines = ['.model D2CL75 D (IS=1e-12 RS=1500 N=25 CJO=1p TT=100n BV=16000 IBV=1u)']
    caps = []
    for ref in refs:
        a,b = pins[(ref,'1')], pins[(ref,'2')]
        if ref.startswith('D'):
            lines.append(f'{ref} {b} {a} D2CL75') # KiCad pin 1 cathode
        else:
            token = values[ref].split()[0]
            if ref.startswith('R') and token.endswith('M'):
                token = token[:-1] + 'MEG'
            token = re.sub(r'F$', '', token)
            lines.append(f'{ref} {a} {b} {token}')
            if ref.startswith('C'):
                caps.append((ref,a,b))
    return '\n'.join(lines), caps, digest


def run_spice(deck, path, vectors):
    output = Path(path)
    code = deck + '\n.control\nset wr_singlescale\nset wr_vecnames\nrun\nwrdata ' + str(output) + ' ' + ' '.join(f'v({n})' for n in vectors) + '\n.endc\n.end\n'
    proc = subprocess.run(['ngspice','-b'], input=code, text=True, capture_output=True)
    if proc.returncode or not output.exists() or 'timestep too small' in proc.stderr.lower():
        raise RuntimeError(f'ngspice failed: {proc.stdout[-1000:]} {proc.stderr[-1000:]}')
    data = np.loadtxt(output, skiprows=1)
    if not np.isfinite(data).all():
        raise RuntimeError('Nonfinite simulation result')
    return data


def shutdown(tmpdir, external_cap_pf=100., duration=5.):
    body, caps, digest = circuit()
    nodes = sorted({n for _,a,b in caps for n in (a,b) if n != '0'} | {'HV_OUT','HV_RET'})
    # Energize the actual passive network. Capture a full settled AC cycle;
    # shutdown initializes every capacitor terminal, including pump nodes.
    startup = run_spice('* Native multiplier pre-shutdown charging\n' + body +
        f'\nC_EXTERNAL HV_OUT HV_RET {external_cap_pf}p\nV_SEC SEC_SOURCE 0 SIN(0 1250 68k)\nR_SEC SEC_SOURCE SEC_IN 350\n.tran 200n 30m 29.97m 200n uic',
        Path(tmpdir)/'shutdown-charge.txt', nodes)
    if startup[-1,0] < .02999:
        raise RuntimeError('Charging simulation did not complete')
    last = startup[-1,1:]
    previous_cycle = np.array([np.interp(.03-1/68000, startup[:,0], startup[:,i+1]) for i in range(len(nodes))])
    cycle_error = float(np.max(abs(last-previous_cycle)))
    if cycle_error > max(10., .01 * float(np.max(abs(last)))):
        raise RuntimeError('Pre-shutdown charging has not converged cycle-to-cycle')
    phases = [np.r_[.03-(1-phase)/68000,
               [np.interp(.03-(1-phase)/68000,startup[:,0],startup[:,i+1]) for i in range(len(nodes))]]
              for phase in (0., .25, .5, .75)]
    scenarios = []
    nominal = None
    for phase_index, state in enumerate(phases):
        for termination in ('clamped_350ohm', 'open_1Tohm'):
            # One resistor open in each two-resistor bank removes that bank.
            faults = [None] + [f'R{i}' for i in range(140,164,2)]
            for fault in faults:
                edited = '\n'.join(line for line in body.splitlines() if not (fault and line.startswith(fault+' ')))
                resistance = '350' if termination.startswith('clamped') else '1e12'
                initial = ' '.join(f'v({n})={v:.12g}' for n,v in zip(nodes,state[1:]))
                deck = ('* Native topology shutdown\n' + edited +
                    f'\nC_EXTERNAL HV_OUT HV_RET {external_cap_pf}p\nR_OFF SEC_IN 0 {resistance}\n.ic {initial}\n.tran 200u {duration} 0 1m uic')
                data = run_spice(deck, Path(tmpdir)/'shutdown-case.txt', nodes)
                if data[-1,0] < duration * .999:
                    raise RuntimeError('Shutdown simulation did not complete')
                voltages = {n:data[:,i+1] for i,n in enumerate(nodes)}
                voltages['0'] = np.zeros(len(data))
                # Require both node-to-ground and every capacitor differential below threshold.
                measures = dict(voltages)
                measures.update({ref:voltages[a]-voltages[b] for ref,a,b in caps})
                measures['C_EXTERNAL'] = voltages['HV_OUT']-voltages['HV_RET']
                envelope = np.max(np.abs(np.column_stack(list(measures.values()))),axis=1)
                above = np.flatnonzero(envelope >= 50.)
                settled = None if len(above) and above[-1] == len(data)-1 else float(data[above[-1]+1,0] if len(above) else data[0,0])
                scenario = dict(phase_index=phase_index, termination=termination, open_resistor=fault,
                    all_nodes_and_capacitors_below_50V_s=settled,
                    max_residual_at_end_V=float(envelope[-1]),
                    last_above_threshold={k:float(data[np.flatnonzero(abs(v)>=50)[-1],0]) if np.any(abs(v)>=50) else None for k,v in measures.items()})
                scenarios.append(scenario)
                if nominal is None:
                    nominal = dict(time_s=data[:,0], v_out=voltages['HV_OUT'], v_raw=voltages['HV_RAW'], envelope=envelope)
    times = [s['all_nodes_and_capacitors_below_50V_s'] for s in scenarios]
    report = dict(netlist_sha256=digest, external_capacitance_pf=external_cap_pf,
        secondary_vpk=1250, frequency_hz=68000, charging_duration_s=.03,
        shutdown_window_s=duration, precharge_cycle_error_V=cycle_error,
        initial_node_voltages=[dict(zip(nodes,map(float,state[1:]))) for state in phases], scenarios=scenarios,
        worst_case_all_nodes_below_50V_s=max(times) if all(t is not None for t in times) else None,
        status='MODEL_ONLY_REQUIRES_HARDWARE_VALIDATION',
        assumptions=['Native passive topology and values; nominal component tolerances',
            'Generic diode model, not manufacturer-qualified',
            'Secondary shutdown bounded by 350 ohm clamp and 1 Tohm open models; actual transformer/bridge dynamics unqualified',
            'Four AC shutdown phases; one open resistor per bleeder bank tested individually',
            'External capacitance must be set to the actual electrode/cable worst case',
            'No automatic enclosure access or safe-touch certification'])
    nominal['report'] = report
    nominal['meas'] = dict(t_safe=report['worst_case_all_nodes_below_50V_s'],
        v_t05=float(np.interp(.5,nominal['time_s'],nominal['v_out'])),
        v_t10=float(np.interp(1.,nominal['time_s'],nominal['v_out'])))
    return nominal


if __name__ == '__main__':
    import argparse, json
    parser=argparse.ArgumentParser()
    parser.add_argument('--external-cap-pf',type=float,default=100.)
    parser.add_argument('--duration',type=float,default=5.)
    parser.add_argument('--output',type=Path,default=ROOT/'exports/shutdown-report.json')
    args=parser.parse_args()
    if args.external_cap_pf <= 0 or args.duration <= 0:
        parser.error('Capacitance and duration must be positive')
    with tempfile.TemporaryDirectory() as td:
        result=shutdown(td,args.external_cap_pf,args.duration)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result['report'],indent=2)+'\n')
    print(json.dumps({k:v for k,v in result['report'].items() if k!='scenarios'},indent=2))
