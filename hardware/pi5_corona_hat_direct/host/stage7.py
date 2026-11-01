#!/usr/bin/env python3
"""Stage 7 (STAGE7_PLAN.md rev 2): first PWM / first HV under the option 1 limits.

  stage7.py dry   FREQ_HZ [SECS]   7.1  PWM on IN1 with the driver ASLEEP and the bridge OFF
  stage7.py burst FREQ_HZ [SECS]   7.2  one single-ended burst (IN1 PWM 50%, IN2 = 0)
  stage7.py sweep F1,F2,...        7.3  1 s bursts, >= 10 s apart, stops at AIN0 >= TARGET
  stage7.py decay SECS             7.5  log AIN0 only (no drive)
  stage7.py comp  FREQ_HZ [SECS]   7.4  ONE complementary burst: IN1 = ch2 normal, IN2 = ch3 INVERSED
                                   (approved 2026-11-01; stop restores ch3 polarity normal and checks GPIO19 low)

Hard limits (refuse/abort):
  * explicit 5 V PD contract only; lid closed (except dry); 20 kHz <= f <= 50 kHz; duty 50 %
  * burst <= 1.0 s; >= 10 s between bursts in a sweep
  * AIN0 > 0.50 V (~3 kV) -> safe-stop;  sweep ends when AIN0 >= 0.33 V (~2 kV)
  * nFAULT low, EFUSE_FLT low, OV trip, interlock open, AIN1 > 0.10 V, VBUS/bridge out of band,
    GPIO19 (IN2) high, 3V3 median +20 mA, any sysfs error -> safe-stop
Safe-stop: GPIO24 low -> PWM disable -> polarity normal -> GPIO25 low. Always on exit.
"""
import csv, os, subprocess, sys, time
from smbus2 import SMBus
import gpiod
from gpiod.line import Direction, Bias

PWMCHIP = "/sys/class/pwm/pwmchip0"
CH = 2                       # GPIO18 = PWM0_CHAN2 = DRV_IN1
F_MIN, F_MAX = 20_000, 50_000
BURST_MAX = 1.0
GAP_MIN = 10.0
AIN0_ABORT, AIN0_TARGET = 0.50, 0.33
AIN1_ABORT = 0.10
KV_PER_V = 1.000164e9 / 164e3 / 1e3   # nominal, uncalibrated
lines = {5: "nFAULT", 6: "EFUSE_FLT", 23: "INTLK", 26: "OVTRIP"}

def sh(*a): return subprocess.run(a, capture_output=True, text=True).stdout.strip()
def gpio(n, level): sh("pinctrl", "set", str(n), "op", "dh" if level else "dl")
def lev(n): return int(sh("pinctrl", "lev", str(n)) or "1")
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

def pwm_dir(ch): return f"{PWMCHIP}/pwm{ch}"

def pwm_setup(freq):
    if not (F_MIN <= freq <= F_MAX): raise ValueError(f"frequency {freq} Hz outside {F_MIN}-{F_MAX}")
    if "1f00098000" not in os.path.realpath(f"{PWMCHIP}/device"): raise RuntimeError("pwmchip0 is not RP1 PWM0")
    d = pwm_dir(CH)
    if not os.path.isdir(d):
        pw(f"{PWMCHIP}/export", CH); time.sleep(0.3)
    pw(f"{d}/enable", 0); pw(f"{d}/polarity", "normal"); pw(f"{d}/duty_cycle", 0)
    period = round(1e9 / freq); pw(f"{d}/period", period); pw(f"{d}/duty_cycle", period // 2)
    rp, rd, pol, en = int(pr(f"{d}/period")), int(pr(f"{d}/duty_cycle")), pr(f"{d}/polarity"), pr(f"{d}/enable")
    f_rb = 1e9 / rp
    if not (F_MIN <= f_rb <= F_MAX) or abs(rd / rp - 0.5) > 0.01 or pol != "normal" or en != "0":
        raise RuntimeError(f"PWM readback bad: period={rp} duty={rd} pol={pol} en={en}")
    if os.path.isdir(pwm_dir(3)) and pr(f"{pwm_dir(3)}/enable") != "0":
        raise RuntimeError("pwm3 (IN2) is enabled - refusing")
    return f_rb

def pwm3_setup(freq):
    """IN2 = PWM0_CHAN3, same period, 50 %, left NORMAL + disabled (pin low).
    A disabled channel with 'inversed' polarity idles HIGH (measured 2026-10-31),
    so polarity is switched to inversed only at enable time (pwm3_start)."""
    d = pwm_dir(3)
    if not os.path.isdir(d):
        pw(f"{PWMCHIP}/export", 3); time.sleep(0.3)
    pw(f"{d}/enable", 0); pw(f"{d}/polarity", "normal"); pw(f"{d}/duty_cycle", 0)
    period = round(1e9 / freq); pw(f"{d}/period", period); pw(f"{d}/duty_cycle", period // 2)
    rp, rd, pol, en = int(pr(f"{d}/period")), int(pr(f"{d}/duty_cycle")), pr(f"{d}/polarity"), pr(f"{d}/enable")
    if rp != period or abs(rd / rp - 0.5) > 0.01 or pol != "normal" or en != "0":
        raise RuntimeError(f"pwm3 readback bad: period={rp} duty={rd} pol={pol} en={en}")

def pwm3_start():
    d = pwm_dir(3)
    pw(f"{d}/polarity", "inversed"); pw(f"{d}/enable", 1)
    pol, en = pr(f"{d}/polarity"), pr(f"{d}/enable")
    if (pol, en) != ("inversed", "1"): raise RuntimeError(f"pwm3 start readback bad: pol={pol} en={en}")

def safe_stop(log, t0):
    gpio(24, 0); log.append((round(time.monotonic() - t0, 4), "GPIO24 low"))
    for ch in (2, 3):
        d = pwm_dir(ch)
        if os.path.isdir(d):
            try: pw(f"{d}/enable", 0); pw(f"{d}/polarity", "normal")
            except OSError as e: log.append((round(time.monotonic() - t0, 4), f"pwm{ch} stop error {e}"))
    log.append((round(time.monotonic() - t0, 4), "PWM disabled/normal"))
    gpio(25, 0); log.append((round(time.monotonic() - t0, 4), "GPIO25 low"))

class Rig:
    def __init__(self, tag):
        self.out = f"/home/uge/stage7_{tag}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        self.req = gpiod.request_lines("/dev/gpiochip0", consumer="stage7",
                    config={tuple(lines): gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.AS_IS)})
        self.b = SMBus(1); self.t0 = time.monotonic(); self.rows = []; self.events = []; self.stoplog = []
        self.last = {"vb": 0.0, "br": 0.0, "a1": 0.0}; self.n = 0; self.base3 = None; self.h3 = []
    def gp(self): return {n: self.req.get_value(l).value for l, n in lines.items()}
    def t(self): return time.monotonic() - self.t0
    def ev(self, m): self.events.append((round(self.t(), 3), m)); print(f"  [{self.t():7.3f}s] {m}", flush=True)
    def sample(self, phase):
        """AIN0 every call; VBUS/bridge/AIN1 round-robin; slow checks every 25th."""
        a0 = ads(self.b, 0)
        k = self.n % 3
        if k == 0: self.last["vb"] = ads(self.b, 2) * 118 / 18
        elif k == 1: self.last["br"] = ads(self.b, 3) * 11
        else: self.last["a1"] = ads(self.b, 1)
        g = self.gp(); g19 = None; i3 = None
        if self.n % 25 == 0:
            g19 = lev(19); i3 = i3v3(); self.h3.append(i3)
        self.n += 1
        self.rows.append([round(self.t(), 4), phase, round(a0, 4), round(self.last["vb"], 3), round(self.last["br"], 3),
                          round(self.last["a1"], 4), g["nFAULT"], g["EFUSE_FLT"], g["INTLK"], g["OVTRIP"],
                          "" if g19 is None else g19, "" if i3 is None else round(i3 * 1000, 1)])
        return a0, g, g19
    def med3(self):
        h = self.h3[-3:]; return sorted(h)[len(h) // 2] if h else float("nan")
    def checks(self, a0, g, g19, live=True, need_intlk=True, bridge_on=True, allow_in2=False):
        why = []
        if a0 > AIN0_ABORT: why.append(f"AIN0 {a0:.3f} V > {AIN0_ABORT} (~{a0*KV_PER_V:.2f} kV)")
        if g["OVTRIP"] == 1: why.append("OV trip high")
        if g["EFUSE_FLT"] == 0: why.append("EFUSE_FLT low")
        if live and g["nFAULT"] == 0: why.append("DRV_nFAULT low")
        if need_intlk and g["INTLK"] == 0: why.append("interlock opened")
        if self.last["a1"] > AIN1_ABORT: why.append(f"AIN1 {self.last['a1']:.3f} V (return current)")
        if self.n > 3 and not 4.5 <= self.last["vb"] <= 5.6: why.append(f"VBUS {self.last['vb']:.2f}")
        if bridge_on and self.n > 6 and not 4.0 <= self.last["br"] <= 5.6: why.append(f"bridge {self.last['br']:.2f}")
        if g19 == 1 and not allow_in2: why.append("GPIO19 (IN2) high")
        if self.base3 and self.med3() - self.base3 > 0.020: why.append(f"3V3 +{(self.med3()-self.base3)*1000:.0f} mA")
        return "; ".join(why)
    def pre(self, need_intlk=True, a0_max=0.01):
        c0 = self.b.read_byte_data(0x42, 0x67) >> 4
        vb = ads(self.b, 2) * 118 / 18; br = ads(self.b, 3) * 11; a0 = ads(self.b, 0); a1 = ads(self.b, 1); g = self.gp()
        self.base3 = sorted(i3v3() for _ in range(5))[2]
        g18, g19, g24, g25 = lev(18), lev(19), lev(24), lev(25)
        print(f"pre: PD=0x{c0:x} VBUS={vb:.2f} bridge={br:.3f} AIN0={a0:.4f} AIN1={a1:.4f} gpio={g} "
              f"g18/19/24/25={g18}{g19}{g24}{g25} 3V3={self.base3*1000:.0f}mA", flush=True)
        ok = (c0 == 1 and 4.6 < vb < 5.6 and br < 0.2 and a0 < a0_max and a1 < AIN1_ABORT and g["nFAULT"] == 1
              and g["EFUSE_FLT"] == 1 and g["OVTRIP"] == 0 and (g["INTLK"] == 1 or not need_intlk)
              and (g18, g19, g24, g25) == (0, 0, 0, 0))
        if not ok: print("PRECONDITION FAILED - nothing driven")
        return ok
    def finish(self, abort):
        try: self.req.release()
        except Exception: pass
        self.b.close()
        with open(self.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t_s", "phase", "ain0_V", "vbus_V", "bridge_V", "ain1_V", "nFAULT", "EFUSE_FLT", "INTLK", "OVTRIP", "g19", "i3v3_mA"])
            w.writerows(self.rows)
        print("RESULT:", "ABORT - " + abort if abort else "completed, no abort")
        print("safe-stop log:", self.stoplog)
        print("csv:", self.out)

def summarize(rows, phase, t_ref=None):
    rs = [r for r in rows if r[1] == phase]
    if not rs: return None
    a0 = [r[2] for r in rs]
    vb = [r[3] for r in rs if r[3]]; br = [r[4] for r in rs if r[4]]; a1 = [r[5] for r in rs]
    pk = max(a0)
    print(f"  {phase:10s} n={len(rs):5d} t={rs[0][0]:.2f}-{rs[-1][0]:.2f}s  AIN0 max {pk:.4f} V (~{pk*KV_PER_V:.3f} kV) "
          f"end {a0[-1]:.4f}  VBUS {min(vb):.2f}-{max(vb):.2f}  bridge {min(br):.3f}-{max(br):.3f}  AIN1 max {max(a1):.4f}  "
          f"nFAULT {set(r[6] for r in rs)} EFLT {set(r[7] for r in rs)} OVTRIP {set(r[9] for r in rs)}")
    return pk

def decay_report(rows, t_stop):
    rs = [r for r in rows if r[1] == "decay"]
    if not rs: return
    a_stop = rs[0][2]
    for thr in (0.1, 0.05, 0.01):
        x = next((r[0] - t_stop for r in rs if r[2] < thr), None)
        print(f"  decay: AIN0 < {thr} V (~{thr*KV_PER_V*1000:.0f} V) after {None if x is None else round(x, 2)} s")
    print(f"  decay end: AIN0 {rs[-1][2]:.4f} V at +{rs[-1][0]-t_stop:.1f} s (start {a_stop:.4f})")

def run_burst(rig, freq, secs, dry, phase_tag="burst", comp=False):
    """One burst. Returns (abort_reason or None, peak AIN0, t_stop)."""
    fr = pwm_setup(freq); rig.ev(f"PWM ch{CH} configured {fr:.0f} Hz 50% normal (readback OK)")
    if comp:
        if dry: raise RuntimeError("comp not allowed in dry")
        pwm3_setup(freq); rig.ev("PWM ch3 configured same period 50%, normal+disabled until start (readback OK)")
    if not dry:
        gpio(25, 1); rig.ev("GPIO25 high")
        ts = time.monotonic()
        while time.monotonic() - ts < 1.0:
            a0, g, g19 = rig.sample("bulk")
            why = rig.checks(a0, g, g19, live=True, bridge_on=False)
            if why: return why, a0, rig.t()
        if not 4.4 <= rig.last["br"] <= 5.4: return f"bridge {rig.last['br']:.2f} V not ~4.9", 0.0, rig.t()
        if lev(18) or lev(19): return "GPIO18/19 not low before wake", 0.0, rig.t()
        gpio(24, 1); rig.ev("GPIO24 high (driver awake)"); time.sleep(0.003)
        if rig.gp()["nFAULT"] == 0: return "nFAULT low after wake", 0.0, rig.t()
    pw(f"{pwm_dir(CH)}/enable", 1)
    if comp: pwm3_start()
    rig.ev(f"PWM ENABLE ({phase_tag} {freq/1e3:.1f} kHz, {secs:.2f} s{', COMPLEMENTARY' if comp else ''})")
    ts = time.monotonic(); peak = 0.0; hi18 = 0; n18 = 0; abort = None
    while time.monotonic() - ts < secs:
        a0, g, g19 = rig.sample(phase_tag); peak = max(peak, a0)
        if dry and rig.n % 7 == 0: n18 += 1; hi18 += lev(18)
        why = rig.checks(a0, g, g19, live=not dry, need_intlk=not dry, bridge_on=not dry, allow_in2=comp)
        if dry and a0 > 0.01: why = (why + "; " if why else "") + f"AIN0 {a0:.3f} with driver asleep"
        if why: abort = why; break
    safe_stop(rig.stoplog, rig.t0); t_stop = rig.t(); rig.ev("safe-stop" + (" (ABORT)" if abort else ""))
    if dry and n18: rig.ev(f"GPIO18 sampled high {hi18}/{n18} times during PWM (expect ~50%)")
    if comp:
        d3 = pwm_dir(3); st = (pr(f"{d3}/enable"), pr(f"{d3}/polarity"), lev(19), lev(18))
        rig.ev(f"post-stop ch3 enable={st[0]} polarity={st[1]} GPIO19={st[2]} GPIO18={st[3]}")
        if st != ("0", "normal", 0, 0): abort = (abort + "; " if abort else "") + f"post-stop IN pins/ch3 not safe {st}"
    return abort, peak, t_stop

def log_decay(rig, secs):
    ts = time.monotonic()
    while time.monotonic() - ts < secs:
        rig.sample("decay"); time.sleep(0.02)

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("dry", "burst", "sweep", "decay", "comp"):
        print(__doc__); return 2
    mode = sys.argv[1]
    gpio(24, 0); gpio(25, 0)
    rig = Rig(mode); abort = None
    try:
        if mode == "decay":
            secs = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
            t_stop = rig.t(); log_decay(rig, secs); decay_report(rig.rows, t_stop)
            return 0
        if not rig.pre(need_intlk=(mode != "dry")): return 2
        if mode in ("dry", "burst", "comp"):
            freq = int(float(sys.argv[2])); secs = min(float(sys.argv[3]) if len(sys.argv) > 3 else 1.0, BURST_MAX)
            abort, peak, t_stop = run_burst(rig, freq, secs, dry=(mode == "dry"), comp=(mode == "comp"))
            log_decay(rig, 15.0 if mode == "burst" else 2.0)
            summarize(rig.rows, "burst"); summarize(rig.rows, "decay"); decay_report(rig.rows, t_stop)
        else:
            freqs = [int(float(x)) for x in sys.argv[2].split(",")]
            for f in freqs:
                if not (F_MIN <= f <= F_MAX): print(f"refusing: {f} Hz outside limits"); return 2
            for i, f in enumerate(freqs):
                tag = f"b{f//1000}k"
                abort, peak, t_stop = run_burst(rig, f, BURST_MAX, dry=False, phase_tag=tag)
                rig.ev(f"{tag}: peak AIN0 {peak:.4f} V (~{peak*KV_PER_V:.2f} kV)")
                log_decay(rig, GAP_MIN)
                if abort: break
                if peak >= AIN0_TARGET: rig.ev(f"target {AIN0_TARGET} V reached at {f} Hz - sweep ends"); break
                if i + 1 < len(freqs) and not rig.pre(a0_max=0.05): abort = "precondition failed between bursts"; break
            print("sweep summary:")
            for f in freqs:
                summarize(rig.rows, f"b{f//1000}k")
            decay_report(rig.rows, t_stop)
    except Exception as e:
        abort = f"exception {type(e).__name__}: {e}"
    finally:
        safe_stop(rig.stoplog, rig.t0)
        rig.finish(abort)
    return 1 if abort else 0

if __name__ == "__main__":
    sys.exit(main())
