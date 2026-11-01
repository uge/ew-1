#!/usr/bin/env python3
"""Stage 5.4 (derived from stage5_2.py): GPIO25 high, wait for the user to open a lid switch;
keep GPIO25 high CUT_HOLD s after GPIO23 falls to show the hardware K1/BULK_EN cut, then GPIO25 low.
Original 5.2/5.3 notes: GPIO25 (BULK_CMD) high for HOLD s at an explicit 5 V contract,
then low and record bridge decay. Auto-aborts (GPIO25 low) on any limit.
The 3V3 current check uses the median of the last 3 samples (single vcgencmd
readings spike by ~30-50 mA at idle); all other checks act on every sample."""
import csv, subprocess, sys, time
from smbus2 import SMBus
import gpiod
from gpiod.line import Direction, Bias

WAIT, CUT_HOLD, DECAY, DT = 60.0, 4.0, 3.0, 0.1
OUT = f"/home/uge/stage5_4_{time.strftime('%Y%m%d_%H%M%S')}.csv"

def sh(*a): return subprocess.run(a, capture_output=True, text=True).stdout
def gpio25(level): sh("pinctrl", "set", "25", "op", "dh" if level else "dl")
def i3v3():
    try: return float(sh("vcgencmd", "pmic_read_adc", "3V3_SYS_A").split("=")[1].rstrip("A\n"))
    except Exception: return float("nan")
def ads(b, ch):
    b.write_i2c_block_data(0x48, 1, [0xC3 | (ch << 4), 0xE3]); time.sleep(0.0015)
    hi, lo = b.read_i2c_block_data(0x48, 0, 2); r = (hi << 8) | lo
    return (r - 65536 if r & 0x8000 else r) * 4.096 / 32768

gpio25(0)
lines = {5: "nFAULT", 6: "EFUSE_FLT", 23: "INTLK", 26: "OVTRIP"}
req = gpiod.request_lines("/dev/gpiochip0", consumer="stage5",
        config={tuple(lines): gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.AS_IS)})
def gp(): return {n: req.get_value(l).value for l, n in lines.items()}

with SMBus(1) as b:
    c0 = b.read_byte_data(0x42, 0x67) >> 4
    vbus0 = ads(b, 2) * 118 / 18; br0 = ads(b, 3) * 11; g0 = gp()
    base3 = sum(i3v3() for _ in range(5)) / 5
    g24 = sh("pinctrl", "lev", "24").strip()
    print(f"pre: PD_CONTRACT=0x{c0:x} VBUS={vbus0:.2f} bridge={br0:.3f} gpio={g0} GPIO24={g24} 3V3={base3*1000:.0f}mA")
    pre_ok = (c0 == 1 and 4.6 < vbus0 < 5.6 and br0 < 0.1 and g24 == "0"
              and g0 == {"nFAULT": 1, "EFUSE_FLT": 1, "INTLK": 1, "OVTRIP": 0})
    if not pre_ok:
        print("PRECONDITION FAILED - GPIO25 not raised"); sys.exit(2)

    rows, abort, phase = [], None, "on"
    t0 = time.monotonic(); last3 = base3; n = 0; hist3 = []
    gpio25(1); t_on = time.monotonic()
    try:
        while True:
            t = time.monotonic() - t0
            if phase == "on" and t >= WAIT:
                gpio25(0); abort = (round(t, 3), ["interlock never opened (timeout)"]); phase = "decay"; t_off = t
            if phase == "cut" and t >= t_cut + CUT_HOLD:
                gpio25(0); phase = "decay"; t_off = t
            if phase == "decay" and t >= t_off + DECAY: break
            vb = ads(b, 2) * 118 / 18; br = ads(b, 3) * 11; g = gp()
            if n % 5 == 0:
                hist3.append(i3v3()); last3 = sorted(hist3[-3:])[len(hist3[-3:]) // 2]  # median of last 3
            n += 1
            rows.append([round(t, 3), phase, round(vb, 3), round(br, 3), g["nFAULT"], g["EFUSE_FLT"],
                         g["INTLK"], g["OVTRIP"], round(last3 * 1000, 1)])
            if phase == "on" and g["INTLK"] == 0:
                phase = "cut"; t_cut = t; rows[-1][1] = "cut"
            if phase == "cut" and g["INTLK"] == 1:
                gpio25(0); abort = (round(t, 3), ["interlock reclosed during cut hold"]); phase = "decay"; t_off = t
            if phase in ("on", "cut"):
                why = []
                if g["EFUSE_FLT"] == 0: why.append("EFUSE_FLT low")
                if g["nFAULT"] == 0: why.append("DRV_nFAULT low")
                if g["OVTRIP"] == 1: why.append("OV trip high")
                if vb < 4.5 or vb > 5.6: why.append(f"VBUS {vb:.2f} V")
                if br > 5.6: why.append(f"bridge {br:.2f} V high")
                if phase == "on" and t > 0.5 and br < 4.0: why.append(f"bridge {br:.2f} V low")
                if last3 - base3 > 0.020: why.append(f"3V3 +{(last3-base3)*1000:.0f} mA")
                if why:
                    gpio25(0); abort = (round(t, 3), why); phase = "decay"; t_off = t
            time.sleep(max(0, DT - ((time.monotonic() - t0) - t)))
    finally:
        gpio25(0)
    req.release()

with open(OUT, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["t_s","phase","vbus_V","bridge_V","nFAULT","EFUSE_FLT","INTLK","OVTRIP","i3v3_mA"]); w.writerows(rows)
on = [r for r in rows if r[1] == "on"]; cut = [r for r in rows if r[1] == "cut"]; dc = [r for r in rows if r[1] == "decay"]
def rng(rs, i): v=[r[i] for r in rs]; return f"{min(v):.3f}..{max(v):.3f}"
print("ABORT:" if abort else "completed, no abort", abort or "")
if on:
    print(f"ON   {len(on)} samples {on[0][0]:.2f}-{on[-1][0]:.2f}s VBUS {rng(on,2)} bridge {rng(on,3)} 3V3 {rng(on,8)} mA EFUSE_FLT {set(r[5] for r in on)} nFAULT {set(r[4] for r in on)} OVTRIP {set(r[7] for r in on)}")
if cut:
    tc = cut[0][0]
    print(f"CUT  interlock opened at t={tc:.2f}s with GPIO25 HIGH; {len(cut)} samples; INTLK {set(r[6] for r in cut)} EFUSE_FLT {set(r[5] for r in cut)}")
    for thr in (2.0, 1.0, 0.5, 0.1):
        x = next((r[0]-tc for r in cut if r[3] < thr), None); print(f"  hardware cut: bridge < {thr} V after {x if x is None else round(x,2)} s")
    print(f"  bridge at end of cut hold: {cut[-1][3]:.3f} V")
if dc: print(f"END  bridge {dc[-1][3]:.3f} V VBUS {dc[-1][2]:.2f} V INTLK {dc[-1][6]}")
print("csv:", OUT)
