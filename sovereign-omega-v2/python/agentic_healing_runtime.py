"""
AEGIS Ω — Live Agentic Healing Bridge V1

Production-side observation/control adapter for the Python bridge.

Authority boundary:
- may observe faults and CoreMatrix failsafe telemetry;
- may inspect and content-address an existing checkpoint without applying it;
- may propose exact checkpoint restore;
- never invokes the checkpoint state-application loader during runtime healing;
- never invokes the human-supervised failsafe reset path;
- never applies durable mutation.

Startup crash recovery remains the existing bridge behavior.
"""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any

from ledger_persist import CheckpointError, inspect_checkpoint

HEALING_SCHEMA = "AEGIS_LIVE_AGENTIC_HEALING_V1"
HEALING_GENESIS = "0" * 64
MAX_HEALING_ATTEMPTS_PER_INCIDENT = 3
MAX_HEALING_RECEIPTS = 256


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _public_checkpoint_metadata(verified: dict) -> dict:
    return {
        "checkpoint_version": verified["checkpoint_version"],
        "sequence": verified["sequence"],
        "epoch": verified["epoch"],
        "era": verified["era"],
        "integrity_hash": verified["integrity_hash"],
        "is_replay_reconstructable": True,
        "verified": True,
    }


class AgenticBridgeHealingRuntime:
    """Bounded, authority-neutral fault observation and recovery planning."""

    def __init__(self, checkpoint_path: str | None = None) -> None:
        self._checkpoint_path = checkpoint_path
        self._receipts: list[dict] = []
        self._lock = threading.RLock()

    def _checkpoint_candidate(self) -> tuple[dict | None, str]:
        try:
            verified = (
                inspect_checkpoint(self._checkpoint_path)
                if self._checkpoint_path is not None
                else inspect_checkpoint()
            )
        except CheckpointError as exc:
            return None, f"CHECKPOINT_UNAVAILABLE:{type(exc).__name__}"

        public = _public_checkpoint_metadata(verified)
        candidate_hash = _digest({
            "schema": "AEGIS_VERIFIED_CHECKPOINT_CANDIDATE_V1",
            **public,
        })
        return {
            **public,
            "candidate_hash": candidate_hash,
        }, "CHECKPOINT_VERIFIED"

    def _attempt_count(self, incident_id: str) -> int:
        return sum(
            1
            for receipt in self._receipts
            if receipt["incident_id"] == incident_id
            and receipt["status"] != "MONITORING"
        )

    def observe_fault(
        self,
        matrix,
        *,
        incident_id: str,
        component_id: str,
        fault_code: str,
        evidence: dict | None = None,
    ) -> dict:
        if not incident_id:
            raise ValueError("incident_id required")
        if not component_id:
            raise ValueError("component_id required")
        if not fault_code:
            raise ValueError("fault_code required")

        telemetry = matrix.emit_vcg_telemetry()
        sequence = int(telemetry.get("sequence", 0))
        epoch = int(telemetry.get("epoch", 0))
        failsafe_state = str(telemetry.get("failsafe_state", "unknown")).lower()
        corruption_count = int(telemetry.get("corruption_count", 0))

        observation = {
            "incident_id": incident_id,
            "component_id": component_id,
            "fault_code": fault_code,
            "sequence": sequence,
            "epoch": epoch,
            "failsafe_state": failsafe_state,
            "corruption_count": corruption_count,
            "pgcs_passes": bool(telemetry.get("pgcs_passes", False)),
            "drift_index": telemetry.get("drift_index"),
            "evidence": evidence or {},
        }
        observation_hash = _digest(observation)

        with self._lock:
            attempts = self._attempt_count(incident_id)
            if attempts >= MAX_HEALING_ATTEMPTS_PER_INCIDENT:
                return self._append_receipt(
                    observation=observation,
                    observation_hash=observation_hash,
                    status="ESCALATED",
                    reason_code="HEALING_ATTEMPT_BUDGET_EXHAUSTED",
                    quarantine_scope="INCIDENT_ONLY",
                    checkpoint_candidate=None,
                    attempt_number=attempts + 1,
                )

            non_nominal_matrix = (
                corruption_count > 0
                or failsafe_state in {"quarantine", "recovering", "frozen"}
            )

            if non_nominal_matrix:
                candidate, candidate_reason = self._checkpoint_candidate()
                if candidate is None:
                    return self._append_receipt(
                        observation=observation,
                        observation_hash=observation_hash,
                        status="ESCALATED",
                        reason_code=candidate_reason,
                        quarantine_scope="CORE_MATRIX",
                        checkpoint_candidate=None,
                        attempt_number=attempts + 1,
                    )

                return self._append_receipt(
                    observation=observation,
                    observation_hash=observation_hash,
                    status="AWAITING_AUTHORITY",
                    reason_code="VERIFIED_CHECKPOINT_RESTORE_AWAITING_AUTHORITY",
                    quarantine_scope="CORE_MATRIX",
                    checkpoint_candidate=candidate,
                    attempt_number=attempts + 1,
                )

            # Application-layer fault while CoreMatrix remains nominal.
            # Do not propose state rollback for an unrelated application error.
            return self._append_receipt(
                observation=observation,
                observation_hash=observation_hash,
                status="QUARANTINED",
                reason_code="APPLICATION_FAULT_CORE_STATE_NOMINAL",
                quarantine_scope="INCIDENT_ONLY",
                checkpoint_candidate=None,
                attempt_number=attempts + 1,
            )

    def _append_receipt(
        self,
        *,
        observation: dict,
        observation_hash: str,
        status: str,
        reason_code: str,
        quarantine_scope: str,
        checkpoint_candidate: dict | None,
        attempt_number: int,
    ) -> dict:
        previous_hash = (
            self._receipts[-1]["receipt_hash"]
            if self._receipts
            else HEALING_GENESIS
        )
        body = {
            "schema": HEALING_SCHEMA,
            "incident_id": observation["incident_id"],
            "component_id": observation["component_id"],
            "sequence": observation["sequence"],
            "epoch": observation["epoch"],
            "status": status,
            "reason_code": reason_code,
            "observation_hash": observation_hash,
            "attempt_number": attempt_number,
            "attempt_budget": MAX_HEALING_ATTEMPTS_PER_INCIDENT,
            "quarantine_scope": quarantine_scope,
            "checkpoint_candidate": checkpoint_candidate,
            "checkpoint_apply_performed": False,
            "durable_apply_performed": False,
            "authority_effect": "NONE",
            "previous_receipt_hash": previous_hash,
            "is_replay_reconstructable": True,
        }
        receipt = {
            **body,
            "receipt_hash": _digest(body),
        }
        self._receipts.append(receipt)
        if len(self._receipts) > MAX_HEALING_RECEIPTS:
            # Retain a bounded in-memory window. The dropped prefix is explicitly
            # represented by the first retained receipt's previous_receipt_hash.
            self._receipts = self._receipts[-MAX_HEALING_RECEIPTS:]
        return dict(receipt)

    def status(self, matrix) -> dict:
        telemetry = matrix.emit_vcg_telemetry()
        with self._lock:
            latest = dict(self._receipts[-1]) if self._receipts else None
            terminal_hash = (
                self._receipts[-1]["receipt_hash"]
                if self._receipts
                else HEALING_GENESIS
            )
            receipt_count = len(self._receipts)

        candidate, candidate_reason = self._checkpoint_candidate()
        failsafe_state = str(telemetry.get("failsafe_state", "unknown")).lower()
        corruption_count = int(telemetry.get("corruption_count", 0))

        if corruption_count > 0 or failsafe_state == "frozen":
            live_state = "ESCALATED"
        elif failsafe_state in {"quarantine", "recovering"}:
            live_state = "CONTAINED"
        else:
            live_state = "MONITORING"

        return {
            "schema": HEALING_SCHEMA,
            "live_state": live_state,
            "matrix": {
                "sequence": int(telemetry.get("sequence", 0)),
                "epoch": int(telemetry.get("epoch", 0)),
                "failsafe_state": failsafe_state,
                "corruption_count": corruption_count,
                "pgcs_passes": bool(telemetry.get("pgcs_passes", False)),
                "drift_index": telemetry.get("drift_index"),
            },
            "checkpoint": {
                "status": candidate_reason,
                "candidate": candidate,
            },
            "receipt_count": receipt_count,
            "terminal_hash": terminal_hash,
            "latest_receipt": latest,
            "runtime_restore_authority": "NONE",
            "startup_verified_checkpoint_restore": "EXISTING_BRIDGE_BEHAVIOR",
            "human_supervised_recovery_reset": "REQUIRED",
            "authority_effect": "NONE",
        }
