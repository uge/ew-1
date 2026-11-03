#!/usr/bin/env python3
"""Hierarchical session file storage and SQLite catalog for ew-1 recordings.

Directory layout under ~/dashboard_runs/:
  ew1_runs.sqlite3
  sessions/
    YYYY-MM-DD/
      sess_YYYYmmdd_HHMMSS_<id>/
        session.json
        runs/
          <stem>/
            <stem>.csv
            <stem>.json
            <stem>.mp4 (optional)
        camera/
          cam_YYYYmmdd_HHMMSS.mp4
"""
import contextlib
import csv
import glob
import io
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import tempfile
import threading
import time
import zipfile

DB_FILENAME = "ew1_runs.sqlite3"
SAFE_NAME_RE = re.compile(r"^(stage7_ramp|cam)_[A-Za-z0-9_]+\.(csv|json|mp4|mjpg)$")

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    label      TEXT NOT NULL DEFAULT '',
    hostname   TEXT NOT NULL DEFAULT '',
    version    TEXT NOT NULL DEFAULT '',
    t_start    REAL NOT NULL,
    t_end      REAL,
    rel_dir    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recordings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    stem                TEXT UNIQUE NOT NULL,
    session_id          TEXT NOT NULL REFERENCES sessions(session_id),
    kind                TEXT NOT NULL,
    t_start             REAL,
    t_end               REAL,
    duration_s          REAL,
    vbus_v              INTEGER,
    freq_hz             INTEGER,
    target_kv           REAL,
    abort_kv            REAL,
    max_duty            REAL,
    ain1_max_v          REAL,
    hold_s              REAL,
    code                INTEGER,
    abort_reason        TEXT,
    stop_reason         TEXT,
    precondition_failed INTEGER,
    peak_kv             REAL,
    peak_ua             REAL,
    duty_end            REAL,
    duty_at_target      REAL,
    sample_count        INTEGER,
    csv_relpath         TEXT,
    json_relpath        TEXT,
    video_relpath       TEXT,
    video_bytes         INTEGER,
    notes               TEXT NOT NULL DEFAULT '',
    params_json         TEXT,
    result_json         TEXT
);

CREATE INDEX IF NOT EXISTS idx_recordings_session ON recordings(session_id, t_start DESC);
CREATE INDEX IF NOT EXISTS idx_recordings_t_start ON recordings(t_start DESC);
"""


class Storage:
    def __init__(self, root_dir, version="dev", session_label=""):
        self.root_dir = os.path.abspath(root_dir)
        self.db_path = os.path.join(self.root_dir, DB_FILENAME)
        self.lock = threading.Lock()
        self.version = version
        self.hostname = socket.gethostname()
        os.makedirs(self.root_dir, exist_ok=True)
        self._init_db()
        self.current_session_id = None
        self.start_session(label=session_label or "boot session")
        self.sync_legacy_files()

    @contextlib.contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self.lock, self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def start_session(self, label=""):
        now = time.time()
        lt = time.localtime(now)
        day_str = time.strftime("%Y-%m-%d", lt)
        ts_str = time.strftime("%Y%m%d_%H%M%S", lt)
        sid = f"sess_{ts_str}_{secrets.token_hex(2)}"
        rel_dir = os.path.join("sessions", day_str, sid)
        abs_dir = os.path.join(self.root_dir, rel_dir)
        os.makedirs(os.path.join(abs_dir, "runs"), exist_ok=True)
        os.makedirs(os.path.join(abs_dir, "camera"), exist_ok=True)
        meta = {
            "session_id": sid,
            "label": label,
            "hostname": self.hostname,
            "version": self.version,
            "t_start": now,
            "rel_dir": rel_dir,
        }
        with open(os.path.join(abs_dir, "session.json"), "w") as f:
            json.dump(meta, f, indent=2)
        with self.lock, self._connect() as conn:
            if self.current_session_id:
                conn.execute("UPDATE sessions SET t_end = ? WHERE session_id = ?", (now, self.current_session_id))
            conn.execute(
                "INSERT INTO sessions (session_id, label, hostname, version, t_start, t_end, rel_dir) "
                "VALUES (?, ?, ?, ?, ?, NULL, ?)",
                (sid, label, self.hostname, self.version, now, rel_dir),
            )
        self.current_session_id = sid
        return meta

    def update_session_label(self, session_id, label):
        with self.lock, self._connect() as conn:
            cur = conn.execute("SELECT rel_dir FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not cur:
                raise ValueError(f"unknown session_id: {session_id}")
            conn.execute("UPDATE sessions SET label = ? WHERE session_id = ?", (label, session_id))
            sjson = os.path.join(self.root_dir, cur["rel_dir"], "session.json")
            if os.path.isfile(sjson):
                try:
                    with open(sjson) as f:
                        d = json.load(f)
                    d["label"] = label
                    with open(sjson, "w") as f:
                        json.dump(d, f, indent=2)
                except Exception:
                    pass

    def _session_rel_dir(self, session_id=None):
        sid = session_id or self.current_session_id
        with self.lock, self._connect() as conn:
            row = conn.execute("SELECT rel_dir FROM sessions WHERE session_id = ?", (sid,)).fetchone()
            if not row:
                raise RuntimeError(f"session {sid} not found")
            return sid, row["rel_dir"]

    def register_run(self, rec, rows=None, session_id=None):
        """Move a finished run's CSV/JSON/video into the active session's runs/<stem>/ folder
        and record its metadata and telemetry summary in SQLite."""
        sid, sess_rel = self._session_rel_dir(session_id)
        csv_name = rec.get("csv")
        t_start = rec.get("t_start") or time.time()
        t_end = rec.get("t_end") or time.time()
        mode = rec.get("mode") or "ramp"
        p = rec.get("params") or {}
        res = rec.get("result") or {}
        if csv_name:
            stem = os.path.splitext(os.path.basename(csv_name))[0]
        else:
            stem = f"stage7_ramp_{mode}_{p.get('vbus', 5)}V_{time.strftime('%Y%m%d_%H%M%S', time.localtime(t_start))}"

        run_rel_dir = os.path.join(sess_rel, "runs", stem)
        run_abs_dir = os.path.join(self.root_dir, run_rel_dir)
        os.makedirs(run_abs_dir, exist_ok=True)

        csv_rel = None
        if csv_name:
            src_csv = csv_name if os.path.isabs(csv_name) else os.path.join(self.root_dir, csv_name)
            dst_csv = os.path.join(run_abs_dir, f"{stem}.csv")
            if os.path.isfile(src_csv) and os.path.abspath(src_csv) != os.path.abspath(dst_csv):
                shutil.move(src_csv, dst_csv)
            if os.path.isfile(dst_csv):
                csv_rel = os.path.join(run_rel_dir, f"{stem}.csv")

        video_rel = None
        video_bytes = None
        vid = rec.get("video") or {}
        if vid.get("file"):
            vfile = os.path.basename(vid["file"])
            src_vid = os.path.join(self.root_dir, vfile)
            dst_vid = os.path.join(run_abs_dir, vfile)
            if os.path.isfile(src_vid) and os.path.abspath(src_vid) != os.path.abspath(dst_vid):
                shutil.move(src_vid, dst_vid)
            if os.path.isfile(dst_vid):
                video_rel = os.path.join(run_rel_dir, vfile)
                video_bytes = os.path.getsize(dst_vid)

        json_rel = os.path.join(run_rel_dir, f"{stem}.json")
        dst_json = os.path.join(self.root_dir, json_rel)
        rec_copy = dict(rec, session_id=sid, csv_relpath=csv_rel, json_relpath=json_rel, video_relpath=video_rel)
        with open(dst_json, "w") as f:
            json.dump(rec_copy, f, indent=1, default=str)
        # Remove any flat duplicate JSON in root_dir
        flat_json = os.path.join(self.root_dir, f"{stem}.json")
        if os.path.isfile(flat_json) and os.path.abspath(flat_json) != os.path.abspath(dst_json):
            try:
                os.remove(flat_json)
            except OSError:
                pass

        peak_ua = None
        sample_count = 0
        if rows:
            sample_count = len(rows)
            a1_vals = [r[8] for r in rows if len(r) > 8 and isinstance(r[8], (int, float))]
            if a1_vals:
                peak_ua = round(max(a1_vals) * 100.0, 3)

        with self.lock, self._connect() as conn:
            conn.execute("UPDATE sessions SET t_end = ? WHERE session_id = ?", (t_end, sid))
            conn.execute(
                """
                INSERT INTO recordings (
                    stem, session_id, kind, t_start, t_end, duration_s,
                    vbus_v, freq_hz, target_kv, abort_kv, max_duty, ain1_max_v, hold_s,
                    code, abort_reason, stop_reason, precondition_failed,
                    peak_kv, peak_ua, duty_end, duty_at_target, sample_count,
                    csv_relpath, json_relpath, video_relpath, video_bytes,
                    params_json, result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stem) DO UPDATE SET
                    session_id=excluded.session_id,
                    t_end=excluded.t_end,
                    duration_s=excluded.duration_s,
                    code=excluded.code,
                    abort_reason=excluded.abort_reason,
                    stop_reason=excluded.stop_reason,
                    peak_kv=excluded.peak_kv,
                    peak_ua=excluded.peak_ua,
                    csv_relpath=excluded.csv_relpath,
                    json_relpath=excluded.json_relpath,
                    video_relpath=excluded.video_relpath,
                    video_bytes=excluded.video_bytes,
                    result_json=excluded.result_json
                """,
                (
                    stem, sid, mode, t_start, t_end, round(t_end - t_start, 3),
                    p.get("vbus"), p.get("freq_hz"), p.get("target_kv"), p.get("abort_kv"),
                    p.get("max_duty"), p.get("ain1_max_v"), p.get("hold_s"),
                    rec.get("code"), rec.get("abort"), rec.get("stop_reason"),
                    1 if rec.get("precondition_failed") else 0,
                    res.get("peak_kv"), peak_ua, res.get("duty_end"), res.get("duty_at_target"),
                    sample_count, csv_rel, json_rel, video_rel, video_bytes,
                    json.dumps(p, default=str), json.dumps(res, default=str),
                ),
            )
        return {"stem": stem, "session_id": sid, "csv_relpath": csv_rel, "json_relpath": json_rel,
                "video_relpath": video_rel}

    def register_camera_clip(self, filename, t0=None, t1=None, session_id=None):
        """Move a standalone manual camera recording into sessions/<date>/<sid>/camera/ and catalog it."""
        if not filename:
            return None
        sid, sess_rel = self._session_rel_dir(session_id)
        base = os.path.basename(filename)
        stem, _ = os.path.splitext(base)
        cam_rel_dir = os.path.join(sess_rel, "camera")
        cam_abs_dir = os.path.join(self.root_dir, cam_rel_dir)
        os.makedirs(cam_abs_dir, exist_ok=True)
        src = filename if os.path.isabs(filename) else os.path.join(self.root_dir, base)
        dst = os.path.join(cam_abs_dir, base)
        if os.path.isfile(src) and os.path.abspath(src) != os.path.abspath(dst):
            shutil.move(src, dst)
        if not os.path.isfile(dst):
            return None
        v_rel = os.path.join(cam_rel_dir, base)
        v_bytes = os.path.getsize(dst)
        t_start = t0 or os.path.getmtime(dst)
        t_end = t1 or time.time()
        with self.lock, self._connect() as conn:
            conn.execute("UPDATE sessions SET t_end = ? WHERE session_id = ?", (t_end, sid))
            conn.execute(
                """
                INSERT INTO recordings (
                    stem, session_id, kind, t_start, t_end, duration_s,
                    video_relpath, video_bytes
                ) VALUES (?, ?, 'camera', ?, ?, ?, ?, ?)
                ON CONFLICT(stem) DO UPDATE SET
                    video_relpath=excluded.video_relpath,
                    video_bytes=excluded.video_bytes,
                    t_end=excluded.t_end
                """,
                (stem, sid, t_start, t_end, round(max(0.0, t_end - t_start), 2), v_rel, v_bytes),
            )
        return {"stem": stem, "session_id": sid, "video_relpath": v_rel, "video_bytes": v_bytes}

    def sync_legacy_files(self):
        """Organize and index any flat stage7_ramp_* or cam_* files sitting in root_dir."""
        flat = sorted(
            glob.glob(os.path.join(self.root_dir, "stage7_ramp_*"))
            + glob.glob(os.path.join(self.root_dir, "cam_*"))
        )
        by_stem = {}
        for p in flat:
            if not os.path.isfile(p):
                continue
            name = os.path.basename(p)
            stem, ext = os.path.splitext(name)
            if ext not in (".csv", ".json", ".mp4", ".mjpg"):
                continue
            by_stem.setdefault(stem, {})[ext] = p
        if not by_stem:
            return 0

        imported = 0
        for stem, files in by_stem.items():
            mtime = max(os.path.getmtime(fp) for fp in files.values())
            day_str = time.strftime("%Y-%m-%d", time.localtime(mtime))
            leg_sid = f"sess_legacy_{day_str.replace('-', '')}"
            leg_rel = os.path.join("sessions", day_str, leg_sid)
            leg_abs = os.path.join(self.root_dir, leg_rel)
            os.makedirs(os.path.join(leg_abs, "runs"), exist_ok=True)
            os.makedirs(os.path.join(leg_abs, "camera"), exist_ok=True)
            with self.lock, self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO sessions (session_id, label, hostname, version, t_start, t_end, rel_dir) "
                    "VALUES (?, 'imported session', ?, ?, ?, ?, ?)",
                    (leg_sid, self.hostname, self.version, mtime, mtime, leg_rel),
                )
            if stem.startswith("cam_") and ".csv" not in files and ".json" not in files:
                vid_fp = files.get(".mp4") or files.get(".mjpg")
                if vid_fp:
                    self.register_camera_clip(vid_fp, t0=mtime, t1=mtime, session_id=leg_sid)
                    imported += 1
                continue
            rec = {"mode": "ramp" if "_ramp_" in stem else "align", "t_start": mtime, "t_end": mtime}
            if ".json" in files:
                try:
                    with open(files[".json"]) as f:
                        rec.update(json.load(f))
                except Exception:
                    pass
            if ".csv" in files:
                rec["csv"] = os.path.basename(files[".csv"])
            vid_fp = files.get(".mp4") or files.get(".mjpg")
            if vid_fp:
                rec["video"] = {"file": os.path.basename(vid_fp)}
            rows = None
            if ".csv" in files:
                try:
                    with open(files[".csv"]) as f:
                        rdr = list(csv.reader(f))
                    rows = []
                    for r in rdr[1:]:
                        if len(r) > 8:
                            row_conv = list(r)
                            try:
                                row_conv[8] = float(r[8]) if r[8] != "" else ""
                            except ValueError:
                                pass
                            rows.append(row_conv)
                except Exception:
                    rows = None
            self.register_run(rec, rows=rows, session_id=leg_sid)
            imported += 1
        return imported

    def list_recordings(self, limit=200, session_id=None):
        with self.lock, self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    """
                    SELECT r.*, s.label AS session_label, s.rel_dir AS session_rel_dir
                    FROM recordings r
                    JOIN sessions s ON s.session_id = r.session_id
                    WHERE r.session_id = ?
                    ORDER BY COALESCE(r.t_start, 0) DESC, r.id DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT r.*, s.label AS session_label, s.rel_dir AS session_rel_dir
                    FROM recordings r
                    JOIN sessions s ON s.session_id = r.session_id
                    ORDER BY COALESCE(r.t_start, 0) DESC, r.id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        out = []
        for r in rows:
            params = json.loads(r["params_json"]) if r["params_json"] else None
            out.append({
                "id": r["id"],
                "stem": r["stem"],
                "session_id": r["session_id"],
                "session_label": r["session_label"],
                "mode": r["kind"],
                "params": params,
                "t_start": r["t_start"],
                "t_end": r["t_end"],
                "duration_s": r["duration_s"],
                "mtime": r["t_end"] or r["t_start"] or 0,
                "code": r["code"],
                "abort": r["abort_reason"],
                "stop_reason": r["stop_reason"],
                "peak_kv": r["peak_kv"],
                "peak_ua": r["peak_ua"],
                "sample_count": r["sample_count"],
                "csv": os.path.basename(r["csv_relpath"]) if r["csv_relpath"] else None,
                "json": os.path.basename(r["json_relpath"]) if r["json_relpath"] else None,
                "video": os.path.basename(r["video_relpath"]) if r["video_relpath"] else None,
                "csv_relpath": r["csv_relpath"],
                "json_relpath": r["json_relpath"],
                "video_relpath": r["video_relpath"],
                "video_bytes": r["video_bytes"],
                "notes": r["notes"],
            })
        return out

    def list_sessions(self, limit=50):
        with self.lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*,
                       COUNT(r.id) AS recording_count,
                       SUM(CASE WHEN r.kind = 'ramp' THEN 1 ELSE 0 END) AS ramp_count,
                       MAX(r.peak_kv) AS max_peak_kv
                FROM sessions s
                LEFT JOIN recordings r ON r.session_id = s.session_id
                GROUP BY s.session_id
                ORDER BY s.t_start DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r, active=(r["session_id"] == self.current_session_id)) for r in rows]

    def resolve_file(self, filename):
        """Resolve a base filename (e.g. stage7_ramp_...csv) to its absolute path in the session hierarchy."""
        if not SAFE_NAME_RE.fullmatch(filename or ""):
            return None
        stem, ext = os.path.splitext(filename)
        col = {".csv": "csv_relpath", ".json": "json_relpath", ".mp4": "video_relpath", ".mjpg": "video_relpath"}[ext]
        with self.lock, self._connect() as conn:
            row = conn.execute(f"SELECT {col} FROM recordings WHERE stem = ?", (stem,)).fetchone()
        if row and row[col]:
            fp = os.path.realpath(os.path.join(self.root_dir, row[col]))
            if fp.startswith(os.path.realpath(self.root_dir) + os.sep) and os.path.isfile(fp):
                return fp
        # Fallback to flat file if not in DB
        flat = os.path.realpath(os.path.join(self.root_dir, filename))
        if flat.startswith(os.path.realpath(self.root_dir) + os.sep) and os.path.isfile(flat):
            return flat
        return None

    def update_recording_notes(self, stem, notes):
        with self.lock, self._connect() as conn:
            cur = conn.execute("UPDATE recordings SET notes = ? WHERE stem = ?", (str(notes or "")[:500], stem))
            if cur.rowcount == 0:
                raise ValueError(f"unknown recording: {stem}")

    def delete_recording(self, stem):
        real_root = os.path.realpath(self.root_dir)
        with self.lock, self._connect() as conn:
            row = conn.execute(
                "SELECT csv_relpath, json_relpath, video_relpath FROM recordings WHERE stem = ?",
                (stem,),
            ).fetchone()
            if not row:
                raise ValueError(f"unknown recording: {stem}")
            dirs = set()
            for col in ("csv_relpath", "json_relpath", "video_relpath"):
                rel = row[col]
                if not rel:
                    continue
                fp = os.path.realpath(os.path.join(real_root, rel))
                if fp.startswith(real_root + os.sep) and os.path.isfile(fp):
                    dirs.add(os.path.dirname(fp))
                    try:
                        os.remove(fp)
                    except OSError:
                        pass
            for d in dirs:
                if os.path.basename(d) == stem and d.startswith(real_root + os.sep):
                    try:
                        os.rmdir(d)
                    except OSError:
                        pass
            conn.execute("DELETE FROM recordings WHERE stem = ?", (stem,))
        return {"deleted": stem}

    def delete_session(self, session_id):
        if session_id == self.current_session_id:
            self.start_session(label="boot session")
        real_root = os.path.realpath(self.root_dir)
        with self.lock, self._connect() as conn:
            row = conn.execute("SELECT rel_dir FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not row:
                raise ValueError(f"unknown session_id: {session_id}")
            rel_dir = row["rel_dir"]
            conn.execute("DELETE FROM recordings WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            abs_dir = os.path.realpath(os.path.join(real_root, rel_dir))
            if abs_dir.startswith(real_root + os.sep) and os.path.isdir(abs_dir):
                shutil.rmtree(abs_dir, ignore_errors=True)
        return {"deleted_session": session_id, "current_session_id": self.current_session_id}

    def build_session_zip(self, session_id):
        real_root = os.path.realpath(self.root_dir)
        with self.lock, self._connect() as conn:
            row = conn.execute("SELECT rel_dir FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not row:
                raise ValueError(f"unknown session_id: {session_id}")
            abs_dir = os.path.realpath(os.path.join(real_root, row["rel_dir"]))
        if not abs_dir.startswith(real_root + os.sep) or not os.path.isdir(abs_dir):
            raise FileNotFoundError(f"session directory missing for {session_id}")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for dirpath, _, filenames in os.walk(abs_dir):
                for fn in sorted(filenames):
                    full = os.path.join(dirpath, fn)
                    arcname = os.path.join(session_id, os.path.relpath(full, abs_dir))
                    zf.write(full, arcname)
        return buf.getvalue()

    def build_recording_zip(self, stem):
        real_root = os.path.realpath(self.root_dir)
        with self.lock, self._connect() as conn:
            row = conn.execute(
                "SELECT csv_relpath, json_relpath, video_relpath FROM recordings WHERE stem = ?",
                (stem,),
            ).fetchone()
            if not row:
                raise ValueError(f"unknown recording: {stem}")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for col in ("csv_relpath", "json_relpath", "video_relpath"):
                rel = row[col]
                if not rel:
                    continue
                fp = os.path.realpath(os.path.join(real_root, rel))
                if fp.startswith(real_root + os.sep) and os.path.isfile(fp):
                    zf.write(fp, os.path.join(stem, os.path.basename(fp)))
        return buf.getvalue()

    def export_sqlite_bytes(self):
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with self.lock, self._connect() as src:
                dst = sqlite3.connect(tmp_path)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
