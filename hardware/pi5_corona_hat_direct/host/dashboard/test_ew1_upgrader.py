#!/usr/bin/env python3
"""Unit tests for ew1_upgrader.py (no network or hardware required)."""
import hashlib
import io
import json
import os
import tarfile
import tempfile
import unittest

import ew1_upgrader as U


def _make_bundle_tarball(version="v0.2.0", bad_path=None):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        files = {
            "VERSION.json": json.dumps({"version": version, "commit": "abc1234", "repo": "uge/ew-1"}),
            "stage7_ramp.py": "x = 1\n",
            "husb238a.py": "x = 1\n",
            "rp1_pwm_sync.py": "x = 1\n",
            "ew1_selftest.py": "x = 1\n",
            "dashboard/VERSION.json": json.dumps({"version": version, "commit": "abc1234", "repo": "uge/ew-1"}),
            "dashboard/ew1_dashboard.py": "x = 1\n",
            "dashboard/ew1_limits.py": "x = 1\n",
            "dashboard/ew1_safestop.py": "x = 1\n",
            "dashboard/static/index.html": "<html></html>\n",
        }
        if bad_path:
            files[bad_path] = "pwn"
        for name, content in files.items():
            raw = content.encode("utf-8")
            ti = tarfile.TarInfo(name=name)
            ti.size = len(raw)
            tf.addfile(ti, io.BytesIO(raw))
    return buf.getvalue()


class TestUpgrader(unittest.TestCase):
    def test_valid_tag(self):
        self.assertTrue(U.valid_tag("v0.1.0"))
        self.assertTrue(U.valid_tag("v1.2.3-rc1"))
        self.assertFalse(U.valid_tag("../etc/passwd"))
        self.assertFalse(U.valid_tag(""))
        self.assertFalse(U.valid_tag("-bad"))

    def test_parse_github_releases(self):
        raw = [
            {
                "tag_name": "v0.2.0",
                "name": "Release v0.2.0",
                "draft": False,
                "prerelease": False,
                "published_at": "2026-11-02T20:00:00Z",
                "html_url": "https://github.com/uge/ew-1/releases/tag/v0.2.0",
                "body": "Notes",
                "assets": [
                    {"name": "ew1-host-v0.2.0.tar.gz", "browser_download_url": "https://example.invalid/t.tar.gz"},
                    {"name": "ew1-host-v0.2.0.tar.gz.sha256", "browser_download_url": "https://example.invalid/t.sha256"},
                ],
            },
            {"tag_name": "v0.3.0-draft", "draft": True, "assets": []},
        ]
        parsed = U.parse_github_releases(raw)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["tag"], "v0.2.0")
        self.assertTrue(parsed[0]["ready"])
        self.assertEqual(parsed[0]["asset_url"], "https://example.invalid/t.tar.gz")

    def test_verify_sha256(self):
        data = b"hello world"
        h = hashlib.sha256(data).hexdigest()
        self.assertEqual(U.verify_sha256(data, f"{h}  ew1-host.tar.gz\n"), h)
        with self.assertRaises(ValueError):
            U.verify_sha256(data, "0" * 64 + "  ew1-host.tar.gz\n")

    def test_tar_slip_rejected(self):
        bad_tar = _make_bundle_tarball(bad_path="../../evil.py")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                U.safe_extract_tar(bad_tar, tmp)

    def test_install_from_github_end_to_end(self):
        tar_bytes = _make_bundle_tarball("v0.2.0")
        sha_hex = hashlib.sha256(tar_bytes).hexdigest()
        releases_json = json.dumps([
            {
                "tag_name": "v0.2.0",
                "name": "v0.2.0",
                "draft": False,
                "prerelease": False,
                "published_at": "2026-11-02T20:00:00Z",
                "assets": [
                    {"name": "ew1-host-v0.2.0.tar.gz", "browser_download_url": "https://mock/ew1-host-v0.2.0.tar.gz"},
                    {"name": "ew1-host-v0.2.0.tar.gz.sha256", "browser_download_url": "https://mock/ew1-host-v0.2.0.tar.gz.sha256"},
                ],
            }
        ]).encode("utf-8")

        def mock_get(url, timeout=10.0, accept=""):
            if url.endswith("/releases?per_page=25"):
                return releases_json
            if url.endswith(".tar.gz"):
                return tar_bytes
            if url.endswith(".sha256"):
                return f"{sha_hex}  ew1-host-v0.2.0.tar.gz\n".encode("utf-8")
            raise AssertionError(f"unexpected URL {url}")

        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, "dashboard", "static"))
            with open(os.path.join(home, "stage7_ramp.py"), "w") as f:
                f.write("old = 1\n")
            res = U.install_from_github("v0.2.0", home_dir=home, http_get=mock_get, run_tests=True)
            self.assertTrue(res["ok"])
            self.assertEqual(res["version"]["version"], "v0.2.0")
            self.assertEqual(U.current_version(os.path.join(home, "dashboard"), home)["version"], "v0.2.0")


if __name__ == "__main__":
    unittest.main()
