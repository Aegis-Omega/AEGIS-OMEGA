"""Exercise the actual bridge POST handler without constructing the 4-GB CoreMatrix.

This test compiles exactly BridgeHandler.do_POST from the candidate source AST
and replaces downstream dependencies with observably bounded stubs. It tests
the HTTP decision path, not the actual HTTP server, provider identity, or E4
statistical correctness. Run in native GitHub Actions on the exact PR HEAD.
"""
from __future__ import annotations

import ast
import io
import json
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

PY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PY_ROOT))
from mutation_admission import (
    MutationAdmissionLedger, control_authenticated,
    control_secrets_distinct, event_digest,
)
from dna import GateSignal, EventClass, SCHEMAS


class FakeGate:
    def __init__(self, deny=False):
        self.deny = deny
        self.signals = []
        self.verdicts = {}
        self._last_sequence = -1
        self._sealed = False
        self.silently_discard = False

    def record_signal(self, signal):
        # Faithfully model the frozen gate's silent drop behavior.
        if self._sealed or self.silently_discard or signal.sequence <= self._last_sequence:
            return
        self._last_sequence = signal.sequence
        self.signals.append(signal)
        self.verdicts[signal.proposal_id] = signal.accepted and not self.deny

    def is_approved(self, proposal_id):
        return self.verdicts.get(proposal_id, False)

    def last_sequence(self):
        return self._last_sequence

    def seal(self):
        self._sealed = True

    @property
    def is_sealed(self):
        return self._sealed


class FakeMatrix:
    def __init__(self):
        self.signals = []

    def receive_gate_signal(self, proposal_id, accepted, sequence):
        self.signals.append((proposal_id, accepted, sequence))


class FakeRouter:
    def __init__(self):
        self.events = []

    def route(self, payload, verifier, context):
        self.events.append((payload, verifier, context))
        return {"status": "ROUTED"}


def make_bridge_post_handler(gate, matrix, router, ledger):
    """Compile actual do_POST implementation against no-IO test dependencies."""
    source = (PY_ROOT / "bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    bridge_classes = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BridgeHandler"
    ]
    if len(bridge_classes) != 1:
        raise AssertionError("bridge source must have exactly one BridgeHandler")
    do_post = [
        node for node in bridge_classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "do_POST"
    ]
    if len(do_post) != 1:
        raise AssertionError("bridge source must have exactly one do_POST")

    # Preserve the exact body of do_POST while excluding unrelated handlers
    # that instantiate external services or allocate the CoreMatrix arena.
    cls = ast.ClassDef(
        name="HttpBridgeUnderTest", bases=[], keywords=[],
        body=do_post, decorator_list=[],
    )
    ast.fix_missing_locations(cls)
    namespace = {
        "os": os, "json": json, "threading": threading,
        "last_ack_sequence": -1, "_lock": threading.Lock(),
        "_mutation_admission": ledger, "gate": gate, "matrix": matrix,
        "router": router, "GateSignal": GateSignal,
        "EventClass": EventClass, "SCHEMAS": SCHEMAS,
        "control_authenticated": control_authenticated,
        "control_secrets_distinct": control_secrets_distinct,
    }
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(PY_ROOT / "bridge.py"), "exec"), namespace)
    return namespace["HttpBridgeUnderTest"]


class BridgeHttpMutationTests(unittest.TestCase):
    GATE_SECRET = "gate_issuer_" + "g" * 50
    EVENT_SECRET = "event_consumer_" + "e" * 50

    def setUp(self):
        self.gate = FakeGate()
        self.matrix = FakeMatrix()
        self.router = FakeRouter()
        self.ledger = MutationAdmissionLedger(max_pending=8)
        self.handler_class = make_bridge_post_handler(
            self.gate, self.matrix, self.router, self.ledger
        )
        self.secrets = {
            "AEGIS_BRIDGE_GATE_SECRET": self.GATE_SECRET,
            "AEGIS_BRIDGE_EVENT_SECRET": self.EVENT_SECRET,
        }

    def send(self, path, obj, credential=None, secrets=None):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode("utf-8")
        handler = self.handler_class()
        handler.path = path
        handler.headers = {
            "Content-Length": str(len(body)),
            "X-Aegis-Bridge-Secret": credential if credential is not None
                else (self.GATE_SECRET if path == "/gate_signal" else self.EVENT_SECRET),
        }
        handler.rfile = io.BytesIO(body)
        replies = []
        handler._respond = lambda code, payload: replies.append((code, payload))
        with patch.dict(os.environ, self.secrets if secrets is None else secrets):
            handler.do_POST()
        self.assertEqual(len(replies), 1)
        return replies[0]

    def signal(self, accepted=True, lcb=0.4, proposal="p1", sequence=1):
        return {
            "proposal_id": proposal, "sequence": sequence,
            "accepted": accepted, "lcb": lcb,
            "event_sha256": event_digest(b"hello", b"\x00", b"ctx"),
        }

    def event(self, proposal="p1", context=b"ctx"):
        return {
            "proposal_id": proposal, "payload_hex": b"hello".hex(),
            "verifier_hex": b"\x00".hex(), "context_hex": context.hex(),
        }

    def test_missing_secrets_reject_before_any_mutation(self):
        missing = {"AEGIS_BRIDGE_GATE_SECRET": "", "AEGIS_BRIDGE_EVENT_SECRET": ""}
        self.assertEqual(self.send("/gate_signal", self.signal(), secrets=missing)[0], 503)
        self.assertEqual(self.send("/event", self.event(), secrets=missing)[0], 503)
        self.assertEqual(len(self.gate.signals), 0)
        self.assertEqual(self.matrix.signals, [])
        self.assertEqual(self.router.events, [])

    def test_identical_role_secrets_rejected(self):
        same = {"AEGIS_BRIDGE_GATE_SECRET": self.GATE_SECRET, "AEGIS_BRIDGE_EVENT_SECRET": self.GATE_SECRET}
        self.assertEqual(self.send("/gate_signal", self.signal(), secrets=same)[0], 503)
        self.assertEqual(self.send("/event", self.event(), secrets=same)[0], 503)
        self.assertEqual(self.ledger.pending_count, 0)

    def test_event_client_cannot_issue_gate_grant(self):
        self.assertEqual(self.send("/gate_signal", self.signal(), credential=self.EVENT_SECRET)[0], 403)
        self.assertEqual(self.ledger.pending_count, 0)
        self.assertEqual(self.matrix.signals, [])

    def test_gate_issuer_cannot_submit_routed_event(self):
        self.assertEqual(self.send("/gate_signal", self.signal())[0], 200)
        self.assertEqual(self.send("/event", self.event(), credential=self.GATE_SECRET)[0], 403)
        self.assertEqual(self.router.events, [])
        self.assertEqual(self.send("/event", self.event())[0], 200)
        self.assertEqual(len(self.router.events), 1)

    def test_bound_event_single_use_and_no_mismatched_route(self):
        self.assertEqual(self.send("/gate_signal", self.signal())[0], 200)
        self.assertEqual(self.matrix.signals, [("p1", True, 1)])
        self.assertEqual(self.send("/event", self.event(context=b"different"))[0], 403)
        self.assertEqual(self.send("/event", self.event(proposal="not-p1"))[0], 403)
        self.assertEqual(self.router.events, [])
        self.assertEqual(self.send("/event", self.event())[0], 200)
        self.assertEqual(self.send("/event", self.event())[0], 403)
        self.assertEqual(len(self.router.events), 1)

    def test_negative_e4_signal_never_writes_m2_or_routes(self):
        self.assertEqual(self.send("/gate_signal", self.signal(accepted=False, lcb=-0.2))[0], 200)
        self.assertEqual(self.matrix.signals, [])
        self.assertEqual(self.send("/event", self.event())[0], 403)
        self.assertEqual(self.router.events, [])

    def test_frozen_constitutional_denial_blocks_m2_before_write(self):
        self.gate.deny = True
        status, reply = self.send("/gate_signal", self.signal())
        self.assertEqual(status, 403)
        self.assertEqual(reply["reason"], "CONSTITUTIONAL_GATE_DENIED")
        self.assertEqual(self.matrix.signals, [])
        self.assertEqual(self.ledger.pending_count, 0)
        self.assertEqual(self.send("/event", self.event())[0], 403)
        self.assertEqual(self.router.events, [])

    def test_missing_event_digest_never_reaches_frozen_gate(self):
        signal = self.signal()
        del signal["event_sha256"]
        self.assertEqual(self.send("/gate_signal", signal)[0], 403)
        self.assertEqual(self.gate.signals, [])
        self.assertEqual(self.matrix.signals, [])

    def test_sealed_gate_rejects_signals_before_ledger_or_matrix(self):
        self.gate.seal()
        status, reply = self.send("/gate_signal", self.signal())
        self.assertEqual(status, 403)
        self.assertEqual(reply["reason"], "CONSTITUTIONAL_GATE_SEALED")
        self.assertEqual(self.ledger.last_sequence, -1)
        self.assertEqual(self.ledger.pending_count, 0)
        self.assertEqual(self.matrix.signals, [])
        self.assertEqual(self.gate.signals, [])
        self.assertEqual(self.send("/event", self.event())[0], 403)
        self.assertEqual(self.router.events, [])

    def test_seal_revokes_effective_authority_of_pending_grant(self):
        self.assertEqual(self.send("/gate_signal", self.signal())[0], 200)
        self.assertEqual(self.ledger.pending_count, 1)
        self.assertTrue(self.gate.is_approved("p1"))
        self.gate.seal()
        self.assertEqual(self.send("/event", self.event())[0], 403)
        self.assertEqual(self.router.events, [])
        self.assertEqual(self.send("/gate_signal", self.signal(sequence=2))[0], 403)

    def test_silent_drop_cannot_reuse_old_approved_proposal(self):
        self.assertEqual(self.send("/gate_signal", self.signal())[0], 200)
        self.assertEqual(self.send("/event", self.event())[0], 200)
        self.assertEqual(len(self.router.events), 1)
        self.assertEqual(self.gate.last_sequence(), 1)
        self.assertTrue(self.gate.is_approved("p1"))

        # This simulates the constitutionally frozen gate silently discarding
        # a new signal while retaining its earlier APPROVED verdict.
        self.gate.silently_discard = True
        status, reply = self.send("/gate_signal", self.signal(sequence=2))
        self.assertEqual(status, 403)
        self.assertEqual(reply["reason"], "CONSTITUTIONAL_SIGNAL_NOT_RECORDED")
        self.assertEqual(self.gate.last_sequence(), 1)
        self.assertEqual(self.ledger.pending_count, 0)
        self.assertEqual(self.matrix.signals, [("p1", True, 1)])
        self.assertEqual(self.send("/event", self.event())[0], 403)
        self.assertEqual(len(self.router.events), 1)

    def test_non_governance_events_cannot_consume_valid_grant(self):
        # A forged valid digest does not turn CALIBRATION, TELEMETRY,
        # EPOCH, unknown or empty verifier classes into GOVERNANCE.
        for verifier in (b"\x01", b"\x02", b"\x03", b"\xff", b""):
            with self.subTest(verifier=verifier):
                self.setUp()
                proposal = "p1"
                signal = self.signal()
                signal["event_sha256"] = event_digest(b"hello", verifier, b"ctx")
                self.assertEqual(self.send("/gate_signal", signal)[0], 200)
                event = self.event()
                event["verifier_hex"] = verifier.hex()
                status, reply = self.send("/event", event)
                self.assertEqual(status, 403, reply)
                self.assertEqual(reply["reason"], "NOT_GOVERNANCE_EVENT")
                self.assertEqual(self.ledger.pending_count, 1)
                self.assertEqual(self.router.events, [])

    def test_governance_schema_limits_checked_before_grant_consumption(self):
        # A syntactically valid, credentialled and granted event larger than
        # the frozen schema must be rejected before router dispatch.
        for payload, verifier, context in (
            (b"x" * (SCHEMAS[EventClass.GOVERNANCE].payload_size_max + 1),
             b"\x00", b""),
            (b"x", b"\x00" * (SCHEMAS[EventClass.GOVERNANCE].verifier_size_max + 1),
             b""),
            (b"x", b"\x00",
             b"x" * (SCHEMAS[EventClass.GOVERNANCE].context_size_max + 1)),
        ):
            with self.subTest(lengths=(len(payload), len(verifier), len(context))):
                self.setUp()
                signal = self.signal()
                signal["event_sha256"] = event_digest(payload, verifier, context)
                self.assertEqual(self.send("/gate_signal", signal)[0], 200)
                event = {
                    "proposal_id": "p1",
                    "payload_hex": payload.hex(),
                    "verifier_hex": verifier.hex(),
                    "context_hex": context.hex(),
                }
                status, reply = self.send("/event", event)
                self.assertEqual(status, 413, reply)
                self.assertEqual(reply["reason"], "GOVERNANCE_EVENT_SIZE")
                self.assertEqual(self.ledger.pending_count, 1)
                self.assertEqual(self.router.events, [])

    def test_malformed_control_json_rejected_not_dispatched(self):
        self.assertEqual(self.send("/gate_signal", b"{invalid")[0], 400)
        self.assertEqual(self.send("/event", b"[]")[0], 400)
        self.assertEqual(self.matrix.signals, [])
        self.assertEqual(self.router.events, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
