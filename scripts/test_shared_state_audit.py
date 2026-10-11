"""Bounded offline negative tests for shared-state SHA preflight."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shared_state_audit import inspect

SHA1 = "a" * 40
SHA2 = "b" * 40
BASE = {
    "schema": "aegis.agent.shared-state.snapshot/1", "advisory_only": True,
    "authority_effect": "NONE", "completeness": "SELECTED_ACTIVE_LANES_ONLY",
    "lanes": [{"repo": "Aegis-Omega/AEGIS-OMEGA", "pr": 732,
               "observed_head_before_coordination_commit": SHA1},
              {"repo": "tarikskalic33/formal-conjectures", "pr": 79,
               "observed_head_before_coordination_commit": SHA2}]
}


class SharedStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "snapshot.json"
        self.path.write_text(json.dumps(BASE), encoding="utf-8")
        self.live = [{"n": 732, "s": SHA1}]
        self.main = {"state": "FRESH", "sha": SHA1}

    def audit(self, live=None, source="github", main=None):
        return inspect(self.live if live is None else live,
                       source, self.main if main is None else main,
                       snapshot_path=self.path)

    def test_match_advisory_only(self):
        a = self.audit()
        self.assertEqual(a["verified_primary_lanes"], 1)
        self.assertEqual(a["out_of_scope_lanes"], 1)
        self.assertEqual(a["admission"], "NOT_VERIFIED")
        self.assertEqual(a["disposition"], "REVIEW_CURRENT_SHARED_STATE")

    def test_new_head_flags_stale(self):
        a = self.audit(live=[{"n": 732, "s": SHA2}])
        self.assertEqual(a["stale_primary_lanes"], 1)
        self.assertEqual(a["observations"][0]["status"], "STALE_HEAD")

    def test_missing_open_pr_is_not_fabricated_closed(self):
        a = self.audit(live=[])
        self.assertEqual(a["observations"][0]["status"], "OPEN_PR_NOT_IN_SNAPSHOT_BOARD")

    def test_partial_list_hold(self):
        a = self.audit(source="partial")
        self.assertEqual(a["disposition"], "HOLD_SHARED_STATE_UNVERIFIED")

    def test_cached_list_hold(self):
        self.assertEqual(self.audit(source="cache")["verified_primary_lanes"], 0)

    def test_unknown_main_hold(self):
        self.assertEqual(self.audit(main={"state": "UNVERIFIED_QUICK"})["verified_primary_lanes"], 0)

    def test_missing_file_hold(self):
        self.path.unlink()
        self.assertIn("SNAPSHOT_MISSING", self.audit()["reason"])

    def test_unknown_schema_hold(self):
        self.path.write_text(json.dumps({**BASE, "schema": "bogus"}))
        self.assertEqual(self.audit()["disposition"], "HOLD_SHARED_STATE_UNVERIFIED")

    def test_duplicate_key_hold(self):
        self.path.write_text('{"schema":"x","schema":"x"}')
        self.assertIn("SNAPSHOT_MISSING_OR_INVALID", self.audit()["reason"])

    def test_duplicate_lane_hold(self):
        self.path.write_text(json.dumps({**BASE, "lanes": BASE["lanes"] * 2}))
        self.assertEqual(self.audit()["verified_primary_lanes"], 0)

    def test_malformed_live_sha_hold(self):
        self.assertEqual(self.audit(live=[{"n": 732, "s": "broken"}])["verified_primary_lanes"], 0)

    def test_duplicate_live_pr_hold(self):
        self.assertIn("DUPLICATED", self.audit(live=self.live * 2)["reason"])

    def test_unknown_constants_hold(self):
        self.path.write_text(json.dumps(BASE)[:-1] + ',"invalid":NaN}')
        self.assertEqual(self.audit()["verified_primary_lanes"], 0)

    def test_oversized_snapshot_hold(self):
        self.path.write_bytes(b" " * 1_048_577)
        self.assertEqual(self.audit()["verified_primary_lanes"], 0)

    def test_never_authorizes(self):
        for source in ("github", "cache", "partial", "unavailable"):
            a = self.audit(source=source)
            self.assertEqual(a["authority_effect"], "NONE")
            self.assertEqual(a["admission"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
