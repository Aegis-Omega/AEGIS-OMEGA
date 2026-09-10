#!/usr/bin/env python3
import copy
import unittest

from gravity_quantum.v4_pipeline import receipt as v4_receipt
from gravity_quantum.v5_pipeline import build_chain, receipt


class TestGravityQuantumV5Pipeline(unittest.TestCase):
    def test_v5_stage_contract_is_explicit_and_ordered(self):
        stages = [record.stage for record in build_chain().records]
        self.assertEqual(
            stages,
            [
                "PARENT_V4_EVIDENCE",
                "EXTERNAL_ADAPTER_POLICY",
                "CSV_CONTRACT_FIXTURE",
                "ADAPTER_CANDIDATE",
                "V5_DISPOSITION",
            ],
        )

    def test_v5_receipt_binds_v4_terminal_hash(self):
        r = receipt()
        self.assertEqual(r["parent_v4_terminal_hash"], v4_receipt()["terminal_hash"])
        self.assertTrue(r["certification"]["is_valid"])

    def test_v5_is_adapter_ready_but_not_empirical_ingress(self):
        disposition = receipt()["stages"][-1]["output"]
        self.assertEqual(disposition["decision"], "HOLD_RESEARCH_ONLY")
        self.assertEqual(disposition["adapter_status"], "IMPLEMENTED_AND_TESTED")
        self.assertEqual(disposition["external_dataset_ingress"], "NOT_PERFORMED")
        self.assertEqual(disposition["empirical_fit_release"], "BLOCKED")
        self.assertEqual(disposition["claim_promotion"], "BLOCKED")
        self.assertEqual(disposition["authority_effect"], "NONE")

    def test_v5_tamper_is_localized(self):
        chain = build_chain()
        forged = copy.deepcopy(chain)
        forged.records[3].output["batch"]["points"][0]["phase_microrad"] += 1
        certification = forged.certify()
        self.assertFalse(certification["is_valid"])
        self.assertEqual(certification["broken_at"], "ADAPTER_CANDIDATE")

    def test_v5_receipt_is_deterministic(self):
        a = receipt()
        b = receipt()
        self.assertEqual(a["terminal_hash"], b["terminal_hash"])
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
