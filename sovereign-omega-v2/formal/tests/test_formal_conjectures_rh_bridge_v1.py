import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "bridges" / "verify_formal_conjectures_rh_bridge_v1.py"
MANIFEST = ROOT / "bridges" / "formal_conjectures_rh_target_v1.json"

spec = importlib.util.spec_from_file_location("rh_bridge_verifier", VERIFIER)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RHBridgeGateTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_current_open_bridge_is_hold_not_proof(self):
        receipt = mod.evaluate(self.manifest)
        self.assertEqual(receipt["decision"], "HOLD_RESEARCH_ONLY")
        self.assertFalse(receipt["rh_proved"])
        self.assertEqual(receipt["claim_promotion"], "BLOCKED")
        self.assertEqual(receipt["merge"], "NOT_PERFORMED")
        self.assertEqual(receipt["authority_effect"], "NONE")

    def test_semantic_obstruction_is_bound_without_promoting_rh(self):
        receipt = mod.evaluate(self.manifest)
        self.assertEqual(
            receipt["semantic_obstruction"],
            "ABSTRACT_QW_REQUIRES_CONCRETE_WEIL_IDENTIFICATION",
        )
        self.assertIn(
            "ABSTRACT_QW_TRIVIAL_POSITIVE_MODEL_PROOF_SOURCE_PINNED",
            receipt["reason_codes"],
        )
        self.assertIn("aegis_weil_semantics_mapped_to_mathlib", receipt["open_gates"])
        self.assertFalse(receipt["rh_proved"])

    def test_promotion_request_with_open_gates_is_denied(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["bridge"]["promotion_requested"] = True
        receipt = mod.evaluate(candidate)
        self.assertEqual(receipt["decision"], "DENY_PROMOTION")
        self.assertIn("OPEN_REQUIRED_GATES", receipt["reason_codes"])

    def test_source_statement_tamper_is_schema_failure(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["external_source"]["source_statement"] += "-- tampered"
        with self.assertRaises(mod.ManifestError):
            mod.evaluate(candidate)

    def test_semantic_obstruction_digest_tamper_is_schema_failure(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["semantic_obstruction"]["source_sha256"] = "0" * 64
        with self.assertRaises(mod.ManifestError):
            mod.evaluate(candidate)

    def test_semantic_obstruction_scope_cannot_claim_rh(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["semantic_obstruction"]["claim_scope"] = "RIEMANN_HYPOTHESIS_PROVED"
        with self.assertRaises(mod.ManifestError):
            mod.evaluate(candidate)

    def test_closed_bridge_cannot_bypass_required_gates(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["bridge"]["status"] = "CLOSED_VERIFIED"
        with self.assertRaises(mod.ManifestError):
            mod.evaluate(candidate)


if __name__ == "__main__":
    unittest.main()
