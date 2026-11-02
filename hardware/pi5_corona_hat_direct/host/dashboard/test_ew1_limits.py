#!/usr/bin/env python3
"""Hardware-free tests for the dashboard's server-side limits and preconditions.
   python3 test_ew1_limits.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ew1_limits import CONFIRM_WORD, check_preconditions, validate_align_params, validate_run_params  # noqa: E402

GOOD = {"vbus": 9, "freq_hz": 32000, "target_kv": 10.0, "abort_kv": 11.0, "max_duty": 0.17,
        "ain1_max_v": 0.5, "hold_s": 10, "confirm": CONFIRM_WORD}
SAFE = {"ain0_v": 0.0003, "ain1_v": 0.0025, "vbus_v": 5.11, "bridge_v": 0.007,
        "gpio": {"nFAULT": 1, "EFUSE_FLT": 1, "INTLK": 1, "OVTRIP": 0},
        "out": {18: 0, 19: 0, 24: 0, 25: 0}, "pwm": {2: {"enable": 0}, 3: {"enable": 0}},
        "pd_contract": "5V", "run_active": False, "lock_holders": []}


class TestRunParams(unittest.TestCase):
    def test_good(self):
        p, e = validate_run_params(GOOD)
        self.assertEqual(e, [])
        self.assertEqual(p["vbus"], 9)

    def bad(self, **kw):
        d = dict(GOOD, **kw)
        p, e = validate_run_params(d)
        self.assertIsNone(p, kw)
        self.assertTrue(e, kw)
        return e

    def test_limits(self):
        self.bad(vbus=20); self.bad(vbus=5.5); self.bad(vbus=10)
        self.bad(freq_hz=19999); self.bad(freq_hz=100001); self.bad(freq_hz=32000.5)
        self.bad(target_kv=15.01, abort_kv=15.5); self.bad(abort_kv=15.51); self.bad(max_duty=0.26); self.bad(max_duty=0.5)
        self.bad(ain1_max_v=0.51); self.bad(hold_s=30.1); self.bad(hold_s=-1)
        self.bad(target_kv=6.0, abort_kv=6.0)
        self.bad(target_kv=float("nan")); self.bad(target_kv="inf"); self.bad(target_kv=True)
        self.bad(target_kv=[1]); self.bad(confirm="yes")

    def test_15kv_limits(self):
        # user 2026-11-01: allow up to 15 kV; abort capped at 15.5 kV, 1.46 kV below the 16.96 kV hardware trip
        for v in (5, 9, 12, 15):
            p, e = validate_run_params(dict(GOOD, vbus=v))
            self.assertEqual(e, [], v); self.assertEqual(p["vbus"], v)
        p, e = validate_run_params(dict(GOOD, vbus=15, target_kv=15.0, abort_kv=15.5))
        self.assertEqual(e, []); self.assertEqual((p["target_kv"], p["abort_kv"]), (15.0, 15.5))
        self.bad(target_kv=15.0, abort_kv=15.0)          # target must stay below abort

    def test_missing(self):
        d = dict(GOOD); del d["abort_kv"]
        self.assertIn("abort_kv: missing", validate_run_params(d)[1])
        d = dict(GOOD); del d["confirm"]
        self.assertTrue(validate_run_params(d)[1])
        self.assertTrue(validate_run_params([1, 2])[1])

    def test_align(self):
        self.assertEqual(validate_align_params({})[0], {"freq_hz": 32000})
        self.assertTrue(validate_align_params({"freq_hz": 150000})[1])


class TestPreconditions(unittest.TestCase):
    def test_safe_ok(self):
        self.assertEqual(check_preconditions(SAFE), [])

    def fails(self, mode="ramp", **kw):
        s = dict(SAFE, **kw)
        f = check_preconditions(s, mode)
        self.assertTrue(f, kw)
        return f

    def test_each(self):
        self.fails(gpio=dict(SAFE["gpio"], INTLK=0))
        self.fails(gpio=dict(SAFE["gpio"], nFAULT=0))
        self.fails(gpio=dict(SAFE["gpio"], EFUSE_FLT=0))
        self.fails(gpio=dict(SAFE["gpio"], OVTRIP=1))
        self.fails(gpio={})
        self.fails(ain0_v=0.05); self.fails(ain0_v=None)
        self.fails(ain1_v=0.2); self.fails(bridge_v=4.8); self.fails(vbus_v=9.0)
        self.fails(pd_contract="9V")
        self.fails(out={18: 0, 19: 0, 24: 1, 25: 0}); self.fails(out={18: 0, 19: 1, 24: 0, 25: 0})
        self.fails(out={})
        self.fails(pwm={2: {"enable": 1}, 3: {"enable": 0}})
        self.fails(run_active=True); self.fails(lock_holders=[1234])

    def test_align_allows_open_lid(self):
        s = dict(SAFE, gpio=dict(SAFE["gpio"], INTLK=0))
        self.assertEqual(check_preconditions(s, "align"), [])
        self.assertTrue(check_preconditions(s, "ramp"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
