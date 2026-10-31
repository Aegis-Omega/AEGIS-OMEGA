import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from agents.epistemic_gravity import plan, supported


def sample():
    return {
        "schema_version": "0.1",
        "heads": {"math": "h1", "code": "c1"},
        "evidence": {
            "lemma": {"source": "math", "sha": "h1", "verified": True},
            "bridge": {"source": "math", "sha": "h1", "verified": False},
            "test": {"source": "code", "sha": "c1", "verified": False},
            "alternative": {"source": "code", "sha": "c1", "verified": False},
        },
        "claims": {
            "formal_lane": {"value": 10, "alternatives": [["lemma", "bridge"]]},
            "product_lane": {"value": 3, "alternatives": [["test"], ["alternative"]]},
            "composed": {"value": 50, "alternatives": [["formal_lane", "product_lane"]]},
        },
        "probes": {
            "check_bridge": {"produces": "bridge", "cost": 2},
            "check_test": {"produces": "test", "cost": 3},
            "check_alternative": {"produces": "alternative", "cost": 5},
        },
        "budget": 5,
    }


class TestGravity(unittest.TestCase):
    def test_compositional_unlock_optimized_not_fixed(self):
        p = plan(sample())
        self.assertEqual(p["proposed_probes"], ["check_bridge", "check_test"])
        self.assertEqual(p["hypothetical_newly_supported"], ["composed", "formal_lane", "product_lane"])
        self.assertEqual(p["hypothetical_unlocked_value"], 63)
        self.assertEqual(p["hypothetical_cost_units"], 5)

    def test_exact_minimal_debt(self):
        p = plan(sample())
        self.assertEqual(p["minimal_proof_debt"]["composed"], {"cost": 5, "probes": ["check_bridge", "check_test"]})
        self.assertEqual(p["minimal_proof_debt"]["product_lane"], {"cost": 3, "probes": ["check_test"]})

    def test_no_real_promotion(self):
        spec = sample()
        result = plan(spec)
        self.assertEqual(result["authority_effect"], "NONE")
        self.assertEqual(result["execution"], "NOT_PERFORMED")
        self.assertNotIn("formal_lane", supported(spec))
        self.assertFalse(spec["evidence"]["bridge"]["verified"])

    def test_stale_source_retracts_downstream(self):
        spec = sample()
        spec["evidence"]["bridge"]["verified"] = True
        spec["evidence"]["test"]["verified"] = True
        self.assertEqual(supported(spec), frozenset(spec["claims"]))
        spec["heads"]["math"] = "h2"
        self.assertEqual(supported(spec), frozenset(["product_lane"]))

    def test_alternative_support_path(self):
        spec = sample()
        spec["evidence"]["alternative"]["verified"] = True
        self.assertIn("product_lane", supported(spec))
        self.assertEqual(plan(spec)["proposed_probes"], ["check_bridge"])

    def test_budget_zero_fail_closed(self):
        spec = sample()
        spec["budget"] = 0
        self.assertEqual(plan(spec)["proposed_probes"], [])
        self.assertEqual(plan(spec)["decision"], "NO_BENEFICIAL_PROPOSAL")

    def test_cycles_rejected(self):
        spec = sample()
        spec["claims"]["formal_lane"]["alternatives"] = [["composed"]]
        with self.assertRaisesRegex(ValueError, "cyclic"):
            plan(spec)

    def test_unregistered_sources_rejected(self):
        spec = sample()
        spec["evidence"]["bridge"]["source"] = "phantom"
        with self.assertRaisesRegex(ValueError, "unknown source"):
            plan(spec)

    def test_id_collision_rejected(self):
        spec = sample()
        spec["claims"]["lemma"] = {"value": 1, "alternatives": [["bridge"]]}
        with self.assertRaisesRegex(ValueError, "collision"):
            plan(spec)

    def test_digest_changes_with_exact_head(self):
        a = sample()
        b = copy.deepcopy(a)
        b["heads"]["math"] = "h2"
        self.assertNotEqual(plan(a)["source_snapshot_digest"], plan(b)["source_snapshot_digest"])

    def test_deterministic_receipt(self):
        self.assertEqual(plan(sample()), plan(sample()))

    def test_unaffordable_probe_has_no_claimed_value(self):
        spec = sample()
        spec["budget"] = 1
        r = plan(spec)
        self.assertEqual(r["hypothetical_unlocked_value"], 0)
        self.assertEqual(r["hypothetical_newly_supported"], [])

    def test_boolean_cost_rejected(self):
        spec = sample()
        spec["probes"]["check_bridge"]["cost"] = True
        with self.assertRaisesRegex(ValueError, "invalid cost"):
            plan(spec)

    def test_limit_declared(self):
        spec = sample()
        spec["probes"].update({f"p{i}": {"produces": "bridge", "cost": 1} for i in range(18)})
        with self.assertRaisesRegex(ValueError, "too many"):
            plan(spec)


if __name__ == '__main__':
    unittest.main()
