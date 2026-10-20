# Pi 5 Corona HV supply

The canonical working design is **N-layout-17-hv-warnings**. Open
[pi5_corona_hv.kicad_pro](hardware/pi5_corona_hat_direct/pi5_corona_hv.kicad_pro)
in **KiCad 10**. This is the active editable project, including the accepted
component substitutions, completed routing and front/back high-voltage warnings.

- [Project guide](hardware/pi5_corona_hat_direct/README.md)
- [Current JLCPCB package](hardware/pi5_corona_hat_direct/exports/jlcpcb-N-layout-17-hv-warnings-package.zip)
- [Front preview](hardware/pi5_corona_hat_direct/renders/hv-warning-front.png) / [back preview](hardware/pi5_corona_hat_direct/renders/hv-warning-back.png)
- [Design status and unresolved issues](hardware/pi5_corona_hat_direct/AUDIT.md)
- [Export and validation commands](hardware/pi5_corona_hat_direct/layout/README.md)

Old project copies, trial boards, revision snapshots and stale generated outputs
have been removed from the working tree. Earlier tracked versions remain in Git
history. Historical design notes under `docs/` are reference material; the project
guide and native files above take precedence. The `doc` link is an alias of `docs`.

The working version is not a qualified 15 kV production release. Native ERC/DRC
checks do not replace the outstanding insulation, surge and component qualification.
