"""AEGIS Ω — Cross-Boundary Authority V1.

An evidence result may cross a domain, carrier, or scope boundary only through an
explicit relation-bound bridge criterion whose required receipts all verify.

The gate never mutates a target claim, never changes repository state, and never
grants runtime or production authority. A passing result means only that a
separate target-status transition is eligible to be considered.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

import research_invariants as ri

SCHEMA = "AEGIS_CROSS_BOUNDARY_AUTHORITY_V1"
RELATION_ID = "CROSS_BOUNDARY_AUTHORITY_BRIDGE_V1"


class BridgeDecision(str, Enum):
    DENY = "DENY"
    ELIGIBLE = "ELIGIBLE_FOR_SEPARATE_TARGET_TRANSITION_ONLY"


@dataclass(frozen=True)
class ClaimCoordinateV1:
    domain_id: str
    carrier_id: str
    scope_id: str
    coordinate_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name, value in (
            ("domain_id", self.domain_id),
            ("carrier_id", self.carrier_id),
            ("scope_id", self.scope_id),
        ):
            if not value:
                raise ValueError(f"{name} must be non-empty")
        object.__setattr__(
            self,
            "coordinate_sha256",
            ri.sha256_hex(
                {
                    "schema": "AEGIS_CLAIM_COORDINATE_V1",
                    "domain_id": self.domain_id,
                    "carrier_id": self.carrier_id,
                    "scope_id": self.scope_id,
                }
            ),
        )


@dataclass(frozen=True)
class BoundClaimV1:
    claim_id: str
    coordinate: ClaimCoordinateV1
    status: str
    evidence_sha256: str
    claim_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.claim_id or not self.status:
            raise ValueError("claim_id and status must be non-empty")
        ri._check_digest(self.evidence_sha256, "evidence_sha256")
        object.__setattr__(
            self,
            "claim_sha256",
            ri.sha256_hex(
                {
                    "schema": "AEGIS_BOUND_CLAIM_V1",
                    "claim_id": self.claim_id,
                    "coordinate_sha256": self.coordinate.coordinate_sha256,
                    "status": self.status,
                    "evidence_sha256": self.evidence_sha256,
                }
            ),
        )


@dataclass(frozen=True)
class BridgeCriterionV1:
    bridge_id: str
    source_coordinate: ClaimCoordinateV1
    target_coordinate: ClaimCoordinateV1
    allowed_source_statuses: tuple[str, ...]
    allowed_target_statuses: tuple[str, ...]
    required_gate_ids: tuple[str, ...]
    criterion_text: str
    criterion_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.bridge_id or not self.criterion_text:
            raise ValueError("bridge_id and criterion_text must be non-empty")
        if not self.allowed_source_statuses or not self.allowed_target_statuses:
            raise ValueError("status allowlists must be non-empty")
        if not self.required_gate_ids:
            raise ValueError("required_gate_ids must be non-empty")
        if len(set(self.required_gate_ids)) != len(self.required_gate_ids):
            raise ValueError("required_gate_ids must be unique")
        if any(
            not value
            for value in (
                *self.allowed_source_statuses,
                *self.allowed_target_statuses,
                *self.required_gate_ids,
            )
        ):
            raise ValueError("criterion identifiers must be non-empty")

        criterion_text_sha256 = ri.literal_sha256(self.criterion_text)
        object.__setattr__(
            self,
            "criterion_sha256",
            ri.sha256_hex(
                {
                    "schema": "AEGIS_BRIDGE_CRITERION_V1",
                    "bridge_id": self.bridge_id,
                    "source_coordinate_sha256": self.source_coordinate.coordinate_sha256,
                    "target_coordinate_sha256": self.target_coordinate.coordinate_sha256,
                    "allowed_source_statuses": self.allowed_source_statuses,
                    "allowed_target_statuses": self.allowed_target_statuses,
                    "required_gate_ids": self.required_gate_ids,
                    "criterion_text_sha256": criterion_text_sha256,
                }
            ),
        )


@dataclass(frozen=True)
class CrossBoundaryAuthorityReceiptV1:
    relation_digest: str
    source_claim_sha256: str
    target_claim_sha256: str
    criterion_sha256: str
    changed_axes: tuple[str, ...]
    required_gate_ids: tuple[str, ...]
    supplied_gate_receipt_digests: tuple[str, ...]
    missing_gate_ids: tuple[str, ...]
    failing_gate_ids: tuple[str, ...]
    malformed_gate_ids: tuple[str, ...]
    extra_gate_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    weakest_verified_transition: str
    decision: BridgeDecision
    claim_promotion: str
    authority_effect: str
    receipt_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name, digest in (
            ("relation_digest", self.relation_digest),
            ("source_claim_sha256", self.source_claim_sha256),
            ("target_claim_sha256", self.target_claim_sha256),
            ("criterion_sha256", self.criterion_sha256),
        ):
            ri._check_digest(digest, name)
        material = {
            "schema": SCHEMA,
            "relation_digest": self.relation_digest,
            "source_claim_sha256": self.source_claim_sha256,
            "target_claim_sha256": self.target_claim_sha256,
            "criterion_sha256": self.criterion_sha256,
            "changed_axes": self.changed_axes,
            "required_gate_ids": self.required_gate_ids,
            "supplied_gate_receipt_digests": self.supplied_gate_receipt_digests,
            "missing_gate_ids": self.missing_gate_ids,
            "failing_gate_ids": self.failing_gate_ids,
            "malformed_gate_ids": self.malformed_gate_ids,
            "extra_gate_ids": self.extra_gate_ids,
            "reason_codes": self.reason_codes,
            "weakest_verified_transition": self.weakest_verified_transition,
            "decision": self.decision.value,
            "claim_promotion": self.claim_promotion,
            "authority_effect": self.authority_effect,
        }
        object.__setattr__(self, "receipt_sha256", ri.sha256_hex(material))


def changed_axes(
    source: ClaimCoordinateV1, target: ClaimCoordinateV1
) -> tuple[str, ...]:
    axes: list[str] = []
    if source.domain_id != target.domain_id:
        axes.append("DOMAIN")
    if source.carrier_id != target.carrier_id:
        axes.append("CARRIER")
    if source.scope_id != target.scope_id:
        axes.append("SCOPE")
    return tuple(axes)


def bind_bridge_relation(
    source: BoundClaimV1,
    target: BoundClaimV1,
    criterion: BridgeCriterionV1,
) -> ri.RelationBindingV1:
    return ri.bind_relation(
        RELATION_ID,
        {
            "source_claim": source.claim_sha256,
            "target_claim": target.claim_sha256,
            "bridge_criterion": criterion.criterion_sha256,
        },
    )


def _receipt_integrity(receipt: ri.GateReceipt) -> bool:
    try:
        return (
            ri.sha256_hex(receipt.deterministic_material())
            == receipt.witness_sha256
        )
    except Exception:
        return False


def evaluate_cross_boundary_authority(
    source: BoundClaimV1,
    target: BoundClaimV1,
    criterion: BridgeCriterionV1,
    gate_receipts: Sequence[ri.GateReceipt],
) -> CrossBoundaryAuthorityReceiptV1:
    reasons: list[str] = []

    def add_reason(code: str) -> None:
        if code not in reasons:
            reasons.append(code)

    axes = changed_axes(source.coordinate, target.coordinate)
    if not axes:
        add_reason("FAIL_NO_BOUNDARY_CHANGE")

    if (
        source.coordinate.coordinate_sha256
        != criterion.source_coordinate.coordinate_sha256
        or target.coordinate.coordinate_sha256
        != criterion.target_coordinate.coordinate_sha256
    ):
        add_reason("FAIL_CRITERION_COORDINATE_BINDING")

    if source.status not in criterion.allowed_source_statuses:
        add_reason("FAIL_SOURCE_STATUS")
    if target.status not in criterion.allowed_target_statuses:
        add_reason("FAIL_TARGET_STATUS")

    relation = bind_bridge_relation(source, target, criterion)

    by_id: dict[str, ri.GateReceipt] = {}
    duplicates: set[str] = set()
    for receipt in gate_receipts:
        if receipt.gate_id in by_id:
            duplicates.add(receipt.gate_id)
        else:
            by_id[receipt.gate_id] = receipt
    if duplicates:
        add_reason("FAIL_DUPLICATE_GATE")

    required = set(criterion.required_gate_ids)
    supplied = set(by_id)
    missing = tuple(sorted(required - supplied))
    extra = tuple(sorted(supplied - required))
    if missing:
        add_reason("FAIL_REQUIRED_GATE")
    if extra:
        add_reason("FAIL_EXTRA_GATE")

    failing: list[str] = []
    malformed: list[str] = []
    for gate_id in criterion.required_gate_ids:
        receipt = by_id.get(gate_id)
        if receipt is None:
            continue
        malformed_receipt = (
            not _receipt_integrity(receipt)
            or receipt.type_signature != "RelationBindingV1"
            or receipt.object_digest != relation.relation_digest
        )
        if malformed_receipt:
            malformed.append(gate_id)
            continue
        if receipt.verdict is not ri.GateVerdict.PASS:
            failing.append(gate_id)

    if malformed:
        add_reason("FAIL_GATE_RECEIPT_BINDING")
    if failing:
        add_reason("FAIL_GATE_VERDICT")

    supplied_digests = tuple(
        by_id[gate_id].witness_sha256
        for gate_id in sorted(by_id)
        if _receipt_integrity(by_id[gate_id])
    )

    if reasons:
        decision = BridgeDecision.DENY
        claim_promotion = "BLOCKED"
        weakest = "UNVERIFIED_OR_FAILED"
    else:
        decision = BridgeDecision.ELIGIBLE
        claim_promotion = "ELIGIBLE_FOR_SEPARATE_TARGET_STATUS_TRANSITION"
        weakest = "VERIFIED"

    return CrossBoundaryAuthorityReceiptV1(
        relation_digest=relation.relation_digest,
        source_claim_sha256=source.claim_sha256,
        target_claim_sha256=target.claim_sha256,
        criterion_sha256=criterion.criterion_sha256,
        changed_axes=axes,
        required_gate_ids=criterion.required_gate_ids,
        supplied_gate_receipt_digests=supplied_digests,
        missing_gate_ids=missing,
        failing_gate_ids=tuple(sorted(failing)),
        malformed_gate_ids=tuple(sorted(malformed)),
        extra_gate_ids=extra,
        reason_codes=tuple(reasons),
        weakest_verified_transition=weakest,
        decision=decision,
        claim_promotion=claim_promotion,
        authority_effect="NONE",
    )


def verify_cross_boundary_authority_receipt(
    receipt: CrossBoundaryAuthorityReceiptV1,
    source: BoundClaimV1,
    target: BoundClaimV1,
    criterion: BridgeCriterionV1,
    gate_receipts: Sequence[ri.GateReceipt],
) -> bool:
    try:
        return receipt == evaluate_cross_boundary_authority(
            source, target, criterion, gate_receipts
        )
    except Exception:
        return False
