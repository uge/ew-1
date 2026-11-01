#!/usr/bin/env python3
"""Stage 6 (reduced, STAGE6_PLAN.md rev 3): driver enable (GPIO24) with NO PWM.

  stage6.py a    6.A'  bridge OFF, GPIO24 high 5 s: GPIO26 must stay 0 (D91 not reversed)
  stage6.py b    6.B   9 V contract, bridge ON, GPIO24 high 30 s: nFAULT 1, AIN0 ~0, no drive
  stage6.py c1   6.C1  as 6.B, then the USER OPENS A LID SWITCH: driver sleeps, bridge cut in HW
  stage6.py c3   6.C3  as 6.B, then the software safe-stop routine (order + timing logged)

Safety:
  * GPIO18/19 (DRV_IN1/IN2) must read 0 with PWM channels 2/3 unexported or disabled with
    normal polarity, checked before GPIO24 goes high and every sample after.
  * Safe-stop order: GPIO24 low -> PWM disable -> polarity normal -> GPIO25 low.
  * Step-down rule: GPIO25 low BEFORE requesting 5 V after a 9 V run.
  * Always exits with GPIO24/25 low and (for b/c*) the 5 V contract re-requested.
"""
import csv, os, subprocess, sys, threading, time
from smbus2 import SMBus
import gpiod
from gpiod.line import Direction, Bias
sys.path.insert(0, "/home/uge")
import husb238a

DT = 0.05
PWM = "/sys/class/pwm/pwmchip0"
AIN0_MAX = 0.05          # V; anything above means HV is being generated
BAND9 = (8.5, 9.6, 8.0, 9.4)   # VBUS lo/hi, bridge lo/hi at the 9 V contract

def sh(*a): return subprocess.run(a, capture_output=True, text=True).stdout.strip()
def gpio(n, level): sh("pinctrl", "set", str(n), "op", "dh" if level else "dl")
def lev(n): return int(sh("pinctrl", "lev", str(n)) or "1")
def i3v3():
    try: return float(sh("vcgencmd", "pmic_read_adc", "3V3_SYS_A").split("=")[1].rstrip("A"))
    except Exception: return float("nan")
def ads(b, ch):
    b.write_i2c_block_data(0x48, 1, [0xC3 | (ch << 4), 0xE3]); time.sleep(0.0015)
    hi, lo = b.read_i2c_block_data(0x48, 0, 2); r = (hi << 8) | lo
    return (r - 65536 if r & 0x8000 else r) * 4.096 / 32768

def pwm_state():
    """Return list of problems with PWM channels 2/3 (empty = safe)."""
    bad = []
    for ch in (2, 3):
        d = f"{PWM}/pwm{ch}"
        if os.path.isdir(d):
            en = open(f"{d}/enable").read().strip(); pol = open(f"{d}/polarity").read().strip()
            if en != "0" or pol != "normal": bad.append(f"pwm{ch} enable={en} polarity={pol}")
    for g in (18, 19):
        if lev(g) != 0: bad.append(f"GPIO{g}=1")
    return bad

def safe_stop(log):
    t = time.monotonic
    gpio(24, 0); log.append((t(), "GPIO24 low"))
    for ch in (2, 3):
        d = f"{PWM}/pwm{ch}"
        if os.path.isdir(d):
            try:
                open(f"{d}/enable", "w").write("0"); open(f"{d}/polarity", "w").write("normal")
            except OSError as e: log.append((t(), f"pwm{ch} stop error {e}"))
    log.append((t(), "PWM disabled/normal"))
    gpio(25, 0); log.append((t(), "GPIO25 low"))

lines = {5: "nFAULT", 6: "EFUSE_FLT", 23: "INTLK", 26: "OVTRIP"}

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("a", "b", "c1", "c3"):
        print(__doc__); return 2
    out = f"/home/uge/stage6_{mode}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    gpio(24, 0); gpio(25, 0)
    req = gpiod.request_lines("/dev/gpiochip0", consumer="stage6",
            config={tuple(lines): gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.AS_IS)})
    gp = lambda: {n: req.get_value(l).value for l, n in lines.items()}
    pd = husb238a.HUSB238A(allow_write=True)
    rows, events, abort = [], [], None
    t0 = time.monotonic()
    ev = lambda m: (events.append((round(time.monotonic() - t0, 3), m)), print(f"  [{time.monotonic()-t0:6.2f}s] {m}"))
    stoplog = []
    b = SMBus(1)
    try:
        # ---------- preconditions ----------
        c0 = b.read_byte_data(0x42, 0x67) >> 4
        vb0 = ads(b, 2) * 118 / 18; br0 = ads(b, 3) * 11; a00 = ads(b, 0); g0 = gp()
        base3 = sorted(i3v3() for _ in range(5))[2]; pw = pwm_state()
        print(f"pre: PD=0x{c0:x} VBUS={vb0:.2f} bridge={br0:.3f} AIN0={a00:.4f} gpio={g0} pwm_problems={pw} 3V3={base3*1000:.0f}mA")
        need_intlk = mode != "a"
        ok = (c0 == 1 and 4.6 < vb0 < 5.6 and br0 < 0.1 and abs(a00) < AIN0_MAX and not pw
              and g0["EFUSE_FLT"] == 1 and g0["OVTRIP"] == 0 and g0["nFAULT"] == 1
              and (g0["INTLK"] == 1 or not need_intlk))
        if not ok:
            print("PRECONDITION FAILED - nothing raised"); return 2

        def sample(phase):
            vb = ads(b, 2) * 118 / 18; br = ads(b, 3) * 11; a0 = ads(b, 0); g = gp()
            rows.append([round(time.monotonic() - t0, 3), phase, round(vb, 3), round(br, 3), round(a0, 4),
                         g["nFAULT"], g["EFUSE_FLT"], g["INTLK"], g["OVTRIP"], lev(18), lev(19), lev(24), lev(25)])
            return vb, br, a0, g

        def hold(phase, secs, band=None, expect_intlk=True, until=None, grace=0.01):
            """Sample for secs; return (reason or None). until(g) -> True ends early with 'until'."""
            hist, last3, n = [], base3, 0; ts = time.monotonic()
            while time.monotonic() - ts < secs:
                vb, br, a0, g = sample(phase)
                if n % 10 == 0:
                    hist.append(i3v3()); last3 = sorted(hist[-3:])[len(hist[-3:]) // 2]
                n += 1
                if until and until(g): return "until"
                why = []
                el = time.monotonic() - ts
                if g["EFUSE_FLT"] == 0: why.append("EFUSE_FLT low")
                if g["OVTRIP"] == 1: why.append("OV trip high")
                if el > grace and g["nFAULT"] == 0: why.append("DRV_nFAULT low")
                if a0 > AIN0_MAX: why.append(f"AIN0 {a0:.3f} V (HV present?)")
                if expect_intlk and g["INTLK"] == 0: why.append("interlock opened")
                if rows[-1][9] or rows[-1][10]: why.append("GPIO18/19 not low")
                if vb > 10 or br > 10: why.append(f"VBUS/bridge > 10 V ({vb:.2f}/{br:.2f})")
                if band:
                    vl, vh, bl, bh = band
                    if not vl <= vb <= vh: why.append(f"VBUS {vb:.2f} out of {vl}-{vh}")
                    if not bl <= br <= bh: why.append(f"bridge {br:.2f} out of {bl}-{bh}")
                if last3 - base3 > 0.020: why.append(f"3V3 +{(last3-base3)*1000:.0f} mA (median)")
                if why: return "; ".join(why)
                time.sleep(max(0, DT - (time.monotonic() - ts - el)))
            return None

        if mode == "a":
            ev("GPIO24 high (bridge off)"); gpio(24, 1)
            r = hold("a", 5.0, band=None, expect_intlk=False, grace=1e9)  # nFAULT irrelevant with VM=0
            if r: abort = r; ev(f"ABORT: {r}")
            ev("GPIO24 low"); gpio(24, 0)
            hold("a_post", 1.0, expect_intlk=False, grace=1e9)
        else:
            ev("request 9 V (GPIO25 low)")
            res = pd.request_fixed(9, max_volts=9); ev(f"request 9 V AMS={res}")
            time.sleep(1.0)
            vb, br, a0, g = sample("to9")
            if not (BAND9[0] <= vb <= BAND9[1]):
                abort = f"VBUS {vb:.2f} not at 9 V after request"; ev("ABORT: " + abort)
            else:
                ev("GPIO25 high"); gpio(25, 1)
                r = hold("bulk9", 1.0, band=None) or None
                vb, br, a0, g = sample("bulk9")
                if r or not (BAND9[2] <= br <= BAND9[3]):
                    abort = r or f"bridge {br:.2f} not at ~8.7 V"; ev("ABORT: " + abort)
                elif pwm_state():
                    abort = f"PWM not safe: {pwm_state()}"; ev("ABORT: " + abort)
                else:
                    ev("GPIO24 high (driver wake, IN1=IN2=0)"); gpio(24, 1)
                    time.sleep(0.003)  # tWAKE <= 1 ms
                    if mode == "b":
                        r = hold("awake", 30.0, band=BAND9)
                        if r: abort = r; ev("ABORT: " + r)
                    elif mode == "c3":
                        r = hold("awake", 3.0, band=BAND9)
                        if r: abort = r; ev("ABORT: " + r)
                    elif mode == "c1":
                        r = hold("awake", 2.0, band=BAND9)
                        if r: abort = r; ev("ABORT: " + r)
                        else:
                            ev(">>> OPEN ONE LID SWITCH NOW (60 s) <<<")
                            r = hold("wait_open", 60.0, band=BAND9, until=lambda g: g["INTLK"] == 0)
                            if r == "until":
                                ev("interlock opened with GPIO24/25 HIGH - recording hardware cut 4 s")
                                r2 = hold("cut", 4.0, band=None, expect_intlk=False, grace=1e9,
                                          until=lambda g: g["INTLK"] == 1)
                                if r2 == "until": ev("interlock re-closed early")
                                elif r2: ev(f"note during cut: {r2}")
                            elif r: abort = r; ev("ABORT: " + r)
                            else: abort = "interlock never opened (timeout)"; ev("ABORT: " + abort)
        # ---------- safe stop + return to 5 V ----------
        ev("safe-stop"); safe_stop(stoplog)
        if mode != "a":
            hold("decay", 4.0, expect_intlk=False, grace=1e9)
            ev("request 5 V (GPIO25 already low)")
            try: ev(f"request 5 V AMS={pd.request_fixed(5, max_volts=5)}")
            except Exception as e: ev(f"request 5 V error {e}")
            time.sleep(1.0); hold("end5", 1.0, expect_intlk=False, grace=1e9)
    finally:
        gpio(24, 0); gpio(25, 0)
        try: req.release()
        except Exception: pass
        b.close()

    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s","phase","vbus_V","bridge_V","ain0_V","nFAULT","EFUSE_FLT","INTLK","OVTRIP","g18","g19","g24","g25"])
        w.writerows(rows)
    print("RESULT:", "ABORT - " + abort if abort else "completed, no abort")
    if stoplog:
        s0 = stoplog[0][0]
        print("safe-stop order:", [(round((t - s0) * 1000, 2), m) for t, m in stoplog], "(ms)")
    for ph in ("a", "a_post", "bulk9", "awake", "wait_open", "cut", "decay", "end5"):
        rs = [r for r in rows if r[1] == ph]
        if rs:
            f = lambda i: f"{min(r[i] for r in rs):.3f}..{max(r[i] for r in rs):.3f}"
            st = lambda i: "".join(sorted(set(str(r[i]) for r in rs)))
            print(f"{ph:9s} n={len(rs):4d} t={rs[0][0]:6.2f}-{rs[-1][0]:6.2f}s VBUS {f(2)} bridge {f(3)} AIN0 {f(4)} "
                  f"nFAULT {st(5)} EFLT {st(6)} INTLK {st(7)} OVTRIP {st(8)} g18/19 {st(9)}{st(10)} g24 {st(11)} g25 {st(12)}")
    cut = [r for r in rows if r[1] == "cut"]
    if cut:
        tc = cut[0][0]
        for thr in (4.0, 1.0, 0.1):
            x = next((r[0] - tc for r in cut if r[3] < thr), None)
            print(f"  hardware cut: bridge < {thr} V after {None if x is None else round(x, 2)} s")
    print("csv:", out)
    return 1 if abort else 0

if __name__ == "__main__":
    sys.exit(main())
