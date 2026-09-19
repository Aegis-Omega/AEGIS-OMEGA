"""AEGIS Ω — Cross-Boundary Authority V1.

An evidence result may cross a domain, carrier, or scope boundary only through an
explicit relation-bound bridge criterion whose required proof-carrying verifier
bundles all replay successfully.

A raw GateReceipt is never sufficient: Cross-Domain Collision V1 already
establishes that hash-valid receipts are evidence objects, not promotion
authority. This module therefore accepts only VerifiedBridgeGateV1 bundles whose
verifier identity is criterion-pinned and whose evidence is replayed by an
exact-head registered verifier.

The gate never mutates a target claim, never changes repository state, and never
grants runtime or production authority. A passing result means only that a
separate target-status transition is eligible to be considered.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

import research_invariants as ri

SCHEMA = "AEGIS_CROSS_BOUNDARY_AUTHORITY_V1"
RELATION_ID = "CROSS_BOUNDARY_AUTHORITY_BRIDGE_V1"
SYNTHETIC_LITERAL_BOOL_VERIFIER_ID = "SYNTHETIC_LITERAL_BOOL_BRIDGE_V1"


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
class BridgeGateRequirementV1:
    gate_id: str
    verifier_id: str

    def __post_init__(self) -> None:
        if not self.gate_id or not self.verifier_id:
            raise ValueError("gate_id and verifier_id must be non-empty")


@dataclass(frozen=True)
class BridgeCriterionV1:
    bridge_id: str
    source_coordinate: ClaimCoordinateV1
    target_coordinate: ClaimCoordinateV1
    allowed_source_statuses: tuple[str, ...]
    allowed_target_statuses: tuple[str, ...]
    required_gates: tuple[BridgeGateRequirementV1, ...]
    criterion_text: str
    criterion_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.bridge_id or not self.criterion_text:
            raise ValueError("bridge_id and criterion_text must be non-empty")
        if not self.allowed_source_statuses or not self.allowed_target_statuses:
            raise ValueError("status allowlists must be non-empty")
        if not self.required_gates:
            raise ValueError("required_gates must be non-empty")
        gate_ids = tuple(gate.gate_id for gate in self.required_gates)
        if len(set(gate_ids)) != len(gate_ids):
            raise ValueError("required gate ids must be unique")
        if any(
            not value
            for value in (
                *self.allowed_source_statuses,
                *self.allowed_target_statuses,
            )
        ):
            raise ValueError("status identifiers must be non-empty")

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
                    "required_gates": tuple(
                        (gate.gate_id, gate.verifier_id)
                        for gate in self.required_gates
                    ),
                    "criterion_text_sha256": criterion_text_sha256,
                }
            ),
        )

    @property
    def required_gate_ids(self) -> tuple[str, ...]:
        return tuple(gate.gate_id for gate in self.required_gates)


@dataclass(frozen=True)
class VerifiedBridgeGateV1:
    gate_id: str
    verifier_id: str
    relation: ri.RelationBindingV1
    evidence: Mapping[str, Any]
    receipt: ri.GateReceipt

    def __post_init__(self) -> None:
        if not self.gate_id or not self.verifier_id:
            raise ValueError("gate_id and verifier_id must be non-empty")
        object.__setattr__(self, "evidence", ri.freeze_hash_material(self.evidence))


@dataclass(frozen=True)
class CrossBoundaryAuthorityReceiptV1:
    relation_digest: str
    source_claim_sha256: str
    target_claim_sha256: str
    criterion_sha256: str
    changed_axes: tuple[str, ...]
    required_gate_bindings: tuple[tuple[str, str], ...]
    supplied_gate_receipt_digests: tuple[str, ...]
    missing_gate_ids: tuple[str, ...]
    failing_gate_ids: tuple[str, ...]
    malformed_gate_ids: tuple[str, ...]
    extra_gate_ids: tuple[str, ...]
    unregistered_verifier_ids: tuple[str, ...]
    unverified_bundle_count: int
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
        if self.unverified_bundle_count < 0:
            raise ValueError("unverified_bundle_count must be non-negative")
        material = {
            "schema": SCHEMA,
            "relation_digest": self.relation_digest,
            "source_claim_sha256": self.source_claim_sha256,
            "target_claim_sha256": self.target_claim_sha256,
            "criterion_sha256": self.criterion_sha256,
            "changed_axes": self.changed_axes,
            "required_gate_bindings": self.required_gate_bindings,
            "supplied_gate_receipt_digests": self.supplied_gate_receipt_digests,
            "missing_gate_ids": self.missing_gate_ids,
            "failing_gate_ids": self.failing_gate_ids,
            "malformed_gate_ids": self.malformed_gate_ids,
            "extra_gate_ids": self.extra_gate_ids,
            "unregistered_verifier_ids": self.unregistered_verifier_ids,
            "unverified_bundle_count": self.unverified_bundle_count,
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


def _receipt_semantically_equal(
    left: ri.GateReceipt, right: ri.GateReceipt
) -> bool:
    return (
        left.deterministic_material() == right.deterministic_material()
        and left.witness_sha256 == right.witness_sha256
    )


BridgeVerifier = Callable[
    [str, ri.RelationBindingV1, Mapping[str, Any]],
    ri.GateReceipt,
]


def _synthetic_literal_bool_verifier(
    gate_id: str,
    relation: ri.RelationBindingV1,
    evidence: Mapping[str, Any],
) -> ri.GateReceipt:
    established = evidence.get("established")
    if set(evidence) != {"established"} or type(established) is not bool:
        verdict = ri.GateVerdict.ERROR
        observation = {
            "verifier_id": SYNTHETIC_LITERAL_BOOL_VERIFIER_ID,
            "reason": "expected-literal-bool-established",
        }
    else:
        verdict = (
            ri.GateVerdict.PASS if established else ri.GateVerdict.FAIL
        )
        observation = {
            "verifier_id": SYNTHETIC_LITERAL_BOOL_VERIFIER_ID,
            "established": established,
        }
    return ri.relation_gate_receipt(
        gate_id=gate_id,
        relation=relation,
        verdict=verdict,
        observation=observation,
        gate_version="1",
    )


_REGISTERED_BRIDGE_VERIFIERS: Mapping[str, BridgeVerifier] = {
    SYNTHETIC_LITERAL_BOOL_VERIFIER_ID: _synthetic_literal_bool_verifier,
}


def mint_synthetic_verified_bridge_gate(
    *,
    gate_id: str,
    relation: ri.RelationBindingV1,
    established: bool,
) -> VerifiedBridgeGateV1:
    evidence = {"established": established}
    receipt = _synthetic_literal_bool_verifier(gate_id, relation, evidence)
    return VerifiedBridgeGateV1(
        gate_id=gate_id,
        verifier_id=SYNTHETIC_LITERAL_BOOL_VERIFIER_ID,
        relation=relation,
        evidence=evidence,
        receipt=receipt,
    )


def verify_verified_bridge_gate(
    bundle: VerifiedBridgeGateV1,
    requirement: BridgeGateRequirementV1,
    expected_relation: ri.RelationBindingV1,
) -> ri.GateReceipt:
    if not isinstance(bundle, VerifiedBridgeGateV1):
        raise TypeError("expected VerifiedBridgeGateV1")
    if bundle.gate_id != requirement.gate_id:
        raise ValueError("bridge bundle gate id mismatch")
    if bundle.verifier_id != requirement.verifier_id:
        raise ValueError("bridge bundle verifier id mismatch")
    if bundle.relation.relation_digest != expected_relation.relation_digest:
        raise ValueError("bridge bundle relation mismatch")
    verifier = _REGISTERED_BRIDGE_VERIFIERS.get(requirement.verifier_id)
    if verifier is None:
        raise ValueError("bridge verifier is not exact-head registered")
    if not _receipt_integrity(bundle.receipt):
        raise ValueError("bridge receipt integrity failure")
    replayed = verifier(bundle.gate_id, expected_relation, bundle.evidence)
    if not _receipt_semantically_equal(replayed, bundle.receipt):
        raise ValueError("verified bridge replay does not reproduce receipt")
    return replayed


def evaluate_cross_boundary_authority(
    source: BoundClaimV1,
    target: BoundClaimV1,
    criterion: BridgeCriterionV1,
    bridge_gate_bundles: Sequence[VerifiedBridgeGateV1 | ri.GateReceipt],
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

    by_id: dict[str, VerifiedBridgeGateV1] = {}
    duplicates: set[str] = set()
    unverified_bundle_count = 0
    for candidate in bridge_gate_bundles:
        if not isinstance(candidate, VerifiedBridgeGateV1):
            unverified_bundle_count += 1
            continue
        if candidate.gate_id in by_id:
            duplicates.add(candidate.gate_id)
        else:
            by_id[candidate.gate_id] = candidate

    if unverified_bundle_count:
        add_reason("FAIL_RAW_OR_UNVERIFIED_GATE_BUNDLE")
    if duplicates:
        add_reason("FAIL_DUPLICATE_GATE")

    required_ids = set(criterion.required_gate_ids)
    supplied_ids = set(by_id)
    missing = tuple(sorted(required_ids - supplied_ids))
    extra = tuple(sorted(supplied_ids - required_ids))
    if missing:
        add_reason("FAIL_REQUIRED_GATE")
    if extra:
        add_reason("FAIL_EXTRA_GATE")

    unregistered = tuple(
        sorted(
            {
                requirement.verifier_id
                for requirement in criterion.required_gates
                if requirement.verifier_id
                not in _REGISTERED_BRIDGE_VERIFIERS
            }
        )
    )
    if unregistered:
        add_reason("FAIL_UNREGISTERED_VERIFIER")

    failing: list[str] = []
    malformed: list[str] = []
    verified_digests: list[str] = []
    for requirement in criterion.required_gates:
        bundle = by_id.get(requirement.gate_id)
        if bundle is None:
            continue
        try:
            receipt = verify_verified_bridge_gate(
                bundle, requirement, relation
            )
        except (TypeError, ValueError):
            malformed.append(requirement.gate_id)
            continue
        verified_digests.append(receipt.witness_sha256)
        if receipt.verdict is not ri.GateVerdict.PASS:
            failing.append(requirement.gate_id)

    if malformed:
        add_reason("FAIL_GATE_BUNDLE_REPLAY")
    if failing:
        add_reason("FAIL_GATE_VERDICT")

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
        required_gate_bindings=tuple(
            (gate.gate_id, gate.verifier_id)
            for gate in criterion.required_gates
        ),
        supplied_gate_receipt_digests=tuple(verified_digests),
        missing_gate_ids=missing,
        failing_gate_ids=tuple(sorted(failing)),
        malformed_gate_ids=tuple(sorted(malformed)),
        extra_gate_ids=extra,
        unregistered_verifier_ids=unregistered,
        unverified_bundle_count=unverified_bundle_count,
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
    bridge_gate_bundles: Sequence[VerifiedBridgeGateV1 | ri.GateReceipt],
) -> bool:
    try:
        return receipt == evaluate_cross_boundary_authority(
            source, target, criterion, bridge_gate_bundles
        )
    except Exception:
        return False
