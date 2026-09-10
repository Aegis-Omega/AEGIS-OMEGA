#!/usr/bin/env python3
import unittest

from gravity_quantum.evidence_pipeline import receipt as v1_receipt
from gravity_quantum.v2_pipeline import build_chain, receipt


def contains_float(value):
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(contains_float(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_float(v) for v in value)
    return False


class TestGravityQuantumV2Pipeline(unittest.TestCase):
    def test_v2_receipt_binds_v1_terminal_hash(self):
        r = receipt()
        parent = v1_receipt()
        self.assertEqual(r["schema"], "AEGIS_GRAVITY_QUANTUM_EVIDENCE_V2")
        self.assertEqual(r["parent_v1_terminal_hash"], parent["terminal_hash"])
        self.assertTrue(parent["certification"]["is_valid"])
        self.assertEqual(r["stages"][0]["stage"], "PARENT_EVIDENCE")
        self.assertEqual(r["stages"][0]["output"]["terminal_hash"], parent["terminal_hash"])

    def test_v2_stage_contract_is_explicit_and_ordered(self):
        r = receipt()
        self.assertEqual(
            [stage["stage"] for stage in r["stages"]],
            [
                "PARENT_EVIDENCE",
                "SCALED_MEASUREMENT",
                "CUBIC_PREFACTOR_IDENTIFIABILITY",
                "MODEL_DISCRIMINATION",
                "V2_DISPOSITION",
            ],
        )
        self.assertTrue(r["certification"]["is_valid"])

    def test_v2_disposition_fails_closed_on_mechanistic_selection(self):
        r = receipt()
        disposition = r["stages"][-1]["output"]
        self.assertEqual(disposition["decision"], "HOLD_RESEARCH_ONLY")
        self.assertEqual(disposition["model_selection"], "NO_UNIQUE_MODEL_SELECTION")
        self.assertEqual(disposition["mechanistic_winner"], "NOT_ESTABLISHED")
        self.assertEqual(disposition["quantum_gravity_status"], "NOT_TESTED")
        self.assertEqual(disposition["claim_promotion"], "BLOCKED")
        self.assertEqual(disposition["authority_effect"], "NONE")

    def test_v2_chain_is_deterministic_and_contains_no_floats(self):
        first = receipt()
        second = receipt()
        self.assertEqual(first["terminal_hash"], second["terminal_hash"])
        self.assertFalse(contains_float(first))

    def test_model_discrimination_tamper_is_localized(self):
        chain = build_chain()
        target = next(record for record in chain.records if record.stage == "MODEL_DISCRIMINATION")
        target.output["decision"] = "QGI_GRAVITY_EP_WINS"
        result = chain.certify()
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["broken_at"], "MODEL_DISCRIMINATION")


if __name__ == "__main__":
    unittest.main(verbosity=2)
