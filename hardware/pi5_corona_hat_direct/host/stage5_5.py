#!/usr/bin/env python3
"""Stage 5.5: bridge powered (GPIO25 high) while the PD contract goes 5 V -> 9 V, then
step-down per option (a): GPIO25 low BEFORE requesting 5 V (avoids TPS25947 reverse-current
blocking FLT), wait until bridge < VBUS - 0.5 V, re-enable GPIO25 at 5 V.
PD requests run in a worker thread so the 10 Hz abort loop stays live.
Abort (GPIO25 low first, then request 5 V) on: EFUSE_FLT/nFAULT low, OV trip high,
interlock open, VBUS or bridge > 10 V, out-of-band VBUS/bridge once a phase settles,
or debounced (median of 3) 3V3 rise > 20 mA. GPIO25 is always low on exit."""
import csv, subprocess, sys, threading, time
from smbus2 import SMBus
import gpiod
from gpiod.line import Direction, Bias
sys.path.insert(0, "/home/uge")
import husb238a

DT, HOLD9, SETTLE = 0.1, 10.0, 3.0
OUT = f"/home/uge/stage5_5a_{time.strftime('%Y%m%d_%H%M%S')}.csv"

def sh(*a): return subprocess.run(a, capture_output=True, text=True).stdout
def gpio25(level): sh("pinctrl", "set", "25", "op", "dh" if level else "dl")
def i3v3():
    try: return float(sh("vcgencmd", "pmic_read_adc", "3V3_SYS_A").split("=")[1].rstrip("A\n"))
    except Exception: return float("nan")
def ads(b, ch):
    b.write_i2c_block_data(0x48, 1, [0xC3 | (ch << 4), 0xE3]); time.sleep(0.0015)
    hi, lo = b.read_i2c_block_data(0x48, 0, 2); r = (hi << 8) | lo
    return (r - 65536 if r & 0x8000 else r) * 4.096 / 32768

pd = husb238a.HUSB238A(allow_write=True)
req_result = {}
def request(v):
    def run():
        try: req_result[v] = pd.request_fixed(v, max_volts=9)
        except Exception as e: req_result[v] = f"ERR {type(e).__name__}: {e}"
    th = threading.Thread(target=run, daemon=True); th.start(); return th

gpio25(0)
lines = {5: "nFAULT", 6: "EFUSE_FLT", 23: "INTLK", 26: "OVTRIP"}
req = gpiod.request_lines("/dev/gpiochip0", consumer="stage5_5",
        config={tuple(lines): gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.AS_IS)})
def gp(): return {n: req.get_value(l).value for l, n in lines.items()}

# expected bands per settled phase: (vbus_lo, vbus_hi, bridge_lo, bridge_hi)
BANDS = {"on5": (4.5, 5.6, 4.4, 5.4), "hold9": (8.5, 9.6, 8.0, 9.4), "re5": (4.5, 5.6, 4.4, 5.4)}
rows, abort = [], None
with SMBus(1) as b:
    c0 = b.read_byte_data(0x42, 0x67) >> 4; pdo9 = b.read_byte_data(0x42, 0x6B)
    vbus0 = ads(b, 2) * 118 / 18; br0 = ads(b, 3) * 11; g0 = gp()
    base3 = sorted(i3v3() for _ in range(5))[2]; g24 = sh("pinctrl", "lev", "24").strip()
    print(f"pre: PD_CONTRACT=0x{c0:x} SRC_PDO_9V=0x{pdo9:02x} VBUS={vbus0:.2f} bridge={br0:.3f} gpio={g0} GPIO24={g24} 3V3={base3*1000:.0f}mA")
    if not (c0 == 1 and pdo9 & 0x80 and 4.6 < vbus0 < 5.6 and br0 < 0.1 and g24 == "0"
            and g0 == {"nFAULT": 1, "EFUSE_FLT": 1, "INTLK": 1, "OVTRIP": 0}):
        print("PRECONDITION FAILED - GPIO25 not raised"); req.release(); sys.exit(2)

    t0 = time.monotonic(); n = 0; hist3 = []; last3 = base3
    phase, t_ph, worker, events = "on5", 0.0, None, []
    gpio25(1); events.append((0.0, "GPIO25 high"))
    try:
        while True:
            t = time.monotonic() - t0
            # phase sequencing
            if phase == "on5" and t >= 2.0:
                worker = request(9); phase, t_ph = "to9", t; events.append((round(t, 2), "request 9 V"))
            elif phase == "to9" and not worker.is_alive() and t >= t_ph + SETTLE:
                phase, t_ph = "hold9", t
            elif phase == "hold9" and t >= t_ph + HOLD9:
                gpio25(0); phase, t_ph = "drop9", t; events.append((round(t, 2), "GPIO25 low (before step-down)"))
            elif phase == "drop9" and t >= t_ph + 0.3:
                worker = request(5); phase, t_ph = "to5", t; events.append((round(t, 2), "request 5 V"))
            elif phase == "to5" and not worker.is_alive() and t >= t_ph + 1.0:
                phase, t_ph = "wait5", t
            elif phase == "wait5" and rows and rows[-1][3] < rows[-1][2] - 0.5:
                gpio25(1); phase, t_ph = "re5", t; events.append((round(t, 2), f"GPIO25 high again (bridge {rows[-1][3]:.2f} < VBUS {rows[-1][2]:.2f} - 0.5)"))
            elif phase == "wait5" and t >= t_ph + 15.0:
                gpio25(0); abort = (round(t, 3), "wait5", ["bridge did not fall below VBUS-0.5 within 15 s"]); phase, t_ph = "off", t
            elif phase == "re5" and t >= t_ph + 3.0:
                gpio25(0); phase, t_ph = "off", t; events.append((round(t, 2), "GPIO25 low"))
            elif phase == "off" and t >= t_ph + 5.0:
                break
            vb = ads(b, 2) * 118 / 18; br = ads(b, 3) * 11; g = gp()
            if n % 5 == 0:
                hist3.append(i3v3()); last3 = sorted(hist3[-3:])[len(hist3[-3:]) // 2]
            n += 1
            rows.append([round(t, 3), phase, round(vb, 3), round(br, 3), g["nFAULT"], g["EFUSE_FLT"], g["INTLK"], g["OVTRIP"], round(last3 * 1000, 1)])
            if phase != "off":
                why = []
                if g["EFUSE_FLT"] == 0: why.append("EFUSE_FLT low")
                if g["nFAULT"] == 0: why.append("DRV_nFAULT low")
                if g["OVTRIP"] == 1: why.append("OV trip high")
                if g["INTLK"] == 0: why.append("interlock opened")
                if vb > 10.0: why.append(f"VBUS {vb:.2f} V > 10")
                if br > 10.0: why.append(f"bridge {br:.2f} V > 10")
                if last3 - base3 > 0.020: why.append(f"3V3 +{(last3-base3)*1000:.0f} mA (median)")
                if phase in BANDS and (phase not in ("on5", "re5") or t > t_ph + 0.5):
                    vl, vh, bl, bh = BANDS[phase]
                    if not vl <= vb <= vh: why.append(f"{phase}: VBUS {vb:.2f} out of {vl}-{vh}")
                    if not bl <= br <= bh: why.append(f"{phase}: bridge {br:.2f} out of {bl}-{bh}")
                if phase == "wait5" and not 4.5 <= vb <= 5.6: why.append(f"wait5: VBUS {vb:.2f} out of 4.5-5.6")
                if why:
                    gpio25(0); abort = (round(t, 3), phase, why); events.append((round(t, 2), "ABORT -> GPIO25 low"))
                    phase, t_ph = "off", t
                    if worker is None or not worker.is_alive(): worker = request(5); events.append((round(t, 2), "abort: request 5 V"))
            time.sleep(max(0, DT - ((time.monotonic() - t0) - t)))
    finally:
        gpio25(0)
        if worker: worker.join(timeout=5)
    req.release()
    if abort:  # make sure we end at 5 V
        try: req_result["final5"] = pd.request_fixed(5, max_volts=5)
        except Exception as e: req_result["final5"] = f"ERR {e}"
    cf = b.read_byte_data(0x42, 0x67) >> 4

with open(OUT, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["t_s","phase","vbus_V","bridge_V","nFAULT","EFUSE_FLT","INTLK","OVTRIP","i3v3_mA"]); w.writerows(rows)
print("ABORT:" if abort else "completed, no abort", abort or "")
print("events:", events); print("PD request results:", req_result)
for ph in ("on5", "to9", "hold9", "drop9", "to5", "wait5", "re5", "off"):
    rs = [r for r in rows if r[1] == ph]
    if rs:
        f = lambda i: f"{min(r[i] for r in rs):.3f}..{max(r[i] for r in rs):.3f}"
        print(f"{ph:6s} n={len(rs):3d} t={rs[0][0]:5.2f}-{rs[-1][0]:5.2f}s VBUS {f(2)} bridge {f(3)} 3V3 {f(8)} mA "
              f"EFUSE_FLT {set(r[5] for r in rs)} nFAULT {set(r[4] for r in rs)} OVTRIP {set(r[7] for r in rs)} INTLK {set(r[6] for r in rs)}")
print(f"final PD_CONTRACT=0x{cf:x}; csv: {OUT}")
