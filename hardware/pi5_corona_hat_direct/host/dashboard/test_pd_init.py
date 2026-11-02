#!/usr/bin/env python3
"""Unit test for ew1_dashboard.ensure_pd_5v() and the pd_auto_init setting, with NO hardware access.

The HV lock, pin reads, ADC reads and the HUSB238A driver are all replaced with fakes, so this can
run on ew-1 while the dashboard is up (it never touches I2C, GPIO or PWM):
    python3 ~/dashboard/test_pd_init.py
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ew1_dashboard as D       # noqa: E402
R = D.R

ok = True
def check(name, cond):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name)

class FakeLock:
    closed = 0
    def close(self): FakeLock.closed += 1

class Board:
    """Fake board state shared by the fakes below."""
    def __init__(self, contract="Type-C 5V (no PD)", g24=0, g25=0, bridge=0.0, vbus=5.1, epr=False,
                 lock_busy=False, request_ok=True):
        self.contract, self.g24, self.g25, self.bridge, self.vbus = contract, g24, g25, bridge, vbus
        self.epr, self.lock_busy, self.request_ok = epr, lock_busy, request_ok
        self.requests = []

B = Board()

def fake_lock():
    if B.lock_busy: raise R.HVLockBusy("held by test")
    return FakeLock()
class FakeBus:
    def __init__(self, n): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
def fake_ads(b, ch):
    return {3: B.bridge / 11, 2: B.vbus * 18 / 118}[ch]
class FakePD:
    def __init__(self, allow_write=False): self.allow_write = allow_write
    def status(self):
        return {"pd_contract": B.contract, "contract_ma": 3000 if B.contract == "5V" else None,
                "attached": B.contract != "Type-C 5V (no PD)", "source_epr_capable": B.epr}
    def request_fixed(self, volts, max_volts=5):
        assert self.allow_write and volts == 5 and max_volts == 5
        B.requests.append(volts)
        if B.request_ok: B.contract = "5V"
        return B.request_ok

R.hv_lock, R.lev, R.SMBus, R.ads = fake_lock, (lambda n: {24: B.g24, 25: B.g25}[n]), FakeBus, fake_ads
D.husb238a.HUSB238A = FakePD
events = []
D.EV.add = lambda level, msg: events.append((level, msg))

def case(name, board, expect, requests):
    global B
    B = board; events.clear(); before = FakeLock.closed
    got = D.ensure_pd_5v()
    check(f"{name}: returns {expect!r} (got {got!r})", got == expect)
    check(f"{name}: {requests} request(s) sent", len(B.requests) == requests)
    if not board.lock_busy:
        check(f"{name}: HV lock released", FakeLock.closed == before + 1)

case("no contract, safe", Board(), "established 5V", 1)
case("already 5V", Board(contract="5V"), "already 5V", 0)
case("GPIO24 high", Board(g24=1), "skipped: outputs not low", 0)
case("GPIO25 high", Board(g25=1), "skipped: outputs not low", 0)
case("bridge charged", Board(bridge=4.9), "skipped: bridge not discharged", 0)
case("no source on J3", Board(vbus=0.3), "skipped: VBUS out of range", 0)
case("HV lock busy", Board(lock_busy=True), "skipped: HV lock busy", 0)
case("request fails", Board(request_ok=False), "failed", 1)
case("EPR source", Board(epr=True), "established 5V", 1)
check("EPR source: error event logged", any(l == "error" and "EPR" in m for l, m in events))

# read_setting: default off, explicit true only
with tempfile.TemporaryDirectory() as td:
    D.SETTINGS_PATH = os.path.join(td, "settings.json")
    check("pd_auto_init absent -> False", D.read_setting("pd_auto_init", False) is False)
    json.dump({"camera_autorecord": True}, open(D.SETTINGS_PATH, "w"))
    check("pd_auto_init missing key -> False", D.read_setting("pd_auto_init", False) is False)
    json.dump({"pd_auto_init": True}, open(D.SETTINGS_PATH, "w"))
    check("pd_auto_init true -> True", D.read_setting("pd_auto_init", False) is True)
    json.dump({"pd_auto_init": "yes"}, open(D.SETTINGS_PATH, "w"))
    check("pd_auto_init 'yes' is not 'is True'", D.read_setting("pd_auto_init", False) is not True)

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
