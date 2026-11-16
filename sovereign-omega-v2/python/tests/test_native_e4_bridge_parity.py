"""Exact-source native E4 -> existing Node codec -> Python bridge parity check.

Consumes JSON produced by the actual RiskBudgetManager in pinned PR #817 and
encoded by bridgeControl.js from the exact candidate PR #811 checkout.
No invented E4 decision, network listener, real CoreMatrix or credential.

This proves syntactic/semantic transport and fail-closed admission only.
Synthetic CI samples and a self-declared TypeScript decision are not real-world
operator identity or independent verifier provenance.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY_ROOT = HERE.parent
sys.path.insert(0, str(PY_ROOT))
sys.path.insert(0, str(HERE))

from mutation_admission import MutationAdmissionLedger, event_digest
from test_mutation_bridge_http import BridgeHttpMutationTests


PARITY_PATH = None


class NativeE4ParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if PARITY_PATH is None:
            raise RuntimeError("Exact native E4 parity fixture required")
        data = json.loads(Path(PARITY_PATH).read_text(encoding="utf-8"))
        cls.expected_sha = os.environ.get("AEGIS_NATIVE_E4_SOURCE_SHA")
        cls.assert_external = isinstance(cls.expected_sha, str) and re.fullmatch(
            r"[0-9a-f]{40}", cls.expected_sha,
        )
        if not cls.assert_external:
            raise RuntimeError("Missing pinned native E4 source SHA")
        if data.get("schema") != "AEGIS_NATIVE_E4_BRIDGE_PARITY_V1":
            raise RuntimeError("Unknown native E4 fixture schema")
        if data.get("source") != "native-PR817-RiskBudgetManager-to-PR811-codec":
            raise RuntimeError("Not an exact source-bound E4 fixture")
        if data.get("fixture_class") != "SYNTHETIC_CI_ONLY_NOT_MUTATION_PROOF":
            raise RuntimeError("E4 fixture trust class mismatch")
        if data.get("e4_sha") != cls.expected_sha:
            raise RuntimeError("E4 native SHA provenance mismatch")
        if data.get("native_component") != "bridge-e4-synthetic-mutation":
            raise RuntimeError("Wrong component provenance")
        if data.get("registered_operator") != "bridge-e4-synthetic-test-v1":
            raise RuntimeError("Wrong registered operator")
        cls.data = data

    def test_exact_native_decision_bytes_are_bound_to_python_grant(self):
        frames = self.data["admitted"]
        signal = frames["gate_signal"]
        event = frames["event"]
        self.assertIs(signal["accepted"], True)
        self.assertEqual(signal["method"], "anytime_valid_bernstein")
        self.assertGreater(signal["sample_size"], 0)
        self.assertGreater(signal["lcb"], 0)
        self.assertGreaterEqual(signal["e_value"], 1 / signal["risk_spent"])
        self.assertEqual(event["proposal_id"], signal["proposal_id"])
        p, v, c = (bytes.fromhex(event[k])
                   for k in ("payload_hex", "verifier_hex", "context_hex"))
        self.assertEqual(event_digest(p, v, c), signal["event_sha256"])
        ledger = MutationAdmissionLedger()
        accepted = ledger.record(
            signal["proposal_id"], signal["sequence"], signal["accepted"],
            signal["lcb"], signal["event_sha256"],
            e_value=signal["e_value"], risk_spent=signal["risk_spent"],
            sample_size=signal["sample_size"], e4_method=signal["method"],
        )
        self.assertEqual(accepted, (True, "ACCEPTED"))
        self.assertFalse(ledger.authorize_event(
            signal["proposal_id"], p, v, c, constitutional_approved=False,
        ))
        self.assertTrue(ledger.authorize_event(
            signal["proposal_id"], p, v, c, constitutional_approved=True,
        ))
        self.assertFalse(ledger.authorize_event(
            signal["proposal_id"], p, v, c, constitutional_approved=True,
        ))

    def test_source_generated_signal_reaches_actual_python_post_handler(self):
        handler = BridgeHttpMutationTests(methodName="test_bound_event_single_use_and_no_mismatched_route")
        handler.setUp()
        signal = self.data["admitted"]["gate_signal"]
        event = self.data["admitted"]["event"]
        status, response = handler.send("/gate_signal", signal)
        self.assertEqual(status, 200, response)
        self.assertEqual(handler.send("/event", event)[0], 200)
        self.assertEqual(handler.send("/event", event)[0], 403)
        self.assertEqual(len(handler.router.events), 1)
        self.assertEqual(handler.ledger.pending_count, 0)

    def test_source_generated_positive_lcb_but_weak_e_value_never_grants(self):
        weak = self.data["weak_decision"]
        self.assertFalse(weak["accepted"])
        self.assertGreater(weak["lcb_value"], 0)
        self.assertEqual(weak["rejection_reason"], "E_VALUE_FAIL")
        self.assertEqual(weak["risk_spent"], 0)
        good = self.data["admitted"]["gate_signal"]
        bad = {**good, "proposal_id": weak["proposal_id"],
               "lcb": weak["lcb_value"], "e_value": weak["e_value"]}
        # A fake caller changing 'accepted' to true cannot forge a gate pass.
        handler = BridgeHttpMutationTests(methodName="test_bound_event_single_use_and_no_mismatched_route")
        handler.setUp()
        status, result = handler.send("/gate_signal", bad)
        self.assertEqual(status, 403, result)
        self.assertEqual(result["reason"], "E_VALUE_FAIL")
        self.assertEqual(handler.ledger.pending_count, 0)
        self.assertEqual(handler.matrix.signals, [])
        self.assertEqual(handler.gate.signals, [])

    def test_signed_offline_claims_do_not_bypass_method_and_alpha_contract(self):
        signal = self.data["admitted"]["gate_signal"]
        for alteration in (
            {"method": "fixed-sample-only"},
            {"e_value": 0.01},
            {"risk_spent": 0},
            {"sample_size": 0},
            {"accepted": False},
        ):
            with self.subTest(alteration=alteration):
                candidate = dict(signal)
                candidate.update(alteration)
                if alteration == {"accepted": False}:
                    candidate["risk_spent"] = 0
                handler = BridgeHttpMutationTests(methodName="test_bound_event_single_use_and_no_mismatched_route")
                handler.setUp()
                status, _ = handler.send("/gate_signal", candidate)
                if alteration == {"accepted": False}:
                    # Explicit rejection updates gate history but never M2.
                    self.assertEqual(status, 200)
                else:
                    self.assertEqual(status, 403)
                self.assertEqual(handler.matrix.signals, [])
                self.assertEqual(handler.ledger.pending_count, 0)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: test_native_e4_bridge_parity.py /path/to/e4-parity.json")
    PARITY_PATH = sys.argv[1]
    sys.argv = [sys.argv[0]]
    unittest.main(verbosity=2)
