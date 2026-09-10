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

    def test_closed_bridge_cannot_bypass_required_gates(self):
        candidate = copy.deepcopy(self.manifest)
        candidate["bridge"]["status"] = "CLOSED_VERIFIED"
        with self.assertRaises(mod.ManifestError):
            mod.evaluate(candidate)


if __name__ == "__main__":
    unittest.main()
