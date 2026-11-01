# Stage 6 plan: driver enable (GPIO24), no PWM (reduced, rev 3)

Status: **rev 3, 2026-11-01. User selected option 1: reduced stage 6, no injection.**
The injected OV-trip test (6.A) and 6.C2 are dropped as impractical on this board:
no clip point, no adjustable supply. **The hardware OV trip (U4/U11/D90/D91/Q2) stays
UNVERIFIED** and is recorded in AUDIT.md. Stage 7 runs under the limits below. Rev 2
added the DRV8876 facts (`procurement/DRV8876.pdf`, SLVSDS7B).
Live log:
[BRINGUP.md](BRINGUP.md). Stage 5 (bulk enable at 5/9 V) passed 2026-11-01 10:57.

## Goal and scope

Stage 6 proves three things before any switching:
- the hardware overvoltage trip works (U4 → U11 → D90 latch → Q2 → DRV_nSLEEP,
  cleared by D91 / GPIO24 low);
- the DRV8876 can be woken with VM present and **stays idle with IN1 = IN2 = 0**;
- every shutdown path leaves the driver asleep.

**Out of scope:** any toggling of GPIO18/19 (that is stage 7), any HV generation,
and any bridge voltage above 5 V.

## Relevant circuit (from `layout/schematic-connectivity.json`)

```
GPIO24 ─ DRV_SLEEP_CMD ─┬─ K1 6→5 ─ DRV_nSLEEP_RLY ─ R105 1k ─ DRV_nSLEEP (U2.3) ─┬─ R5 10k → GND
                        │                                                          └─ Q2 AO3400A drain (OV trip pulls low)
                        └─ D91 cathode;  D91 anode = OV_SENSE   (GPIO24 low clamps OV_SENSE ≈ 0.6 V → trip disabled/cleared)

HV_OUT ─ R30…R39 (1 GΩ) ─ HV_SENSE_RAW (C13 / R8+R9 164k / R110) ─ R110 10k ─ U4 TLV9001 buffer ─ HV_SENSE_BUF
HV_SENSE_BUF ─ R7 1k ─ D1 clamp ─ HV_SENSE_ADC → ADS1115 AIN0
HV_SENSE_BUF ─ R100 56.2k ─ OV_SENSE ─ R101 82k → GND ;  OV_REF = 3V3 × R103/(R102+R103) = 1.65 V
U11 TLV7031: OV_SENSE > OV_REF → HV_OV_TRIP high → Q2 on (DRV_nSLEEP low), R106 1k → GPIO26
Latch: HV_OV_TRIP ─ D90 (A→K) ─ OV_LATCH ─ R104 10k ─ OV_SENSE

U2 DRV8876: PMODE (pin 5) = 3V3, i.e. PWM (IN/IN) mode. IN1 = GPIO18, IN2 = GPIO19. VM = HV_BRIDGE.
OUT1 = DRV_A ─ C11 120 nF 630 V ─ T1.1 (PRI_A);  OUT2 = DRV_B ─ T1.5.  ITRIP ≈ 2.2 A (R61 1.5 kΩ).
```

**DRV8876 facts** (datasheet SLVSDS7B; pin numbers are the PWP package):

| Item | Datasheet | This board | Consequence |
|---|---|---|---|
| Control mode | PMODE pin **16**: high = PWM mode | U2.16 = 3V3 | IN1 = IN2 = 0 → **coast (Hi-Z)**; 10/01 → drive; 11 → brake (Table 4) |
| VREF | pin 5 | U2.5 = 3V3 | ITRIP = 3.3 V / (1.5 kΩ × 1000 µA/A) = 2.2 A |
| IMODE | 62 kΩ to GND = cycle-by-cycle chopping, **OCP outputs latched off**, nFAULT on chopping **and** overcurrent (Table 6) | R62 62 kΩ | In stage 7, nFAULT pulses during current chopping are *not* faults. OCP (3.5–5.5 A) latches until nSLEEP cycles |
| VM range | 4.5–37 V | bridge 4.88 V at 5 V, 8.73 V at 9 V | |
| VM UVLO | falling 4.2–4.5 V, +100 mV hysteresis; nFAULT low, outputs disabled | | **At a 5 V contract the bridge (4.88 V) has only ~0.3 V of worst-case margin, so 6.B/6.C run at the 9 V contract** |
| tWAKE / tSLEEP | ≤ 1 ms each | | Wait ≥ 2 ms after nSLEEP edges before judging nFAULT |
| Logic inputs | 0–5.5 V; "inputs can be powered before VM" | nSLEEP ≈ 3.0 V via R105/R5 | 6.A (GPIO24 high, VM = 0) is within ratings |
| Internal pulldowns | IN1, IN2, nSLEEP | plus R5 10 kΩ | Floating Pi pins default to coast/sleep |

**Trip point:**
- HV_SENSE_BUF must exceed 1.65 × 138.2 / 82 = **2.781 V**;
- with the 1 GΩ / 164 kΩ divider that is **16.96 kV** nominal HV_OUT;
- AIN0 reads HV_SENSE_BUF through R7, so the ADC shows ≈ 2.78 V at the trip.

## Preconditions (all stages 6.x)

| Item | Requirement |
|---|---|
| Stages 0–5 | Passed (5.0 inspection was skipped; record it if done now) |
| Supply | 65 W SPR on J3, explicit **5 V** contract. No requests above 5 V in stage 6 |
| Lid | Closed (GPIO23 = 1) unless a step says otherwise. It is the enclosure interlock |
| HV output J60/J61 | Unchanged/open, enclosure closed, nothing within reach of HV nodes. Stage 6 must not create HV, but a PWM-pin glitch with the driver awake would |
| GPIO18/19 | **a3 PWM, level 0, PWM channels not exported.** Checked before every GPIO24 high, and abort if either level reads 1 |
| Polarity | No PWM channel left `inversed` (it idles high) |
| Abort | **Software safe-stop:** GPIO24 low → disable PWM → polarity normal → GPIO25 low. **Physical:** open the lid, unplug J3 |

## 6.A′ No-injection checks: bridge OFF (GPIO25 low)

The original injected-trip test (resistor bracket into HV_SENSE_RAW) is **not run**;
see the rev 2 text in git history. What can still be checked without touching the board:

| Step | Action | Expect |
|---|---|---|
| 6.A′.1 | GPIO25 low, PWM pins low and unexported. Raise GPIO24 for 5 s at 20 Hz | **GPIO26 stays 0**: no false trip, so D91 is not reversed. AIN0 ≈ 0. DRV_nFAULT 1 (VM = 0) |
| 6.A′.2 | GPIO24 low | Idle |

**Not verified by stage 6:** the trip at HV_SENSE_BUF = 2.781 V (16.96 kV), the D90
latch, the D91 clear, Q2 → DRV_nSLEEP, and the AIN0 → kV scale at the trip point.

## 6.B Driver wake with VM present, IN1 = IN2 = 0

| Step | Action | Expect / abort |
|---|---|---|
| 6.B.1 | Pre-checks. With GPIO25 low, request the **9 V** contract, then GPIO25 high | Bridge 8.73 V, as in 5.5 (UVLO margin ≫ 0.3 V) |
| 6.B.2 | Re-check GPIO18/19 = 0, then GPIO24 high | **DRV_nFAULT stays 1.** Bridge, VBUS and 3V3 unchanged. AIN0 ≈ 0, AIN1 ≈ offset. Outputs coast (Hi-Z), so no T1 drive |
| 6.B.3 | Hold 30 s, sampling at 10 Hz | No change. Abort (safe-stop) on: nFAULT → 0, EFUSE_FLT → 0, GPIO26 → 1, AIN0 > 0.05 V, bridge or VBUS out of band, GPIO18/19 ≠ 0 |
| 6.B.4 | Safe-stop in order: GPIO24 low, then GPIO25 low. Then request 5 V (the step-down rule) | Bridge decays below 0.1 V in about 3 s; ends at the 5 V contract |

## 6.C Shutdown paths with the driver awake (VM present)

| Step | Action | Expect |
|---|---|---|
| 6.C.1 | 9 V contract. GPIO25 high, GPIO24 high. **User opens one lid switch** | GPIO23 → 0. K1 releases both gates: R5 pulls DRV_nSLEEP low and BULK_EN opens, so the bridge decays. nFAULT stays 1. The script then sets GPIO24/25 low before the switch is reclosed |
| 6.C.3 | GPIO25 high, GPIO24 high, run the software safe-stop routine (as it will exist in firmware) | Order respected; the bridge decays; every input idle at the end |

## Logging and records

- One script, `host/stage6.py` with subcommands `a` / `b` / `c1` / `c3`, in the
  same style as `stage5_*.py`:
  - armed, with preconditions checked;
  - 10 Hz CSV on ew-1;
  - auto safe-stop on any abort condition;
  - GPIO24 then GPIO25 forced low on exit.
- 6.C1 prompts the user to open one lid switch, waiting up to 60 s.
- Results go into BRINGUP.md the same session (stage table, snapshot, log).

## Stage 7 limits while the hardware OV trip is unverified (option 1)

Firmware is the **only** overvoltage protection until the trip is tested.

| Limit | Value |
|---|---|
| Bridge supply | **5 V contract only** (bridge ≈ 4.9 V), so no 9–20 V drive |
| Software HV cutoff | Safe-stop when **AIN0 > 0.50 V** (≈ 3.0 kV nominal; the hardware trip is 2.78 V). Checked every sample at ≥ 100 Hz during PWM |
| Bursts | Short, bounded bursts (length set in the stage 7 plan) with the safe-stop on exit |
| Enclosure | Lid closed (interlock), HV output terminated per the stage 7 plan |
| Lifting the limits | Only after the trip is verified: temporary fly lead on HV_SENSE_RAW, or a board revision with a test point / self-test injection |

## Open items before stage 7 (PWM / first HV)

- The HV output termination and load at J60/J61, the HV probe, the grounding
  stick and the discharge-verification procedure are still undefined.
  Simulated discharge is about 0.93 s nominal and > 5 s with one open
  bleeder, which is model-only.
- Drive frequency/duty start point (shutdown model used 68 kHz) and the
  burst-length limits need defining.
- A software OV threshold well below the 16.96 kV hardware trip needs choosing.
- DRV8876 datasheet added as `procurement/DRV8876.pdf` (2026-11-01). The
  facts are in the table above. During stage 7 PWM, nFAULT pulses on
  current chopping (IMODE = 62 kΩ); firmware must not treat those as faults.
- Every IN1/IN2 edge with nSLEEP high and VM present sends one pulse into
  T1/C11. Even a "static" level change is a drive event.
- The 5.0 visual inspection (D50/D51/C60/C70) is still undone. They behave
  correctly in-circuit at 5 and 9 V.
