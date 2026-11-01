#!/usr/bin/env python3
"""On-board test (ew-1) of Controller.start() refusals WITHOUT any possibility of HV.

stage7_ramp.run, any GPIO-high write and any PWM enable are replaced by functions that raise,
so nothing can be driven even if a check were broken. Reads the real board once (read-only,
under the HV lock so a running dashboard's monitor pauses) to show the live precondition result.
   python3 ~/dashboard/test_start_refusal.py
"""
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ew1_dashboard as D       # noqa: E402
R = D.R

calls = []
def no_run(*a, **k):
    calls.append("run"); raise AssertionError("stage7_ramp.run must not be called in this test")
real_gpio, real_pw = R.gpio, R.pw
def guard_gpio(n, level):
    if level: raise AssertionError(f"GPIO{n} high attempted")
    return real_gpio(n, level)
def guard_pw(path, val):
    if path.endswith("/enable") and str(val) != "0": raise AssertionError(f"PWM enable attempted: {path}")
    return real_pw(path, val)
R.run, R.gpio, R.pw = no_run, guard_gpio, guard_pw

PARAMS = {"vbus": 5, "freq_hz": 32000, "target_kv": 3.0, "abort_kv": 4.0, "max_duty": 0.1, "ain1_max_v": 0.1, "hold_s": 1.0}
mon = D.Monitor(threading.Lock())
ctl = D.Controller(mon, mon.bus_lock)
ok = True

def check(name, cond):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name)

# 1) live board snapshot, read-only, under the HV lock
lk = R.hv_lock(); time.sleep(0.5)
real = ctl._fresh_snapshot()
lk.close()
print("live snapshot:", {k: real[k] for k in ("ain0_v", "ain1_v", "vbus_v", "bridge_v", "gpio", "out", "pd_contract")})
live = D.check_preconditions(real, "ramp")
print("live preconditions (ramp):", live or "OK")
check("live: forcing interlock open is refused", D.check_preconditions(dict(real, gpio=dict(real["gpio"], INTLK=0))))

# 2) Controller.start() with faked fresh snapshots -> refusal, nothing driven, lock released
base = dict(real, gpio={"nFAULT": 1, "EFUSE_FLT": 1, "INTLK": 1, "OVTRIP": 0}, ain0_v=0.0, ain1_v=0.002,
            bridge_v=0.0, vbus_v=5.1, out={18: 0, 19: 0, 24: 0, 25: 0}, pd_contract="5V")
for name, snap in [("interlock open", dict(base, gpio=dict(base["gpio"], INTLK=0))),
                   ("nFAULT low", dict(base, gpio=dict(base["gpio"], nFAULT=0))),
                   ("OV trip latched", dict(base, gpio=dict(base["gpio"], OVTRIP=1))),
                   ("AIN0 0.2 V (HV present)", dict(base, ain0_v=0.2)),
                   ("PD contract 9V", dict(base, pd_contract="9V")),
                   ("GPIO24 high", dict(base, out={18: 0, 19: 0, 24: 1, 25: 0}))]:
    ctl._fresh_snapshot = lambda s=snap: s
    code, body = ctl.start("ramp", PARAMS)
    check(f"start refused: {name} -> {code} {body.get('errors')}", code == 412 and not calls and ctl.active is None)
    try:
        R.hv_lock().close(); check("  HV lock released afterwards", True)
    except R.HVLockBusy:
        check("  HV lock released afterwards", False)

# 3) lock held by another process -> 409 before any read
p = subprocess.Popen([sys.executable, "-c", "import sys,time; sys.path.insert(0,'/home/uge'); import stage7_ramp as R; "
                      "l=R.hv_lock(); print('held', flush=True); time.sleep(5)"], stdout=subprocess.PIPE, text=True)
p.stdout.readline()
ctl._fresh_snapshot = lambda: base
code, body = ctl.start("ramp", PARAMS)
check(f"start refused while another process holds the lock -> {code} {body.get('errors')}", code == 409 and not calls)
p.kill(); p.wait()
print("guards: stage7_ramp.run called" if calls else "guards: stage7_ramp.run never called")
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
