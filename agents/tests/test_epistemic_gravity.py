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


    def test_stale_probe_cannot_hypothetically_bypass_head(self):
        spec = sample()
        spec["heads"]["math"] = "h2"
        result = plan(spec)
        self.assertEqual(result["blocked_probes"], {"check_bridge": "STALE_SOURCE_BINDING"})
        self.assertEqual(result["proposed_probes"], ["check_test"])
        self.assertNotIn("formal_lane", result["hypothetical_newly_supported"])
        self.assertIsNone(result["minimal_proof_debt"]["composed"])
        self.assertNotIn("formal_lane", supported(spec, ("check_bridge",)))

    def test_wrongly_typed_dependency_is_controlled_rejection(self):
        spec = sample()
        spec["claims"]["formal_lane"]["alternatives"] = [[{"malformed": "dict"}]]
        with self.assertRaisesRegex(ValueError, "dependency IDs"):
            plan(spec)

    def test_bool_dependency_is_controlled_rejection(self):
        spec = sample()
        spec["claims"]["formal_lane"]["alternatives"] = [[True]]
        with self.assertRaisesRegex(ValueError, "dependency IDs"):
            plan(spec)

    def test_malformed_claim_and_probe_identifiers_rejected(self):
        spec = sample()
        spec["probes"][1] = {"produces": "bridge", "cost": 1}
        with self.assertRaisesRegex(ValueError, "IDs must be nonempty strings"):
            plan(spec)
        spec = sample()
        spec["claims"][""] = {"value": 1, "alternatives": [["lemma"]]}
        with self.assertRaisesRegex(ValueError, "IDs must be nonempty strings"):
            plan(spec)

    def test_source_rebind_allows_probe_only_after_new_snapshot(self):
        spec = sample()
        spec["heads"]["math"] = "h2"
        stale = plan(spec)
        spec["evidence"]["bridge"]["sha"] = "h2"
        # The old verified lemma is still stale. Only an explicitly refreshed
        # snapshot with new lemma evidence can recover dependent claims.
        self.assertNotIn("formal_lane", plan(spec)["hypothetical_newly_supported"])
        spec["evidence"]["lemma"]["sha"] = "h2"
        updated = plan(spec)
        self.assertEqual(updated["blocked_probes"], {})
        self.assertIn("formal_lane", updated["hypothetical_newly_supported"])
        self.assertNotEqual(stale["source_snapshot_digest"], updated["source_snapshot_digest"])

    def test_multiple_stale_probes_cannot_unlock_alternative(self):
        spec = sample()
        spec["heads"]["code"] = "c2"
        p = plan(spec)
        self.assertEqual(set(p["blocked_probes"]), {"check_test", "check_alternative"})
        self.assertNotIn("product_lane", p["hypothetical_newly_supported"])

    def test_empty_evidence_id_is_rejected(self):
        spec = sample()
        spec["evidence"][""] = {"source": "code", "sha": "c1", "verified": False}
        with self.assertRaisesRegex(ValueError, "IDs must be nonempty strings"):
            plan(spec)


if __name__ == '__main__':
    unittest.main()
