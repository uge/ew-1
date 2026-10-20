#!/usr/bin/env python3
"""Generate both manufacturing archives from a fresh KiCad 10 staging directory."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[2]

def regenerate():
    version=subprocess.check_output(['kicad-cli','version'],text=True).strip()
    if not version.startswith('10.'):
        raise RuntimeError('KiCad 10 required')
    board=ROOT/'pi5_corona_hv.kicad_pcb'
    with tempfile.TemporaryDirectory(prefix='corona-fab-') as temp:
        stage=Path(temp)
        subprocess.run(['kicad-cli','pcb','export','gerbers','--check-zones','--layers',
            'F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,F.Paste,B.Paste,Edge.Cuts',
            '-o',str(stage)+'/',str(board)],check=True)
        subprocess.run(['kicad-cli','pcb','export','drill','--excellon-separate-th',
            '--drill-origin','absolute','--excellon-units','mm','-o',str(stage)+'/',str(board)],check=True)
        drills=sorted(p.name for p in stage.glob('*.drl'))
        if drills != ['pi5_corona_hv-NPTH.drl','pi5_corona_hv-PTH.drl']:
            raise RuntimeError(f'Unexpected drill set: {drills}')
        for filename,plating in [('pi5_corona_hv-PTH.drl','Plated,1,2,PTH'),
                                  ('pi5_corona_hv-NPTH.drl','NonPlated,1,2,NPTH')]:
            if plating not in (stage/filename).read_text():
                raise RuntimeError(f'Unexpected plating header: {filename}')
        paths=sorted(p for p in stage.iterdir() if p.is_file())
        manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        for name in ['jlcpcb-gerbers.zip']:
            dest=ROOT/'exports'/name
            temporary=dest.with_suffix('.zip.tmp')
            with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
                for p in paths:
                    archive.write(p,p.name)
            with zipfile.ZipFile(temporary) as archive:
                if archive.testzip() or sorted(n for n in archive.namelist() if n.endswith('.drl')) != drills:
                    raise RuntimeError('Archive validation failed')
                for n,digest in manifest.items():
                    if hashlib.sha256(archive.read(n)).hexdigest()!=digest:
                        raise RuntimeError('Archive payload mismatch')
            temporary.replace(dest)
        report=dict(kicad_version=version,board_sha256=hashlib.sha256(board.read_bytes()).hexdigest(),
            drills=drills,files=manifest,status='ARCHIVE_INTEGRITY_VERIFIED_INSULATION_RELEASE_HOLD',
            archives={n:hashlib.sha256((ROOT/'exports'/n).read_bytes()).hexdigest()
                      for n in ['jlcpcb-gerbers.zip']})
        (ROOT/'exports/manufacturing-archive-validation.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))

if __name__=='__main__':
    regenerate()
