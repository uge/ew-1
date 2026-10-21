# Canonical working design

Use KiCad 10 for this project and every generated KiCad artifact. Confirm
`kicad-cli version` is 10.x before exporting. The single working design is
N-layout-17-hv-warnings: `pi5_corona_hv.kicad_pro`, its PCB, root schematic and
five adjacent sheets. `README.md`, `AUDIT.md` and `exports/working-version.json`
are current; older tracked versions live in Git history, not duplicate directories.
Do not regenerate a board from placements: preserve accepted routes and graphics.

# Supply and ground semantics

Use actual KiCad power symbols for supply/ground rails, including named custom
symbols when needed; labels are not replacements. Preserve net names/scope and
raw/fused/protected/switched rail distinctions. Do not merge HV_RETURN with GND.
PWR_FLAG declares a source, not a replacement power symbol. Keep power pin
numbers hidden, text clear, and flags on short extensions. Run ERC and compare
native connectivity after symbol conversions.

# Procurement and accepted parts

`procurement/part-assignments.json` and dated evidence govern selected parts.
Keep hidden LCSC, LCSC Part, JLCPCB Part #, Manufacturer and MPN fields consistent
on placed symbols and native footprints. Check ratings, package and pad numbers;
a catalog ID alone is insufficient. Do not invent IDs. Regenerate complete BOM,
matching BOM/CPL and exceptions after changes. Never mark an unavailable/THT part DNP.

C100–C111: STE A12B1D102KN0B0S0N0 / C249245, 1 nF / 6 kV / Y5P / 10%,
ionic_thrust_hv:STE_A12B1D102K_P10.0mm. Preserve corrected body/courtyard and
original pad/drill geometry. R20–R29: Bourns CHV2512-JW-106ELF / C2095568,
10 MΩ / 5% / 1 W / 3 kV / 2512; the user accepted 5%. D51: hongjiacheng
SMBJ22A / C49066946, unidirectional SMB; cathode pad 1, existing nets/pose.
T1 Coilcraft FL2015-4LD remains externally sourced. J60/J61 and J62–J69 are
solder-wire copper terminations, not purchased generic connectors. C63/R64
are schematic DNP. MP1 is board-only, DNP, locked, padless, excluded from BOM/POS.
Current matching BOM has 159 components / 53 rows. R14 is C25819 (0603WAF4702T5E, 47 kΩ;
never C25816, which is 383 kΩ). C18 is C15849 / CL10A105KB8NNNC (1 µF 50 V X5R).

R30–R39 and R140–R163 use Bourns CHV2512-JW-107ELF / C2089706,
100 MΩ / 5% / 3 kV / 2512. Preserve ten divider parts and two parts per
200 MΩ bleeder bank; never bypass R39. Recalculate voltage sharing/discharge
when changing these banks; calibrate HV sensing. D10–D21 use Sunmate 2CL75 /
C424512, 16 kV, 5 mA average, 0.5 A nonrepetitive surge, trr ≤100 ns and
Cj 1 pF under datasheet test conditions. Use Sunmate_2CL75_D3_L12_P26,
26 mm formed pitch, 0.9 mm drills; pad 1 cathode/band, pad 2 anode.
Confirm stock for new selections and validate charging pulses, not just output current.

# Circuit constraints

U9 isolates bulk capacitance until GPIO25/BULK_CMD is gated by K1 into BULK_EN
after a PD contract. Preserve external default-off pulldowns and the <10 µF attach /
<100 µF post-contract limits. Recalculate tolerances, bypass and parasitic reserve
when changing a USB capacitor/power path. Current budgets: 9.10242 µF attach,
97.34662 µF negotiated. C82/C83 are Pi-powered; C73 is 1 µF / 50 V / 10%.
Do not restore 220 µF without a validated inrush design. Confirm effective LDO
output capacitance ≥0.5 µF at bias/temperature.

U7 HUSB238A pin 5 is Pi 3V3: default 5 V USB attach, 5–20 V programmable at
I²C 0x42. R73 1.2 kΩ / C22765 sets eFuse 2.78 A, above U2 current limit
2.20 A from R61 1.5 kΩ / C22843. K1 G6K-2F-Y DC3 is regulated at 3 V via
U10 TPS7A0230. No bridge/USB power on its coil or logic contacts. K1 contacts
3/4 gate BULK_CMD/BULK_EN; 6/5 gate DRV_SLEEP_CMD/DRV_nSLEEP_RLY, then R105 1 kΩ
to DRV_nSLEEP. GPIO23 via R92 senses the switched coil feed, not proven contact
state; keep GPIO24 separate.

Hardware HV overvoltage trip (independent of firmware): U11 TLV7031DBVR / C2869832
compares HV_SENSE_BUF (U4 output, not the ADC node) × R101/(R100+R101) =
82k/(56.2k 0.1%+82k) against OV_REF = 3V3 × R103/(R102+R103) = 1.65 V; trip is
16.96 kV nominal HV_OUT. D90 + R104 latch the trip; D91 clears it only while
DRV_SLEEP_CMD is low. Q2 AO3400A / C20917 pulls DRV_nSLEEP low; R105 limits GPIO
current. R106 reports the latched trip on GPIO26 (J2.37, HV_OV_TRIP_GPIO).
The input is filtered by the 164 kΩ·C13 divider pole (~16 ms), so it limits
steady-state overvoltage, not fast overshoot. Recalculate the trip point if the
HV divider, R100–R103 or the 3V3 rail changes; never bypass Q2/R105.

U4 IN+ is fed through R110 10 kΩ from HV_SENSE_RAW (C13/R8/R39 node) to limit arc-transient
current into the op-amp input; no external clamp, to avoid leakage error on the 1 GΩ divider.

Firmware telemetry: DRV_nFAULT (global label; R63 pull-up, TP50) → GPIO5 (J2.29).
U9 FLT → EFUSE_FLT, R107 10 kΩ pull-up → GPIO6 (J2.31). HV_BRIDGE/11 via R108 100 kΩ /
R109 10 kΩ / C92 100 nF (sheet 02, where the sheet-local HV_BRIDGE symbol lives) →
global BRIDGE_VMON → ADS1115 AIN3; 35.5 V D51 clamp reads 3.23 V. C72 (DVDT) sits
left of U9 at (76.3,141.5)/180° to free U9's left-side escapes.

T1 manufacturer SMT Package 1 numbering is counterclockwise: primary 1/5,
unused CT 3, unused feedback 2/4, secondary 8/9. Guards 6/GND, 7/SEC_A,
10/GND; T1.6/9/10 remain GND, J61–R90.1 remains HV_RETURN. Do not bypass R90
or route generator circulation through the external-return shunt. R90 remains
CRCW120610K0FKEAHP, 10 kΩ / 0.75 W pulse-rated. D5 SMBJ15A pad 1 cathode
is HV_RETURN; pad 2 anode GND. R91 is 10 kΩ ahead of the ADC clamps.

U8/J51/C80/C81 belong to the illumination mini board; J50 belongs to the host.
Both connectors: 1 GND, 2 Pi 3V3, 3 SDA, 4 SCL; only those nets cross its neck.
No LEDs or parallel I²C pull-ups without a low-light/bus-loading review.
S3–S6 DEALON TK-0013-R / C19724218 stay populated, normally-open in series:
COIL_3V → S3 → LID_INT → S4 → LID_2 → S5 → LID_3 → S6 → RELAY_COIL_POS.
Custom pads 1 COM, 2 NO, 3 NC (unused). Mini connectors J62/J63/J66/J67
pair with host J64/J65/J68/J69. Only corresponding COM/NO nets cross each neck;
never bypass a switch in attached or detached topology. Verify actual contact map/load.

# Geometry, routing and markings

Two-layer, 1.6 mm board: carrier 196 × 120 mm, x50–246/y51–171;
five left mini boards make the overall envelope 231 × 120 mm. Accepted
footprint/reference poses are in layout/optimized-placement.json. J3 stays
(55.8,144.4), -90°. J2 stays F.Cu (54.23,106.63), 180°. MP1 stays
(3,115), 90°, model rotation (180,0,0), offset (0,0,13.306) mm; official
Pi STEP and MIT license stay included. The 12 mm standoff remains provisional;
do not hide connector interference by moving the model or changing selections.
H1/H2 at (55.5,111.5)/(55.5,53.5), H3 (105,55), H4 (55,166);
H5/H6 are omitted. Preserve break-off board outlines and neck topology.

Preserve custom HV rules: 4 mm stage spacing, 10 mm highest-voltage clearance,
10 mm highest-voltage edge/NPTH setback, and the voltage-tiered "HV stage N mm to LV"
rules (≤2.5 kV 4 mm, ≤5 kV 6 mm, ≤7.5 kV 8 mm, >7.5 kV 10 mm to any non-HV net).
Add any new HV node to the tier matching its peak voltage. Narrow rated-part/series-node exceptions
are not universal HV exemptions. No pours on either side in HV; LV GND pour
x52–101, both-layer HV no-pour region from x102. Native DRC is not HV certification.
Preserve 16 mm cell pitch, 8 mm inner/12 mm final diode offsets and 11.75 mm
R30-to-R31 spacing. Diodes D10–D21 are staggered vertically: even refs at y=95.75, odd
refs at y=102.25 (±3.25 mm), D21 at x=223.4, so adjacent stage pads are ≥7.63 mm apart
(IPC-2221 B4 at 2.5 kV). The S-bleeder row R142/R143/R150/R151/R158/R159 is at y=147.4.
The warning band sits between the lowered diode pads and the S caps (DANGER text 55%,
second line 75%, triangles 70% of the original size); C101–C111 references are below the caps. Pumping-column bleeders R140–R161 form one row at y=63 on an
8 mm pitch (adjacent pads share a net); keep every HV_STAGE pad ≥10 mm from Edge.Cuts
(enforced by the "HV_STAGE to board edge" rule). Recalculate insulation/fit after compaction.

Keep D5 (132.5,158)/90°, R90 (132.5,162.95)/180°, J61 (126,156).
J61→D5 is 8.219 mm and J61→R90 11.625 mm on F.Cu without vias.
Preserve 1.5 mm return/GND trunks, parallel GND vias at (127.5,150.5) and
(128.5,150.5), and separate sense pickup at R90.1. LV trunk targets:
1.5 mm USB/bridge supply, 1.0 mm bridge outputs, 0.6 mm 3V3, 0.5 mm coil;
local narrower escapes remain. Preserve staggered U7 fanout and U2 charge pump routes.

Keep large bold DANGER HIGH VOLTAGE / DO NOT TOUCH - STORED CHARGE text
and two vector lightning triangles on each silk layer. Back text is mirrored
for underside viewing. Preserve the open warning band and reference clearance.

# Validation and saves

Use layout/validation/refresh_exports.py for native netlist, 17 connectivity audits,
ERC, DRC/parity, BOM/CPL and Gerbers/package. Zero DRC violations with opens is
still a hold. Review AUDIT.md before any release claim. The pcbnew legacy save API
can overwrite project settings: preserve/restore .kicad_pro and custom rules around
PCB saves; never replace them with defaults. Do not include unrelated root index.html
in hardware commits. Keep the working tree free of old version folders and trial boards.
