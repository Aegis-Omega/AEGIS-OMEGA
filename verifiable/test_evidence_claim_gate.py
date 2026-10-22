import copy
import unittest

try:
    from verifiable.evidence_claim_gate import validate
except ModuleNotFoundError:
    from evidence_claim_gate import validate

SHA = "a" * 64
HEAD = "b" * 40


def sample(status="VERIFIED", kind="test", observation="PASS"):
    return {
        "schema": "aegis.evidence-claim.v1",
        "claim_id": "sample-1",
        "target": "Service A request reaches intended backend",
        "status": status,
        "scope": {"description": "service A, sandbox tenant, 2026-10-22", "revision": HEAD},
        "evidence": [{"kind": kind, "observation": observation, "uri": "https://example.invalid/build/123",
                      "observed_at": "2026-10-22T12:00:00Z", "target_match": True, "sha256": SHA}],
        "side_effects": {"performed": False},
    }


class EvidenceGateTests(unittest.TestCase):
    def test_valid_verified(self):
        self.assertEqual(validate(sample()), [])

    def test_valid_open_without_evidence(self):
        x = sample("OPEN"); x["evidence"] = []
        self.assertEqual(validate(x), [])

    def test_metadata_cannot_promote_verified(self):
        x = sample(kind="metadata")
        self.assertTrue(any("VERIFIED" in e for e in validate(x)))

    def test_pr_description_cannot_promote_verified(self):
        x = sample(kind="pr_description")
        self.assertTrue(validate(x))

    def test_ci_of_other_target_not_accepted(self):
        x = sample(); x["evidence"][0]["target_match"] = False
        self.assertTrue(validate(x))

    def test_missing_blob_binding_not_accepted(self):
        x = sample(); x["evidence"][0].pop("sha256")
        self.assertTrue(validate(x))

    def test_import_failure_not_refutation(self):
        x = sample("REFUTED", "compiler", "FAIL")
        self.assertTrue(any("REFUTED" in e for e in validate(x)))

    def test_actual_counterexample_can_refute(self):
        x = sample("REFUTED", "counterexample", "COUNTEREXAMPLE")
        self.assertEqual(validate(x), [])

    def test_absence_not_false(self):
        x = sample("UNKNOWN"); x["evidence"] = []; x["claim_is_false"] = True
        self.assertTrue(validate(x))

    def test_unauthorized_side_effect_rejected(self):
        x = sample(); x["side_effects"] = {"performed": True}
        self.assertTrue(validate(x))

    def test_explicitly_authorized_effect_structurally_accepted(self):
        x = sample(); x["side_effects"] = {"performed": True, "operator_authorization_ref": "user-turn-15", "exact_operations": ["create branch"]}
        self.assertEqual(validate(x), [])

    def test_incomplete_universal_scan_rejected(self):
        x = sample(); x["scope"]["universal"] = True
        self.assertTrue(validate(x))

    def test_unmatched_inventory_total_rejected(self):
        x = sample(); x["inventory"] = {"complete": True, "reported_total": 91, "items": [1, 2]}
        self.assertTrue(validate(x))

    def test_complete_inventory_accepted(self):
        x = sample(); x["inventory"] = {"complete": True, "reported_total": 2, "items": [1, 2]}
        self.assertEqual(validate(x), [])

    def test_status_not_hardcoded_false(self):
        x = sample(); x["status"] = False
        self.assertTrue(validate(x))


if __name__ == "__main__":
    unittest.main()