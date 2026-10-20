# Procurement for the working design

`part-assignments.json` and the native hidden fields define the current selections.
The working design is N-layout-17-hv-warnings; the part-assignment revision records
the most recent procurement change. Dated catalog responses and manufacturer PDFs
are evidence for those selections, not alternate projects or reserved inventory.

The [matching BOM](../exports/jlcpcb-bom.csv) and [CPL](../exports/jlcpcb-cpl.csv)
cover 141 populated components in 51 BOM rows. The [complete BOM](../exports/procurement-bom.csv)
includes DNP items and copper-only features. [Exceptions](../exports/procurement-exceptions.csv)
record unavailable/unassigned procurement items; identity/qualification holds are
also recorded in [AUDIT.md](../AUDIT.md).

| References | Current selection | JLCPCB |
|---|---|---|
| C100–C111 | STE A12B1D102KN0B0S0N0, 1 nF / 6 kV / Y5P / 10%, 10 mm pitch | C249245 |
| R20–R29 | Bourns CHV2512-JW-106ELF, 10 MΩ / 5% / 1 W / 3 kV / 2512 | C2095568 |
| D51 | hongjiacheng SMBJ22A, unidirectional SMB | C49066946 |
| D10–D21 | Sunmate 2CL75, 16 kV / 5 mA, formed 26 mm pitch | C424512 |
| R30–R39, R140–R163 | Bourns CHV2512-JW-107ELF, 100 MΩ / 5% / 3 kV | C2089706 |
| S3–S6 | DEALON TK-0013-R, populated COM/NO interlocks | C19724218 |
| T1 | Coilcraft FL2015-4LD | External source |

The user accepted the 5% ballast tolerance. Initial ballast range is 95–105 MΩ;
see the [substitution review](../exports/stock-substitution-review.md) for calculations
and remaining mechanical/pulse qualification. D51's replacement supersedes its
old stock shortage; see [D51 review](../exports/d51-substitution-review.json).

C63 and R64 are intentionally DNP optional primary snubber parts. T1 is the only
required purchased part outside the matching BOM. J60/J61 and J62–J69 are copper
solder-wire features; TP50 is a copper test pad. MP1 is a board-only Pi model and
is excluded from assembly. Never mark unavailable or THT parts DNP for convenience.

R14/C18 catalog-ID/MPN mismatches remain unresolved as detailed in AUDIT.md.
Stock and assembly-service eligibility must be checked again at order time.
Switch contact mapping/ratings, capacitor height/leads/bias/pulse behavior, diode
charging pulses and transformer/insulation operation remain qualification items.
