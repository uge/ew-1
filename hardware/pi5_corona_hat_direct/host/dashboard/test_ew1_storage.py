#!/usr/bin/env python3
"""Unit tests for ew1_storage.py (hierarchical session storage + SQLite catalog)."""
import json
import os
import tempfile
import time
import unittest

import ew1_storage as S


class TestStorage(unittest.TestCase):
    def test_session_and_run_lifecycle(self):
        with tempfile.TemporaryDirectory() as root:
            st = S.Storage(root, version="v0.1.0", session_label="initial bench")
            sessions = st.list_sessions()
            self.assertEqual(len(sessions), 1)
            sid = sessions[0]["session_id"]
            self.assertEqual(sessions[0]["label"], "initial bench")
            self.assertTrue(os.path.isfile(os.path.join(root, S.DB_FILENAME)))

            # Create a simulated run CSV and video in root_dir (as stage7_ramp.py and ew1_camera.py do)
            stem = "stage7_ramp_ramp_5V_20261102_210500"
            csv_path = os.path.join(root, f"{stem}.csv")
            with open(csv_path, "w") as f:
                f.write("t_s,phase,duty,ain0_V,pred_V,slope_kV_per_ms,vbus_V,bridge_V,ain1_V,nFAULT,EFUSE_FLT,INTLK,OVTRIP\n")
                f.write("0.01,ramp,0.01,0.5,0.51,0.01,5.1,5.0,0.025,1,1,1,0\n")
            vid_path = os.path.join(root, f"{stem}.mp4")
            with open(vid_path, "wb") as f:
                f.write(b"fake-mp4-bytes")

            rows = [[0.01, "ramp", 0.01, 0.5, 0.51, 0.01, 5.1, 5.0, 0.025, 1, 1, 1, 0]]
            rec = {
                "mode": "ramp",
                "params": {"vbus": 5, "freq_hz": 32000, "target_kv": 3.0, "abort_kv": 4.0,
                           "max_duty": 0.17, "ain1_max_v": 0.10, "hold_s": 2.0},
                "t_start": 1000.0,
                "t_end": 1002.5,
                "code": 0,
                "abort": None,
                "result": {"peak_kv": 3.05, "duty_end": 0.08, "duty_at_target": 0.08},
                "csv": f"{stem}.csv",
                "video": {"file": f"{stem}.mp4"},
            }
            info = st.register_run(rec, rows=rows)
            self.assertEqual(info["session_id"], sid)
            # Files moved into hierarchical session folder
            self.assertFalse(os.path.exists(csv_path))
            self.assertFalse(os.path.exists(vid_path))
            resolved_csv = st.resolve_file(f"{stem}.csv")
            resolved_json = st.resolve_file(f"{stem}.json")
            resolved_vid = st.resolve_file(f"{stem}.mp4")
            self.assertTrue(os.path.isfile(resolved_csv))
            self.assertTrue(os.path.isfile(resolved_json))
            self.assertTrue(os.path.isfile(resolved_vid))
            self.assertIn(os.path.join("sessions", ""), resolved_csv)

            recs = st.list_recordings()
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["stem"], stem)
            self.assertAlmostEqual(recs[0]["peak_kv"], 3.05)
            self.assertAlmostEqual(recs[0]["peak_ua"], 2.5)
            self.assertEqual(recs[0]["sample_count"], 1)
            self.assertEqual(recs[0]["video_bytes"], 14)

            # Start a second session and record a standalone camera clip
            m2 = st.start_session(label="second session")
            cam_name = "cam_20261102_211000.mp4"
            with open(os.path.join(root, cam_name), "wb") as f:
                f.write(b"12345678")
            st.register_camera_clip(cam_name, t0=2000.0, t1=2005.0)
            self.assertTrue(os.path.isfile(st.resolve_file(cam_name)))
            self.assertEqual(len(st.list_recordings(session_id=m2["session_id"])), 1)
            self.assertEqual(len(st.list_recordings()), 2)

            # Notes update + ZIP archives + SQLite export
            st.update_recording_notes(stem, "gap=10mm clean")
            self.assertEqual(st.list_recordings(session_id=sid)[0]["notes"], "gap=10mm clean")
            rzip = st.build_recording_zip(stem)
            self.assertGreater(len(rzip), 50)
            szip = st.build_session_zip(sid)
            self.assertGreater(len(szip), 50)
            db_bytes = st.export_sqlite_bytes()
            self.assertTrue(db_bytes.startswith(b"SQLite format 3"))

            # Delete recording and delete session
            st.delete_recording(stem)
            self.assertIsNone(st.resolve_file(f"{stem}.csv"))
            self.assertEqual(len(st.list_recordings(session_id=sid)), 0)
            st.delete_session(sid)
            self.assertNotIn(sid, {s["session_id"] for s in st.list_sessions()})

    def test_legacy_flat_files_imported(self):
        with tempfile.TemporaryDirectory() as root:
            stem = "stage7_ramp_align_5V_20261101_120000"
            with open(os.path.join(root, f"{stem}.csv"), "w") as f:
                f.write("t_s,phase,duty,ain0_V,pred_V,slope_kV_per_ms,vbus_V,bridge_V,ain1_V,nFAULT,EFUSE_FLT,INTLK,OVTRIP\n")
            with open(os.path.join(root, f"{stem}.json"), "w") as f:
                json.dump({"mode": "align", "code": 0, "result": {"align": 1.0}}, f)
            with open(os.path.join(root, "cam_20261101_120500.mp4"), "wb") as f:
                f.write(b"legacy-cam")

            st = S.Storage(root)
            recs = st.list_recordings()
            stems = {r["stem"] for r in recs}
            self.assertIn(stem, stems)
            self.assertIn("cam_20261101_120500", stems)
            self.assertTrue(os.path.isfile(st.resolve_file(f"{stem}.csv")))
            self.assertTrue(os.path.isfile(st.resolve_file("cam_20261101_120500.mp4")))


if __name__ == "__main__":
    unittest.main()
