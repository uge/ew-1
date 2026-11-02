#!/usr/bin/env python3
"""Stage 7.6: phase-aligned complementary drive with a slew-limited soft start.

  stage7_ramp.py align [FREQ]                         dry: driver asleep, bridge off; align IN1/IN2, report
  stage7_ramp.py ramp [--vbus 5|9|12|15] [--freq F] [--target-kv K] [--max-duty D] [--hold S]
  stage7_ramp.py ramp ... --ain1-max V   return-current abort on AIN1 (default 0.10 V = 10 uA; max 0.6)
  stage7_ramp.py ramp ... --abort-kv A --expect-trip   OV-trip test (2026-11-01, user request): ramp until
        the HARDWARE trip (GPIO26) fires; keep PWM 100 ms to prove Q2 stops the drive; check latch (D90)
        with GPIO24 high after HV decays; GPIO24 low must clear it (D91). --abort-kv is the firmware backstop.

Why: 2026-11-01 12:36 vs 12:51, identical complementary settings gave 0.36 kV vs >= 3 kV
(uncontrolled phase between separately enabled RP1 PWM ch2/ch3), and a 0.16 kV/ms ramp
overshot the 16 ms-filtered readout by ~2.5 kV.

Phase: ch2/ch3 counters re-synchronised by rp1_pwm_sync.py (root) before the driver wakes.
Hold: duty regulated every 50 ms on the PREDICTED value (down above target, up below target - 0.1 kV).
Tuning per bridge voltage: TUNING[vbus] = (duty step, slew limit); target entry also uses the prediction.
Drive: IN1 = ch2 normal, duty D*T (high at period start); IN2 = ch3 INVERSED, duty (1-D)*T
(high for the last D*T). D = 0.5 is full complementary. Phase is checked with the driver
ASLEEP by sampling GPIO18/19 (they must differ >= ALIGN_MIN of the time at D = 0.5); the
channels are re-enabled until aligned, then D drops to D0 before the driver wakes.

Limits (user-approved 2026-11-01): abort when AIN0 or the PREDICTED AIN0 (a0 + slope*TAU)
reaches 6.0 kV (0.984 V); stop ramping at --target-kv (default 5.0) and hold; duty only
increases while the HV slope is below SLEW (20 V/ms). Plus every stage7.py abort.
Safe-stop: GPIO24 low -> PWM disable -> polarity normal -> GPIO25 low. Any --vbus other than 5 returns to 5 V.

Library use (2026-11-01, dashboard/): run(mode, ...) is the whole align/ramp procedure; main() only parses
the CLI, takes the shared HV-owner lock (hv_lock(), /run/lock/ew1-hv.lock) and calls run(). run() adds an
optional per-sample callback and an external stop Event; with neither, it behaves exactly as before.
"""
import csv, fcntl, os, subprocess, sys, time
from smbus2 import SMBus
import gpiod
from gpiod.line import Direction, Bias
sys.path.insert(0, "/home/uge")
import husb238a

PWMCHIP = "/sys/class/pwm/pwmchip0"
KV_PER_V = 1.000164e9 / 164e3 / 1e3          # nominal, uncalibrated (~6.10 kV/V)
ABORT_KV, TAU = 6.0, 0.016
SLEW_KV_PER_MS = 0.020
D0, D_STEP, STEP_DT = 0.005, 0.0025, 0.020
HOLD_BAND_KV = 0.10
HOLD_DT = 0.050
# per-bridge-voltage loop tuning (2026-11-01: 9 V hold limit-cycled 4.2-5.7 kV with 0.0025 / 20 V/ms)
TUNING = {5: (0.0010, 0.010), 9: (0.0010, 0.010), 12: (0.00075, 0.010), 15: (0.0005, 0.010)}  # 12/15 V added 2026-11-01 (15 kV limit): finer step as kV per duty rises with VM
# previous 5/9 V tuning note:  # 5 V: finer after 0.3-0.85 kV overshoot at 3 kV (13:09 sweep)   # (duty step, slew kV/ms)
ALIGN_MIN, ALIGN_TRIES, ALIGN_SAMPLES = 0.90, 30, 150
F_MIN, F_MAX = 20_000, 100_000   # 100 kHz = DRV8876 fPWM max (user-requested 36-100 kHz sweep 2026-11-01)
RAMP_TIMEOUT = 20.0
lines = {5: "nFAULT", 6: "EFUSE_FLT", 23: "INTLK", 26: "OVTRIP"}

def sh(*a): return subprocess.run(a, capture_output=True, text=True).stdout.strip()
def gpio(n, level): sh("pinctrl", "set", str(n), "op", "dh" if level else "dl")
def lev(n): return int(sh("pinctrl", "lev", str(n)) or "1")
def lev1819():
    a, b = sh("pinctrl", "lev", "18,19").split(); return int(a), int(b)
def i3v3():
    try: return float(sh("vcgencmd", "pmic_read_adc", "3V3_SYS_A").split("=")[1].rstrip("A"))
    except Exception: return float("nan")
def ads(b, ch):
    b.write_i2c_block_data(0x48, 1, [0xC3 | (ch << 4), 0xE3]); time.sleep(0.0013)
    hi, lo = b.read_i2c_block_data(0x48, 0, 2); r = (hi << 8) | lo
    return (r - 65536 if r & 0x8000 else r) * 4.096 / 32768
def pw(path, val):
    with open(path, "w") as f: f.write(str(val))
def pr(path):
    with open(path) as f: return f.read().strip()
def d(ch): return f"{PWMCHIP}/pwm{ch}"

def pwm_prepare(freq):
    if not F_MIN <= freq <= F_MAX: raise ValueError(f"freq {freq} outside {F_MIN}-{F_MAX}")
    if "1f00098000" not in os.path.realpath(f"{PWMCHIP}/device"): raise RuntimeError("pwmchip0 is not RP1 PWM0")
    period = round(1e9 / freq)
    for ch in (2, 3):
        if not os.path.isdir(d(ch)): pw(f"{PWMCHIP}/export", ch); time.sleep(0.3)
        pw(f"{d(ch)}/enable", 0); pw(f"{d(ch)}/polarity", "normal"); pw(f"{d(ch)}/duty_cycle", 0)
        pw(f"{d(ch)}/period", period)
        if int(pr(f"{d(ch)}/period")) != period: raise RuntimeError(f"pwm{ch} period readback")
    return period

def set_duty(period, D):
    D = max(0.0, min(0.5, D))
    pw(f"{d(2)}/duty_cycle", round(D * period))
    pw(f"{d(3)}/duty_cycle", round((1 - D) * period))
    return D

def align(period, log):
    """Enable ch2/ch3 at D=0.5 (ch3 inversed) with the driver ASLEEP, then re-synchronise
    their counters with rp1_pwm_sync.py (one GLOBAL_CTRL write + SET_UPDATE, root).
    Refuses unless the helper verifies >= 99 % complementary."""
    if lev(24) != 0 or lev(25) != 0: raise RuntimeError("align requires GPIO24/25 low")
    for ch in (2, 3): pw(f"{d(ch)}/enable", 0)
    pw(f"{d(3)}/polarity", "normal"); set_duty(period, 0.5); pw(f"{d(3)}/polarity", "inversed")
    pw(f"{d(2)}/enable", 1); pw(f"{d(3)}/enable", 1)
    r = subprocess.run(["sudo", "-n", "python3", "/home/uge/rp1_pwm_sync.py"], capture_output=True, text=True)
    log((r.stdout + r.stderr).strip())
    if r.returncode != 0: raise RuntimeError("IN1/IN2 phase sync failed - refusing to drive")
    return 1.0

def safe_stop(log):
    gpio(24, 0)
    for ch in (2, 3):
        if os.path.isdir(d(ch)):
            try: pw(f"{d(ch)}/enable", 0); pw(f"{d(ch)}/polarity", "normal")
            except OSError as e: log(f"pwm{ch} stop error {e}")
    gpio(25, 0); log("safe-stop: GPIO24 low -> PWM off/normal -> GPIO25 low")

CSV_HEADER = ["t_s", "phase", "duty", "ain0_V", "pred_V", "slope_kV_per_ms", "vbus_V", "bridge_V", "ain1_V",
              "nFAULT", "EFUSE_FLT", "INTLK", "OVTRIP"]
LOCK_PATH = "/run/lock/ew1-hv.lock"     # shared with the dashboard: one HV-driving owner at a time

class HVLockBusy(RuntimeError):
    pass

def hv_lock(path=LOCK_PATH):
    """Take the exclusive HV-owner lock (non-blocking flock). Keep the returned file open while
    driving; closing it (or process death) releases it. Raises HVLockBusy if another owner holds it."""
    f = open(path, "a+")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        try: f.seek(0); who = f.read().strip()
        except OSError: who = "?"
        f.close(); raise HVLockBusy(f"HV lock {path} held by: {who or '?'}")
    f.seek(0); f.truncate(); f.write(f"{os.getpid()} {os.path.basename(sys.argv[0])} {time.strftime('%H:%M:%S')}\n"); f.flush()
    return f

def vbus_bands(vbus):
    """(VBUS band, bridge band) in V for a PD contract. 5 and 9 V keep their measured bands;
    12/15 V follow the 9 V pattern (VBUS V-0.5..V+0.6, bridge V-1.4..V+0.4; the bridge sits one
    D50 Schottky drop below VBUS and sags ~0.1 V under drive)."""
    if vbus == 5: return (4.5, 5.6), (4.0, 5.6)
    return (vbus - 0.5, vbus + 0.6), (vbus - 1.4, vbus + 0.4)

def check_args(mode, vbus, target_kv, abort_kv, ain1_max):
    """The CLI's argument limits; returns an error string or None."""
    if mode not in ("align", "ramp"): return "mode must be align or ramp"
    if vbus not in TUNING: return f"--vbus must be one of {sorted(TUNING)}"
    if ain1_max > 0.6: return "ain1-max capped at 0.6 V (60 uA)"
    if abort_kv > 19.0: return "abort-kv capped at 19.0"
    if target_kv >= abort_kv: return "target must be below the abort"
    return None

def _print(m): print(m, flush=True)

def run(mode, freq=32000, vbus=5, target_kv=5.0, max_d=0.5, hold=0.5, abort_kv=ABORT_KV, expect_trip=False,
        ain1_max=0.10, out_dir="/home/uge", on_sample=None, stop=None, out=_print):
    """One align or ramp run, exactly as the CLI does it (the CLI is a thin wrapper around this).
    on_sample(row, extra): called with every CSV row as it is taken (extra = {"i3v3": A} in the loop).
    stop: optional threading.Event; when set, the run aborts ("external stop") and safe-stops.
    Returns {"code", "abort", "result", "csv", "rows", "events", "precondition_failed"}.
    The caller must hold hv_lock(). Safe-stop always runs before this returns or raises."""
    err = check_args(mode, vbus, target_kv, abort_kv, ain1_max)
    if err: raise ValueError(err)
    max_d = min(max_d, 0.5)
    a0_abort, a0_target = abort_kv / KV_PER_V, target_kv / KV_PER_V
    d_step, slew = TUNING[vbus]

    t0 = time.monotonic(); rows = []; ev_log = []
    def log(m): ev_log.append((round(time.monotonic() - t0, 3), m)); out(f"  [{time.monotonic()-t0:7.3f}s] {m}")
    def add(row, extra=None):
        rows.append(row)
        if on_sample is not None: on_sample(row, extra or {})
    def chk():
        if stop is not None and stop.is_set(): raise RuntimeError("external stop requested")
    def nap(s):
        if stop is not None: stop.wait(s)
        else: time.sleep(s)
        chk()
    ret = {"code": None, "abort": None, "result": {}, "csv": None, "rows": rows, "events": ev_log, "precondition_failed": False}
    gpio(24, 0); gpio(25, 0)
    req = gpiod.request_lines("/dev/gpiochip0", consumer="stage7_ramp",
            config={tuple(lines): gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.AS_IS)})
    gp = lambda: {n: req.get_value(l).value for l, n in lines.items()}
    b = SMBus(1); pd = husb238a.HUSB238A(allow_write=True)
    abort = None; result = ret["result"]
    csv_path = os.path.join(out_dir, f"stage7_ramp_{mode}_{vbus}V_{time.strftime('%Y%m%d_%H%M%S')}.csv")
    try:
        c0 = b.read_byte_data(0x42, 0x67) >> 4; vb = ads(b, 2) * 118 / 18; br = ads(b, 3) * 11
        a0 = ads(b, 0); a1 = ads(b, 1); g = gp(); base3 = sorted(i3v3() for _ in range(5))[2]
        out(f"pre: PD=0x{c0:x} VBUS={vb:.2f} bridge={br:.3f} AIN0={a0:.4f} AIN1={a1:.4f} gpio={g} g18/19={lev1819()} 3V3={base3*1000:.0f}mA "
            f"| freq={freq} vbus={vbus} target={target_kv} kV abort={abort_kv} kV ain1_max={ain1_max} V max_duty={max_d}")
        ok = (c0 == 1 and 4.6 < vb < 5.6 and br < 0.2 and a0 < 0.01 and a1 < 0.1 and g["nFAULT"] == 1 and g["EFUSE_FLT"] == 1
              and g["OVTRIP"] == 0 and (g["INTLK"] == 1 or mode == "align") and lev1819() == (0, 0))
        if not ok:
            out("PRECONDITION FAILED - nothing driven"); ret.update(code=2, precondition_failed=True); return ret
        chk()
        period = pwm_prepare(freq); log(f"PWM ch2/ch3 prepared, period {period} ns")
        diff = align(period, log); result["align"] = diff
        set_duty(period, D0); log(f"phase synced; duty -> {D0} (driver still asleep)")
        if mode == "align":
            for Dt in (0.25, D0):
                set_duty(period, Dt); time.sleep(0.01)
                smp = [lev1819() for _ in range(300)]
                f1 = sum(a for a, _ in smp) / 300; f2 = sum(b2 for _, b2 in smp) / 300; both = sum(a and b2 for a, b2 in smp) / 300
                log(f"duty {Dt}: IN1 high {f1*100:.0f}%  IN2 high {f2*100:.0f}%  BOTH high {both*100:.1f}% (expect ~{Dt*100:.0f}/{Dt*100:.0f}/0)")
                result[f"d{Dt}"] = (round(f1, 3), round(f2, 3), round(both, 3))
            ret["code"] = 0; return ret

        vb_band, br_band = vbus_bands(vbus)
        if vbus != 5:
            log(f"request {vbus} V (GPIO25 low) - user override")
            log(f"request {vbus} V AMS={pd.request_fixed(vbus, max_volts=vbus)}"); nap(1.0)
            vb = ads(b, 2) * 118 / 18
            if not vb_band[0] <= vb <= vb_band[1]: raise RuntimeError(f"VBUS {vb:.2f} not at {vbus} V")
        chk()
        gpio(25, 1); log("GPIO25 high"); nap(1.0)
        br = ads(b, 3) * 11
        if not br_band[0] + 0.3 <= br <= br_band[1]: raise RuntimeError(f"bridge {br:.2f} out of band")
        if gp()["nFAULT"] != 1: raise RuntimeError("nFAULT low before wake")
        chk()
        gpio(24, 1); log(f"GPIO24 high: DRIVE at duty {D0}"); time.sleep(0.003)

        D = D0; hist = []; t_step = time.monotonic(); phase = "ramp"; t_hold = None
        last = {"vb": vb, "br": br, "a1": a1}; n = 0; h3 = []; peak = 0.0; d_at_target = None
        t_ramp = time.monotonic()
        while True:
            now = time.monotonic(); t = now - t0
            a0 = ads(b, 0); peak = max(peak, a0); hist.append((now, a0)); hist = hist[-6:]
            k = n % 3
            if k == 0: last["vb"] = ads(b, 2) * 118 / 18
            elif k == 1: last["br"] = ads(b, 3) * 11
            else: last["a1"] = ads(b, 1)
            g = gp()
            if n % 25 == 0: h3.append(i3v3())
            n += 1
            slope = 0.0
            if len(hist) >= 4:
                dt = hist[-1][0] - hist[0][0]
                if dt > 0: slope = (hist[-1][1] - hist[0][1]) / dt        # V/s on AIN0
            pred = a0 + max(slope, 0.0) * TAU
            add([round(t, 4), phase, round(D, 4), round(a0, 4), round(pred, 4), round(slope * KV_PER_V / 1000, 4),
                 round(last["vb"], 3), round(last["br"], 3), round(last["a1"], 4),
                 g["nFAULT"], g["EFUSE_FLT"], g["INTLK"], g["OVTRIP"]], {"i3v3": h3[-1] if h3 else None})
            why = []
            if a0 >= a0_abort or pred >= a0_abort: why.append(f"AIN0 {a0:.3f} pred {pred:.3f} >= {a0_abort:.3f} ({abort_kv} kV)")
            if g["OVTRIP"]:
                if expect_trip:
                    result["trip_kv_ain0"] = round(a0 * KV_PER_V, 3); result["trip_t"] = round(t, 4); result["trip_duty"] = D
                    log(f"HARDWARE OV TRIP: GPIO26=1 at AIN0 {a0:.4f} V (~{a0*KV_PER_V:.2f} kV), duty {D:.4f}")
                    break
                why.append("OV trip")
            if g["EFUSE_FLT"] == 0: why.append("EFUSE_FLT low")
            if g["nFAULT"] == 0: why.append("nFAULT low")
            if g["INTLK"] == 0: why.append("interlock opened")
            if last["a1"] > ain1_max: why.append(f"AIN1 {last['a1']:.3f} V > {ain1_max} (return current ~{last['a1']*100:.0f} uA)")
            if n > 3 and not vb_band[0] <= last["vb"] <= vb_band[1]: why.append(f"VBUS {last['vb']:.2f}")
            if n > 6 and not br_band[0] <= last["br"] <= br_band[1]: why.append(f"bridge {last['br']:.2f}")
            if len(h3) >= 3 and sorted(h3[-3:])[1] - base3 > 0.020: why.append("3V3 +20 mA")
            if stop is not None and stop.is_set(): why.append("external stop")
            if why: abort = "; ".join(why); break
            if phase == "ramp":
                if pred >= a0_target:
                    phase, t_hold, d_at_target = "hold", now, D
                    log(f"target {target_kv} kV reached (predicted) at duty {D:.4f}, AIN0 {a0*KV_PER_V:.2f} kV; hold {hold}s")
                elif now - t_step >= STEP_DT:
                    t_step = now
                    if slope * KV_PER_V / 1000 < slew and D < max_d:
                        D = set_duty(period, min(D + d_step, max_d))
                    elif D >= max_d and abs(slope * KV_PER_V / 1000) < 0.002 and now - t_ramp > 2.0:
                        phase, t_hold = "hold", now; log(f"max duty {max_d} reached, HV settled at {a0*KV_PER_V:.2f} kV; hold {hold}s")
                if now - t_ramp > RAMP_TIMEOUT:
                    phase, t_hold = "hold", now; log("ramp timeout; hold")
            else:
                if now - t_step >= HOLD_DT:            # regulate on the PREDICTED value, slow loop
                    t_step = now; kv = pred * KV_PER_V
                    if kv > target_kv: D = set_duty(period, max(D - d_step, 0.0))
                    elif kv < target_kv - HOLD_BAND_KV and slope * KV_PER_V / 1000 < slew: D = set_duty(period, min(D + d_step, max_d))
                if now - t_hold >= hold:
                    log(f"hold complete (duty {D:.4f})"); break
            time.sleep(0.001)
        result.update(peak_kv=peak * KV_PER_V, duty_end=D, duty_at_target=d_at_target)
        if expect_trip and "trip_kv_ain0" in result and not abort:
            # 1) PWM keeps running 100 ms: HV must FALL (Q2 holds DRV_nSLEEP low)
            ts = time.monotonic(); a_first = None; a_last = None; amax = 0.0
            while time.monotonic() - ts < 0.100:
                a0 = ads(b, 0); amax = max(amax, a0); a_first = a_first if a_first is not None else a0; a_last = a0
                add([round(time.monotonic() - t0, 4), "trip_pwm_on", round(D, 4), round(a0, 4), "", "", "", "", "", gp()["nFAULT"], gp()["EFUSE_FLT"], gp()["INTLK"], gp()["OVTRIP"]])
                if a0 >= a0_abort: abort = f"HV still rising after trip: AIN0 {a0:.3f}"; break
            result["post_trip_100ms"] = (round(a_first * KV_PER_V, 2), round(amax * KV_PER_V, 2), round(a_last * KV_PER_V, 2))
            log(f"100 ms after trip with PWM still running: AIN0 {a_first*KV_PER_V:.2f} -> {a_last*KV_PER_V:.2f} kV (max {amax*KV_PER_V:.2f})")
            for ch in (2, 3): pw(f"{d(ch)}/enable", 0); pw(f"{d(ch)}/polarity", "normal")
            log("PWM disabled (GPIO24 still high)")
            # 2) latch: wait for HV < 2 kV with GPIO24 high, GPIO26 must stay 1
            ts = time.monotonic(); latched = True
            while time.monotonic() - ts < 5.0:
                a0 = ads(b, 0); g = gp()
                add([round(time.monotonic() - t0, 4), "latch", 0, round(a0, 4), "", "", "", "", "", g["nFAULT"], g["EFUSE_FLT"], g["INTLK"], g["OVTRIP"]])
                if g["OVTRIP"] == 0: latched = False
                if a0 * KV_PER_V < 2.0 and time.monotonic() - ts > 0.5: break
                time.sleep(0.01)
            result["latch_held"] = latched; result["latch_hv_kv"] = round(a0 * KV_PER_V, 2)
            log(f"latch check: GPIO26 {'stayed 1' if latched else 'DROPPED'} while HV fell to {a0*KV_PER_V:.2f} kV (GPIO24 high)")
            # 3) clear: GPIO24 low -> GPIO26 must go 0
            gpio(24, 0); tc = time.monotonic(); cleared = None
            while time.monotonic() - tc < 0.5:
                if gp()["OVTRIP"] == 0: cleared = round((time.monotonic() - tc) * 1000, 2); break
            result["clear_ms"] = cleared
            log(f"clear check: GPIO24 low -> GPIO26 {'0 after ' + str(cleared) + ' ms' if cleared is not None else 'STILL 1 after 500 ms'}")
        elif expect_trip and not abort:
            abort = "expected hardware trip did not occur"
    except Exception as e:
        abort = f"exception {type(e).__name__}: {e}"
    finally:
        safe_stop(log)
        if True:
            ts = time.monotonic()
            while time.monotonic() - ts < 5.0:
                try:
                    a0 = ads(b, 0); add([round(time.monotonic() - t0, 4), "decay", 0, round(a0, 4), "", "", "", round(ads(b, 3) * 11, 3), "", "", "", "", ""])
                except Exception: break
                time.sleep(0.02)
        if mode == "ramp" and vbus != 5:
            try: log(f"request 5 V AMS={pd.request_fixed(5, max_volts=5)}")
            except Exception as e: log(f"request 5 V FAILED {e}")
        try: req.release()
        except Exception: pass
        b.close()
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        w.writerows(rows)
    live = [r for r in rows if r[1] in ("ramp", "hold")]
    if live:
        sl = [r[5] for r in live if r[5] != ""]
        out(f"  live n={len(live)} t={live[0][0]:.2f}-{live[-1][0]:.2f}s  duty {live[0][2]:.3f}->{live[-1][2]:.3f}  "
            f"AIN0 max {max(r[3] for r in live):.4f} V (~{max(r[3] for r in live)*KV_PER_V:.2f} kV)  "
            f"max slope {max(sl):.3f} kV/ms  bridge min {min(r[7] for r in live):.3f}  AIN1 max {max(r[8] for r in live):.4f}")
    dec = [r for r in rows if r[1] == "decay"]
    if dec:
        out(f"  decay: AIN0 max {max(r[3] for r in dec):.4f} V (~{max(r[3] for r in dec)*KV_PER_V:.2f} kV, filter lag)  end {dec[-1][3]:.4f} V")
    out("RESULT: " + (("ABORT - " + abort) if abort else "completed, no abort") + " " + str(result))
    out("csv: " + csv_path)
    ret.update(code=1 if abort else 0, abort=abort, csv=csv_path)
    return ret

def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("align", "ramp"): print(__doc__); return 2
    mode = args[0]
    def opt(name, default, cast=float):
        return cast(args[args.index(name) + 1]) if name in args else default
    freq = int(opt("--freq", 32000 if mode == "ramp" else (float(args[1]) if len(args) > 1 and not args[1].startswith("--") else 32000)))
    vbus = int(opt("--vbus", 5, int)); target_kv = opt("--target-kv", 5.0); max_d = min(opt("--max-duty", 0.5), 0.5)
    hold = opt("--hold", 0.5)
    abort_kv = opt("--abort-kv", ABORT_KV); expect_trip = "--expect-trip" in args
    ain1_max = opt("--ain1-max", 0.10)        # V on AIN1 (100 uA/V); 0.5 V = 50 uA corona design point
    err = check_args(mode, vbus, target_kv, abort_kv, ain1_max)
    if err: print(err); return 2
    try: lk = hv_lock()
    except HVLockBusy as e: print(f"REFUSED: {e}"); return 2
    try:
        return run(mode, freq=freq, vbus=vbus, target_kv=target_kv, max_d=max_d, hold=hold, abort_kv=abort_kv,
                   expect_trip=expect_trip, ain1_max=ain1_max)["code"]
    finally:
        lk.close()

if __name__ == "__main__":
    sys.exit(main())
