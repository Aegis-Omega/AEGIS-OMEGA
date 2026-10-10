"""Live inference must not downgrade provider failures to approved templates.

Hermetic: an injected client replaces anth_client; no network or billing.
"""
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import platform_helpers as ph


class LiveProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.depts = ph.PLATFORM_DEPARTMENTS[:2]
        self.persisted = []

    def run_live(self, *, payload=None, stop_reason=None, unavailable=False):
        if unavailable:
            def no_client():
                raise RuntimeError("NO_PROVIDER")
            fake = types.SimpleNamespace(get_client=no_client, make_cached_system=lambda s: s)
        else:
            if payload is None:
                payload = {
                    "departments": [
                        {"id": d["id"], "output": "provider response for " + d["id"]}
                        for d in self.depts
                    ],
                    "constitutional_audit": {"verdict": "FLAG", "concerns": []},
                    "projection": {"first_year_arr_usd": 1200000, "tier": "T2",
                                   "governed_note": "unverified forecast"},
                }
            raw = payload if isinstance(payload, str) else json.dumps(payload)
            response = types.SimpleNamespace(
                stop_reason=stop_reason,
                content=[types.SimpleNamespace(text=raw)],
            )
            client = types.SimpleNamespace(messages=types.SimpleNamespace(
                create=lambda **kwargs: response))
            fake = types.SimpleNamespace(
                get_client=lambda: client, make_cached_system=lambda s: s,
            )
        with patch.dict(sys.modules, {"anth_client": fake}):
            with patch.object(ph, "store_swarm_memory",
                              side_effect=lambda *a: self.persisted.append(a)):
                return ph.swarm_collaborate_live(
                    "bounded source verification", "analysis", self.depts,
                    email="operator@example.invalid",
                )

    def test_missing_provider_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "LIVE_PROVIDER"):
            self.run_live(unavailable=True)
        self.assertEqual(self.persisted, [])

    def test_provider_refusal_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "LIVE_PROVIDER"):
            self.run_live(stop_reason="refusal")
        self.assertEqual(self.persisted, [])

    def test_invalid_json_rejected(self):
        with self.assertRaisesRegex(ValueError, "LIVE_RESPONSE_INVALID_JSON"):
            self.run_live(payload="{malformed")
        self.assertEqual(self.persisted, [])

    def test_incomplete_department_payload_rejected(self):
        p = {"departments": [{"id": self.depts[0]["id"], "output": "one"}],
             "constitutional_audit": {"verdict": "APPROVED", "concerns": []},
             "projection": {"first_year_arr_usd": 1000}}
        with self.assertRaisesRegex(ValueError, "LIVE_RESPONSE_MISSING_DEPARTMENT_OUTPUT"):
            self.run_live(payload=p)

    def test_duplicate_department_payload_rejected(self):
        p = {"departments": [
                {"id": self.depts[0]["id"], "output": "a"},
                {"id": self.depts[0]["id"], "output": "duplicate"},
                {"id": self.depts[1]["id"], "output": "b"},
             ], "constitutional_audit": {"verdict": "APPROVED", "concerns": []},
             "projection": {"first_year_arr_usd": 1000}}
        with self.assertRaisesRegex(ValueError, "LIVE_RESPONSE_DUPLICATE_DEPARTMENT"):
            self.run_live(payload=p)

    def test_unknown_verdict_rejected_not_rewritten_approved(self):
        p = {"departments": [
                {"id": d["id"], "output": "done"} for d in self.depts
             ], "constitutional_audit": {"verdict": "INVALID", "concerns": []},
             "projection": {"first_year_arr_usd": 1000}}
        with self.assertRaisesRegex(ValueError, "LIVE_RESPONSE_UNVERIFIED_VERDICT"):
            self.run_live(payload=p)

    def test_missing_arr_rejected_not_defaulted(self):
        p = {"departments": [
                {"id": d["id"], "output": "done"} for d in self.depts
             ], "constitutional_audit": {"verdict": "APPROVED", "concerns": []},
             "projection": {}}
        with self.assertRaisesRegex(ValueError, "LIVE_RESPONSE_INVALID_PROJECTION"):
            self.run_live(payload=p)

    def test_good_complete_live_response_no_early_memory_write(self):
        result = self.run_live()
        self.assertEqual(len(result["artifacts"]), len(self.depts))
        self.assertEqual(result["constitutional_audit"]["verdict"], "FLAG")
        self.assertEqual(result["projection"]["first_year_arr_usd"], 1200000)
        self.assertEqual(self.persisted, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
