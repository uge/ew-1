# ew-1 HV dashboard

A live HTTP dashboard for monitoring and controlling the corona HV board on the ew-1 Pi 5.
It uses the Python standard library plus the packages already on ew-1 (`smbus2`, `gpiod`).
The page is self-contained: no CDN, canvas charts, vanilla JS.

- **URL:** <http://ew-1.local:8080/> (or <http://192.168.0.130:8080/>). Camera helper: port 8081.
- **Control token:** `~/.ew1-dashboard-token` on ew-1 (mode 600). It is generated on first
  start. Read it with `ssh ew-1.local cat ~/.ew1-dashboard-token` and paste it into the
  page's *Control token* field; it is stored only in that browser's localStorage.
  Delete the file and restart to rotate the token.
- **Run data:** `~/dashboard_runs/`. For each run it holds:
  - the CSV, with the same columns as `stage7_ramp.py`;
  - a JSON summary (parameters, result, abort reason, events, video link);
  - the optional camera video.

## Files

| File | Role |
|---|---|
| `ew1_dashboard.py` | HTTP server, monitor thread, run controller, watchdog |
| `ew1_limits.py` | Hard limits, parameter validation, precondition checker (pure; unit-tested) |
| `ew1_safestop.py` | Safe-stop CLI, the dead-man child, and the systemd `ExecStopPost` hook |
| `ew1_camera.py` | Optional camera helper (separate process, port 8081) |
| `bme280.py`, `tsl2591.py` | Sensor drivers |
| `static/index.html` | The page |
| `test_ew1_limits.py` | `python3 test_ew1_limits.py` (no hardware) |
| `test_pd_init.py` | Startup PD-init logic with fakes, `python3 test_pd_init.py` (no hardware) |
| `ew1-dashboard.service`, `install_service.sh` | systemd unit (installed, never auto-enabled) |
| `deploy.sh` | Copies everything from the repo to ew-1. Run it on the workstation |

The dashboard runs from `~/dashboard/` and imports `~/stage7_ramp.py` and `~/husb238a.py`,
which sit in the parent directory. In the repo layout those are `host/dashboard/` and `host/`.

## Architecture

```
browser ──SSE /api/stream (5 Hz idle, 20 Hz in a run)──► ThreadingHTTPServer (CPUs 0-1)
        ──POST + X-EW1-Token────────────────────────────►  ├─ Monitor thread (10 Hz): ADS1115 x4, GPIO in (gpiod),
                                                            │   BME280 1 Hz, HUSB238A status 0.5 Hz (read-only),
                                                            │   TSL2591 probe/30 s or 1 Hz, vcgencmd 3V3, pinctrl, PWM sysfs
                                                            ├─ Controller: one run thread -> stage7_ramp.run(...)
                                                            │   publishes every control-loop sample (on_sample)
                                                            ├─ Watchdog (10 Hz)   ├─ Historian (1 Hz, 10 min)
                                                            ├─ dead-man child: ew1_safestop.py --watch-stdin
                                                            └─ camera helper child: ew1_camera.py (CPUs 2-3, nice)
```

- **HV is driven only by `stage7_ramp.run()`.** That is the same code as the CLI:
  - phase sync with the driver asleep, refusing to drive if it fails;
  - a slew-limited ramp (per-vbus tuning: step 0.001, 10 V/ms);
  - the predictive abort on AIN0 + slope × 16 ms;
  - a hold regulated every 50 ms;
  - every abort: nFAULT, EFUSE_FLT, OV_TRIP, interlock, AIN1, VBUS/bridge band, 3V3 rise.

  The UI never writes PWM duty. The refactor of `stage7_ramp.py` turned `main()` into
  `run()` plus a thin CLI. `run()` takes two new optional arguments:
  - `on_sample` (live samples for the dashboard);
  - `stop` (an Event; when set, the run aborts with "external stop").

  The CLI also takes the shared HV lock now. With neither argument set, behaviour is unchanged.
- **One HV owner at a time.** `flock` on `/run/lock/ew1-hv.lock` (`stage7_ramp.hv_lock()`),
  taken by the dashboard for every run or dry sync and by the `stage7_ramp.py` CLI. A second
  owner is refused.
- **Monitoring never disturbs a control loop.** The monitor reads `/proc/locks` and pauses
  all I2C, ADC and vcgencmd polling whenever anyone holds the HV lock. That includes a CLI run
  started from a shell. During a dashboard run, the values shown (kV, µA, VBUS, bridge, GPIO,
  3V3, duty) come from the control loop's own samples. BME280 and TSL2591 are not read during
  runs, so their graphs show a gap. The dashboard process is pinned to CPUs 0–1, and the camera
  and encoder to CPUs 2–3 at nice 15.

## Hard limits (server-side, `ew1_limits.py`)

| Parameter | Allowed |
|---|---|
| PD contract `vbus` | 5, 9, 12 or 15 V (12/15 V added 2026-11-01: 9 V tops out at ≈ 12.5 kV unloaded) |
| `freq_hz` | 20 000 – 100 000 |
| `target_kv` | 0.1 – 15.0, and < `abort_kv` (user: up to 15 kV, 2026-11-01) |
| `abort_kv` | ≤ 15.5 (predictive), 1.46 kV below the 16.96 kV hardware OV trip, which is **unverified** |
| `max_duty` | 0.01 – 0.25 (raised from 0.17 so a corona-loaded gap can reach 10 kV; HV vs duty is non-monotonic, unloaded peak ≈ 0.16, so beyond it more duty gives less HV) |
| `ain1_max_v` | 0.01 – 0.5 V (≤ 50 µA) |
| `hold_s` | 0 – 30 |

- ⚠️ **Above ~12.5 kV the board is outside anything bench-tested** (highest so far: 12.5 kV
  unloaded, with ≈ 7 µA return current). The insulation is unqualified (AUDIT.md), the
  hardware OV trip is unverified, there's no grounding stick, and bare leads ~10 mm apart will
  likely arc near 15 kV. Approach 15 kV stepwise (for example 12 → 13.5 → 15 kV targets) with a
  tight `ain1_max_v`, and keep the 5-minute do-not-touch wait.
- **12/15 V contracts** are requested by `run()` with GPIO25 low. VBUS is verified in the
  contract's band before GPIO25 goes high, and the bridge is verified after. The run returns to
  5 V after safe-stop. `stage7_ramp.TUNING`: 12 V step 0.00075, 15 V step 0.0005, both
  10 V/ms.
- Every field is required.
- `confirm` must be the string `"HV ON"`; the UI sends it only from the confirmation dialog,
  which shows the target.
- `stage7_ramp.run()` applies its own limits on top: abort ≤ 19 kV, AIN1 ≤ 0.6 V, and
  frequency 20–100 kHz.

## Safety behaviour

- **Safe-stop order:** GPIO24 low → PWM ch2/ch3 enable 0 → polarity normal → GPIO25 low
  (`stage7_ramp.safe_stop`). It runs:
  - at dashboard start, unless another process holds the HV lock;
  - at the end of every run, on every path (`run()`'s own `finally`, then once more by the controller);
  - on the **SAFE STOP** button. It needs the token; it always acts, even mid-run, and also
    sets the run's stop Event;
  - on a **watchdog** trip, any of:
    - no control-page heartbeat for 2 s during an HV ramp (the page sends one every 0.5 s,
      so closing the tab or losing the network stops the run);
    - no control-loop sample for 1 s during ramp/hold;
    - the run exceeding ramp timeout + hold + 30 s;
  - on SIGTERM/SIGINT/SIGHUP and at interpreter exit;
  - in the **dead-man child** when the dashboard dies for any reason, SIGKILL included (its
    stdin pipe closes);
  - in systemd `ExecStopPost` after the service stops.

  The last two skip only if a *different* live process (a CLI run) holds the HV lock.
- **Start preconditions** are re-read fresh on the board after the lock is taken, with the
  monitor paused (`check_preconditions`):
  - interlock = 1 (ramp only);
  - nFAULT = 1, EFUSE_FLT = 1, OV_TRIP = 0;
  - AIN0 < 0.05 V, AIN1 < 0.10 V, bridge < 0.2 V;
  - VBUS 4.6–5.6 V and PD contract 5 V;
  - GPIO18/19/24/25 low, PWM disabled;
  - no other run or lock holder.

  `run()` then applies its own stricter pre-check (AIN0 < 0.01 V, and so on) before driving
  anything.
- **9 → 5 V:** `run()` requests 9 V with GPIO25 low and returns to 5 V after safe-stop
  (GPIO25 low).
- After any HV ramp, the page shows a **"DO NOT TOUCH" 5-minute countdown** and the time
  since the last HV. This is persisted in `~/dashboard_runs/last_hv.json` and seeded from the
  newest `~/stage7_ramp_ramp_*.csv`.
- **HUSB238A:** the monitor only reads it. Two things write to it:
  - `run()` with `vbus 9`;
  - the optional startup PD init below.

## Startup PD init (opt-in, `pd_auto_init`)

U7 comes up with `CONTROL1.ENABLE = 0` after every power cycle and reports
`Type-C 5V (no PD)`. `check_preconditions()` then refuses every run ("PD contract … is not
5V"). To establish the explicit 5 V contract automatically when the dashboard starts:

```sh
# on ew-1; any existing keys are preserved
python3 - <<'EOF'
import json, os; p = os.path.expanduser("~/dashboard_runs/settings.json")
s = json.load(open(p)) if os.path.exists(p) else {}; s["pd_auto_init"] = True; json.dump(s, open(p, "w"))
EOF
```

- **Off by default.** It runs only if the setting is exactly `true`. `--no-pd-init` overrides
  it. It is deliberately not settable from the web page.
- **What it does** (`ensure_pd_5v()`): it runs after the startup safe-stop and before the
  monitor starts. It takes the HV lock, then requires GPIO24/25 low, a bridge < 0.2 V and
  VBUS 4.5–5.6 V. If the contract isn't already 5 V, it calls `request_fixed(5, max_volts=5)`.
  If any check fails it logs the reason and does nothing. It never raises.
- ⚠️ **Only with an SPR-only source on J3** (≤ 20 V, no EPR). Enabling U7 makes this
  `-BB001` part **auto-request the source's highest PDO** before 5 V is selected (AUDIT.md,
  U7 boot voltage). On the 65 W SPR supply that is a brief ~20 V excursion upstream of U9,
  with U9 off and OVLO at 22 V. **With an EPR charger it would be 28 V into U9 (28 V abs max)
  and F1 (24 V).**
  - Every startup with the setting on logs a warning.
  - If the source reports EPR capability afterwards, the init logs an error to inspect U9/F1.
  - Set `pd_auto_init` false before connecting any other charger.
- Test without hardware: `python3 test_pd_init.py`. It fakes the lock, pins, ADC and U7.

## API

- **Open (read-only):**
  - `GET /`;
  - `/api/state`, `/api/stream` (SSE; includes new events and new run samples);
  - `/api/limits`, `/api/history` (5 min HV/µA), `/api/slow_history` (10 min, 1 Hz);
  - `/api/run_samples`, `/api/runs`, `/api/camera`, `/api/events`;
  - `/runs/<file>` (csv/json/mp4/mjpg download).
- **Token (`X-EW1-Token: <token>`):** `POST /api/safe_stop`, `/api/run`, `/api/align` (dry
  phase-sync check, driver asleep / bridge off), `/api/heartbeat`,
  `/api/settings` `{"camera_autorecord": bool}`, `/api/camera/record`
  `{"action": "start"|"stop"}`.

```sh
TOK=$(ssh ew-1.local cat .ew1-dashboard-token)
curl -s -XPOST -H "X-EW1-Token: $TOK" http://ew-1.local:8080/api/safe_stop
```

## Running

Manual, in the foreground; Ctrl-C safe-stops:

```sh
ssh ew-1.local
cd ~/dashboard && python3 -u ew1_dashboard.py            # --port 8080 --bind 0.0.0.0
```

Manual, in the background:

```sh
cd ~/dashboard && setsid nohup python3 -u ew1_dashboard.py > dashboard.out 2>&1 < /dev/null &
pkill -TERM -f '[e]w1_dashboard.py'                      # stop (SIGTERM -> safe-stop)
```

As a systemd service. It is **installed but never enabled automatically**, and `Restart=no`:

```sh
sh ~/dashboard/install_service.sh          # copies the unit + daemon-reload only
sudo systemctl start ew1-dashboard         # start now
sudo systemctl enable ew1-dashboard        # optional: start at boot
sudo systemctl stop ew1-dashboard          # SIGTERM -> safe-stop; ExecStopPost safe-stop again
journalctl -u ew1-dashboard -f
```

Manual safe-stop from any shell: `python3 ~/dashboard/ew1_safestop.py --force`.

## Graphs

- **HV rolling chart:** kV and µA, 30 s / 60 s / 5 min.
- **Run graphs:** HV kV with the predicted value and target/abort lines; return µA with the
  AIN1 abort line; duty with the max-duty line; bridge V and VBUS. All plotted against run
  time (the CSV `t_s`), with hold and decay shaded.
  - They update live from the control loop's samples at ≤ 100 Hz and stay on screen after
    the run.
  - Use *graph* in the run list to reopen any past run from its CSV, and *show live / latest
    run graphs* to go back.
- **History:** 10 min at 1 Hz for kV, µA, VBUS, bridge, 3V3 mA/V, T, P, RH and lux.

## Camera (optional, inert without a camera)

`ew1_camera.py` runs as a separate child process on port 8081, pinned to CPUs 2–3 and niced.
It never touches I2C-1, GPIO or PWM. A CSI camera's own I2C is a separate bus.

- **Detection.** It runs at start and every 30 s:
  - **CSI** via `rpicam-hello --list-cameras`;
  - **USB UVC** via `/sys/class/video4linux/*` with driver `uvcvideo` and index 0. The
    `pispbe`/`rpi-hevc-dec` nodes on the Pi 5 are not cameras and are ignored.

  It reports which tools it found or is missing: `ffmpeg`, `rpicam-vid`, `rpicam-hello`,
  `v4l2-ctl`, `picamera2`. On ew-1 (2026-11-01) all are present and no camera is detected,
  so the page shows "no camera detected".
- **Live view:** `http://ew-1.local:8081/stream.mjpg`, 640×480 at 15 fps, MJPEG. The capture
  process starts only on demand and stops 5 s after the last viewer or recording.
  - CSI: `rpicam-vid -t 0 -n --codec mjpeg -o -`.
  - USB: `ffmpeg -f v4l2 -input_format mjpeg … -c:v copy -f mjpeg -`. The camera must offer
    MJPEG at 640×480; for a YUYV-only camera, change the ffmpeg arguments in `_cmd()`.
- **Recording:** the same frames are piped to `ffmpeg -c:v libx264 -preset ultrafast` and
  written as MP4 to `~/dashboard_runs/`. Without ffmpeg it writes raw `.mjpg`.
  - Manual recordings are named `cam_YYYYmmdd_HHMMSS.mp4`.
  - With **auto-record HV runs** ticked (persisted in `~/dashboard_runs/settings.json`),
    recording starts just before `run()` and stops after it returns, decay included. The
    file is renamed to the run's CSV stem (`stage7_ramp_ramp_9V_<ts>.mp4`) and linked in
    the run's JSON. The JSON's `video.offset_s` gives the video start relative to the run start.
- **Plugging in a camera later:**
  - USB: plug it in; it is picked up within 30 s.
  - CSI: connect it to CAM/DISP0 with the Pi off. Camera auto-detect is on by default in
    `config.txt` (`camera_auto_detect=1`); otherwise add the sensor's `dtoverlay`. Then
    check with `rpicam-hello --list-cameras`. The helper picks it up within 30 s of boot.
  - No dashboard changes are needed for either.

## Not verified without HV

The following need a supervised HV run (see the session report):
- the live ramp through the dashboard;
- the live run graphs with real samples;
- watchdog / heartbeat aborts mid-run;
- SAFE STOP mid-run;
- the 9 V round-trip;
- camera auto-record.
