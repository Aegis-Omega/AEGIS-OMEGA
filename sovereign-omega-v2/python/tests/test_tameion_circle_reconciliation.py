"""Circle CCTP-v2 reservation correlation; all fixtures synthetic, no network."""
from __future__ import annotations

import tempfile
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from harness.sdk.tameion_economic_reservations import EconomicReservationLedger, ReservationDenied
from harness.sdk.tameion_circle_attestation import (
    build_circle_v2_messages_request, parse_circle_v2_messages_response,
)
from harness.sdk.tameion_circle_reconciliation import (
    CircleReservationBinding, reconcile_circle_v2_observation,
)

H1, H2, H3 = '1' * 64, '2' * 64, '3' * 64
TX = '0x' + 'a' * 64
SCOPE = 'treasury.testnet.cctp'
ATTEMPT = 'openmeter:circle-a'


class CircleReconciliationLab(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.ledger = EconomicReservationLedger(Path(d.name) / 'test.sqlite3')
        self.ledger.open_scope(scope=SCOPE, policy_root=H1, budget_microunits=500)
        self.ledger.reserve(scope=SCOPE, policy_root=H1, attempt_id=ATTEMPT,
                            intent_root=H2, boundary_root=H3,
                            amount_microunits=300, expected_generation=0)
        self.request = build_circle_v2_messages_request(0, TX)
        self.binding = CircleReservationBinding(
            schema_version='1.0.0', scope=SCOPE, attempt_id=ATTEMPT,
            policy_root=H1, transfer_plan_root=H2, economic_boundary_root=H3,
            circle_request_root=self.request.root, source_domain=0,
            source_transaction_hash=TX,
        )

    def observation(self, status='complete'):
        return parse_circle_v2_messages_response(self.request, {
            'messages': [{'status': status, 'message': '0x1234',
                          'attestation': '0xabcd' if status == 'complete' else 'PENDING'}]
        })

    def correlate(self, **kw):
        opts = dict(ledger=self.ledger, binding=self.binding,
                    pinned_binding_root=self.binding.root,
                    request=self.request, observation=self.observation(),
                    expected_generation=self.ledger.snapshot(SCOPE).generation)
        opts.update(kw)
        return reconcile_circle_v2_observation(**opts)

    def test_complete_correlates_only_bytes_not_settlement(self):
        r = self.correlate()
        self.assertEqual(r.outcome, 'CIRCLE_COMPLETE_BYTES_CORRELATED_NOT_SETTLED')
        self.assertEqual((r.authority_effect, r.network_effect), ('NONE','NONE'))
        self.assertFalse(r.settlement_asserted)
        self.assertFalse(r.budget_released)
        self.assertEqual(self.ledger.snapshot(SCOPE).observed_microunits, 300)

    def test_complete_does_not_release_budget(self):
        self.correlate()
        with self.assertRaisesRegex(ReservationDenied, 'ATOMIC_BUDGET_EXCEEDED'):
            self.ledger.reserve(scope=SCOPE, policy_root=H1, attempt_id='another',
                                intent_root=H2, boundary_root=H3,
                                amount_microunits=201, expected_generation=2)

    def test_pending_keeps_unknown_reservation(self):
        r = self.correlate(observation=self.observation('pending_confirmations'))
        self.assertEqual(r.outcome, 'CIRCLE_PENDING_RESERVATION_RETAINED')
        s = self.ledger.snapshot(SCOPE)
        self.assertEqual((s.unknown_microunits, s.used_microunits), (300, 300))

    def test_pending_then_complete_preserves_budget(self):
        self.correlate(observation=self.observation('pending_confirmations'))
        self.correlate()
        self.assertEqual(self.ledger.snapshot(SCOPE).used_microunits, 300)

    def test_complete_is_idempotent(self):
        self.correlate()
        before = self.ledger.snapshot(SCOPE).root
        self.correlate()
        self.assertEqual(before, self.ledger.snapshot(SCOPE).root)

    def test_binding_pin_mismatch(self):
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_BINDING_PIN_MISMATCH'):
            self.correlate(pinned_binding_root=H2)
        self.assertEqual(self.ledger.snapshot(SCOPE).generation, 1)

    def test_source_transaction_mismatch(self):
        other = build_circle_v2_messages_request(0, '0x'+'b'*64)
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_REQUEST_ROOT_MISMATCH'):
            self.correlate(request=other)

    def test_wrong_observation_request_root(self):
        o = replace(self.observation(), request_root=H2)
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_OBSERVATION_REQUEST_MISMATCH'):
            self.correlate(observation=o)

    def test_wrong_domain_observation(self):
        o = replace(self.observation(), source_domain=1,
                    endpoint='https://iris-api-sandbox.circle.com/v2/messages/1?transactionHash='+TX)
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_SOURCE_DOMAIN_MISMATCH'):
            self.correlate(observation=o)

    def test_destination_endpoint_escalation_rejected(self):
        fake = replace(self.request, endpoint='https://evil.example/v2/messages/0?transactionHash='+TX)
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_SOURCE_INVALID'):
            self.correlate(request=fake)

    def test_broadcast_on_request_rejected(self):
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_SOURCE_INVALID'):
            self.correlate(request=replace(self.request, broadcast_allowed=True))

    def test_broadcast_on_observation_rejected(self):
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_SOURCE_INVALID'):
            self.correlate(observation=replace(self.observation(), signer_attached=True))

    def test_wrong_plan_binding(self):
        x = replace(self.binding, transfer_plan_root=H1)
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_RESERVATION_BINDING_MISMATCH'):
            self.correlate(binding=x, pinned_binding_root=x.root)

    def test_nonexistent_attempt(self):
        x = replace(self.binding, attempt_id='openmeter:does-not-exist')
        with self.assertRaisesRegex(ReservationDenied, 'UNKNOWN_ATTEMPT'):
            self.correlate(binding=x, pinned_binding_root=x.root)

    def test_stale_generation(self):
        with self.assertRaisesRegex(ReservationDenied, 'STALE_FENCING_GENERATION'):
            self.correlate(expected_generation=0)

    def test_multiple_messages_ambiguous(self):
        o = parse_circle_v2_messages_response(self.request, {
            'messages': [{'status':'complete','message':'0x1234','attestation':'0xabcd'},
                         {'status':'complete','message':'0x5678','attestation':'0xefab'}]
        })
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_MULTI_MESSAGE_AMBIGUOUS'):
            self.correlate(observation=o)

    def test_invalid_complete_evidence_fails(self):
        o = replace(self.observation(), attestation_sha256=(None,))
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_SOURCE_INVALID'):
            self.correlate(observation=o)

    def test_invalid_binding_authority_escalation(self):
        x = replace(self.binding, authority_effect='GRANTED')
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_BINDING_AUTHORITY_FORBIDDEN'):
            self.correlate(binding=x)

    def test_binding_root_is_deterministic(self):
        self.assertEqual(self.binding.root, replace(self.binding).root)

    def second_attempt(self, attempt='openmeter:circle-b'):
        self.ledger.reserve(scope=SCOPE, policy_root=H1, attempt_id=attempt,
                            intent_root=H2, boundary_root=H3,
                            amount_microunits=100, expected_generation=1)
        binding = replace(self.binding, attempt_id=attempt)
        return binding

    def test_one_circle_source_cannot_fund_two_attempts(self):
        b = self.second_attempt()
        self.correlate(expected_generation=2)
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_SOURCE_ALREADY_CLAIMED'):
            self.correlate(binding=b, pinned_binding_root=b.root, expected_generation=3)
        self.assertEqual(self.ledger.snapshot(SCOPE).used_microunits, 400)

    def test_pending_source_claim_blocks_second_attempt(self):
        b = self.second_attempt()
        self.correlate(observation=self.observation('pending_confirmations'), expected_generation=2)
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_SOURCE_ALREADY_CLAIMED'):
            self.correlate(binding=b, pinned_binding_root=b.root, expected_generation=3)

    def test_attempt_cannot_replace_its_source_transaction(self):
        self.correlate(observation=self.observation('pending_confirmations'))
        other = build_circle_v2_messages_request(0, '0x'+'b'*64)
        b = replace(self.binding, circle_request_root=other.root,
                    source_transaction_hash=other.transaction_hash)
        o = parse_circle_v2_messages_response(other, {
            'messages':[{'status':'complete','message':'0x1234','attestation':'0xabcd'}]
        })
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_ATTEMPT_SOURCE_IMMUTABLE'):
            self.correlate(binding=b, pinned_binding_root=b.root,
                           request=other, observation=o)

    def test_two_workers_cannot_claim_same_circle_source(self):
        b = self.second_attempt()
        gate = threading.Barrier(2)
        def worker(binding):
            gate.wait()
            try:
                self.correlate(binding=binding, pinned_binding_root=binding.root,
                               expected_generation=2)
                return 'RECORDED'
            except ReservationDenied as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, (self.binding, b)))
        self.assertEqual(results.count('RECORDED'), 1, results)
        self.assertTrue(any('CIRCLE_SOURCE_ALREADY_CLAIMED' in x for x in results), results)

    def test_circle_source_claim_is_global_across_scopes(self):
        second_scope = 'treasury.testnet.other'
        self.ledger.open_scope(scope=second_scope, policy_root=H1, budget_microunits=500)
        self.ledger.reserve(scope=second_scope, policy_root=H1, attempt_id='other',
                            intent_root=H2, boundary_root=H3,
                            amount_microunits=100, expected_generation=0)
        self.correlate()
        b = replace(self.binding, scope=second_scope, attempt_id='other')
        with self.assertRaisesRegex(ReservationDenied, 'CIRCLE_SOURCE_ALREADY_CLAIMED'):
            self.correlate(binding=b, pinned_binding_root=b.root, expected_generation=1)
        self.assertEqual(self.ledger.snapshot(second_scope).reserved_microunits, 100)

    def test_get_attempt_is_read_only(self):
        original = self.ledger.snapshot(SCOPE).root
        x = self.ledger.get_attempt(scope=SCOPE, attempt_id=ATTEMPT)
        self.assertEqual((x.intent_root, x.boundary_root), (H2,H3))
        self.assertEqual(original, self.ledger.snapshot(SCOPE).root)


if __name__ == '__main__':
    unittest.main()
