#!/usr/bin/env python3
"""Validate and regenerate exports for the canonical working project without saving it."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def get_python():
    candidates = [
        '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3',
        '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3',
        sys.executable,
        '/usr/bin/python3',
    ]
    for c in candidates:
        if Path(c).exists():
            res = subprocess.run([c, '-c', 'import pcbnew'], capture_output=True)
            if res.returncode == 0:
                return c
    return sys.executable


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def refresh():
    version = subprocess.check_output(['kicad-cli', 'version'], text=True).strip()
    if not version.startswith('10.'):
        raise RuntimeError('KiCad 10 required')
    board = ROOT / 'pi5_corona_hv.kicad_pcb'
    schematic = ROOT / 'pi5_corona_hv.kicad_sch'
    sources = [*ROOT.glob('*.kicad_sch'), board, ROOT / 'pi5_corona_hv.kicad_pro',
               ROOT / 'pi5_corona_hv.kicad_dru']
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    before = {path: digest(path) for path in sources}
    exports = ROOT / 'exports'
    exports.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='corona-native-net-') as temp:
        netlist = Path(temp) / 'current.net'
        run('kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr',
            '--output', netlist, schematic)
        run('ruby', ROOT / 'layout/export_connectivity.rb', netlist)
    run('ruby', ROOT / 'layout/validation/check_audit_nets.rb')
    run('kicad-cli', 'sch', 'erc', '--format', 'json', '--exit-code-violations',
        '--output', exports / 'erc.json', schematic)
    run('kicad-cli', 'pcb', 'drc', '--schematic-parity', '--format', 'json',
        '--exit-code-violations', '--output', exports / 'jlcpcb-drc.json', board)
    run('ruby', ROOT / 'layout/export_procurement.rb')
    py = get_python()
    run(py, ROOT / 'layout/generate_jlcpcb_cpl.py')
    run(py, ROOT / 'layout/validation/regenerate_manufacturing.py')
    run(py, ROOT / 'layout/validation/package_jlcpcb.py')
    if any(digest(path) != value for path, value in before.items()):
        raise RuntimeError('Export unexpectedly altered native design sources')
    report = json.loads((exports / 'jlcpcb-validation.json').read_text())
    working = dict(role='canonical working design', revision=report['revision'],
                   project='hardware/pi5_corona_hat_direct/pi5_corona_hv.kicad_pro',
                   kicad_version=version, production_release=False,
                   native_checks=dict(erc_violations=0, drc_violations=0,
                                      unconnected_items=0, schematic_parity_issues=0,
                                      connectivity_audits_passed=17),
                   source_sha256={path.name: value for path, value in before.items()},
                   matching_bom_components=report['jlcpcb_bom_part_quantity'],
                   matching_bom_rows=report['jlcpcb_bom_rows'],
                   package=f"exports/jlcpcb-{report['revision']}-package.zip",
                   release_holds='See AUDIT.md')
    (exports / 'working-version.json').write_text(json.dumps(working, indent=2) + '\n')
    print('Canonical working design validated; source files unchanged.')


if __name__ == '__main__':
    refresh()
