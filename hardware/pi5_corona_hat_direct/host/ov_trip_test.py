#!/usr/bin/env python3
"""Live hardware OV-trip test at the REAL 16.96 kV threshold (user request 2026-11-01:
"try 17kv briefly to see if ov trips"). Board insulation is NOT qualified above ~15 kV
(AUDIT.md); the user was told and chose to proceed.

Sequence (one run, 9 V contract by default):
  1. Phase-synced complementary drive (stage7_ramp helpers), slew-limited ramp
     (duty step 0.001 / 20 ms while HV slope < 10 V/ms), up to max duty 0.5.
  2. EXPECT GPIO26 (HV_OV_TRIP) -> 1 near AIN0 = 2.781 V (16.96 kV nominal).
     Software backstop: AIN0 or predicted AIN0 (a0 + slope*16 ms) >= 3.03 V (~18.5 kV)
     -> immediate safe-stop and FAIL (hardware trip did not act).
  3. On trip: keep PWM + GPIO24/25 as-is for up to 50 ms and verify the HV stops rising
     (Q2 pulls DRV_nSLEEP low). If AIN0 exceeds trip + 0.08 V (~+0.5 kV) or the backstop,
     software safe-stop immediately (Q2 path FAIL).
  4. PWM off + GPIO25 low, but GPIO24 HIGH: verify GPIO26 stays 1 for 2 s while HV
     decays (D90 latch).
  5. GPIO24 low: verify GPIO26 -> 0 (D91 clear).
  6. GPIO24 high again with no drive: verify GPIO26 stays 0 (no false trip), then low.
  7. Full safe-stop, return to 5 V.
Usage: ov_trip_test.py [--vbus 9] [--freq 32000]
"""
import csv, sys, time
sys.path.insert(0, "/home/uge")
import stage7_ramp as R

KV = R.KV_PER_V
TRIP_EXPECT_V = 1.65 * (56.2 + 82) / 82          # 2.781 V HV_SENSE_BUF
BACKSTOP_V = 18.5 / KV                            # ~3.03 V
SLEW, D_STEP, STEP_DT, D0, MAX_D = 0.010, 0.001, 0.020, 0.005, 0.5
RAMP_TIMEOUT = 40.0

def main():
    a = sys.argv[1:]
    vbus = int(a[a.index("--vbus") + 1]) if "--vbus" in a else 9
    freq = int(a[a.index("--freq") + 1]) if "--freq" in a else 32000
    if vbus not in (5, 9): print("vbus 5 or 9 only"); return 2
    t0 = time.monotonic(); rows = []; res = {}
    def log(m): print(f"  [{time.monotonic()-t0:7.3f}s] {m}", flush=True)
    R.gpio(24, 0); R.gpio(25, 0)
    req = R.gpiod.request_lines("/dev/gpiochip0", consumer="ov_trip_test",
            config={tuple(R.lines): R.gpiod.LineSettings(direction=R.Direction.INPUT, bias=R.Bias.AS_IS)})
    gp = lambda: {n: req.get_value(l).value for l, n in R.lines.items()}
    b = R.SMBus(1); pd = R.husb238a.HUSB238A(allow_write=True)
    out = f"/home/uge/ov_trip_test_{vbus}V_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    verdict = "INCOMPLETE"; period = None
    last = {"vb": 0.0, "br": 0.0, "a1": 0.0}; n = [0]
    def sample(phase, D):
        a0 = R.ads(b, 0); k = n[0] % 3
        if k == 0: last["vb"] = R.ads(b, 2) * 118 / 18
        elif k == 1: last["br"] = R.ads(b, 3) * 11
        else: last["a1"] = R.ads(b, 1)
        n[0] += 1; g = gp()
        rows.append([round(time.monotonic() - t0, 4), phase, round(D, 4), round(a0, 4), round(last["vb"], 3),
                     round(last["br"], 3), round(last["a1"], 4), g["nFAULT"], g["EFUSE_FLT"], g["INTLK"], g["OVTRIP"],
                     R.lev(24), R.lev(25)])
        return a0, g
    def pwm_off():
        for ch in (2, 3):
            try: R.pw(f"{R.d(ch)}/enable", 0); R.pw(f"{R.d(ch)}/polarity", "normal")
            except OSError: pass
    try:
        c0 = b.read_byte_data(0x42, 0x67) >> 4; vb = R.ads(b, 2) * 118 / 18; a0 = R.ads(b, 0); g = gp()
        print(f"pre: PD=0x{c0:x} VBUS={vb:.2f} AIN0={a0:.4f} gpio={g} g18/19={R.lev1819()} "
              f"expect trip AIN0 {TRIP_EXPECT_V:.3f} V (~{TRIP_EXPECT_V*KV:.2f} kV), backstop {BACKSTOP_V:.3f} V", flush=True)
        if not (c0 == 1 and 4.6 < vb < 5.6 and a0 < 0.01 and g == {"nFAULT": 1, "EFUSE_FLT": 1, "INTLK": 1, "OVTRIP": 0}
                and R.lev1819() == (0, 0) and R.lev(24) == 0 and R.lev(25) == 0):
            print("PRECONDITION FAILED - nothing driven"); return 2
        period = R.pwm_prepare(freq); R.align(period, log); R.set_duty(period, D0); log(f"phase synced; duty {D0}")
        vb_band = (4.5, 5.6) if vbus == 5 else (8.5, 9.6)
        if vbus == 9:
            log(f"request 9 V AMS={pd.request_fixed(9, max_volts=9)}"); time.sleep(1.0)
            if not 8.5 <= R.ads(b, 2) * 118 / 18 <= 9.6: raise RuntimeError("VBUS not at 9 V")
        R.gpio(25, 1); log("GPIO25 high"); time.sleep(1.0)
        R.gpio(24, 1); log("GPIO24 high: DRIVE")
        # ---- 1-2: ramp until trip ----
        D = D0; hist = []; t_step = time.monotonic(); t_ramp = time.monotonic(); trip_t = None; a_trip = None
        while True:
            now = time.monotonic(); a0, g = sample("ramp", D); hist.append((now, a0)); hist = hist[-6:]
            slope = (hist[-1][1] - hist[0][1]) / (hist[-1][0] - hist[0][0]) if len(hist) >= 4 else 0.0
            pred = a0 + max(slope, 0) * R.TAU
            if g["OVTRIP"]:
                trip_t, a_trip = now, a0; log(f"*** HARDWARE OV TRIP: GPIO26=1 at AIN0 {a0:.3f} V (~{a0*KV:.2f} kV), duty {D:.3f}"); break
            why = []
            if a0 >= BACKSTOP_V or pred >= BACKSTOP_V: why.append(f"BACKSTOP AIN0 {a0:.3f} pred {pred:.3f} (~{max(a0,pred)*KV:.2f} kV) with NO hardware trip")
            if g["EFUSE_FLT"] == 0: why.append("EFUSE_FLT low")
            if g["nFAULT"] == 0: why.append("nFAULT low")
            if g["INTLK"] == 0: why.append("interlock opened")
            if last["a1"] > 0.10: why.append(f"AIN1 {last['a1']:.3f} V (>10 uA return)")
            if n[0] > 3 and not vb_band[0] <= last["vb"] <= vb_band[1]: why.append(f"VBUS {last['vb']:.2f}")
            if now - t_ramp > RAMP_TIMEOUT: why.append("ramp timeout without trip")
            if why:
                R.safe_stop(log); verdict = "FAIL/ABORT: " + "; ".join(why); log(verdict); raise StopIteration
            if now - t_step >= STEP_DT:
                t_step = now
                if slope * KV / 1000 < SLEW and D < MAX_D: D = R.set_duty(period, min(D + D_STEP, MAX_D))
                elif D >= MAX_D and abs(slope * KV / 1000) < 0.002 and now - t_ramp > 3:
                    R.safe_stop(log); verdict = f"NOT REACHED: plateau {a0*KV:.2f} kV at max duty {MAX_D} ({vbus} V)"; log(verdict); raise StopIteration
            time.sleep(0.001)
        res["trip_kv"] = a_trip * KV; res["trip_duty"] = D
        # ---- 3: hardware must stop the HV (PWM still running) ----
        peak = a_trip; q2_ok = True
        while time.monotonic() - trip_t < 0.050:
            a0, g = sample("post_trip_pwm_on", D); peak = max(peak, a0)
            if a0 > a_trip + 0.08 or a0 >= BACKSTOP_V:
                R.safe_stop(log); q2_ok = False; log(f"Q2 FAIL: HV still rising after trip (AIN0 {a0:.3f}) - software stop"); break
        res["post_trip_peak_kv"] = peak * KV; res["q2_ok"] = q2_ok
        log(f"50 ms after trip with PWM still on: AIN0 peak {peak:.3f} V (~{peak*KV:.2f} kV), now {a0:.3f} V; nFAULT {g['nFAULT']}")
        # ---- 4: latch hold with GPIO24 high, energy removed ----
        pwm_off(); R.gpio(25, 0); log("PWM off, GPIO25 low; GPIO24 kept HIGH for latch test")
        held = True; t4 = time.monotonic()
        while time.monotonic() - t4 < 2.0:
            a0, g = sample("latch_hold", 0)
            if g["OVTRIP"] == 0: held = False
            time.sleep(0.01)
        res["latch_held"] = held; log(f"latch after 2 s (HV now {a0*KV:.2f} kV): GPIO26={g['OVTRIP']} -> {'HELD (D90 OK)' if held else 'RELEASED (D90 FAIL)'}")
        # ---- 5: clear via GPIO24 low ----
        R.gpio(24, 0); time.sleep(0.05); g = gp(); res["cleared"] = g["OVTRIP"] == 0
        log(f"GPIO24 low -> GPIO26={g['OVTRIP']} -> {'CLEARED (D91 OK)' if res['cleared'] else 'NOT CLEARED (D91 FAIL)'}")
        # ---- 6: re-arm, no drive ----
        R.gpio(24, 1); time.sleep(0.2); g = gp(); res["no_false_trip"] = g["OVTRIP"] == 0; R.gpio(24, 0)
        log(f"GPIO24 high again, no drive: GPIO26={g['OVTRIP']} -> {'OK' if res['no_false_trip'] else 'FALSE TRIP'}")
        ok = q2_ok and held and res["cleared"] and res["no_false_trip"]
        verdict = ("PASS" if ok else "PARTIAL FAIL") + f": trip at ~{res['trip_kv']:.2f} kV"
    except StopIteration:
        pass
    except Exception as e:
        verdict = f"ERROR {type(e).__name__}: {e}"
    finally:
        R.safe_stop(log)
        ts = time.monotonic()
        while time.monotonic() - ts < 5.0:
            try: sample("decay", 0)
            except Exception: break
            time.sleep(0.02)
        if vbus == 9:
            try: log(f"request 5 V AMS={pd.request_fixed(5, max_volts=5)}")
            except Exception as e: log(f"request 5 V FAILED {e}")
        try: req.release()
        except Exception: pass
        b.close()
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "phase", "duty", "ain0_V", "vbus_V", "bridge_V", "ain1_V", "nFAULT", "EFUSE_FLT", "INTLK", "OVTRIP", "g24", "g25"])
        w.writerows(rows)
    mx = max((r[3] for r in rows), default=0)
    print(f"max AIN0 {mx:.3f} V (~{mx*KV:.2f} kV)  max AIN1 {max((r[6] for r in rows), default=0):.4f} V")
    print("VERDICT:", verdict, res); print("csv:", out)
    return 0 if verdict.startswith("PASS") else 1

if __name__ == "__main__":
    sys.exit(main())
