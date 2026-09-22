"""Executable fail-closed policy evaluator for the AEGIS Gravity/Quantum lane.

A policy digest proves only byte identity. Admission requires an executed policy
receipt whose decision replays from the exact candidate transition receipts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import research_invariants as ri

POLICY_SCHEMA = "AEGIS_GQ_ADMISSION_POLICY_V1"
RECEIPT_SCHEMA = "AEGIS_GQ_POLICY_EVALUATION_RECEIPT_V1"


@dataclass(frozen=True)
class GravityQuantumPolicyV1:
    policy_id: str
    required_transitions: tuple[str, ...]
    forbidden_statuses: tuple[str, ...] = (
        "FAIL",
        "DENY",
        "OPEN",
        "NOT_RUN",
        "BLOCKED",
        "INCONCLUSIVE",
        "STALE",
    )
    allowed_status: str = "PASS"
    missing_evidence_behavior: str = "DENY"
    authority_ceiling: str = "EPISTEMIC_ONLY"
    policy_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.policy_id or not self.required_transitions:
            raise ValueError("gravity policy id and required transitions are mandatory")
        if len(set(self.required_transitions)) != len(self.required_transitions):
            raise ValueError("duplicate required gravity transition")
        if self.allowed_status != "PASS":
            raise ValueError("V1 admits PASS only")
        if self.missing_evidence_behavior != "DENY":
            raise ValueError("gravity policy must fail closed")
        if self.authority_ceiling != "EPISTEMIC_ONLY":
            raise ValueError("gravity policy cannot grant runtime authority")
        object.__setattr__(
            self,
            "policy_sha256",
            ri.sha256_hex(
                {
                    "schema": POLICY_SCHEMA,
                    "policy_id": self.policy_id,
                    "required_transitions": self.required_transitions,
                    "forbidden_statuses": self.forbidden_statuses,
                    "allowed_status": self.allowed_status,
                    "missing_evidence_behavior": self.missing_evidence_behavior,
                    "authority_ceiling": self.authority_ceiling,
                }
            ),
        )


@dataclass(frozen=True)
class TransitionEvidenceV1:
    transition_id: str
    status: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        if not self.transition_id or not self.status:
            raise ValueError("transition id/status are mandatory")
        ri._check_digest(self.receipt_sha256, "receipt_sha256")


@dataclass(frozen=True)
class GravityQuantumPolicyReceiptV1:
    policy_sha256: str
    candidate_id: str
    bound_transitions: tuple[tuple[str, str], ...]
    failures: tuple[tuple[str, str], ...]
    decision: str
    authority_effect: str = "NONE"
    receipt_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        ri._check_digest(self.policy_sha256, "policy_sha256")
        if self.decision not in {"PASS", "DENY"}:
            raise ValueError("invalid policy decision")
        if self.authority_effect != "NONE":
            raise ValueError("policy receipt may not grant authority")
        object.__setattr__(
            self,
            "receipt_sha256",
            ri.sha256_hex(
                {
                    "schema": RECEIPT_SCHEMA,
                    "policy_sha256": self.policy_sha256,
                    "candidate_id": self.candidate_id,
                    "bound_transitions": self.bound_transitions,
                    "failures": self.failures,
                    "decision": self.decision,
                    "authority_effect": self.authority_effect,
                }
            ),
        )


def evaluate_policy(
    policy: GravityQuantumPolicyV1,
    candidate_id: str,
    transitions: Mapping[str, TransitionEvidenceV1],
) -> GravityQuantumPolicyReceiptV1:
    failures: list[tuple[str, str]] = []
    bound: list[tuple[str, str]] = []

    for transition_id in policy.required_transitions:
        evidence = transitions.get(transition_id)
        if evidence is None:
            failures.append((transition_id, "MISSING"))
            continue
        if evidence.transition_id != transition_id:
            failures.append((transition_id, "ID_MISMATCH"))
            continue
        bound.append((transition_id, evidence.receipt_sha256))
        if evidence.status in policy.forbidden_statuses:
            failures.append((transition_id, f"FORBIDDEN_STATUS:{evidence.status}"))
        elif evidence.status != policy.allowed_status:
            failures.append((transition_id, f"NON_PASS_STATUS:{evidence.status}"))

    return GravityQuantumPolicyReceiptV1(
        policy_sha256=policy.policy_sha256,
        candidate_id=candidate_id,
        bound_transitions=tuple(bound),
        failures=tuple(failures),
        decision="DENY" if failures else "PASS",
    )
