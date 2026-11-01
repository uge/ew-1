#!/usr/bin/env python3
"""ew-1 camera helper: optional live MJPEG view + recording, in its OWN process (port 8081).

Started by ew1_dashboard.py (niced, pinned to CPUs 2-3) and exits when the dashboard's stdin
pipe to it closes. It never touches I2C-1, GPIO or PWM. With no camera it only re-runs
detection every 30 s and answers /status.

  GET  /status         JSON: tools found/missing, cameras detected, streaming/recording state
  GET  /stream.mjpg    multipart MJPEG live view (starts the capture on demand)
  GET  /snapshot.jpg   latest frame
  POST /record/start   {"name": "<stem>"}  (X-EW1-Token) -> records <stem>.mp4 into ~/dashboard_runs
  POST /record/stop    (X-EW1-Token) -> finalises the file, returns its name and size

Sources (first found wins): CSI camera via rpicam-vid (--codec mjpeg), else a USB UVC webcam via
ffmpeg -f v4l2. Recording re-encodes the same MJPEG frames with ffmpeg (libx264 ultrafast) to MP4;
without ffmpeg it writes the raw .mjpg stream.
"""
import argparse
import glob
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME = os.path.expanduser("~")
RUNS_DIR = os.path.join(HOME, "dashboard_runs")
TOKEN_PATH = os.path.join(HOME, ".ew1-dashboard-token")
W, H, FPS = 640, 480, 15
IDLE_STOP_S = 5.0
DETECT_EVERY_S = 30.0
TOOLS = ("ffmpeg", "rpicam-vid", "rpicam-hello", "v4l2-ctl")
quit_evt = threading.Event()


def log(m):
    print(f"[ew1_camera {time.strftime('%H:%M:%S')}] {m}", flush=True)


def tools():
    found = {t: shutil.which(t) for t in TOOLS}
    try:
        import importlib.util
        found["picamera2 (python)"] = "yes" if importlib.util.find_spec("picamera2") else None
    except Exception:
        found["picamera2 (python)"] = None
    return found


def detect_csi():
    if not shutil.which("rpicam-hello"):
        return []
    try:
        out = subprocess.run(["rpicam-hello", "--list-cameras"], capture_output=True, text=True, timeout=10)
        txt = out.stdout + out.stderr
    except Exception:
        return []
    cams = []
    for m in re.finditer(r"^\s*(\d+)\s*:\s*(\S+)\s*\[([^\]]*)\]\s*\(([^)]*)\)", txt, re.M):
        cams.append({"kind": "csi", "index": int(m.group(1)), "sensor": m.group(2), "mode": m.group(3),
                     "path": m.group(4)})
    return cams


def detect_uvc():
    cams = []
    for d in sorted(glob.glob("/sys/class/video4linux/video*")):
        try:
            drv = os.path.basename(os.path.realpath(os.path.join(d, "device", "driver")))
            idx = open(os.path.join(d, "index")).read().strip()
            name = open(os.path.join(d, "name")).read().strip()
        except OSError:
            continue
        if drv == "uvcvideo" and idx == "0":            # index 0 = capture node (1 = metadata)
            cams.append({"kind": "uvc", "dev": "/dev/" + os.path.basename(d), "name": name})
    return cams


class Camera:
    def __init__(self):
        self.lock = threading.Lock()
        self.tools = tools()
        self.cams = []
        self.t_detect = 0.0
        self.proc = None
        self.frame = None
        self.frame_id = 0
        self.frame_cv = threading.Condition()
        self.viewers = 0
        self.t_last_use = 0.0
        self.rec = None             # {"proc", "path", "t0", "fh"}
        self.error = None
        self.source = None

    # ---------------- detection
    def detect(self, force=False):
        if not force and time.monotonic() - self.t_detect < DETECT_EVERY_S:
            return
        if self.proc is not None:              # don't probe libcamera while we hold the camera
            self.t_detect = time.monotonic(); return
        self.t_detect = time.monotonic()
        cams = detect_csi() + detect_uvc()
        if [c.get("path") or c.get("dev") for c in cams] != [c.get("path") or c.get("dev") for c in self.cams]:
            log(f"cameras: {cams or 'none'}")
        self.cams = cams

    def status(self):
        with self.lock:
            rec = self.rec
            return {"tools": self.tools, "missing": [k for k, v in self.tools.items() if not v],
                    "cameras": self.cams, "detected": bool(self.cams), "streaming": self.proc is not None,
                    "source": self.source, "viewers": self.viewers, "frame_id": self.frame_id,
                    "recording": None if not rec else {"file": os.path.basename(rec["path"]),
                                                       "t0": rec["t0"], "elapsed_s": round(time.time() - rec["t0"], 1)},
                    "error": self.error, "size": [W, H], "fps": FPS}

    # ---------------- capture
    def _cmd(self):
        pin = ["taskset", "-c", "2,3"] if shutil.which("taskset") else []
        nice = ["nice", "-n", "15"]
        for c in self.cams:
            if c["kind"] == "csi" and self.tools.get("rpicam-vid"):
                return c, pin + nice + ["rpicam-vid", "-t", "0", "-n", "--camera", str(c["index"]), "--codec", "mjpeg",
                                         "--width", str(W), "--height", str(H), "--framerate", str(FPS), "-o", "-"]
            if c["kind"] == "uvc" and self.tools.get("ffmpeg"):
                return c, pin + nice + ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "v4l2",
                                         "-input_format", "mjpeg", "-video_size", f"{W}x{H}", "-framerate", str(FPS),
                                         "-i", c["dev"], "-c:v", "copy", "-f", "mjpeg", "-"]
        return None, None

    def ensure_running(self):
        with self.lock:
            self.t_last_use = time.monotonic()
            if self.proc is not None:
                return True
            if not self.cams:
                self.detect(force=True)
            cam, cmd = self._cmd()
            if not cmd:
                self.error = "no camera detected" if not self.cams else "no capture tool for this camera"
                return False
            log("start capture: " + " ".join(cmd))
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
            self.source = cam
            self.error = None
            threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()
            return True

    def _reader(self, proc):
        buf = b""
        fh = proc.stdout
        while True:
            chunk = fh.read1(65536) if hasattr(fh, "read1") else fh.read(65536)
            if not chunk:
                break
            buf += chunk
            while True:
                s = buf.find(b"\xff\xd8")
                if s < 0:
                    buf = b""; break
                e = buf.find(b"\xff\xd9", s + 2)
                if e < 0:
                    buf = buf[s:]; break
                jpg = buf[s:e + 2]
                buf = buf[e + 2:]
                with self.frame_cv:
                    self.frame = jpg
                    self.frame_id += 1
                    self.frame_cv.notify_all()
                rec = self.rec
                if rec:
                    try:
                        rec["fh"].write(jpg)
                    except Exception as ex:
                        self.error = f"recording write failed: {ex}"
            if len(buf) > 4 << 20:
                buf = b""
        rc = proc.wait()
        with self.lock:
            if self.proc is proc:
                self.proc = None
                if rc not in (0, -15):
                    self.error = f"capture exited rc={rc}"
                log(f"capture stopped rc={rc}")
        with self.frame_cv:
            self.frame_cv.notify_all()

    def stop_capture(self):
        with self.lock:
            p = self.proc
        if p:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()

    def housekeeping(self):
        while not quit_evt.is_set():
            time.sleep(1.0)
            with self.lock:
                idle = self.proc is not None and self.viewers == 0 and self.rec is None and \
                    time.monotonic() - self.t_last_use > IDLE_STOP_S
            if idle:
                self.stop_capture()
            self.detect()

    # ---------------- recording
    def rec_start(self, name):
        if not re.fullmatch(r"[A-Za-z0-9_]{1,80}", name or ""):
            raise ValueError("bad name")
        with self.lock:
            if self.rec:
                raise RuntimeError(f"already recording {os.path.basename(self.rec['path'])}")
        if not self.ensure_running():
            raise RuntimeError(self.error or "camera not available")
        os.makedirs(RUNS_DIR, exist_ok=True)
        if self.tools.get("ffmpeg"):
            path = os.path.join(RUNS_DIR, name + ".mp4")
            pin = ["taskset", "-c", "2,3"] if shutil.which("taskset") else []
            enc = subprocess.Popen(pin + ["nice", "-n", "15", "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                                          "-f", "mjpeg", "-framerate", str(FPS), "-i", "pipe:0",
                                          "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                                          "-movflags", "+faststart", path],
                                   stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            fh = enc.stdin
        else:
            path = os.path.join(RUNS_DIR, name + ".mjpg")
            enc = None
            fh = open(path, "wb")
        with self.lock:
            self.rec = {"proc": enc, "path": path, "t0": time.time(), "fh": fh}
        log(f"recording -> {path}")
        return {"file": os.path.basename(path), "t0": self.rec["t0"]}

    def rec_stop(self):
        with self.lock:
            rec, self.rec = self.rec, None
        if not rec:
            return {"file": None}
        try:
            rec["fh"].close()
        except Exception:
            pass
        if rec["proc"]:
            try:
                rec["proc"].wait(timeout=20)
            except subprocess.TimeoutExpired:
                rec["proc"].kill()
        size = os.path.getsize(rec["path"]) if os.path.exists(rec["path"]) else 0
        log(f"recording stopped: {rec['path']} {size} bytes")
        return {"file": os.path.basename(rec["path"]), "bytes": size, "t0": rec["t0"], "t1": time.time()}


CAM = Camera()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        d = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(d)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(d)

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        try:
            if p == "/status":
                return self._json(200, CAM.status())
            if p == "/snapshot.jpg":
                if not CAM.ensure_running():
                    return self._json(404, {"error": CAM.error})
                with CAM.frame_cv:
                    CAM.frame_cv.wait_for(lambda: CAM.frame is not None, timeout=5)
                    f = CAM.frame
                if f is None:
                    return self._json(504, {"error": "no frame"})
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(f)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return self.wfile.write(f)
            if p == "/stream.mjpg":
                if not CAM.ensure_running():
                    return self._json(404, {"error": CAM.error})
                self.close_connection = True
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                with CAM.lock:
                    CAM.viewers += 1
                last = -1
                try:
                    while not quit_evt.is_set():
                        with CAM.frame_cv:
                            CAM.frame_cv.wait_for(lambda: CAM.frame_id != last or CAM.proc is None, timeout=5)
                            f, last = CAM.frame, CAM.frame_id
                        if CAM.proc is None or f is None:
                            break
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                                         str(len(f)).encode() + b"\r\n\r\n" + f + b"\r\n")
                        CAM.t_last_use = time.monotonic()
                finally:
                    with CAM.lock:
                        CAM.viewers -= 1
                return
            return self._json(404, {"error": "not found"})
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_POST(self):
        p = self.path.split("?", 1)[0]
        tok = self.headers.get("X-EW1-Token", "").strip()
        if not tok or not hmac.compare_digest(tok.encode(), self.server.token.encode()):
            return self._json(401, {"error": "missing or bad token"})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(min(n, 4096)) or b"{}")
        except Exception:
            return self._json(400, {"error": "bad JSON"})
        try:
            if p == "/record/start":
                return self._json(200, CAM.rec_start(body.get("name") or time.strftime("cam_%Y%m%d_%H%M%S")))
            if p == "/record/stop":
                return self._json(200, CAM.rec_stop())
            return self._json(404, {"error": "not found"})
        except Exception as e:
            return self._json(409, {"error": f"{type(e).__name__}: {e}"})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8081)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--watch-stdin", action="store_true", help="exit when stdin closes (parent gone)")
    a = ap.parse_args()
    try:
        os.nice(10)
    except OSError:
        pass
    try:
        os.sched_setaffinity(0, {2, 3})
    except (AttributeError, OSError):
        pass
    import signal
    def on_term(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    srv = Server((a.bind, a.port), Handler)
    try:
        srv.token = open(TOKEN_PATH).read().strip()
    except OSError:
        srv.token = os.urandom(16).hex()          # no token file: control endpoints effectively disabled
    CAM.detect(force=True)
    log(f"tools: {CAM.tools}")
    threading.Thread(target=CAM.housekeeping, daemon=True).start()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"camera helper on :{a.port}")
    try:
        if a.watch_stdin:
            while sys.stdin.buffer.read(4096):
                pass
        else:
            while True:
                time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        quit_evt.set()
        CAM.rec_stop()
        CAM.stop_capture()
        log("exit")


if __name__ == "__main__":
    main()
