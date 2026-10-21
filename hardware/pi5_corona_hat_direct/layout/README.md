# Validate and export the working design

The working board is `../pi5_corona_hv.kicad_pcb`, N-layout-17-hv-warnings.
`optimized-placement.json` records accepted poses; `schematic-connectivity.json`
is refreshed from a native netlist. Do not recreate the PCB from a board generator:
that discards accepted routing and warning graphics. Obsolete generators and
routing trials are no longer part of this working tree.

From the repository root, with KiCad 10, Ruby and `/usr/bin/python3`/pcbnew installed:

```sh
/usr/bin/python3 hardware/pi5_corona_hat_direct/layout/validation/refresh_exports.py
```

This checks KiCad version, exports a fresh native netlist, refreshes connectivity,
runs the 17 net audits and native ERC/DRC including parity, exports procurement
BOMs/CPL and fresh Gerbers with separate PTH/NPTH drills, then validates and
packages the current JLCPCB files. It never saves or reroutes the native design.
The final package manifest identifies its source PCB by SHA-256.

Current outputs are under `../exports/`; only the current versioned package is
retained. Component substitutions and dated procurement evidence are kept because
they explain current choices; they are not alternative working boards.

The front/back SVG/PNG previews describe the current warning graphics. After a
future graphics/placement change, regenerate previews with `kicad-cli pcb export svg`
using F.Silkscreen/F.Fab/F.Mask/Edge.Cuts and B.Silkscreen/B.Mask/Edge.Cuts respectively.
Use `--mirror` for the back preview. Inkscape can render the SVG files to PNG.

Additional insulation and simulation checks are described in [validation/README.md](validation/README.md).
Passing native DRC does not clear the qualification holds in [../AUDIT.md](../AUDIT.md).
