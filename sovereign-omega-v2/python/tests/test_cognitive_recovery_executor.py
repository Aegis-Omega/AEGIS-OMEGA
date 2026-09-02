from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
EXECUTOR_PATH = REPO_ROOT / "scripts" / "cognitive-recovery-executor.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


executor = load_module("cognitive_recovery_executor", EXECUTOR_PATH)

REQ = "a" * 64
CANDIDATE = "b" * 40
APPROVAL = "c" * 64
RESERVATION = "11111111-1111-1111-1111-111111111111"


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.initialize_result = executor.ReplayRecord(REQ, "UNUSED", 0, None)
        self.reserve_result = executor.ReplayRecord(REQ, "RESERVED", 1, RESERVATION)
        self.consume_result = executor.ReplayRecord(REQ, "CONSUMED", 2, RESERVATION)
        self.unknown_result = executor.ReplayRecord(REQ, "UNKNOWN", 2, RESERVATION)

    def initialize(self, binding):
        self.calls.append(("initialize", binding.request_digest, binding.candidate_sha))
        return self.initialize_result

    def reserve(self, request_digest, expected_generation):
        self.calls.append(("reserve", request_digest, expected_generation))
        return self.reserve_result

    def consume(self, request_digest, reservation_id, expected_generation):
        self.calls.append(("consume", request_digest, reservation_id, expected_generation))
        return self.consume_result

    def mark_unknown(self, request_digest, reservation_id, expected_generation):
        self.calls.append(("unknown", request_digest, reservation_id, expected_generation))
        return self.unknown_result


class RecoveryExecutorTests(TestCase):
    def setUp(self) -> None:
        self.binding = executor.RecoveryBinding(
            request_digest=REQ,
            repository_id="Aegis-Omega/AEGIS-OMEGA",
            candidate_sha=CANDIDATE,
            operator_approval_digest=APPROVAL,
        )

    def test_verified_effect_is_consumed_exactly_once(self) -> None:
        store = FakeStore()
        external_calls: list[str] = []

        def effect():
            external_calls.append("effect")
            return {"effect_receipt": "verified"}

        def verify(result):
            external_calls.append("verify")
            return result["effect_receipt"] == "verified"

        result = executor.execute_recovery_once(store, self.binding, effect, verify)
        self.assertEqual(result.status, "CONSUMED")
        self.assertTrue(result.effect_attempted)
        self.assertEqual(external_calls, ["effect", "verify"])
        self.assertEqual(
            store.calls,
            [
                ("initialize", REQ, CANDIDATE),
                ("reserve", REQ, 0),
                ("consume", REQ, RESERVATION, 1),
            ],
        )

    def test_binding_conflict_never_attempts_effect(self) -> None:
        store = FakeStore()
        store.initialize_result = None
        called = []
        result = executor.execute_recovery_once(
            store, self.binding, lambda: called.append("effect"), lambda _: True
        )
        self.assertEqual(result.status, "BINDING_CONFLICT")
        self.assertFalse(result.effect_attempted)
        self.assertEqual(called, [])
        self.assertEqual(store.calls, [("initialize", REQ, CANDIDATE)])

    def test_failed_reservation_never_attempts_effect(self) -> None:
        store = FakeStore()
        store.reserve_result = None
        called = []
        result = executor.execute_recovery_once(
            store, self.binding, lambda: called.append("effect"), lambda _: True
        )
        self.assertEqual(result.status, "REPLAY_BLOCKED")
        self.assertFalse(result.effect_attempted)
        self.assertEqual(called, [])
        self.assertEqual(
            store.calls,
            [("initialize", REQ, CANDIDATE), ("reserve", REQ, 0)],
        )

    def test_effect_exception_marks_exact_reservation_unknown_without_retry(self) -> None:
        store = FakeStore()
        calls = []

        def effect():
            calls.append("effect")
            raise RuntimeError("boom")

        result = executor.execute_recovery_once(store, self.binding, effect, lambda _: True)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertTrue(result.effect_attempted)
        self.assertEqual(calls, ["effect"])
        self.assertEqual(store.calls[-1], ("unknown", REQ, RESERVATION, 1))
        self.assertFalse(any(call[0] == "consume" for call in store.calls))

    def test_unverified_effect_marks_unknown_instead_of_consuming(self) -> None:
        store = FakeStore()
        result = executor.execute_recovery_once(
            store, self.binding, lambda: {"effect": "observed"}, lambda _: False
        )
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(store.calls[-1], ("unknown", REQ, RESERVATION, 1))
        self.assertFalse(any(call[0] == "consume" for call in store.calls))

    def test_failed_consume_quarantines_reserved_request(self) -> None:
        store = FakeStore()
        store.consume_result = None
        result = executor.execute_recovery_once(
            store, self.binding, lambda: {"effect_receipt": "verified"}, lambda _: True
        )
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(
            store.calls[-2:],
            [
                ("consume", REQ, RESERVATION, 1),
                ("unknown", REQ, RESERVATION, 1),
            ],
        )

    def test_failed_unknown_transition_remains_indeterminate_reserved(self) -> None:
        store = FakeStore()
        store.unknown_result = None

        def effect():
            raise RuntimeError("ambiguous dispatch")

        result = executor.execute_recovery_once(store, self.binding, effect, lambda _: True)
        self.assertEqual(result.status, "INDETERMINATE_RESERVED")
        self.assertTrue(result.effect_attempted)
        self.assertEqual(store.calls[-1], ("unknown", REQ, RESERVATION, 1))


if __name__ == "__main__":
    main()
