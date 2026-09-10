#!/usr/bin/env python3
import copy
import unittest

from gravity_quantum.v3_pipeline import receipt as v3_receipt
from gravity_quantum.v4_pipeline import build_chain, receipt


class TestGravityQuantumV4Pipeline(unittest.TestCase):
    def test_v4_stage_contract_is_explicit_and_ordered(self):
        stages = [record.stage for record in build_chain().records]
        self.assertEqual(
            stages,
            [
                "PARENT_V3_EVIDENCE",
                "INGRESS_POLICY",
                "CONTRACT_FIXTURE",
                "INGRESS_VALIDATION",
                "ANALYSIS_RELEASE_GATE",
                "V4_DISPOSITION",
            ],
        )

    def test_v4_receipt_binds_v3_terminal_hash(self):
        r = receipt()
        self.assertEqual(r["parent_v3_terminal_hash"], v3_receipt()["terminal_hash"])
        self.assertTrue(r["certification"]["is_valid"])

    def test_v4_contract_is_ready_but_empirical_ingress_is_not_performed(self):
        disposition = receipt()["stages"][-1]["output"]
        self.assertEqual(disposition["decision"], "HOLD_RESEARCH_ONLY")
        self.assertEqual(disposition["contract_status"], "IMPLEMENTED_AND_TESTED")
        self.assertEqual(disposition["empirical_point_level_ingress"], "NOT_PERFORMED")
        self.assertEqual(disposition["empirical_fit_release"], "BLOCKED")
        self.assertEqual(disposition["claim_promotion"], "BLOCKED")
        self.assertEqual(disposition["authority_effect"], "NONE")

    def test_v4_tamper_is_localized(self):
        chain = build_chain()
        forged = copy.deepcopy(chain)
        forged.records[2].output["batch"]["points"][0]["phase_microrad"] += 1
        certification = forged.certify()
        self.assertFalse(certification["is_valid"])
        self.assertEqual(certification["broken_at"], "CONTRACT_FIXTURE")

    def test_v4_receipt_is_deterministic(self):
        a = receipt()
        b = receipt()
        self.assertEqual(a["terminal_hash"], b["terminal_hash"])
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
