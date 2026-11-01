# Stage 7 plan: first PWM / first HV, under the option 1 limits

Status: **rev 2, 2026-11-01. Approved by the user with a 2 kV initial limit.**
User answers: J60 insulated and > 10 mm from anything; **no grounding stick**; lid assumed
on (the enclosure); 2 kV is OK for initial testing. Live log: [BRINGUP.md](BRINGUP.md).
Stages 0–6 have passed. Stage 6 was the reduced version: **the hardware OV trip, the D90
latch and Q2 are unverified** (AUDIT.md), so **firmware is the only overvoltage
protection** in this stage.

## Goal

Generate HV for the first time, at **low kV and in short bursts**, and measure:
- the AIN0 response vs drive frequency (the gain curve below resonance);
- the bridge sag and fault behaviour;
- the HV_OUT discharge time after stop.

Stop well below the 16.96 kV hardware trip. Not in scope:
- corona operation;
- bridge voltages above 5 V;
- operating at or near resonance;
- long runs.

## Drive physics (why frequency is the gain knob)

| Item | Value | Source |
|---|---|---|
| T1 FL2015-4LD | **1:50**, L_pri **44 µH** (both halves, pins 1/5), pri ≤ 32 Vrms / 40 Vpk, sec ≤ 1600 Vrms / 2000 Vpk, I_sec ≤ 7 mA, 6 W | `procurement/Coilcraft_FL_current.pdf` |
| C11 | 120 nF / 630 V in series with the primary (DRV_A → C11 → T1.1; DRV_B → T1.5) | netlist |
| Series resonance | **f₀ = 1/(2π√(44 µH·120 nF)) ≈ 69.3 kHz** (the design point is 68 kHz) | calc |
| Multiplier | 6-stage CW, D10–D21 / C100–C111. Open-circuit model: 1250 Vpk sec → 14.6 kV raw → **13.3 kV HV_OUT** (100 MΩ ballast + 1 GΩ divider) | `spice-multiplier-report.json` @ 8cedf38 |
| HV readout | AIN0 = HV_SENSE_BUF. HV_OUT ≈ **6.10 kV/V** nominal, **uncalibrated** (±5–10%). Sense filter 164 kΩ·C13 ≈ **16 ms** | netlist |
| Return current | AIN1, 100 µA/V via R90 10 kΩ (offset ≈ 2 mV ≈ 0.2 µA) | netlist |

**Ideal lossless, unloaded estimate** at VM = 4.9 V (5 V contract). This is an upper-bound
guide only: T1's secondary self-capacitance reflects ×2500 onto the primary and will
**pull the real resonance down**, so the measured curve rules.

| f | Single-ended (IN1 PWM, IN2 = 0) | Complementary (IN1/IN2) |
|---|---|---|
| 20 kHz | ~0.15 kV | ~0.30 kV |
| 30 kHz | ~0.38 kV | ~0.77 kV |
| 40 kHz | ~0.83 kV | ~1.7 kV |
| 50 kHz | ~1.8 kV | ~3.6 kV |
| 60 kHz | ~5.0 kV | ~10 kV |

**Single-ended drive first.** In DRV8876 PWM mode, IN1 = PWM and IN2 = 0 alternates
forward (OUT1 H, OUT2 L) with coast (Hi-Z). C11 AC-couples it, so T1 still sees AC, at
about half the complementary amplitude. **It also needs no `inversed` PWM channel**,
which avoids the idle-high polarity hazard found on 2026-10-31.

## Hard limits (enforced in software, `stage7.py`)

| Limit | Value |
|---|---|
| PD contract | **5 V only** (bridge ≈ 4.9 V). Refuse to start otherwise |
| Frequency | **20–50 kHz**, period read back from sysfs before enable. Refuse anything outside the range |
| Drive mode | Single-ended (IN1 = PWM ch2 50%, IN2 = 0) for 7.2–7.3. Complementary only in 7.4, at the lowest frequency, if approved |
| Duty | 50% (IN1) |
| Burst | ≤ **1.0 s** per burst, then ≥ **10 s** off |
| **HV cutoff** | Safe-stop when **AIN0 > 0.50 V** (≈ 3.0 kV) |
| Step target | End the sweep when AIN0 ≥ **0.33 V** (≈ 2.0 kV) |
| Other aborts | DRV_nFAULT low (chopping pulses are treated as faults in this stage); EFUSE_FLT low; GPIO26 high; interlock open; AIN1 > 0.10 V (≈ 10 µA return current, i.e. arcing/corona to return); VBUS outside 4.5–5.6 V; bridge < 4.0 V or > 5.6 V; 3V3 median +20 mA; any sysfs/PWM error |
| Sampling | AIN0 every other ADS1115 conversion at 860 SPS (≈ 200 Hz on AIN0, ≈ 70 Hz on the rest) |
| Exit | Safe-stop (GPIO24 low → PWM disable → polarity normal → GPIO25 low) on every path, then log the HV decay for 15 s |

The detection latency is about 20–30 ms (sense filter plus conversions). That is
acceptable because each burst's final kV is set by the drive frequency, not by time: the
CW charges in ≈ 30 ms in the model.

## Safety and equipment (to confirm before running)

- **Lid closed** (interlock) for every burst. Nobody's hands in the enclosure while
  GPIO24/25 are high, or for **≥ 60 s** after a stop.
- **J60/J61 termination:**
  - proposed: **J60 open**, with its pad or wire end insulated and ≥ 10 mm from anything;
  - J61 left as built (HV_RETURN via R90 to GND);
  - no emitter/collector attached in stage 7.
- **Discharge before touching (no grounding stick available):**
  - wait **≥ 5 min** after the last burst, and confirm AIN0 < 0.01 V (≈ 60 V);
  - even then, **don't touch the HV section** (CW stages, J60, R20–R39). AIN0 only
    sees HV_OUT. The internal stages rely on their own 200 MΩ bleeders (model:
    0.93 s nominal, > 5 s with an open bleeder);
  - **build a grounding stick before any hands-on work inside the enclosure.** For
    example, a ≥ 10 MΩ / ≥ 3 kV resistor string on an insulated rod, clip-lead to
    board GND, applied to HV_OUT and each CW stage.
- An HV probe is not required: AIN0 is the readout, but it's uncalibrated. A scope
  on J2.12 to confirm the PWM frequency is optional.

## Steps

| Step | Conditions | Action | Pass / record |
|---|---|---|---|
| **7.1 Dry PWM check** | **Driver asleep** (GPIO24 low), bridge off | Configure PWM ch2 at 20 kHz / 50%, enable for 1 s, then safe-stop. Repeat at 50 kHz | sysfs readback matches. Safe-stop leaves GPIO18/19 low with channels disabled/normal. AIN0 stays 0 (driver asleep) |
| **7.2 First HV** | 5 V contract, lid closed, bridge on, driver awake | **20 kHz single-ended, one 1.0 s burst** | AIN0 rises a little (estimate ≤ 0.05 V ≈ 0.3 kV). No faults. Record the AIN0 peak, bridge sag, AIN1, and the **decay after stop** |
| **7.3 Frequency sweep** | as 7.2 | 1 s bursts at 25, 30, 35, 40, 45, 50 kHz, ≥ 10 s apart. **Stop the sweep early** if AIN0 ≥ 0.33 V; abort at 0.50 V | Gain curve (AIN0 vs f), bridge sag, AIN1, nFAULT behaviour, decay τ per burst |
| **7.4 (optional) Complementary** | as 7.2, needs separate approval | One 1 s burst, complementary, at **20 kHz only** | AIN0 ≈ 2× the 7.2 value. Verify the `inversed` channel is restored to `normal` on stop |
| **7.5 Discharge check** | after the last burst | Log AIN0 for 60 s | Time for HV_OUT to fall below 60 V (AIN0 < 0.01 V). Compare with the 0.93 s model |

Every step waits for the user's go-ahead. Each step logs to CSV on ew-1 and is recorded
in BRINGUP.md in the same session.

## Not covered by stage 7 (later stages, each needs its own plan)

- Calibrating the AIN0 → kV scale against an HV probe.
- Verifying the hardware OV trip (needs a test point or fly lead). The option 1 limits
  stay in force until it is done.
- Bridge voltages above 5 V, operation near resonance, corona load, long runs,
  thermal behaviour of T1/U2/C11, and handling nFAULT current-chopping pulses as
  normal operation.
