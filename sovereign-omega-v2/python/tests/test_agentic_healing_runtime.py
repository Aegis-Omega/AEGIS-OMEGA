"""
AEGIS Ω — Live Agentic Healing Bridge V1 tests.

Mock-based: does not allocate the 4GB CoreMatrix.
Run:
    python python/tests/test_agentic_healing_runtime.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PYTHON_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PYTHON_DIR)

from agentic_healing_runtime import (
    HEALING_GENESIS,
    MAX_HEALING_ATTEMPTS_PER_INCIDENT,
    AgenticBridgeHealingRuntime,
)
from ledger_persist import (
    CHECKPOINT_VERSION,
    CheckpointError,
    _M1_ENTRY_BYTES,
    inspect_checkpoint,
)


class FakeMatrix:
    def __init__(
        self,
        *,
        sequence: int = 10,
        epoch: int = 2,
        failsafe_state: str = "active",
        corruption_count: int = 0,
    ) -> None:
        self.sequence = sequence
        self.epoch = epoch
        self.failsafe_state = failsafe_state
        self.corruption_count = corruption_count

    def emit_vcg_telemetry(self) -> dict:
        return {
            "sequence": self.sequence,
            "epoch": self.epoch,
            "failsafe_state": self.failsafe_state,
            "corruption_count": self.corruption_count,
            "pgcs_passes": True,
            "drift_index": 0.01,
        }


def write_checkpoint(path: str, *, tamper: bool = False) -> dict:
    sequence = 9
    epoch = 2
    era = 0
    entry_hex = ("00" * _M1_ENTRY_BYTES)
    integrity_hash = hashlib.sha256(
        f"{sequence}:{epoch}:{era}:{entry_hex}".encode()
    ).hexdigest()
    if tamper:
        integrity_hash = "f" * 64

    payload = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "sequence": sequence,
        "epoch": epoch,
        "era": era,
        "last_m1_entry_hex": entry_hex,
        "integrity_hash": integrity_hash,
        "is_replay_reconstructable": True,
    }
    Path(path).write_text(json.dumps(payload), encoding="utf-8")
    return payload


class LiveAgenticHealingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.checkpoint = os.path.join(self.tmp.name, "checkpoint.json")

    def test_inspect_checkpoint_verifies_without_matrix_argument(self) -> None:
        expected = write_checkpoint(self.checkpoint)
        verified = inspect_checkpoint(self.checkpoint)
        self.assertTrue(verified["verified"])
        self.assertEqual(verified["sequence"], expected["sequence"])
        self.assertEqual(verified["integrity_hash"], expected["integrity_hash"])
        self.assertEqual(len(verified["last_m1_entry_bytes"]), _M1_ENTRY_BYTES)

    def test_inspect_checkpoint_rejects_tamper(self) -> None:
        write_checkpoint(self.checkpoint, tamper=True)
        with self.assertRaises(CheckpointError):
            inspect_checkpoint(self.checkpoint)

    def test_application_fault_with_nominal_matrix_does_not_propose_rollback(self) -> None:
        write_checkpoint(self.checkpoint)
        runtime = AgenticBridgeHealingRuntime(self.checkpoint)
        receipt = runtime.observe_fault(
            FakeMatrix(),
            incident_id="collaboration:1",
            component_id="platform-collaboration",
            fault_code="RuntimeError",
            evidence={"message_hash": "a" * 64},
        )
        self.assertEqual(receipt["status"], "QUARANTINED")
        self.assertEqual(
            receipt["reason_code"],
            "APPLICATION_FAULT_CORE_STATE_NOMINAL",
        )
        self.assertEqual(receipt["quarantine_scope"], "INCIDENT_ONLY")
        self.assertIsNone(receipt["checkpoint_candidate"])
        self.assertFalse(receipt["checkpoint_apply_performed"])
        self.assertFalse(receipt["durable_apply_performed"])
        self.assertEqual(receipt["authority_effect"], "NONE")

    def test_recovering_matrix_gets_verified_checkpoint_candidate_only(self) -> None:
        write_checkpoint(self.checkpoint)
        runtime = AgenticBridgeHealingRuntime(self.checkpoint)
        receipt = runtime.observe_fault(
            FakeMatrix(failsafe_state="recovering"),
            incident_id="matrix:recovering:10",
            component_id="core-matrix",
            fault_code="CORE_MATRIX_RECOVERING",
            evidence={"router_result_hash": "b" * 64},
        )
        self.assertEqual(receipt["status"], "AWAITING_AUTHORITY")
        self.assertEqual(
            receipt["reason_code"],
            "VERIFIED_CHECKPOINT_RESTORE_AWAITING_AUTHORITY",
        )
        candidate = receipt["checkpoint_candidate"]
        self.assertIsNotNone(candidate)
        self.assertTrue(candidate["verified"])
        self.assertRegex(candidate["candidate_hash"], r"^[0-9a-f]{64}$")
        self.assertFalse(receipt["checkpoint_apply_performed"])
        self.assertFalse(receipt["durable_apply_performed"])
        self.assertEqual(receipt["authority_effect"], "NONE")

    def test_frozen_matrix_with_invalid_checkpoint_escalates(self) -> None:
        write_checkpoint(self.checkpoint, tamper=True)
        runtime = AgenticBridgeHealingRuntime(self.checkpoint)
        receipt = runtime.observe_fault(
            FakeMatrix(failsafe_state="frozen", corruption_count=1),
            incident_id="matrix:frozen:10",
            component_id="core-matrix",
            fault_code="CORE_MATRIX_FROZEN",
        )
        self.assertEqual(receipt["status"], "ESCALATED")
        self.assertTrue(receipt["reason_code"].startswith("CHECKPOINT_UNAVAILABLE:"))
        self.assertEqual(receipt["quarantine_scope"], "CORE_MATRIX")
        self.assertIsNone(receipt["checkpoint_candidate"])

    def test_attempt_budget_stops_repeated_incident(self) -> None:
        write_checkpoint(self.checkpoint)
        runtime = AgenticBridgeHealingRuntime(self.checkpoint)
        matrix = FakeMatrix(failsafe_state="recovering")

        for attempt in range(1, MAX_HEALING_ATTEMPTS_PER_INCIDENT + 1):
            receipt = runtime.observe_fault(
                matrix,
                incident_id="same-incident",
                component_id="core-matrix",
                fault_code="CORE_MATRIX_RECOVERING",
            )
            self.assertEqual(receipt["attempt_number"], attempt)
            self.assertEqual(receipt["status"], "AWAITING_AUTHORITY")

        exhausted = runtime.observe_fault(
            matrix,
            incident_id="same-incident",
            component_id="core-matrix",
            fault_code="CORE_MATRIX_RECOVERING",
        )
        self.assertEqual(exhausted["status"], "ESCALATED")
        self.assertEqual(
            exhausted["reason_code"],
            "HEALING_ATTEMPT_BUDGET_EXHAUSTED",
        )
        self.assertEqual(
            exhausted["attempt_number"],
            MAX_HEALING_ATTEMPTS_PER_INCIDENT + 1,
        )
        self.assertFalse(exhausted["checkpoint_apply_performed"])

    def test_status_is_read_only_and_reports_candidate(self) -> None:
        write_checkpoint(self.checkpoint)
        runtime = AgenticBridgeHealingRuntime(self.checkpoint)
        status = runtime.status(FakeMatrix(failsafe_state="recovering"))
        self.assertEqual(status["live_state"], "CONTAINED")
        self.assertEqual(status["receipt_count"], 0)
        self.assertEqual(status["terminal_hash"], HEALING_GENESIS)
        self.assertEqual(status["checkpoint"]["status"], "CHECKPOINT_VERIFIED")
        self.assertTrue(status["checkpoint"]["candidate"]["verified"])
        self.assertEqual(status["runtime_restore_authority"], "NONE")
        self.assertEqual(status["human_supervised_recovery_reset"], "REQUIRED")
        self.assertEqual(status["authority_effect"], "NONE")

    def test_receipts_form_hash_chain(self) -> None:
        write_checkpoint(self.checkpoint)
        runtime = AgenticBridgeHealingRuntime(self.checkpoint)
        matrix = FakeMatrix()

        first = runtime.observe_fault(
            matrix,
            incident_id="app:1",
            component_id="platform-collaboration",
            fault_code="ErrorA",
        )
        matrix.sequence += 1
        second = runtime.observe_fault(
            matrix,
            incident_id="app:2",
            component_id="platform-collaboration",
            fault_code="ErrorB",
        )

        self.assertEqual(first["previous_receipt_hash"], HEALING_GENESIS)
        self.assertEqual(second["previous_receipt_hash"], first["receipt_hash"])
        self.assertRegex(first["receipt_hash"], r"^[0-9a-f]{64}$")
        self.assertRegex(second["receipt_hash"], r"^[0-9a-f]{64}$")


class LiveHealingBridgeSourceContract(unittest.TestCase):
    def test_bridge_wiring_is_read_only_for_healing(self) -> None:
        source = Path(PYTHON_DIR, "bridge.py").read_text(encoding="utf-8")
        self.assertIn("AgenticBridgeHealingRuntime", source)
        self.assertIn("'/platform/healing/status'", source)
        self.assertIn("_healing_runtime.status(matrix)", source)
        self.assertIn("_healing_runtime.observe_fault(", source)

    def test_healing_module_never_applies_checkpoint(self) -> None:
        source = Path(PYTHON_DIR, "agentic_healing_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("load_checkpoint(", source)
        self.assertNotIn("reset_after_recovery(", source)
        self.assertIn('"checkpoint_apply_performed": False', source)
        self.assertIn('"durable_apply_performed": False', source)
        self.assertIn('"authority_effect": "NONE"', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
