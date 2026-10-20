#!/usr/bin/env python3
"""Package current validated fabrication/assembly exports without altering the design."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import pcbnew

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'layout'))
from generate_jlcpcb_cpl import current_centroids, ROTATION_OFFSETS


def package():
    exports = ROOT / 'exports'
    board = pcbnew.LoadBoard(str(ROOT / 'pi5_corona_hv.kicad_pcb'))
    revision = board.GetTitleBlock().GetRevision()
    out = exports / ('jlcpcb-' + revision)
    out.mkdir(exist_ok=True)
    read = lambda name: list(csv.DictReader((exports / name).open()))
    bom, cpl = read('jlcpcb-bom.csv'), read('jlcpcb-cpl.csv')
    refs = [ref.strip() for row in bom for ref in row['Designator'].split(',')]
    assert len(refs) == len(set(refs)) == len(cpl)
    assert set(refs) == {row['Designator'] for row in cpl}
    assert not {'C63', 'R64', 'MP1'} & set(refs)
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    centers = current_centroids(board)
    audit = []
    for row in cpl:
        ref = row['Designator']
        fp = footprints[ref]
        x, y = centers.get(ref, (fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6))
        assert abs(float(row['Mid X']) - x) < 0.00011, ref
        assert abs(float(row['Mid Y']) + y) < 0.00011, ref
        angle = (fp.GetOrientationDegrees() + ROTATION_OFFSETS.get(ref, 0)) % 360
        assert abs(float(row['Rotation']) - angle) < 0.051, ref
        assert row['Layer'] == ('Bottom' if fp.IsFlipped() else 'Top'), ref
        audit.append(dict(reference=ref, board_centroid_mm=[x, y], rotation=angle))
    drc = json.loads((exports / 'jlcpcb-drc.json').read_text())
    for key in ['violations', 'unconnected_items', 'schematic_parity']:
        assert not drc.get(key), key
    erc = json.loads((exports / 'erc.json').read_text())
    assert not any(sheet['violations'] for sheet in erc['sheets'])
    validation = json.loads((exports / 'jlcpcb-validation.json').read_text())
    assert validation['revision'] == revision
    assert validation['jlcpcb_bom_part_quantity'] == len(refs)
    assert not validation['pin_pad_mismatches']
    board_hash = hashlib.sha256((ROOT / 'pi5_corona_hv.kicad_pcb').read_bytes()).hexdigest()
    fab = json.loads((exports / 'manufacturing-archive-validation.json').read_text())
    assert fab['board_sha256'] == board_hash
    with zipfile.ZipFile(exports / 'jlcpcb-gerbers.zip') as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(fab['files'])
        for name, digest in fab['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    proc = read('procurement-bom.csv')
    external = [row for row in proc if row['DNP'] == 'No' and row['Procurement Status'] in
                ['EXTERNAL_SOURCE', 'DIRECT_PROCUREMENT']]
    files = {'jlcpcb-gerbers.zip': 'gerbers.zip', 'jlcpcb-bom.csv': 'bom.csv',
             'jlcpcb-cpl.csv': 'cpl.csv', 'procurement-bom.csv': 'complete-procurement-bom.csv',
             'procurement-exceptions.csv': 'procurement-exceptions.csv',
             'jlcpcb-drc.json': 'drc.json', 'erc.json': 'erc.json',
             'jlcpcb-validation.json': 'bom-validation.json',
             'manufacturing-archive-validation.json': 'gerber-validation.json',
             'stock-substitution-review.json': 'stock-substitution-review.json',
             'stock-substitution-review.md': 'stock-substitution-review.md'}
    if (exports / 'd51-substitution-review.json').exists():
        files['d51-substitution-review.json'] = 'd51-substitution-review.json'
    if (exports / 'hv-warning-silkscreen-review.json').exists():
        files['hv-warning-silkscreen-review.json'] = 'hv-warning-silkscreen-review.json'
    for source, dest in files.items():
        shutil.copyfile(exports / source, out / dest)
    if (exports / 'hv-warning-silkscreen-review.json').exists():
        for side in ['front', 'back']:
            for ext in ['png', 'svg']:
                name = f'hv-warning-{side}.{ext}'
                shutil.copyfile(ROOT / 'renders' / name, out / name)
    shutil.copyfile(ROOT / 'procurement/accepted-stock-parts-2026-10-19.json',
                    out / 'accepted-parts-stock-evidence.json')
    with (out / 'manual-external-parts.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(proc[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(external)
    (out / 'centroid-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    external_qty = sum(int(row['Quantity']) for row in external)
    (out / 'README.md').write_text(f'''# JLCPCB exports — {revision}

Large bold DANGER HIGH VOLTAGE / stored-charge warnings and two lightning
triangles are on each silkscreen layer. Back markings read from the underside.
Front/back previews and silkscreen validation are included.

Canonical working-design exports generated with KiCad {fab['kicad_version']}.
Upload gerbers.zip for the two-layer, 1.6 mm PCB. It contains copper, mask,
silkscreen, paste, outline, and separate metric PTH/NPTH drill files.
Upload bom.csv and cpl.csv for assembly: {len(refs)} components / {len(bom)} BOM rows.
CPL coordinates use mm, X right and Y up from KiCad absolute origin;
negative Y values are intentional. Rotations are counterclockwise with existing
JLC library offsets. Review placement/orientation in the JLCPCB assembly preview.

Accepted substitutions: C100–C111 = C249245, R20–R29 = C2095568 (5%).
D51 now uses hongjiacheng SMBJ22A / C49066946. Its current positive stock
evidence and metadata-only geometry check are in d51-substitution-review.json.
Dated stock evidence and electrical/footprint review are included; stock is not reserved.
manual-external-parts.csv contains {external_qty} required externally sourced
component(s): T1. C63/R64 remain DNP; MP1 is a mechanical reference;
copper-only terminations and test pads require no purchased component.
THT/manual assembly service and component stock must be confirmed at order.

Zero ERC/DRC violations, opens and schematic parity issues; 13 connectivity
audits pass. Exact BOM/CPL reference and centroid correspondence and Gerber
archive payload hashes were validated. Copper/drills/placements/nets and DNP
states are unchanged by the substitutions. Capacitor drawings/courtyard and
procurement metadata were updated; its prior generic 3D model was removed.

RELEASE HOLD: existing HV insulation and arc qualification remain open.
Capacitor height, lead tolerances and pulse/bias behavior remain unqualified.
The unrelated R14/C18 catalog-ID mismatches remain unresolved. The old
D51 zero-quantity hold is superseded by the accepted C49066946 substitution.
stock-substitution-review describes N-layout-15 before the D51 change; its
old D51 stock warning is superseded by d51-substitution-review.json.
Dated procurement evidence is retained under procurement/ in the working project.
These files are manufacturing exports, not a qualified 15 kV production release.
''')
    manifest = dict(revision=revision, kicad_version=fab['kicad_version'],
                    base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                                        cwd=ROOT, text=True).strip(),
                    source_state='canonical working design; source SHA-256 identifies the exact board', board_sha256=board_hash,
                    bom_rows=len(bom), catalog_components=len(refs),
                    external_components=external_qty, production_release=False,
                    files={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(out.iterdir()) if p.is_file() and p.name != 'manifest.json'})
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    dest = exports / ('jlcpcb-' + revision + '-package.zip')
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.iterdir()):
            archive.write(path, out.name + '/' + path.name)
    with zipfile.ZipFile(dest) as archive:
        assert archive.testzip() is None
    print(f'Validated {len(refs)} placements / {len(bom)} BOM rows; {external_qty} external parts.')
    print(dest)


if __name__ == '__main__':
    package()
