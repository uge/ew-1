#!/usr/bin/env python3
"""ew-1 HV board dashboard: live monitoring + ramp control over HTTP (stdlib only).

  python3 ew1_dashboard.py [--port 8080] [--bind 0.0.0.0]

Monitoring (GET) is open on the LAN. Control (POST) needs the token in ~/.ew1-dashboard-token,
sent as header "X-EW1-Token". HV is only ever driven through stage7_ramp.run() (phase sync,
slew-limited ramp, predictive abort, regulated hold, all of its aborts). See README.md.
"""
import argparse
import atexit
import collections
import copy
import glob
import hmac
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))       # ~/ on ew-1 (stage7_ramp, husb238a), host/ in the repo
import stage7_ramp as R                          # noqa: E402
import husb238a                                  # noqa: E402
import gpiod                                     # noqa: E402
from gpiod.line import Bias, Direction           # noqa: E402
from smbus2 import SMBus                         # noqa: E402
from bme280 import BME280                        # noqa: E402
import tsl2591                                   # noqa: E402
from ew1_limits import (LIMITS, DEFAULTS, CONFIRM_WORD, DO_NOT_TOUCH_S,  # noqa: E402
                        validate_run_params, validate_align_params, check_preconditions)
from ew1_safestop import lock_holder_pids        # noqa: E402

HOME = os.path.expanduser("~")
TOKEN_PATH = os.path.join(HOME, ".ew1-dashboard-token")
RUNS_DIR = os.path.join(HOME, "dashboard_runs")
LAST_HV_PATH = os.path.join(RUNS_DIR, "last_hv.json")
SETTINGS_PATH = os.path.join(RUNS_DIR, "settings.json")
CAMERA_PORT = 8081
CAMERA_URL = f"http://127.0.0.1:{CAMERA_PORT}"
RUN_BUF_DT = 0.010              # run-graph samples kept at <= 100 Hz
STATIC = os.path.join(HERE, "static")
KV = R.KV_PER_V
HEARTBEAT_TIMEOUT_S = 2.0       # an HV run aborts if no control client heartbeats for this long
SAMPLE_STALL_S = 1.0            # an HV run aborts if the control loop stops producing samples
IN_LINES = {5: "nFAULT", 6: "EFUSE_FLT", 23: "INTLK", 26: "OVTRIP"}
RUN_COLS = ["t_s", "phase", "duty", "kv", "pred_kv", "i_ua", "bridge_v", "vbus_v"]

shutdown_evt = threading.Event()


# ------------------------------------------------------------------ events
class Events:
    def __init__(self, n=600):
        self.buf = collections.deque(maxlen=n)
        self.lock = threading.Lock()
        self.next_id = 1

    def add(self, level, msg):
        with self.lock:
            e = {"id": self.next_id, "t": time.time(), "level": level, "msg": msg}
            self.next_id += 1
            self.buf.append(e)
        print(f"{time.strftime('%H:%M:%S')} [{level}] {msg}", flush=True)

    def since(self, eid):
        with self.lock:
            return [e for e in self.buf if e["id"] > eid]


EV = Events()


def info(m): EV.add("info", m)
def warn(m): EV.add("warn", m)
def err(m): EV.add("error", m)


def do_safe_stop(why):
    """The one safe-stop (stage7_ramp.safe_stop): GPIO24 low -> PWM off -> normal -> GPIO25 low."""
    try:
        R.safe_stop(lambda m: info(f"{m} ({why})"))
        return True
    except Exception as e:
        err(f"safe-stop error ({why}): {type(e).__name__}: {e}")
        # fall back to the raw pin writes in the required order
        try:
            R.gpio(24, 0)
        except Exception:
            pass
        for ch in (2, 3):
            try:
                R.pw(f"{R.d(ch)}/enable", 0); R.pw(f"{R.d(ch)}/polarity", "normal")
            except Exception:
                pass
        try:
            R.gpio(25, 0)
        except Exception:
            pass
        return False


# ------------------------------------------------------------------ camera helper (separate process)
CAM_TOKEN = {"t": ""}


def camera_call(path, body=None, timeout=1.0):
    """Talk to ew1_camera.py on localhost. Never raises; returns {"error": ...} on failure."""
    try:
        if body is None:
            req = urllib.request.Request(CAMERA_URL + path)
        else:
            req = urllib.request.Request(CAMERA_URL + path, data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "X-EW1-Token": CAM_TOKEN["t"]})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"error": f"HTTP {e.code}"}
    except Exception as e:
        return {"error": f"camera helper unreachable: {type(e).__name__}"}


def camera_poller(ctl):
    while not shutdown_evt.is_set():
        st = camera_call("/status", timeout=1.0)
        st["ok"] = "error" not in st or "tools" in st
        ctl.camera = st
        shutdown_evt.wait(3.0)


def spawn_camera():
    try:
        return subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "ew1_camera.py"), "--port", str(CAMERA_PORT),
                                 "--watch-stdin"], stdin=subprocess.PIPE, start_new_session=True)
    except Exception as e:
        warn(f"camera helper not started: {e}")
        return None


# ------------------------------------------------------------------ slow history (10 min @ 1 Hz)
SLOW_KEYS = ("hv_kv", "i_ua", "vbus_v", "bridge_v", "i3v3_ma", "v3v3_v", "t_c", "p_hpa", "rh_pct", "lux")
SLOW = collections.deque(maxlen=600)


def historian(mon, ctl):
    while not shutdown_evt.wait(1.0):
        try:
            st = build_state(mon, ctl)
            b = st.get("bme") or {}
            t = st.get("tsl") or {}
            vals = {"hv_kv": st["hv_kv"], "i_ua": st["i_ua"], "vbus_v": st["vbus_v"], "bridge_v": st["bridge_v"],
                    "i3v3_ma": st["i3v3_ma"], "v3v3_v": st["v3v3_v"], "t_c": b.get("t_c"), "p_hpa": b.get("p_hpa"),
                    "rh_pct": b.get("rh_pct"), "lux": t.get("lux")}
            SLOW.append([round(st["t"], 1)] + [None if vals[k] is None else round(vals[k], 4) for k in SLOW_KEYS])
        except Exception as e:
            print("historian:", e, flush=True)


# ------------------------------------------------------------------ token
def load_token():
    if os.path.exists(TOKEN_PATH):
        os.chmod(TOKEN_PATH, 0o600)
        with open(TOKEN_PATH) as f:
            t = f.read().strip()
        if t:
            return t
    t = secrets.token_urlsafe(24)
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(t + "\n")
    info(f"generated new control token in {TOKEN_PATH}")
    return t


# ------------------------------------------------------------------ hardware reads (no writes)
def sh(*a, timeout=2.0):
    try:
        return subprocess.run(a, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def read_outputs():
    """Levels/funcs of GPIO18/19/24/25 from `pinctrl get` (instantaneous; not a phase measurement)."""
    out, func = {}, {}
    for line in sh("pinctrl", "get", "18,19,24,25").splitlines():
        m = re.match(r"\s*(\d+):\s+(\S+)(?:\s+(\S+))?\s+\S+\s+\|\s+(hi|lo)", line)
        if m:
            pin = int(m.group(1))
            out[pin] = 1 if m.group(4) == "hi" else 0
            func[pin] = m.group(2) + ("" if not m.group(3) or m.group(3) == "|" else " " + m.group(3))
    return out, func


def read_pwm():
    res = {}
    for ch in (2, 3):
        p = R.d(ch)
        if not os.path.isdir(p):
            res[ch] = {"exported": False}
            continue
        st = {"exported": True}
        for k in ("enable", "polarity", "period", "duty_cycle"):
            try:
                v = R.pr(f"{p}/{k}")
                st[k] = v if k == "polarity" else int(v)
            except Exception:
                st[k] = None
        if st.get("period"):
            st["freq_hz"] = round(1e9 / st["period"])
            st["duty"] = round(st["duty_cycle"] / st["period"], 4) if st.get("duty_cycle") is not None else None
        res[ch] = st
    return res


def read_i3v3_median():
    v = sorted(R.i3v3() for _ in range(3))
    return v[1]


def read_v3v3():
    try:
        return float(sh("vcgencmd", "pmic_read_adc", "3V3_SYS_V").split("=")[1].strip().rstrip("V"))
    except Exception:
        return None


def read_gpio_inputs():
    with gpiod.request_lines("/dev/gpiochip0", consumer="ew1-dashboard",
                             config={tuple(IN_LINES): gpiod.LineSettings(direction=Direction.INPUT,
                                                                          bias=Bias.AS_IS)}) as req:
        return {n: req.get_value(l).value for l, n in IN_LINES.items()}


# ------------------------------------------------------------------ monitor
class Monitor(threading.Thread):
    """Polls the board when no HV owner exists. I2C/ADC polling pauses while the HV lock is held
    by anyone (this dashboard's run or a CLI stage7_ramp.py), so it never disturbs a control loop."""

    def __init__(self, bus_lock):
        super().__init__(daemon=True, name="monitor")
        self.bus_lock = bus_lock
        self.lock = threading.Lock()
        self.s = {"t": 0, "ain_v": [None] * 4, "gpio": {}, "out": {}, "out_func": {}, "pwm": {},
                  "bme": None, "pd": None, "tsl2591": None, "tsl": None, "i3v3_a": None, "v3v3": None, "errors": {},
                  "i2c_paused": False, "t_i2c": 0}
        self.history = collections.deque(maxlen=3000)      # (epoch, kV, uA)
        self.bme = None
        self.tsl = None
        self.paused = False

    def snap(self):
        with self.lock:
            return copy.deepcopy(self.s)

    def _set(self, **kw):
        with self.lock:
            self.s.update(kw)

    def _err(self, key, e):
        with self.lock:
            if e is None:
                self.s["errors"].pop(key, None)
            else:
                self.s["errors"][key] = f"{type(e).__name__}: {e}"

    def run(self):
        n = 0
        last_bme = last_pd = last_tsl = last_3v3 = 0.0
        bus = None
        while not shutdown_evt.is_set():
            t_cycle = time.monotonic()
            # non-I2C state: always (cheap; never touches the ADC or the PWM)
            try:
                out, func = read_outputs()
                self._set(out=out, out_func=func, pwm=read_pwm())
                self._err("pins", None)
            except Exception as e:
                self._err("pins", e)
            holders = [p for p in lock_holder_pids() if p != os.getpid()]
            own = os.getpid() in lock_holder_pids()
            if holders or own or self.paused or not self.bus_lock.acquire(blocking=False):
                self._set(i2c_paused=True, lock_holders=holders, t=time.time())
                time.sleep(0.2)          # keep the bus fd open (no traffic); the sensor objects hold it
                continue
            try:
                if bus is None:
                    bus = SMBus(1)
                now = time.monotonic()
                try:
                    ain = [R.ads(bus, ch) for ch in range(4)]
                    self._set(ain_v=[round(v, 5) for v in ain], t_i2c=time.time())
                    self.history.append((time.time(), ain[0] * KV, ain[1] * 100))
                    self._err("ads1115", None)
                except Exception as e:
                    self._err("ads1115", e)
                try:
                    self._set(gpio=read_gpio_inputs())
                    self._err("gpio", None)
                except Exception as e:
                    self._set(gpio={})
                    self._err("gpio", e)
                if now - last_bme >= 1.0:
                    last_bme = now
                    try:
                        if self.bme is None:
                            self.bme = BME280(bus)
                            info("BME280 configured (normal mode, 1 s standby)")
                        self._set(bme=self.bme.read())
                        self._err("bme280", None)
                    except Exception as e:
                        self.bme = None
                        self._err("bme280", e)
                if now - last_pd >= 2.0:
                    last_pd = now
                    try:
                        st = husb238a.HUSB238A(allow_write=False).status()     # read-only
                        self._set(pd={k: st[k] for k in ("pd_contract", "contract_ma", "attached", "pd_comm",
                                                          "ams_in_progress", "fault", "thermal_shutdown",
                                                          "cc_advertised", "dpm_contract")},
                                  pd_pdos=[v for v, p in st["src_fixed_pdos"].items() if p["detect"]])
                        self._err("husb238a", None)
                    except Exception as e:
                        self._err("husb238a", e)
                # TSL2591: probe at start and every 30 s while absent; read at 1 Hz while present
                if (self.tsl is None and (last_tsl == 0.0 or now - last_tsl >= 30.0)) or \
                        (self.tsl is not None and now - last_tsl >= 1.0):
                    last_tsl = now
                    try:
                        if self.tsl is None:
                            if tsl2591.probe(bus):
                                self.tsl = tsl2591.TSL2591(bus)
                                info("TSL2591 detected at 0x29 (gain 25x, 100 ms)")
                            else:
                                self._set(tsl2591=False, tsl=None)
                        if self.tsl is not None:
                            self._set(tsl2591=True, tsl=self.tsl.read())
                        self._err("tsl2591", None)
                    except Exception as e:
                        if self.tsl is not None:
                            warn(f"TSL2591 lost: {e}")
                        self.tsl = None
                        self._set(tsl2591=False, tsl=None)
            except Exception as e:
                self._err("i2c", e)
                try:
                    bus.close()
                except Exception:
                    pass
                bus = None
                self.bme = None
                self.tsl = None
            finally:
                self.bus_lock.release()
            # vcgencmd (no I2C) also paused during runs; the run reports its own 3V3 samples
            if time.monotonic() - last_3v3 >= 1.5:
                last_3v3 = time.monotonic()
                try:
                    v = read_i3v3_median()
                    self._set(i3v3_a=v if v == v else None, v3v3=read_v3v3())
                except Exception as e:
                    self._err("3v3", e)
            self._set(i2c_paused=False, lock_holders=[], t=time.time())
            n += 1
            time.sleep(max(0.0, 0.1 - (time.monotonic() - t_cycle)))
        if bus is not None:
            bus.close()


# ------------------------------------------------------------------ controller
class Controller:
    def __init__(self, monitor, bus_lock):
        self.mon = monitor
        self.bus_lock = bus_lock
        self.lock = threading.Lock()
        self.active = None          # dict describing the active run, or None
        self.stop = None
        self.thread = None
        self.last_sample = None     # dict from on_sample
        self.last_sample_mono = 0.0
        self.live_started = False
        self.heartbeat = 0.0
        self.last_run = None
        self.last_hv = self._load_last_hv()
        self.run_id = 0
        self.run_buf = []           # compact samples of the current/last run for the live graphs
        self.run_meta = None        # {"run_id", "mode", "params", "t_start", "csv", "video"}
        self.settings = self._load_settings()
        self.camera = {"ok": False}

    def _load_settings(self):
        s = {"camera_autorecord": False}
        try:
            with open(SETTINGS_PATH) as f:
                s.update(json.load(f))
        except Exception:
            pass
        return s

    def save_settings(self, upd):
        if "camera_autorecord" in upd:
            if not isinstance(upd["camera_autorecord"], bool):
                raise ValueError("camera_autorecord must be true/false")
            self.settings["camera_autorecord"] = upd["camera_autorecord"]
        with open(SETTINGS_PATH, "w") as f:
            json.dump(self.settings, f)
        info(f"settings: {self.settings}")
        return self.settings

    # -- persistence
    def _load_last_hv(self):
        try:
            with open(LAST_HV_PATH) as f:
                return json.load(f)
        except Exception:
            pass
        # seed from the newest CLI HV run on ew-1 (file mtime = end of the run)
        files = glob.glob(os.path.join(HOME, "stage7_ramp_ramp_*.csv")) + glob.glob(os.path.join(HOME, "ov_trip_test_*.csv"))
        if files:
            newest = max(files, key=os.path.getmtime)
            return {"t_end": os.path.getmtime(newest), "source": os.path.basename(newest)}
        return None

    def _save_last_hv(self, rec):
        self.last_hv = rec
        try:
            with open(LAST_HV_PATH, "w") as f:
                json.dump(rec, f)
        except Exception as e:
            warn(f"could not save last_hv: {e}")

    # -- state for the UI
    def status(self):
        with self.lock:
            a = dict(self.active) if self.active else None
            s = dict(self.last_sample) if self.last_sample else None
        return {"active": a, "sample": s, "last_run": self.last_run, "last_hv": self.last_hv,
                "run_id": self.run_id, "run_meta": self.run_meta, "run_n": len(self.run_buf),
                "heartbeat_age_s": round(time.monotonic() - self.heartbeat, 2) if a else None}

    def beat(self):
        self.heartbeat = time.monotonic()

    # -- samples published by the control loop
    def _on_sample(self, row, extra):
        phase = row[1]
        smp = {"t": time.time(), "t_run": row[0], "phase": phase, "duty": row[2], "ain0_v": row[3],
               "kv": row[3] * KV if isinstance(row[3], (int, float)) else None,
               "pred_kv": row[4] * KV if isinstance(row[4], (int, float)) else None,
               "slope_kv_ms": row[5] if row[5] != "" else None,
               "vbus_v": row[6] if row[6] != "" else None, "bridge_v": row[7] if row[7] != "" else None,
               "ain1_v": row[8] if row[8] != "" else None,
               "gpio": None if row[9] == "" else {"nFAULT": row[9], "EFUSE_FLT": row[10], "INTLK": row[11],
                                                   "OVTRIP": row[12]}}
        if extra.get("i3v3") is not None:
            smp["i3v3_a"] = extra["i3v3"]
        with self.lock:
            prev = self.last_sample or {}
            for k in ("vbus_v", "bridge_v", "ain1_v", "gpio", "i3v3_a"):     # keep last known value
                if smp.get(k) is None and prev.get(k) is not None:
                    smp[k] = prev[k]
            self.last_sample = smp
            self.last_sample_mono = time.monotonic()
            if phase in ("ramp", "hold"):
                self.live_started = True
            if self.active:
                self.active["phase"] = phase
        ua = smp["ain1_v"] * 100 if smp.get("ain1_v") is not None else None
        rb = self.run_buf
        if not rb or row[0] - rb[-1][0] >= RUN_BUF_DT or phase != rb[-1][1]:
            rb.append([row[0], phase, row[2], None if smp["kv"] is None else round(smp["kv"], 4),
                       None if smp["pred_kv"] is None else round(smp["pred_kv"], 4),
                       None if ua is None else round(ua, 3), smp.get("bridge_v"), smp.get("vbus_v")])
        h = self.mon.history
        if not h or smp["t"] - h[-1][0] >= 0.02:
            h.append((smp["t"], smp["kv"], ua))

    def _out(self, m):
        m = m.rstrip()
        if m:
            (warn if ("ABORT" in m or "FAILED" in m or "REFUSED" in m) else info)(m.strip())

    # -- fresh precondition read (caller holds bus_lock and the HV lock)
    def _fresh_snapshot(self):
        with SMBus(1) as b:
            ain = [R.ads(b, ch) for ch in range(4)]
        pd = husb238a.HUSB238A(allow_write=False).status()["pd_contract"]
        out, _ = read_outputs()
        return {"ain0_v": ain[0], "ain1_v": ain[1], "vbus_v": ain[2] * 118 / 18, "bridge_v": ain[3] * 11,
                "gpio": read_gpio_inputs(), "out": out, "pwm": read_pwm(), "pd_contract": pd,
                "run_active": False, "lock_holders": []}

    def start(self, mode, params):
        """Returns (http_status, body)."""
        with self.lock:
            if self.active:
                return 409, {"ok": False, "errors": ["a run is already active"]}
            self.active = {"mode": mode, "params": params, "state": "starting", "t_start": time.time(), "phase": "pre"}
        lk = None
        have_bus = False
        handed_off = False
        try:
            try:
                lk = R.hv_lock()
            except R.HVLockBusy as e:
                return 409, {"ok": False, "errors": [str(e)]}
            self.mon.paused = True
            have_bus = self.bus_lock.acquire(timeout=3.0)
            if not have_bus:
                return 503, {"ok": False, "errors": ["monitor did not release the I2C bus"]}
            snap = self._fresh_snapshot()
            fails = check_preconditions(snap, mode=mode)
            if fails:
                warn(f"{mode} refused: " + "; ".join(fails))
                return 412, {"ok": False, "errors": fails, "snapshot": snap}
            self.stop = threading.Event()
            self.run_id += 1
            self.run_buf = []
            self.run_meta = {"run_id": self.run_id, "mode": mode, "params": params, "t_start": time.time(),
                             "csv": None, "video": None}
            self.last_sample = None
            self.live_started = False
            self.beat()
            with self.lock:
                self.active["state"] = "running"
            self.thread = threading.Thread(target=self._worker, args=(mode, params, lk), daemon=True, name="hvrun")
            self.thread.start()
            handed_off = True  # ownership of the HV lock and the bus passes to the worker
            info(f"{mode} started: {json.dumps(params)}")
            return 200, {"ok": True}
        except Exception as e:
            err(f"{mode} start failed: {type(e).__name__}: {e}")
            do_safe_stop("start failure")
            return 500, {"ok": False, "errors": [f"{type(e).__name__}: {e}"]}
        finally:
            if not handed_off:
                if have_bus:
                    self.bus_lock.release()
                if lk is not None:
                    lk.close()
                self.mon.paused = False
                with self.lock:
                    self.active = None

    def _worker(self, mode, p, lk):
        t_start = time.time()
        res = None
        hv = False
        video = None
        tmp_name = time.strftime("cam_run_%Y%m%d_%H%M%S", time.localtime(t_start))
        if mode == "ramp" and self.settings.get("camera_autorecord") and self.camera.get("detected"):
            r = camera_call("/record/start", {"name": tmp_name}, timeout=5.0)
            if r.get("file"):
                video = r
                info(f"camera recording started: {r['file']}")
            else:
                warn(f"camera auto-record failed: {r.get('error')}")
        try:
            if mode == "ramp":
                res = R.run("ramp", freq=p["freq_hz"], vbus=p["vbus"], target_kv=p["target_kv"],
                            max_d=p["max_duty"], hold=p["hold_s"], abort_kv=p["abort_kv"],
                            ain1_max=p["ain1_max_v"], out_dir=RUNS_DIR,
                            on_sample=self._on_sample, stop=self.stop, out=self._out)
                hv = not res.get("precondition_failed")
            else:
                res = R.run("align", freq=p["freq_hz"], out_dir=RUNS_DIR,
                            on_sample=self._on_sample, stop=self.stop, out=self._out)
        except Exception as e:
            err(f"run crashed: {type(e).__name__}: {e}")
            traceback.print_exc()
            hv = mode == "ramp"
        finally:
            do_safe_stop("end of run")           # run() already did; repeat on every path
            t_end = time.time()
            if video:
                v = camera_call("/record/stop", {}, timeout=30.0)
                video.update({k: v.get(k) for k in ("bytes", "t1")})
                if res and res.get("csv") and v.get("file"):
                    ext = os.path.splitext(v["file"])[1]
                    new = os.path.splitext(os.path.basename(res["csv"]))[0] + ext
                    try:
                        os.rename(os.path.join(RUNS_DIR, v["file"]), os.path.join(RUNS_DIR, new))
                        video["file"] = new
                    except OSError as e:
                        warn(f"could not rename video: {e}")
                video["offset_s"] = round(video["t0"] - t_start, 3) if video.get("t0") else None
                info(f"camera recording saved: {video['file']} ({video.get('bytes')} bytes)")
            try:
                self.bus_lock.release()
            except RuntimeError:
                pass
            lk.close()
            self.mon.paused = False
            rec = {"mode": mode, "params": p, "t_start": t_start, "t_end": t_end,
                   "code": res.get("code") if res else None, "abort": res.get("abort") if res else "crash",
                   "result": res.get("result") if res else None,
                   "csv": os.path.basename(res["csv"]) if res and res.get("csv") else None,
                   "events": res.get("events") if res else None,
                   "precondition_failed": res.get("precondition_failed") if res else None,
                   "stop_reason": self.active.get("stop_reason") if self.active else None,
                   "video": video, "t_start_note": "CSV t_s is seconds from run() start (~t_start)"}
            if self.run_meta:
                self.run_meta.update(csv=rec["csv"], video=(video or {}).get("file"), t_end=t_end,
                                     abort=rec["abort"], result=rec["result"])
            if mode == "ramp" and hv:
                peak = (res or {}).get("result", {}).get("peak_kv")
                self._save_last_hv({"t_end": t_end, "source": rec["csv"], "peak_kv": peak})
            stem = os.path.splitext(rec["csv"])[0] if rec["csv"] else \
                f"stage7_ramp_{mode}_{p.get('vbus', 5)}V_{time.strftime('%Y%m%d_%H%M%S', time.localtime(t_start))}"
            try:
                with open(os.path.join(RUNS_DIR, stem + ".json"), "w") as f:
                    json.dump(rec, f, indent=1, default=str)
            except Exception as e:
                warn(f"could not write run summary: {e}")
            self.last_run = {k: rec[k] for k in ("mode", "t_start", "t_end", "code", "abort", "csv",
                                                 "result", "stop_reason")}
            lvl = warn if rec["abort"] else info
            lvl(f"{mode} finished: {'ABORT - ' + str(rec['abort']) if rec['abort'] else 'completed'}"
                f"{' csv ' + rec['csv'] if rec['csv'] else ''}")
            with self.lock:
                self.active = None

    def request_stop(self, why):
        with self.lock:
            a = self.active
            if a:
                a["stop_reason"] = why
        if self.stop is not None:
            self.stop.set()
        return do_safe_stop(why)

    def watchdog(self):
        while not shutdown_evt.is_set():
            time.sleep(0.1)
            with self.lock:
                a = self.active
                live = self.live_started
                phase = self.last_sample.get("phase") if self.last_sample else None
                age = time.monotonic() - self.last_sample_mono
            if not a or a.get("state") != "running" or self.stop is None or self.stop.is_set():
                continue
            why = None
            if a["mode"] == "ramp" and time.monotonic() - self.heartbeat > HEARTBEAT_TIMEOUT_S:
                why = f"watchdog: no control-client heartbeat for {HEARTBEAT_TIMEOUT_S} s"
            elif live and phase in ("ramp", "hold") and age > SAMPLE_STALL_S:
                why = f"watchdog: control loop stalled ({age:.2f} s without a sample)"
            elif a["mode"] == "ramp" and time.time() - a["t_start"] > R.RAMP_TIMEOUT + a["params"]["hold_s"] + 30:
                why = "watchdog: run exceeded its maximum duration"
            if why:
                warn(why)
                self.request_stop(why)


# ------------------------------------------------------------------ snapshot for clients
def build_state(mon, ctl):
    s = mon.snap()
    c = ctl.status()
    ain = s["ain_v"]
    st = {
        "t": time.time(), "source": "monitor",
        "hv_kv": ain[0] * KV if ain[0] is not None else None,
        "ain0_v": ain[0], "ain1_v": ain[1],
        "i_ua": ain[1] * 100 if ain[1] is not None else None,
        "vbus_v": ain[2] * 118 / 18 if ain[2] is not None else None,
        "bridge_v": ain[3] * 11 if ain[3] is not None else None,
        "i3v3_ma": s["i3v3_a"] * 1000 if s.get("i3v3_a") is not None else None,
        "gpio": s["gpio"], "out": {str(k): v for k, v in s["out"].items()}, "out_func": s["out_func"],
        "v3v3_v": s.get("v3v3"),
        "pwm": s["pwm"], "bme": s["bme"], "pd": s["pd"], "pd_pdos": s.get("pd_pdos"),
        "tsl2591": s["tsl2591"], "tsl": s.get("tsl"), "errors": s["errors"], "i2c_paused": s["i2c_paused"],
        "camera": ctl.camera, "settings": ctl.settings,
        "lock_holders": s.get("lock_holders", []), "t_i2c": s.get("t_i2c"),
        "run": c,
    }
    smp = c.get("sample")
    if smp and (c["active"] or time.time() - smp["t"] < 1.0):
        st["source"] = "run"
        st["hv_kv"] = smp["kv"]; st["ain0_v"] = smp["ain0_v"]
        if smp.get("ain1_v") is not None:
            st["ain1_v"] = smp["ain1_v"]; st["i_ua"] = smp["ain1_v"] * 100
        if smp.get("vbus_v") is not None:
            st["vbus_v"] = smp["vbus_v"]
        if smp.get("bridge_v") is not None:
            st["bridge_v"] = smp["bridge_v"]
        if smp.get("gpio"):
            st["gpio"] = smp["gpio"]
        if smp.get("i3v3_a") is not None:
            st["i3v3_ma"] = smp["i3v3_a"] * 1000
    lh = c.get("last_hv")
    if lh and lh.get("t_end"):
        st["since_hv_s"] = time.time() - lh["t_end"]
        st["do_not_touch_s"] = max(0.0, DO_NOT_TOUCH_S - st["since_hv_s"])
    else:
        st["since_hv_s"] = None
        st["do_not_touch_s"] = 0.0
    if c["active"] and c["active"]["mode"] == "ramp":
        st["do_not_touch_s"] = DO_NOT_TOUCH_S
    # precondition preview (from the monitor snapshot; the real check is re-done fresh at start)
    pre = {"ain0_v": st["ain0_v"], "ain1_v": st["ain1_v"], "vbus_v": st["vbus_v"], "bridge_v": st["bridge_v"],
           "gpio": st["gpio"], "out": s["out"], "pwm": s["pwm"],
           "pd_contract": (s["pd"] or {}).get("pd_contract"),
           "run_active": bool(c["active"]), "lock_holders": st["lock_holders"]}
    st["pre_ramp"] = check_preconditions(pre, "ramp")
    st["pre_align"] = check_preconditions(pre, "align")
    if s["i2c_paused"] and not c["active"]:
        st["pre_ramp"].append("monitor paused (another HV owner?)")
    return st


def list_runs():
    out = []
    for p in sorted(glob.glob(os.path.join(RUNS_DIR, "stage7_ramp_*")) + glob.glob(os.path.join(RUNS_DIR, "cam_*")),
                    reverse=True):
        name = os.path.basename(p)
        stem, ext = os.path.splitext(name)
        if ext not in (".csv", ".json", ".mp4", ".mjpg"):
            continue
        if ext in (".mp4", ".mjpg"):
            ext = ".video"
        rec = next((r for r in out if r["stem"] == stem), None)
        if rec is None:
            rec = {"stem": stem, "csv": None, "json": None, "video": None, "mtime": os.path.getmtime(p)}
            out.append(rec)
        rec[ext[1:]] = name
        if ext == ".video":
            rec["video_bytes"] = os.path.getsize(p)
        if ext == ".json":
            try:
                with open(p) as f:
                    j = json.load(f)
                rec.update(mode=j.get("mode"), params=j.get("params"), abort=j.get("abort"),
                           code=j.get("code"), peak_kv=(j.get("result") or {}).get("peak_kv"))
            except Exception:
                pass
    out.sort(key=lambda r: r["mtime"], reverse=True)
    return out[:200]


# ------------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "ew1-dashboard/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else (json.dumps(body, default=str).encode()
                                                     if ctype == "application/json" else body.encode())
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _authed(self):
        tok = self.headers.get("X-EW1-Token", "")
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            tok = tok or auth[7:]
        return bool(tok) and hmac.compare_digest(tok.strip().encode(), self.server.token.encode())

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 8192:
            raise ValueError("body too large")
        raw = self.rfile.read(n) if n else b""
        if not raw:
            return {}
        return json.loads(raw)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        mon, ctl = self.server.mon, self.server.ctl
        try:
            if path in ("/", "/index.html"):
                with open(os.path.join(STATIC, "index.html"), "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if path == "/api/state":
                return self._send(200, build_state(mon, ctl))
            if path == "/api/limits":
                return self._send(200, {"limits": LIMITS, "defaults": DEFAULTS, "confirm": CONFIRM_WORD,
                                        "do_not_touch_s": DO_NOT_TOUCH_S, "kv_per_v": KV,
                                        "heartbeat_timeout_s": HEARTBEAT_TIMEOUT_S})
            if path == "/api/history":
                cut = time.time() - 300
                return self._send(200, [[round(t, 3), None if k is None else round(k, 4),
                                         None if u is None else round(u, 3)]
                                        for t, k, u in list(mon.history) if t >= cut])
            if path == "/api/slow_history":
                return self._send(200, {"keys": ["t"] + list(SLOW_KEYS), "rows": list(SLOW)})
            if path == "/api/run_samples":
                return self._send(200, {"meta": ctl.run_meta, "cols": RUN_COLS, "rows": list(ctl.run_buf)})
            if path == "/api/camera":
                return self._send(200, ctl.camera)
            if path == "/api/events":
                return self._send(200, EV.since(0))
            if path == "/api/runs":
                return self._send(200, list_runs())
            if path.startswith("/runs/"):
                name = path[6:]
                if not re.fullmatch(r"(stage7_ramp|cam)_[A-Za-z0-9_]+\.(csv|json|mp4|mjpg)", name):
                    return self._send(404, {"error": "not found"})
                fp = os.path.join(RUNS_DIR, name)
                if not os.path.isfile(fp):
                    return self._send(404, {"error": "not found"})
                with open(fp, "rb") as f:
                    data = f.read()
                ct = {"csv": "text/csv", "json": "application/json", "mp4": "video/mp4",
                      "mjpg": "video/x-motion-jpeg"}[name.rsplit(".", 1)[1]]
                return self._send(200, data, ct, {"Content-Disposition": f'attachment; filename="{name}"'})
            if path == "/api/stream":
                return self._stream()
            return self._send(404, {"error": "not found"})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as e:
            traceback.print_exc()
            try:
                self._send(500, {"error": f"{type(e).__name__}: {e}"})
            except Exception:
                pass

    def _stream(self):
        mon, ctl = self.server.mon, self.server.ctl
        q = self.path.split("?", 1)[1] if "?" in self.path else ""
        m = re.search(r"since=(\d+)", q)
        last_ev = int(m.group(1)) if m else 0
        rid, ridx = -1, 0
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        self.close_connection = True
        try:
            while not shutdown_evt.is_set():
                st = build_state(mon, ctl)
                evs = EV.since(last_ev)
                if evs:
                    last_ev = evs[-1]["id"]
                st["events"] = evs
                if ctl.run_id != rid:
                    rid, ridx = ctl.run_id, 0
                    st["run_reset"] = True
                buf = ctl.run_buf
                st["run_samples"] = buf[ridx:ridx + 600]
                ridx += len(st["run_samples"])
                self.wfile.write(b"data: " + json.dumps(st, default=str).encode() + b"\n\n")
                self.wfile.flush()
                time.sleep(0.05 if st["run"]["active"] else 0.2)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        ctl = self.server.ctl
        if not self._authed():
            if path == "/api/safe_stop":
                warn(f"SAFE STOP request from {self.client_address[0]} rejected: missing/bad token")
            return self._send(401, {"ok": False, "errors": ["missing or bad token (X-EW1-Token)"]})
        try:
            body = self._body()
        except Exception as e:
            return self._send(400, {"ok": False, "errors": [f"bad JSON body: {e}"]})
        try:
            if path == "/api/safe_stop":
                warn(f"SAFE STOP requested from {self.client_address[0]}")
                ok = ctl.request_stop("SAFE STOP button")
                out, _ = read_outputs()
                return self._send(200 if ok else 500, {"ok": ok, "out": out, "pwm": read_pwm()})
            if path == "/api/heartbeat":
                ctl.beat()
                return self._send(200, {"ok": True, "active": bool(ctl.active)})
            if path == "/api/run":
                p, errors = validate_run_params(body)
                if errors:
                    warn("run rejected: " + "; ".join(errors))
                    return self._send(400, {"ok": False, "errors": errors})
                code, res = ctl.start("ramp", p)
                return self._send(code, res)
            if path == "/api/settings":
                try:
                    return self._send(200, {"ok": True, "settings": ctl.save_settings(body)})
                except ValueError as e:
                    return self._send(400, {"ok": False, "errors": [str(e)]})
            if path == "/api/camera/record":
                act = body.get("action")
                if act == "start":
                    if ctl.active:
                        return self._send(409, {"ok": False, "errors": ["use auto-record during runs"]})
                    r = camera_call("/record/start", {"name": time.strftime("cam_%Y%m%d_%H%M%S")}, timeout=5.0)
                elif act == "stop":
                    r = camera_call("/record/stop", {}, timeout=30.0)
                else:
                    return self._send(400, {"ok": False, "errors": ["action must be start or stop"]})
                return self._send(200 if "error" not in r else 409, dict(r, ok="error" not in r))
            if path == "/api/align":
                p, errors = validate_align_params(body)
                if errors:
                    return self._send(400, {"ok": False, "errors": errors})
                code, res = ctl.start("align", p)
                return self._send(code, res)
            return self._send(404, {"ok": False, "errors": ["not found"]})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {"ok": False, "errors": [f"{type(e).__name__}: {e}"]})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ------------------------------------------------------------------ main
def spawn_deadman():
    """Child that safe-stops when our stdin pipe to it closes (we exited or were SIGKILLed)."""
    try:
        return subprocess.Popen([sys.executable, os.path.join(HERE, "ew1_safestop.py"), "--watch-stdin"],
                                stdin=subprocess.PIPE, start_new_session=True)
    except Exception as e:
        err(f"could not start dead-man child: {e}")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--bind", default="0.0.0.0")
    a = ap.parse_args()
    os.makedirs(RUNS_DIR, exist_ok=True)
    token = load_token()
    CAM_TOKEN["t"] = token
    try:
        os.sched_setaffinity(0, {0, 1})      # CPUs 2-3 are left to the camera helper / encoder
    except (AttributeError, OSError):
        pass

    holders = lock_holder_pids()
    if holders:
        warn(f"HV lock held by {holders} at startup; outputs left alone, monitoring paused until released")
    else:
        do_safe_stop("dashboard start")

    bus_lock = threading.Lock()
    mon = Monitor(bus_lock)
    ctl = Controller(mon, bus_lock)
    deadman = spawn_deadman()
    camera = spawn_camera()

    stopped = {"done": False}

    def final_stop(why):
        if stopped["done"]:
            return
        stopped["done"] = True
        if ctl.active:
            ctl.request_stop(why)
            if ctl.thread:
                ctl.thread.join(timeout=8.0)
        elif not [p for p in lock_holder_pids() if p != os.getpid()]:
            do_safe_stop(why)
        else:
            info(f"{why}: HV lock held by another process; outputs left to it")

    atexit.register(final_stop, "exit")

    def on_signal(signum, _frame):
        warn(f"signal {signal.Signals(signum).name}: shutting down")
        shutdown_evt.set()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGHUP, on_signal)

    srv = Server((a.bind, a.port), Handler)
    srv.token, srv.mon, srv.ctl = token, mon, ctl
    mon.start()
    threading.Thread(target=ctl.watchdog, daemon=True, name="watchdog").start()
    threading.Thread(target=camera_poller, args=(ctl,), daemon=True, name="campoll").start()
    threading.Thread(target=historian, args=(mon, ctl), daemon=True, name="historian").start()
    threading.Thread(target=srv.serve_forever, daemon=True, name="http").start()
    info(f"dashboard on http://{a.bind}:{a.port}/  (token file {TOKEN_PATH}, runs in {RUNS_DIR})")
    try:
        while not shutdown_evt.wait(0.5):
            pass
    finally:
        final_stop("dashboard shutdown")
        srv.shutdown()
        if camera:
            try:
                camera.stdin.close()
                camera.wait(timeout=25)
            except Exception:
                pass
        if deadman:
            try:
                deadman.stdin.close()
                deadman.wait(timeout=5)
            except Exception:
                pass
        info("dashboard stopped")


if __name__ == "__main__":
    main()
