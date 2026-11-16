"""Native source-bound regressions for the bridge mutation admission boundary.

Run from repository root:
    python sovereign-omega-v2/python/tests/test_mutation_admission.py
No CoreMatrix allocation or network dependency.
"""

from __future__ import annotations

import ast
import math
import sys
import threading
import unittest
from pathlib import Path

PY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PY_ROOT))

from mutation_admission import (  # noqa: E402
    MutationAdmissionLedger,
    control_binding_authorized,
    control_authenticated,
    control_secrets_distinct,
    event_digest,
)


class MutationAdmissionTests(unittest.TestCase):
    SECRET = "aegis-bridge-control-" + "f" * 48

    def make_ledger(self):
        return MutationAdmissionLedger(max_pending=4)

    def record_grant(self, ledger, proposal="p1", sequence=1, digest=None):
        if digest is None:
            digest = event_digest(b"payload", b"\x00", b"context")
        return ledger.record(proposal, sequence, True, 0.25, digest,
                             e_value=32.0, risk_spent=0.05,
                             sample_size=20, e4_method="anytime_valid_bernstein",
                             component_id="bridge-test-component",
                             operator_id="bridge-test-operator",
                             capability_class="SELF_MODIFYING")

    def test_server_binding_policy_is_strict_and_fail_closed(self):
        valid = '{"bridge-test-component":["bridge-test-operator"]}'
        self.assertTrue(control_binding_authorized(
            "bridge-test-component", "bridge-test-operator", "SELF_MODIFYING", valid
        ))
        for config in (
            None, "", "{}", "[]", "{", '{"bridge-test-component":[]}',
            '{"bridge-test-component":["bridge-test-operator","bridge-test-operator"]}',
            '{"bridge-test-component":["bridge-test-operator"],"bridge-test-component":["evil"]}',
            '{"bridge-test-component":["evil"]}',
        ):
            with self.subTest(config=config):
                self.assertFalse(control_binding_authorized(
                    "bridge-test-component", "bridge-test-operator", "SELF_MODIFYING", config
                ))
        for component, operator, capability in (
            ("pipeline-main", "bridge-test-operator", "SELF_MODIFYING"),
            ("bridge-test-component", "evil", "SELF_MODIFYING"),
            ("bridge-test-component", "bridge-test-operator", "INFERENCE_ONLY"),
            ("bad/component", "bridge-test-operator", "SELF_MODIFYING"),
        ):
            with self.subTest(component=component, operator=operator, capability=capability):
                self.assertFalse(control_binding_authorized(
                    component, operator, capability, valid
                ))

    def test_ledger_grant_cannot_be_retargeted_between_components_or_operators(self):
        ledger = self.make_ledger()
        self.assertEqual(self.record_grant(ledger), (True, "ACCEPTED"))
        for component, operator in (
            ("pipeline-main", "bridge-test-operator"),
            ("bridge-test-component", "evil"),
            ("pipeline-main", "evil"),
        ):
            self.assertFalse(ledger.authorize_event(
                "p1", b"payload", b"\x00", b"context", True,
                component_id=component, operator_id=operator,
            ))
        self.assertEqual(ledger.pending_count, 1)
        self.assertTrue(ledger.authorize_event(
            "p1", b"payload", b"\x00", b"context", True,
            component_id="bridge-test-component", operator_id="bridge-test-operator",
        ))
        self.assertEqual(ledger.pending_count, 0)

    def test_control_auth_is_fail_closed(self):
        self.assertTrue(control_authenticated(self.SECRET, self.SECRET))
        for candidate, configured in (
            (None, self.SECRET),
            ("", self.SECRET),
            ("wrong", self.SECRET),
            (self.SECRET, None),
            (self.SECRET, ""),
            (self.SECRET, "short"),
            (self.SECRET + "x", self.SECRET),
        ):
            with self.subTest(candidate=candidate, configured=configured):
                self.assertFalse(control_authenticated(candidate, configured))

    def test_issuer_and_consumer_secrets_are_independent(self):
        issuer = "gate-" + "g" * 48
        consumer = "event-" + "e" * 48
        self.assertTrue(control_secrets_distinct(issuer, consumer))
        self.assertTrue(control_authenticated(issuer, issuer))
        self.assertTrue(control_authenticated(consumer, consumer))
        self.assertFalse(control_authenticated(consumer, issuer))
        self.assertFalse(control_authenticated(issuer, consumer))
        for gate_secret, event_secret in (
            (None, consumer), (issuer, None), ("", consumer),
            (issuer, ""), ("short", consumer), (issuer, "short"),
            (issuer, issuer),
        ):
            with self.subTest(gate_secret=gate_secret, event_secret=event_secret):
                self.assertFalse(control_secrets_distinct(gate_secret, event_secret))

    def test_digest_length_framing_and_type(self):
        event = event_digest(b"abc", b"\x01", b"def")
        self.assertEqual(len(event), 64)
        self.assertEqual(event, event_digest(b"abc", b"\x01", b"def"))
        self.assertNotEqual(event, event_digest(b"ab", b"c\x01", b"def"))
        self.assertNotEqual(event, event_digest(b"abc", b"\x02", b"def"))
        self.assertNotEqual(event, event_digest(b"abc", b"\x01", b"de"))
        with self.assertRaises(TypeError):
            event_digest("abc", b"\x01", b"def")

    def test_positive_approved_proposal_is_bound_single_use(self):
        ledger = self.make_ledger()
        self.assertEqual(self.record_grant(ledger), (True, "ACCEPTED"))
        self.assertEqual(ledger.pending_count, 1)
        self.assertFalse(ledger.authorize_event("p1", b"payload", b"\x00", b"context", False,
            component_id="bridge-test-component", operator_id="bridge-test-operator"))
        self.assertEqual(ledger.pending_count, 1)
        self.assertFalse(ledger.authorize_event("p1", b"payload", b"\x00", b"wrong", True,
            component_id="bridge-test-component", operator_id="bridge-test-operator"))
        self.assertFalse(ledger.authorize_event("other", b"payload", b"\x00", b"context", True,
            component_id="bridge-test-component", operator_id="bridge-test-operator"))
        self.assertFalse(ledger.authorize_event("p1", b"payload", b"\x01", b"context", True,
            component_id="bridge-test-component", operator_id="bridge-test-operator"))
        self.assertEqual(ledger.pending_count, 1)
        self.assertTrue(ledger.authorize_event("p1", b"payload", b"\x00", b"context", True,
            component_id="bridge-test-component", operator_id="bridge-test-operator"))
        self.assertEqual(ledger.pending_count, 0)
        self.assertFalse(ledger.authorize_event("p1", b"payload", b"\x00", b"context", True,
            component_id="bridge-test-component", operator_id="bridge-test-operator"))

    def test_replay_out_of_order_and_duplicate_pending(self):
        ledger = self.make_ledger()
        digest = event_digest(b"payload", b"\x00", b"context")
        self.assertEqual(self.record_grant(ledger), (True, "ACCEPTED"))
        self.assertEqual(self.record_grant(ledger, sequence=1), (
            False, "SEQUENCE_DESYNC"
        ))
        self.assertEqual(self.record_grant(ledger, sequence=2), (
            False, "DUPLICATE_PENDING_PROPOSAL"
        ))
        self.assertEqual(ledger.last_sequence, 1)
        self.assertEqual(ledger.pending_count, 1)
        self.assertEqual(ledger.record("p1", 2, False, -0.1, digest, e_value=32.0, risk_spent=0.0, sample_size=20, e4_method="anytime_valid_bernstein",
                             component_id="bridge-test-component",
                             operator_id="bridge-test-operator",
                             capability_class="SELF_MODIFYING"), (
            True, "ACCEPTED"
        ))
        self.assertEqual(ledger.pending_count, 0)
        self.assertFalse(ledger.authorize_event("p1", b"payload", b"\x00", b"context", True,
            component_id="bridge-test-component", operator_id="bridge-test-operator"))

    def test_negative_and_invalid_lcb_never_authorize(self):
        valid_digest = event_digest(b"payload", b"\x00", b"context")
        for accepted, lcb in (
            (True, 0.0), (True, -0.1), (True, math.nan),
            (True, math.inf), (True, -math.inf), (False, 0.2),
            (False, math.nan), (1, 0.2),
        ):
            with self.subTest(accepted=accepted, lcb=lcb):
                ledger = self.make_ledger()
                allowed, _ = ledger.record("p", 1, accepted, lcb, valid_digest, e_value=32.0, risk_spent=0.05, sample_size=20, e4_method="anytime_valid_bernstein",
                             component_id="bridge-test-component",
                             operator_id="bridge-test-operator",
                             capability_class="SELF_MODIFYING")
                self.assertFalse(allowed)
                self.assertEqual(ledger.pending_count, 0)
                self.assertEqual(ledger.last_sequence, -1)
        ledger = self.make_ledger()
        self.assertEqual(ledger.record("p", 1, False, -0.25, valid_digest, e_value=32.0, risk_spent=0.0, sample_size=20, e4_method="anytime_valid_bernstein",
                             component_id="bridge-test-component",
                             operator_id="bridge-test-operator",
                             capability_class="SELF_MODIFYING"), (
            True, "ACCEPTED"
        ))
        self.assertFalse(ledger.authorize_event("p", b"payload", b"\x00", b"context", True,
            component_id="bridge-test-component", operator_id="bridge-test-operator"))

    def test_bad_proposal_sequence_and_digest(self):
        digest = event_digest(b"payload", b"\x00", b"context")
        for proposal in ("", "with space", "../path", "a" * 129, None):
            with self.subTest(proposal=proposal):
                ledger = self.make_ledger()
                self.assertFalse(ledger.record(proposal, 1, True, 0.25, digest , e_value=32.0, risk_spent=0.05, sample_size=20, e4_method="anytime_valid_bernstein",
                             component_id="bridge-test-component",
                             operator_id="bridge-test-operator",
                             capability_class="SELF_MODIFYING")[0])
        for seq in (-1, True, False, 1.0, 2**64, None):
            with self.subTest(seq=seq):
                ledger = self.make_ledger()
                self.assertFalse(ledger.record("p", seq, True, 0.25, digest , e_value=32.0, risk_spent=0.05, sample_size=20, e4_method="anytime_valid_bernstein",
                             component_id="bridge-test-component",
                             operator_id="bridge-test-operator",
                             capability_class="SELF_MODIFYING")[0])
        for malformed in ("", "0" * 63, "Z" * 64, "0" * 65, None):
            with self.subTest(malformed=malformed):
                ledger = self.make_ledger()
                self.assertFalse(ledger.record("p", 1, True, 0.25, malformed , e_value=32.0, risk_spent=0.05, sample_size=20, e4_method="anytime_valid_bernstein",
                             component_id="bridge-test-component",
                             operator_id="bridge-test-operator",
                             capability_class="SELF_MODIFYING")[0])

    def test_bounded_pending_and_revocation(self):
        ledger = MutationAdmissionLedger(max_pending=2)
        for i, proposal in enumerate(("a", "b")):
            self.assertTrue(self.record_grant(ledger, proposal, i + 1)[0])
        self.assertEqual(self.record_grant(ledger, "c", 3)[1], "PENDING_CAPACITY")
        self.assertEqual(ledger.last_sequence, 2)
        ledger.revoke("a")
        self.assertTrue(self.record_grant(ledger, "c", 3)[0])
        self.assertEqual(ledger.pending_count, 2)
        with self.assertRaises(ValueError):
            MutationAdmissionLedger(max_pending=0)

    def test_concurrent_consumption_exactly_one(self):
        ledger = self.make_ledger()
        self.assertTrue(self.record_grant(ledger)[0])
        barrier = threading.Barrier(8)
        outcomes = [False] * 8

        def consume(i):
            barrier.wait(timeout=5)
            outcomes[i] = ledger.authorize_event("p1", b"payload", b"\x00", b"context", True,
            component_id="bridge-test-component", operator_id="bridge-test-operator")

        threads = [threading.Thread(target=consume, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
        self.assertEqual(sum(outcomes), 1)

    def test_bridge_route_has_explicit_admission_check(self):
        # Source-bound integration guard. This is NOT a live HTTP integration test.
        source = (PY_ROOT / "bridge.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        handlers = [
            fn for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "BridgeHandler"
            for fn in node.body
            if isinstance(fn, ast.FunctionDef) and fn.name == "do_POST"
        ]
        self.assertEqual(len(handlers), 1)
        method = handlers[0]
        rendered = ast.unparse(method)
        self.assertIn("control_authenticated(", rendered)
        self.assertIn("control_secrets_distinct(", rendered)
        self.assertIn("AEGIS_BRIDGE_GATE_SECRET", rendered)
        self.assertIn("AEGIS_BRIDGE_EVENT_SECRET", rendered)
        self.assertIn("_mutation_admission.authorize_event(", rendered)
        self.assertIn("gate.is_approved(", rendered)
        self.assertIn("router.route(payload, verifier, context)", rendered)
        self.assertIn("matrix.receive_gate_signal(proposal_id, True, seq)", rendered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
