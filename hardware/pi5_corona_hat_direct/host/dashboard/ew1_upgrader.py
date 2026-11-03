#!/usr/bin/env python3
"""Self-upgrade manager for the ew-1 HV host & dashboard from GitHub Releases.

Fetches releases from https://api.github.com/repos/<repo>/releases, verifies SHA-256
checksums, runs pre-flight syntax and unit-test checks in a staging directory, installs
atomically into /home/uge/, and schedules a clean systemd service restart.
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

DEFAULT_REPO = "uge/ew-1"
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
REQUIRED_FILES = (
    "stage7_ramp.py",
    "husb238a.py",
    "rp1_pwm_sync.py",
    "dashboard/ew1_dashboard.py",
    "dashboard/ew1_limits.py",
    "dashboard/ew1_safestop.py",
    "dashboard/static/index.html",
)


def valid_tag(tag):
    return isinstance(tag, str) and bool(TAG_RE.match(tag)) and ".." not in tag


def current_version(here_dir=None, home_dir=None):
    here_dir = here_dir or os.path.dirname(os.path.abspath(__file__))
    home_dir = home_dir or os.path.expanduser("~")
    for p in (os.path.join(here_dir, "VERSION.json"), os.path.join(home_dir, "VERSION.json")):
        if os.path.isfile(p):
            try:
                with open(p) as f:
                    d = json.load(f)
                if isinstance(d, dict) and d.get("version"):
                    d.setdefault("repo", DEFAULT_REPO)
                    return d
            except Exception:
                pass
    return {"version": "dev", "commit": "working-tree", "built_at": None, "repo": DEFAULT_REPO}


def list_local_releases(home_dir=None):
    home_dir = home_dir or os.path.expanduser("~")
    rel_root = os.path.join(home_dir, "releases")
    if not os.path.isdir(rel_root):
        return []
    out = []
    for name in sorted(os.listdir(rel_root), reverse=True):
        if name.startswith("."):
            continue
        vp = os.path.join(rel_root, name, "VERSION.json")
        if os.path.isfile(vp):
            try:
                with open(vp) as f:
                    out.append(json.load(f))
                continue
            except Exception:
                pass
        if os.path.isdir(os.path.join(rel_root, name)):
            out.append({"version": name})
    return out


def _http_get(url, timeout=10.0, accept="application/vnd.github+json"):
    req = urllib.request.Request(
        url,
        headers={"Accept": accept, "User-Agent": "ew1-dashboard-upgrader/1"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_github_releases(raw_releases):
    out = []
    for r in raw_releases:
        if not isinstance(r, dict) or r.get("draft"):
            continue
        tag = r.get("tag_name") or ""
        if not valid_tag(tag):
            continue
        assets = r.get("assets") or []
        tar_url = None
        sha_url = None
        for a in assets:
            name = a.get("name") or ""
            url = a.get("browser_download_url")
            if not url:
                continue
            if name in (f"ew1-host-{tag}.tar.gz", "ew1-host.tar.gz") and not tar_url:
                tar_url = url
            elif name in (f"ew1-host-{tag}.tar.gz.sha256", "ew1-host.tar.gz.sha256") and not sha_url:
                sha_url = url
        out.append({
            "tag": tag,
            "name": r.get("name") or tag,
            "published_at": r.get("published_at"),
            "prerelease": bool(r.get("prerelease")),
            "html_url": r.get("html_url"),
            "body": (r.get("body") or "")[:1000],
            "asset_url": tar_url,
            "sha256_url": sha_url,
            "ready": bool(tar_url),
        })
    return out


def fetch_github_releases(repo=DEFAULT_REPO, timeout=8.0, http_get=_http_get):
    url = f"https://api.github.com/repos/{repo}/releases?per_page=25"
    raw = json.loads(http_get(url, timeout=timeout).decode("utf-8"))
    if not isinstance(raw, list):
        raise RuntimeError("unexpected GitHub releases response")
    return parse_github_releases(raw)


def verify_sha256(data_bytes, sha256_text):
    tokens = (sha256_text or "").strip().split()
    if not tokens:
        raise ValueError("empty sha256 file")
    expected = tokens[0].lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError(f"invalid sha256 digest format: {expected!r}")
    actual = hashlib.sha256(data_bytes).hexdigest().lower()
    if actual != expected:
        raise ValueError(f"SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def safe_extract_tar(tar_bytes, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    real_dest = os.path.realpath(dest_dir)
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
        for m in tf.getmembers():
            if m.issym() or m.islnk() or m.ischr() or m.isblk() or m.isfifo() or m.isdev():
                raise ValueError(f"refusing special tar entry: {m.name}")
            target = os.path.realpath(os.path.join(real_dest, m.name))
            if target != real_dest and not target.startswith(real_dest + os.sep):
                raise ValueError(f"unsafe path in archive: {m.name}")
        tf.extractall(real_dest)


def verify_extracted_bundle(stage_dir, run_tests=True):
    for rel in REQUIRED_FILES:
        fp = os.path.join(stage_dir, rel)
        if not os.path.isfile(fp):
            raise RuntimeError(f"release bundle missing required file: {rel}")
    if run_tests:
        py_files = [
            os.path.join(stage_dir, "stage7_ramp.py"),
            os.path.join(stage_dir, "husb238a.py"),
            os.path.join(stage_dir, "rp1_pwm_sync.py"),
        ] + [
            os.path.join(stage_dir, "dashboard", f)
            for f in os.listdir(os.path.join(stage_dir, "dashboard"))
            if f.endswith(".py")
        ]
        r = subprocess.run([sys.executable, "-m", "py_compile"] + py_files, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"py_compile failed: {(r.stderr or r.stdout).strip()}")
        test_fp = os.path.join(stage_dir, "dashboard", "test_ew1_limits.py")
        if os.path.isfile(test_fp):
            r2 = subprocess.run([sys.executable, test_fp], capture_output=True, text=True)
            if r2.returncode != 0:
                raise RuntimeError(f"unit test failed: {(r2.stderr or r2.stdout).strip()}")


def activate_staged_release(stage_dir, tag, home_dir=None):
    """Copy a verified release into ~/releases/<tag> and atomically update ~/ and ~/dashboard/."""
    home_dir = home_dir or os.path.expanduser("~")
    rel_root = os.path.join(home_dir, "releases")
    os.makedirs(rel_root, exist_ok=True)
    rel_dir = os.path.join(rel_root, tag)
    if os.path.exists(rel_dir):
        shutil.rmtree(rel_dir)
    shutil.copytree(stage_dir, rel_dir)

    # Save a backup of current live files before overwriting
    cur = current_version(os.path.join(home_dir, "dashboard"), home_dir).get("version") or "unknown"
    bkp_dir = os.path.join(rel_root, f"backup-{cur}-{time.strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(os.path.join(bkp_dir, "dashboard", "static"), exist_ok=True)
    for top in ("stage7_ramp.py", "husb238a.py", "rp1_pwm_sync.py", "ew1_selftest.py", "ew1_host_setup.sh", "VERSION.json"):
        src = os.path.join(home_dir, top)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(bkp_dir, top))
    dash_dst = os.path.join(home_dir, "dashboard")
    os.makedirs(os.path.join(dash_dst, "static"), exist_ok=True)
    for fn in os.listdir(dash_dst):
        src = os.path.join(dash_dst, fn)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(bkp_dir, "dashboard", fn))
    idx_src = os.path.join(dash_dst, "static", "index.html")
    if os.path.isfile(idx_src):
        shutil.copy2(idx_src, os.path.join(bkp_dir, "dashboard", "static", "index.html"))

    # Copy new top-level files atomically via temp file + os.replace
    for top in ("stage7_ramp.py", "husb238a.py", "rp1_pwm_sync.py", "ew1_selftest.py", "ew1_host_setup.sh", "VERSION.json"):
        src = os.path.join(rel_dir, top)
        if os.path.isfile(src):
            dst = os.path.join(home_dir, top)
            tmp = dst + ".tmp"
            shutil.copy2(src, tmp)
            os.replace(tmp, dst)

    rel_dash = os.path.join(rel_dir, "dashboard")
    for fn in os.listdir(rel_dash):
        src = os.path.join(rel_dash, fn)
        if os.path.isfile(src):
            dst = os.path.join(dash_dst, fn)
            tmp = dst + ".tmp"
            shutil.copy2(src, tmp)
            os.replace(tmp, dst)

    rel_idx = os.path.join(rel_dash, "static", "index.html")
    if os.path.isfile(rel_idx):
        dst = os.path.join(dash_dst, "static", "index.html")
        tmp = dst + ".tmp"
        shutil.copy2(rel_idx, tmp)
        os.replace(tmp, dst)

    return current_version(dash_dst, home_dir)


def install_from_github(tag, repo=DEFAULT_REPO, home_dir=None, http_get=_http_get, run_tests=True):
    if not valid_tag(tag):
        raise ValueError(f"invalid release tag: {tag!r}")
    home_dir = home_dir or os.path.expanduser("~")
    releases = fetch_github_releases(repo=repo, http_get=http_get)
    match = next((r for r in releases if r["tag"] == tag), None)
    if not match:
        raise ValueError(f"release {tag} not found in {repo}")
    if not match.get("asset_url"):
        raise ValueError(f"release {tag} does not have a packaged ew1-host tarball asset")

    tar_bytes = http_get(match["asset_url"], timeout=30.0, accept="application/octet-stream")
    sha256_hex = None
    if match.get("sha256_url"):
        sha_text = http_get(match["sha256_url"], timeout=10.0, accept="application/octet-stream").decode("utf-8")
        sha256_hex = verify_sha256(tar_bytes, sha_text)
    else:
        sha256_hex = hashlib.sha256(tar_bytes).hexdigest()

    with tempfile.TemporaryDirectory(prefix=f"ew1-stage-{tag}-") as stage_dir:
        safe_extract_tar(tar_bytes, stage_dir)
        v_path = os.path.join(stage_dir, "VERSION.json")
        if not os.path.isfile(v_path):
            v_data = {"version": tag, "repo": repo, "built_at": match.get("published_at")}
            with open(v_path, "w") as f:
                json.dump(v_data, f, indent=2)
            shutil.copy2(v_path, os.path.join(stage_dir, "dashboard", "VERSION.json"))
        verify_extracted_bundle(stage_dir, run_tests=run_tests)
        ver = activate_staged_release(stage_dir, tag, home_dir=home_dir)
    return {"ok": True, "version": ver, "sha256": sha256_hex}


def schedule_service_restart(service="ew1-dashboard.service"):
    """Trigger a detached restart of ew1-dashboard.service ~1s later so the HTTP reply finishes first."""
    try:
        subprocess.Popen(
            ["sudo", "-n", "systemd-run", "--on-active=1s", "/bin/systemctl", "restart", service],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception:
        return False
