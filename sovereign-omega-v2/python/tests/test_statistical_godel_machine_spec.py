from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "governance" / "statistical-godel-machine-v1.json"


class StatisticalGodelMachineSpecTests(unittest.TestCase):
    def load(self):
        return json.loads(SPEC.read_text(encoding="utf-8"))

    def test_existing_statistical_godel_machine_prior_art_is_bound(self):
        spec = self.load()
        prior = spec["prior_art_boundary"]
        self.assertEqual(
            prior["statistical_godel_machine_2025"]["source"],
            "arXiv:2510.10232",
        )
        self.assertEqual(prior["novelty_status"], "NOT_ESTABLISHED")
        self.assertFalse(prior["global_optimality_claimed"])

    def test_aegis_name_is_conservation_qualified(self):
        spec = self.load()
        self.assertIn("Conservation-Qualified", spec["name"])

    def test_conservation_gate_is_mandatory_before_benefit_gate(self):
        gate = self.load()["conservation_gate"]
        for field in (
            "trusted_receipt_required",
            "exact_parent_state_binding_required",
            "exact_semantic_lineage_binding_required",
            "authority_non_amplifying_required",
            "semantic_accounting_pass_required",
            "uncertainty_accounting_pass_required",
        ):
            self.assertIs(gate[field], True)

    def test_rewrite_never_self_grants_authority(self):
        spec = self.load()
        decision = spec["rewrite_decision"]
        self.assertFalse(decision["automatic_external_mutation"])
        self.assertFalse(decision["automatic_authority_expansion"])
        self.assertEqual(decision["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
