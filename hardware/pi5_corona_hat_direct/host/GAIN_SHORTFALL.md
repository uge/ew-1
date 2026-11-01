# Findings note: HV gain shortfall (stage 7 bring-up)

**Date:** 2026-11-01. **Board:** N-layout-17-hv-warnings, bench host ew-1.
**Status:** measured findings plus working hypotheses. Nothing here has been
verified with a scope or an HV probe yet.
**Raw data:** `host/data/stage7_*.csv`. **Run log:** [BRINGUP.md](BRINGUP.md) stage 7.

## Summary

At the only bridge voltage allowed so far (≈ 4.83 V under drive, 5 V PD contract),
the HV stage produces **at most ≈ 0.36 kV** on HV_OUT. The design model predicts
**13.3 kV** open-circuit. Two things differ from the design:

1. **The response peaks at ≈ 26 and ≈ 32 kHz and falls to ~0 by 50 kHz.** The
   design drives at **68 kHz**, the calculated C11 + L_pri series resonance
   (69.3 kHz). There the board produces almost nothing.
2. **Voltage transfer is about 10× below a simple series-tank estimate, even at the
   measured peak.** The board isn't power-limited: the bridge sags only ~70 mV,
   nFAULT never asserted, and there was no current-limit activity.

Extrapolating linearly, the best measured point (≈ 74 V of HV_OUT per volt of
bridge) gives only **≈ 1.4–1.5 kV at a 20 V bridge**, the U9/F1 practical ceiling.
Meeting the design target needs a change to the drive/transformer/multiplier design,
not just a higher supply. The extrapolation is uncertain, because the multiplier
diodes make the transfer nonlinear (H3).

## Measurements (HV_OUT ≈ AIN0 × 6.10 kV/V, nominal and uncalibrated, ±10%)

Conditions: 5 V contract, bridge 4.83 V under drive, 1 s bursts, J60 open and
insulated, lid closed. AIN0 is the median over each burst.

**Single-ended drive** (IN1 = PWM 50%, IN2 = 0):

| f (kHz) | 20 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 | 30 | 31 | **32** | 33 | 34 | 35 | 40 | 45 | 50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AIN0 (mV) | 7.5 | 3.1 | 4.9 | 13.2 | 23.4 | 27.0 | 19.1 | 17.9 | 22.5 | 27.0 | 27.0 | **32.1** | 29.5 | 20.0 | 13.6 | 12.4 | 1.5 | 0.3 |
| ≈ HV_OUT (V) | 46 | 19 | 30 | 80 | 143 | 165 | 116 | 109 | 137 | 165 | 165 | **196** | 180 | 122 | 83 | 76 | 9 | 2 |

- 25 and 30 kHz repeat to within 0.3 mV across two sweeps 3 min apart.
- The 20 kHz point (7.5 mV) is higher than 22 kHz (3.1 mV), which hints at a
  further mode below 20 kHz. That range is outside the stage 7 software limits
  (20–50 kHz).

**Complementary drive** (IN1 = ch2 normal, IN2 = ch3 inversed, 50%) at 32 kHz:
AIN0 **55.6 mV median / 58.6 mV peak ≈ 340–357 V**, which is **1.74×** single-ended.

**Every burst:**
- AIN1 (return current) stayed at the 2 mV offset;
- nFAULT = 1, EFUSE_FLT = 1, OV trip 0;
- the bridge sagged 4.90 → 4.83 V, the same at every frequency, so input power
  is very low;
- after stop, HV_OUT fell below 61 V within 0.3 s.

## Expected vs measured

| | Design / estimate | Measured |
|---|---|---|
| Operating frequency | 68 kHz (C11 120 nF + L_pri 44 µH → 69.3 kHz) | Peaks at **26 and 32 kHz**; ~0 at 50 kHz |
| HV_OUT | 13.3 kV open circuit, from 1250 Vpk secondary (SPICE, `spice-multiplier-report.json` @ 8cedf38) | **0.36 kV** best (complementary, 32 kHz, 4.8 V bridge) |
| Implied secondary peak (HV_raw ≈ 1.1 × HV_OUT, ÷ 11.7 CW gain, ideal diodes) | 1250 V | **≈ 34 V** |
| Implied primary peak (÷ 50) | 25 V | **≈ 0.67 V**, against a **6.2 V** drive fundamental (4/π × 4.83 V) |
| Bridge power | Watts (design 0.43 W at the 50 µA corona point) | Bridge sag 70 mV, no chopping. Milliwatts |

The design and drive numbers (1250 Vpk secondary, the bridge voltage that produces
it) were never tied together in the model: the SPICE run drove the secondary
directly. **No modelled path from VM to 1250 Vpk exists in the repo.**

## Hypotheses (ranked)

**H1. The real tank isn't C11 + L_magnetizing. The secondary-side capacitance
reflected through 1:50 dominates.** *Most likely cause of the frequency shift.*
- Any capacitance on the secondary appears ×2500 on the primary. The CW input
  ladder (C100 1 nF, plus diode and winding capacitance) reflects to about
  **2.5 µF** whenever the diodes conduct. With 44 µH that alone resonates near
  **15 kHz**. Together with C11 and T1's leakage inductance (not in the Coilcraft
  datasheet), it forms a two-mode coupled system.
- That fits the **twin peaks at 26/32 kHz**, the hint of a mode below 20 kHz, and
  the collapse above 40 kHz, where the reflected capacitance shorts the drive.
- The 68 kHz design point came from treating T1 as a bare 44 µH inductor with an
  open secondary.

**H2. Heavy reflected loading at every frequency, so a low voltage transfer.**
- The same reflected capacitance also loads the primary, roughly 2 Ω at 32 kHz
  (Xc of 2.5 µF).
- The bridge's square-wave fundamental is divided across C11, the leakage
  inductance and that load, so only a fraction reaches the magnetizing branch.
- That fits ~0.67 V against 6.2 V at the primary.
- It doesn't explain why the bridge draws so little current. A capacitive load
  draws reactive current, which the bridge/eFuse ADCs wouldn't show and the DRV
  wouldn't flag below the 2.2 A ITRIP. **Measuring primary current (DRV8876
  IPROPI, ≈ 1.5 V/A across R61) would settle H1/H2.**

**H3. Multiplier diode threshold.**
- The 2CL75 is a stacked 16 kV diode, **VF ≤ 43 V at 5 mA**
  (`procurement/Sunmate_2CL75_C424512.pdf`). At µA currents the drop is lower but
  still likely several volts per diode, across 12 diodes, against a secondary of
  only ~34 Vpk.
- This would make the transfer strongly nonlinear: poor at low drive,
  proportionally better at high drive.
- **Partly contradicted:** doubling the drive amplitude (complementary) gave only
  1.74× output, where a pure threshold loss would give > 2×. The single-ended
  baseline isn't exactly half amplitude, though (the coast phase lets the tank
  ring), so this is inconclusive.
- The higher-bridge test settles it: if 9 V gives ≫ 1.9× the 5 V output, the
  threshold matters.

**H4. Wiring/pinout error at T1 (lower probability, cheap to rule out).**
- T1's pad numbering was corrected once already (commit eaf8b2d, counter-clockwise
  Package 1 numbering).
- A primary on only half the winding, or a secondary/guard mix-up, would change
  the ratio and the resonance.
- Check pin continuity against the datasheet schematic A (pri 1–5 via CT 3,
  sec 8–9 in our use).

**Ruled out as the main cause:**
- **AIN0 scale error:** uncalibrated, but ±10% can't explain ~30×. Return current
  and the OV comparator are consistent with low kV.
- **Divider/bleeder loading:** 1.1 GΩ at 357 V is 0.3 µA; the bleeders take µA at
  these voltages.
- **Driver limiting:** nFAULT never asserted, no chopping, and the bridge barely
  sagged.
- **PWM error:** the frequency was read back from sysfs, and the 7.1 dry run
  showed IN1 toggling at about 50%.

## Recommended next steps (no hardware change first)

1. **Scope the primary side** at 20–35 kHz, single-ended and complementary:
   - DRV_A–DRV_B (differential);
   - T1.1 after C11;
   - IPROPI (U2 pin 6, ≈ 1.5 V/A) for primary current.

   That gives the real tank behaviour, the current and the phase.
2. **Extend the sweep below 20 kHz** (10–20 kHz) to find the lower mode H1
   predicts. That needs a STAGE7_PLAN amendment, because the script's 20 kHz floor
   is a plan limit.
3. **Re-model:** SPICE with T1 as coupled inductors (Lm 44 µH, leakage measured or
   estimated, secondary winding capacitance, 1:50), driven by the DRV8876 bridge
   at VM 5/9/20 V through C11 into the CW ladder. Fit it to the measured curve,
   then use it to choose the drive frequency, C11 and the expected kV vs VM.
4. **Linearity test at a 9 V bridge.** It tests H3 and is the extrapolation basis,
   but it's **blocked by option 1** until the hardware OV trip is verified (fly
   lead on HV_SENSE_RAW, or the board revision).
5. **Measure T1 in isolation** (board unpowered): primary inductance with the
   secondary open and shorted, which gives the leakage. An LCR meter at 30 kHz
   would do.

## Design options to evaluate (after 1–3)

- **Retune C11** for the real tank: likely a smaller C11, or remove the series
  resonance and drive at the reflected-capacitance mode deliberately.
- **Higher-ratio transformer in the same family.** FL2015-5L_ is 1:125, 20 µH,
  pri 12 Vrms, sec 1600 Vrms. Check that the footprint/package matches before
  assuming it's a drop-in. Reflected capacitance scales with n², which also moves
  the tank.
- **Higher bridge voltage** (up to the 20 V PD contract): about 4× on its own if
  linear. Insufficient alone at the current transfer, and it needs the OV trip
  verified first.
- **Multiplier changes:** more stages, or lower-VF diodes in the first stages,
  where the voltage per diode is lowest (H3).
- **A different topology:** for example, a flyback/resonant driver designed for
  this capacitive load, instead of a CCFL transformer driven from an H-bridge with
  series C.
