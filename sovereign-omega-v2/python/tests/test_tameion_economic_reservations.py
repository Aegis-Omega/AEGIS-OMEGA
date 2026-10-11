"""Durable atomic reservation safety lab. Synthetic USDC, no network."""
from __future__ import annotations

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from harness.sdk.tameion_economic_reservations import (
    EconomicReservationLedger, ReservationDenied,
)

H1, H2, H3 = "1" * 64, "2" * 64, "3" * 64


class AtomicReservationLab(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "test.sqlite3"
        self.ledger = EconomicReservationLedger(self.path)
        self.ledger.open_scope(scope="treasury.testnet.case1", policy_root=H1, budget_microunits=1000)

    def reserve(self, key="openmeter:event-a", *, expected_generation=0, amount=500,
                root=H2, intent=H3):
        return self.ledger.reserve(scope="treasury.testnet.case1", policy_root=H1,
                                   attempt_id=key, intent_root=intent, boundary_root=root,
                                   amount_microunits=amount, expected_generation=expected_generation)

    def test_persistence_restart(self):
        first = self.reserve()
        reopened = EconomicReservationLedger(self.path)
        self.assertEqual(reopened.snapshot("treasury.testnet.case1").reserved_microunits, 500)
        retry = reopened.reserve(scope="treasury.testnet.case1", policy_root=H1,
            attempt_id="openmeter:event-a", intent_root=H3, boundary_root=H2,
            amount_microunits=500, expected_generation=0)
        self.assertEqual(retry.state, first.state)
        self.assertEqual(retry.operation, "REPLAYED_NO_MUTATION")
        self.assertEqual(reopened.snapshot("treasury.testnet.case1").generation, 1)

    def test_deterministic_receipts(self):
        a = self.reserve()
        self.assertEqual(a.root, a.root)
        self.assertEqual(len(a.root), 64)

    def test_identical_retry_is_not_second_reservation(self):
        first = self.reserve()
        second = self.reserve()
        self.assertEqual(first.state, second.state)
        self.assertEqual(second.operation, "REPLAYED_NO_MUTATION")
        self.assertEqual(self.ledger.snapshot("treasury.testnet.case1").reserved_microunits, 500)

    def test_same_key_different_intent_denied(self):
        self.reserve()
        with self.assertRaisesRegex(ReservationDenied, "IDEMPOTENCY_COLLISION"):
            self.reserve(intent=H2)

    def test_same_key_different_policy_denied(self):
        self.reserve()
        with self.assertRaisesRegex(ReservationDenied, "POLICY_ROOT_MISMATCH"):
            self.ledger.reserve(scope="treasury.testnet.case1", policy_root=H2,
                attempt_id="openmeter:event-a", intent_root=H3, boundary_root=H2,
                amount_microunits=500, expected_generation=0)

    def test_stale_generation_denied(self):
        self.reserve()
        with self.assertRaisesRegex(ReservationDenied, "STALE_FENCING_GENERATION"):
            self.reserve("openmeter:event-b", expected_generation=0, amount=100)

    def test_atomic_budget_denied(self):
        self.reserve()
        with self.assertRaisesRegex(ReservationDenied, "ATOMIC_BUDGET_EXCEEDED"):
            self.reserve("openmeter:event-b", expected_generation=1, amount=501)
        self.assertEqual(self.ledger.snapshot("treasury.testnet.case1").reserved_microunits, 500)

    def test_exact_budget_succeeds(self):
        self.reserve()
        self.reserve("openmeter:event-b", expected_generation=1)
        self.assertEqual(self.ledger.snapshot("treasury.testnet.case1").used_microunits, 1000)

    def test_many_simultaneous_workers_only_one_wins(self):
        gate = threading.Barrier(12)
        def worker(i):
            ledger = EconomicReservationLedger(self.path)
            gate.wait()
            try:
                ledger.reserve(scope="treasury.testnet.case1", policy_root=H1,
                   attempt_id=f"openmeter:event-{i}", intent_root=H3, boundary_root=H2,
                   amount_microunits=700, expected_generation=0)
                return "YES"
            except ReservationDenied as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=12) as ex:
            result = list(ex.map(worker, range(12)))
        self.assertEqual(result.count("YES"), 1, result)
        self.assertTrue(all(x == "STALE_FENCING_GENERATION" for x in result if x != "YES"), result)
        self.assertEqual(self.ledger.snapshot("treasury.testnet.case1").used_microunits, 700)

    def test_no_implicit_release_when_unknown(self):
        self.reserve()
        r = self.ledger.record_unknown(scope="treasury.testnet.case1", attempt_id="openmeter:event-a", expected_generation=1)
        self.assertEqual(r.state, "OUTCOME_UNKNOWN")
        self.assertEqual(self.ledger.snapshot("treasury.testnet.case1").unknown_microunits, 500)
        with self.assertRaisesRegex(ReservationDenied, "ATOMIC_BUDGET_EXCEEDED"):
            self.reserve("openmeter:event-b", expected_generation=2, amount=501)

    def test_unknown_to_observed_does_not_free_budget(self):
        self.reserve()
        self.ledger.record_unknown(scope="treasury.testnet.case1", attempt_id="openmeter:event-a", expected_generation=1)
        r = self.ledger.record_observation(scope="treasury.testnet.case1", attempt_id="openmeter:event-a", expected_generation=2, observation_root=H3)
        self.assertEqual(r.state, "OBSERVATION_RECORDED")
        s = self.ledger.snapshot("treasury.testnet.case1")
        self.assertEqual(s.unknown_microunits, 0)
        self.assertEqual(s.observed_microunits, 500)
        self.assertFalse(r.settlement_asserted)

    def test_unique_observation_cannot_be_reused(self):
        self.reserve()
        self.reserve("openmeter:event-b", expected_generation=1, amount=100)
        self.ledger.record_observation(scope="treasury.testnet.case1", attempt_id="openmeter:event-a", expected_generation=2, observation_root=H3)
        with self.assertRaisesRegex(ReservationDenied, "OBSERVATION_REUSE_FORBIDDEN"):
            self.ledger.record_observation(scope="treasury.testnet.case1", attempt_id="openmeter:event-b", expected_generation=3, observation_root=H3)
        self.assertEqual(self.ledger.snapshot("treasury.testnet.case1").generation, 3)

    def test_observation_is_idempotent(self):
        self.reserve()
        self.ledger.record_observation(scope="treasury.testnet.case1", attempt_id="openmeter:event-a", expected_generation=1, observation_root=H3)
        x = self.ledger.record_observation(scope="treasury.testnet.case1", attempt_id="openmeter:event-a", expected_generation=1, observation_root=H3)
        self.assertEqual(x.operation, "REPLAYED_NO_MUTATION")

    def test_observation_conflict_forbidden(self):
        self.reserve()
        self.ledger.record_observation(scope="treasury.testnet.case1", attempt_id="openmeter:event-a", expected_generation=1, observation_root=H3)
        with self.assertRaisesRegex(ReservationDenied, "OBSERVED_STATE_IMMUTABLE"):
            self.ledger.record_observation(scope="treasury.testnet.case1", attempt_id="openmeter:event-a", expected_generation=2, observation_root=H2)

    def test_unknown_cannot_overwrite_observed(self):
        self.reserve()
        self.ledger.record_observation(scope="treasury.testnet.case1", attempt_id="openmeter:event-a", expected_generation=1, observation_root=H3)
        with self.assertRaisesRegex(ReservationDenied, "OBSERVED_STATE_IMMUTABLE"):
            self.ledger.record_unknown(scope="treasury.testnet.case1", attempt_id="openmeter:event-a", expected_generation=2)

    def test_scope_policy_immutable(self):
        with self.assertRaisesRegex(ReservationDenied, "SCOPE_POLICY_IMMUTABLE"):
            self.ledger.open_scope(scope="treasury.testnet.case1", policy_root=H1, budget_microunits=1100)

    def test_float_amount_denied(self):
        with self.assertRaisesRegex(ReservationDenied, "amount:INVALID_INTEGER"):
            self.reserve(amount=500.0)

    def test_bool_amount_denied(self):
        with self.assertRaisesRegex(ReservationDenied, "amount:INVALID_INTEGER"):
            self.reserve(amount=True)

    def test_inmemory_database_denied(self):
        with self.assertRaisesRegex(ReservationDenied, "DATABASE_PERSISTENCE_REQUIRED"):
            EconomicReservationLedger(":memory:")

    def test_no_external_side_effect_claims(self):
        r = self.reserve()
        self.assertEqual((r.authority_effect, r.network_effect, r.settlement_asserted), ("NONE", "NONE", False))

    def test_unknown_id_denied(self):
        with self.assertRaisesRegex(ReservationDenied, "UNKNOWN_ATTEMPT"):
            self.ledger.record_unknown(scope="treasury.testnet.case1", attempt_id="missing", expected_generation=0)

    def test_bad_hash_denied(self):
        with self.assertRaisesRegex(ReservationDenied, "intent_root:INVALID_HASH"):
            self.reserve(intent="not a hash")

    def test_generation_stale_on_observation(self):
        self.reserve()
        with self.assertRaisesRegex(ReservationDenied, "STALE_FENCING_GENERATION"):
            self.ledger.record_observation(scope="treasury.testnet.case1", attempt_id="openmeter:event-a", expected_generation=0, observation_root=H3)

    def test_scope_reopen_idempotent(self):
        s = self.ledger.open_scope(scope="treasury.testnet.case1", policy_root=H1, budget_microunits=1000)
        self.assertEqual(s.generation, 0)


if __name__ == "__main__":
    unittest.main()