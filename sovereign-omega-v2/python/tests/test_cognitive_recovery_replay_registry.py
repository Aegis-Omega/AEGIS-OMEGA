from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = REPO_ROOT / "scripts" / "cognitive-recovery-replay-registry.py"

REPOSITORY_ID = "Aegis-Omega/AEGIS-OMEGA"
REQUEST_DIGEST = "1" * 64
CANDIDATE_SHA = "2" * 40
APPROVAL_DIGEST = "3" * 64


def load_registry():
    spec = importlib.util.spec_from_file_location("aegis_replay_registry", REGISTRY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(REGISTRY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReplayRegistryContractTests(TestCase):
    def setUp(self) -> None:
        self.registry = load_registry()
        self.tmp = TemporaryDirectory()
        self.store = Path(self.tmp.name) / "replay-state.json"
        self.initial = self.registry.build_state(
            repository_id=REPOSITORY_ID,
            request_digest=REQUEST_DIGEST,
            candidate_sha=CANDIDATE_SHA,
            operator_approval_digest=APPROVAL_DIGEST,
            state="UNUSED",
            generation=7,
            reservation_digest=None,
        )
        self.store.write_bytes(self.registry.canonical_bytes(self.initial) + b"\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_reserve_is_digest_bound_and_authority_neutral(self) -> None:
        receipt = self.registry.reserve(
            self.store,
            expected_state_digest=self.initial["replay_state_digest"],
        )
        stored = json.loads(self.store.read_text(encoding="utf-8"))
        self.assertEqual(receipt["receipt_kind"], "AEGIS_COGNITIVE_RECOVERY_REPLAY_RESERVATION_V1")
        self.assertEqual(receipt["transition"], "UNUSED_TO_RESERVED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertEqual(receipt["mutation_authority"], "NONE")
        self.assertEqual(receipt["execution_trust"], "NOT_ESTABLISHED")
        self.assertEqual(stored["state"], "RESERVED")
        self.assertEqual(stored["generation"], 8)
        self.assertEqual(stored["reservation_digest"], receipt["reservation_digest"])
        self.assertEqual(stored["replay_state_digest"], receipt["new_state_digest"])

    def test_double_reserve_fails_closed_without_state_change(self) -> None:
        first = self.registry.reserve(
            self.store,
            expected_state_digest=self.initial["replay_state_digest"],
        )
        before = self.store.read_bytes()
        with self.assertRaises(self.registry.ReplayConflictError) as caught:
            self.registry.reserve(
                self.store,
                expected_state_digest=first["new_state_digest"],
            )
        self.assertEqual(caught.exception.code, "STATE_NOT_UNUSED")
        self.assertEqual(self.store.read_bytes(), before)

    def test_tampered_state_digest_is_rejected(self) -> None:
        tampered = dict(self.initial)
        tampered["replay_state_digest"] = "9" * 64
        self.store.write_bytes(self.registry.canonical_bytes(tampered) + b"\n")
        with self.assertRaises(self.registry.ReplayIntegrityError) as caught:
            self.registry.reserve(self.store, expected_state_digest="9" * 64)
        self.assertEqual(caught.exception.code, "STATE_DIGEST_MISMATCH")

    def test_consume_requires_exact_reservation_binding(self) -> None:
        reservation = self.registry.reserve(
            self.store,
            expected_state_digest=self.initial["replay_state_digest"],
        )
        forged = dict(reservation)
        forged["request_digest"] = "9" * 64
        with self.assertRaises(self.registry.ReplayBindingError) as caught:
            self.registry.consume(self.store, reservation_receipt=forged)
        self.assertEqual(caught.exception.code, "RESERVATION_RECEIPT_BINDING_MISMATCH")

    def test_consume_is_single_use_and_remains_authority_neutral(self) -> None:
        reservation = self.registry.reserve(
            self.store,
            expected_state_digest=self.initial["replay_state_digest"],
        )
        consumed = self.registry.consume(self.store, reservation_receipt=reservation)
        stored = json.loads(self.store.read_text(encoding="utf-8"))
        self.assertEqual(consumed["receipt_kind"], "AEGIS_COGNITIVE_RECOVERY_REPLAY_CONSUMPTION_V1")
        self.assertEqual(consumed["transition"], "RESERVED_TO_CONSUMED")
        self.assertEqual(consumed["authority"], "NONE")
        self.assertEqual(consumed["mutation_authority"], "NONE")
        self.assertEqual(consumed["execution_trust"], "NOT_ESTABLISHED")
        self.assertEqual(stored["state"], "CONSUMED")
        with self.assertRaises(self.registry.ReplayConflictError) as caught:
            self.registry.consume(self.store, reservation_receipt=reservation)
        self.assertEqual(caught.exception.code, "STATE_NOT_RESERVED")

    def test_concurrent_cli_reserve_has_exactly_one_winner(self) -> None:
        command = [
            sys.executable,
            str(REGISTRY_PATH),
            "reserve",
            "--store",
            str(self.store),
            "--expected-state-digest",
            self.initial["replay_state_digest"],
        ]
        first = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        second = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        first_stdout, first_stderr = first.communicate(timeout=10)
        second_stdout, second_stderr = second.communicate(timeout=10)
        results = sorted([first.returncode, second.returncode])
        self.assertEqual(results, [0, 4], (first_stdout, first_stderr, second_stdout, second_stderr))
        winner = first_stdout if first.returncode == 0 else second_stdout
        loser_err = first_stderr if first.returncode != 0 else second_stderr
        receipt = json.loads(winner)
        self.assertEqual(receipt["authority"], "NONE")
        self.assertIn("REPLAY_CONFLICT", loser_err)


if __name__ == "__main__":
    main()
