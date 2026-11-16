"""Verify frames emitted by the *built Node server module* in Python.

Required command:
  python3 sovereign-omega-v2/python/tests/test_bridge_transport_vectors.py \
    /path/to/native-node-vectors.json

The input must come from Cockpit's built bridgeControl.js in the same CI job.
No fixture self-generation is permitted on the Python side.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_DIR))
from mutation_admission import MutationAdmissionLedger, event_digest
from test_mutation_bridge_http import BridgeHttpMutationTests

VECTORS_PATH = None


class NativeNodeToPythonTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if VECTORS_PATH is None:
            raise RuntimeError("Native Node JSON vector path is required")
        payload = json.loads(Path(VECTORS_PATH).read_text(encoding="utf-8"))
        assert payload.get("schema") == "AEGIS_BRIDGE_MUTATION_TRANSPORT_V1"
        assert payload.get("source") == "native-node-bridge-control"
        vectors = payload.get("vectors")
        assert isinstance(vectors, list) and len(vectors) == 3
        cls.vectors = vectors

    def test_exact_cross_language_hash_and_byte_contract(self):
        seen = set()
        for vector in self.vectors:
            with self.subTest(name=vector["name"]):
                signal = vector["gate_signal"]
                event = vector["event"]
                self.assertIs(signal["accepted"], True)
                self.assertIs(type(signal["sequence"]), int)
                self.assertGreater(signal["lcb"], 0)
                self.assertEqual(signal["proposal_id"], event["proposal_id"])
                self.assertNotIn(signal["proposal_id"], seen)
                seen.add(signal["proposal_id"])
                payload = bytes.fromhex(event["payload_hex"])
                verifier = bytes.fromhex(event["verifier_hex"])
                context = bytes.fromhex(event["context_hex"])
                self.assertTrue(verifier and verifier[0] == 0x00)
                self.assertEqual(
                    event_digest(payload, verifier, context),
                    signal["event_sha256"],
                )
                self.assertEqual(len(signal["event_sha256"]), 64)
                self.assertNotEqual(
                    event_digest(payload, verifier, context + b"\x00"),
                    signal["event_sha256"],
                )
        self.assertEqual(len(seen), 3)

    def test_node_frames_enforce_single_use_on_real_python_ledger(self):
        ledger = MutationAdmissionLedger()
        for vector in self.vectors:
            signal = vector["gate_signal"]
            event = vector["event"]
            with self.subTest(name=vector["name"]):
                ok, reason = ledger.record(
                    signal["proposal_id"], signal["sequence"],
                    signal["accepted"], signal["lcb"], signal["event_sha256"],
                )
                self.assertEqual((ok, reason), (True, "ACCEPTED"))
                p, v, c = (
                    bytes.fromhex(event[field])
                    for field in ("payload_hex", "verifier_hex", "context_hex")
                )
                self.assertFalse(ledger.authorize_event(
                    signal["proposal_id"], p, v, c, constitutional_approved=False,
                ))
                self.assertFalse(ledger.authorize_event(
                    signal["proposal_id"], p, v, c + b"\x00", constitutional_approved=True,
                ))
                self.assertTrue(ledger.authorize_event(
                    signal["proposal_id"], p, v, c, constitutional_approved=True,
                ))
                self.assertFalse(ledger.authorize_event(
                    signal["proposal_id"], p, v, c, constitutional_approved=True,
                ))
        self.assertEqual(ledger.pending_count, 0)

    def test_native_node_frames_pass_actual_bridge_post_handler(self):
        # The actual bridge.py do_POST source is executed, with the physical
        # CoreMatrix replaced by an observable stub (no large allocations).
        for vector in self.vectors:
            with self.subTest(name=vector["name"]):
                instance = BridgeHttpMutationTests(methodName="test_bound_event_single_use_and_no_mismatched_route")
                instance.setUp()
                signal = vector["gate_signal"]
                event = vector["event"]
                status, response = instance.send("/gate_signal", signal)
                self.assertEqual(status, 200, response)
                self.assertEqual(instance.send("/event", event)[0], 200)
                self.assertEqual(instance.send("/event", event)[0], 403)
                self.assertEqual(len(instance.router.events), 1)
                self.assertEqual(
                    instance.router.events[0],
                    tuple(bytes.fromhex(event[field])
                          for field in ("payload_hex", "verifier_hex", "context_hex")),
                )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: test_bridge_transport_vectors.py /path/to/native-node-vectors.json")
    VECTORS_PATH = sys.argv[1]
    sys.argv = [sys.argv[0]]
    unittest.main(verbosity=2)
