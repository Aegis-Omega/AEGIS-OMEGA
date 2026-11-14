"""Offline falsifiers for UWP-09 Crescendo V2.1 checkpoint adapter.

All fixtures are synthesized in memory; no private holdouts or model responses.
"""
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import uwp09_crescendo_adapter as ad


def digest(data):
    return hashlib.sha256(data).hexdigest()


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pre = {
            "schema": ad.SCHEMA,
            "candidate": "SEC-002-V2.1-PUBLIC-FIXTURE",
            "status": "PLAN_ONLY_NOT_RUN",
            "arms": {"A": "solo", "B": "gated solo", "C": "multi agent"},
            "design": {
                "paired_cases_per_candidate": 30,
                "trial_slots": [
                    {"pair_id": f"SEC02-P{i:03d}", "case_fixture": "NOT_ASSIGNED",
                     "variant_seed": 2026111400 + i, "arms": ["A", "B", "C"],
                     "status": "NOT_RUN"} for i in range(1, 31)
                ]
            }
        }
        cls.source = json.dumps(cls.pre, sort_keys=True).encode("utf-8")
        cls.hash = digest(cls.source)

    def base(self):
        return copy.deepcopy(self.pre)

    def record(self, pair="SEC02-P001", arm="A"):
        return {"pair_id": pair, "arm": arm, "case_sha256": "a" * 64,
                "run_sha256": "b" * 64, "provider": "synthetic",
                "model": "no_real_model", "transcript_integrity": "SELF_CONSISTENT",
                "machine_verdict": "PROVISIONAL_RECORD_CONSISTENT",
                "evidence_origin": "LOCAL_SELF_REPORT",
                "review_authentication": "UNKNOWN"}

    def observations(self, *records):
        return {"schema": ad.OBS_SCHEMA, "candidate": self.pre["candidate"],
                "records": list(records)}

    def test_30_pairs_are_not_30_trials(self):
        r = ad.checkpoint(self.base(), self.hash)
        self.assertEqual(r["registered_pairs"], 30)
        self.assertEqual(r["registered_arm_slots"], 90)
        self.assertEqual(r["verified_execution_denominator"], 0)
        self.assertIsNone(r["verified_false_pass_rate"])
        self.assertEqual(r["promotion_status"], "HOLD")

    def test_one_local_perfect_grade_cannot_promote(self):
        r = ad.checkpoint(self.base(), self.hash, self.observations(self.record()))
        self.assertEqual(r["status"], "UNAUTHENTICATED_REPORTS")
        self.assertEqual(r["locally_reported_arm_records"], 1)
        self.assertEqual(r["verified_execution_denominator"], 0)
        self.assertEqual(r["promotion_status"], "HOLD")

    def test_three_reported_arms_are_not_verified_pair(self):
        records = [self.record(arm=arm) for arm in ("A", "B", "C")]
        r = ad.checkpoint(self.base(), self.hash, self.observations(*records))
        self.assertEqual(r["complete_pairs_locally_reported"], 1)
        self.assertEqual(r["verified_execution_denominator"], 0)

    def test_false_approved_reviewer_rejected(self):
        row = self.record()
        row["review_authentication"] = "VERIFIED"
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(self.base(), self.hash, self.observations(row))

    def test_false_promoted_field_rejected(self):
        row = self.record()
        row["promotion_status"] = "VERIFIED"
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(self.base(), self.hash, self.observations(row))

    def test_duplicate_pair_arm_rejected(self):
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(self.base(), self.hash, self.observations(self.record(), self.record()))

    def test_cross_arm_case_digest_conflict_rejected(self):
        second = self.record(arm="B")
        second["case_sha256"] = "c" * 64
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(self.base(), self.hash, self.observations(self.record(), second))

    def test_duplicate_prereg_pair_rejected(self):
        p = self.base()
        p["design"]["trial_slots"][1]["pair_id"] = p["design"]["trial_slots"][0]["pair_id"]
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(p, self.hash)

    def test_pretend_run_in_plan_rejected(self):
        p = self.base()
        p["design"]["trial_slots"][0]["status"] = "PASSED"
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(p, self.hash)

    def test_boolean_seed_rejected(self):
        p = self.base()
        p["design"]["trial_slots"][0]["variant_seed"] = True
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(p, self.hash)

    def test_wrong_arm_order_rejected(self):
        p = self.base()
        p["design"]["trial_slots"][0]["arms"] = ["A", "C", "B"]
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(p, self.hash)

    def test_extra_arm_rejected(self):
        p = self.base()
        p["arms"]["D"] = "fake"
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(p, self.hash)

    def test_invalid_digest_rejected(self):
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(self.base(), "bad")

    def test_invalid_grade_token_rejected(self):
        row = self.record()
        row["machine_verdict"] = "VERIFIED"
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(self.base(), self.hash, self.observations(row))

    def test_failed_local_grade_not_promoted(self):
        row = self.record()
        row["machine_verdict"] = "FAIL"
        r = ad.checkpoint(self.base(), self.hash, self.observations(row))
        self.assertEqual(r["reported_failure_records"], 1)
        self.assertEqual(r["authority_effect"], "NONE")

    def test_json_duplicate_keys_rejected(self):
        with self.assertRaises(ad.InvalidEvidence):
            json.loads('{"schema":1,"schema":2}', object_pairs_hook=ad.unique_object)

    def test_cli_valid_plan_is_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.json"
            path.write_bytes(self.source)
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                status = ad.main(["--prereg", str(path), "--expected-prereg-sha256", self.hash])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(out.getvalue())["status"], "PLAN_ONLY_NOT_RUN")

    def test_cli_source_hash_change_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.json"
            path.write_bytes(self.source)
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                status = ad.main(["--prereg", str(path), "--expected-prereg-sha256", "0" * 64])
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(out.getvalue())["status"], "INVALID_INPUT")

    def test_null_root_cannot_promote(self):
        with self.assertRaises(ad.InvalidEvidence):
            ad.checkpoint(None, self.hash)

    def test_synthetic_30_full_reports_remain_unknown(self):
        rows = [self.record(f"SEC02-P{i:03d}", arm) for i in range(1, 31)
                for arm in ("A", "B", "C")]
        r = ad.checkpoint(self.base(), self.hash, self.observations(*rows))
        self.assertEqual(r["locally_reported_arm_records"], 90)
        self.assertEqual(r["complete_pairs_locally_reported"], 30)
        self.assertEqual(r["verified_execution_denominator"], 0)
        self.assertIsNone(r["verified_success_rate"])


if __name__ == "__main__":
    unittest.main()
