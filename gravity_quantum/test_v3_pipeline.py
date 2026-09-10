#!/usr/bin/env python3
import copy
import unittest

from gravity_quantum.v2_pipeline import receipt as v2_receipt
from gravity_quantum.v3_pipeline import build_chain, receipt


class TestGravityQuantumV3Pipeline(unittest.TestCase):
    def test_v3_stage_contract_is_explicit_and_ordered(self):
        stages = [record.stage for record in build_chain().records]
        self.assertEqual(
            stages,
            [
                "PARENT_V2_EVIDENCE",
                "PUBLISHED_FORMULA_BINDING",
                "COUNTERFACTUAL_GRID",
                "FORMULA_DIVERGENCE_ANALYSIS",
                "V3_DISPOSITION",
            ],
        )

    def test_v3_receipt_binds_v2_terminal_hash(self):
        r = receipt()
        self.assertEqual(r["parent_v2_terminal_hash"], v2_receipt()["terminal_hash"])
        self.assertTrue(r["certification"]["is_valid"])

    def test_v3_finds_formula_divergence_but_blocks_empirical_winner(self):
        r = receipt()
        disposition = r["stages"][-1]["output"]
        self.assertEqual(disposition["simulation_result"], "DISCRIMINATING_PARAMETER_REGIONS_EXIST")
        self.assertEqual(disposition["empirical_model_selection"], "BLOCKED")
        self.assertEqual(disposition["mechanistic_winner"], "NOT_ESTABLISHED")
        self.assertEqual(disposition["quantum_gravity_status"], "NOT_TESTED")
        self.assertEqual(disposition["authority_effect"], "NONE")

    def test_v3_tamper_is_localized(self):
        chain = build_chain()
        forged = copy.deepcopy(chain)
        forged.records[2].output["rows"][0]["formula_divergence"] = True
        certification = forged.certify()
        self.assertFalse(certification["is_valid"])
        self.assertEqual(certification["broken_at"], "COUNTERFACTUAL_GRID")

    def test_v3_receipt_is_deterministic(self):
        a = receipt()
        b = receipt()
        self.assertEqual(a["terminal_hash"], b["terminal_hash"])
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
