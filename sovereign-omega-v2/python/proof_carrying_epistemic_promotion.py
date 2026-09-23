"""AEGIS Ω — Proof-Carrying Epistemic Promotion V1.

The conservative meet is evidence-free because it weakens or preserves every
epistemic coordinate. Any candidate stronger than that meet creates explicit
promotion obligations.

Promotion dimensions:
- CLAIM_GAIN: candidate asserts an exact canonical claim not in the meet.
- AUTHORITY_GAIN: candidate authority exceeds the meet authority.
- UNCERTAINTY_REDUCTION: candidate loss uncertainty is below the meet value.

A promotion receipt is content-addressed and exact-bound to both inputs, the
candidate, the obligation, a verifier root, a policy root, and supporting
evidence. A passing receipt makes a separate promotion transition eligible; it
never mutates authority or claim state by itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Protocol

from no_free_epistemic_gain import (
    EpistemicStateV1,
    conservative_meet,
    epistemic_le,
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PASS = "PASS"
DENY = "DENY"
NO_AUTHORITY = "NONE"


def _canonical_hash(domain: str, payload: object) -> str:
    raw = json.dumps(
        {"domain": domain, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def state_sha256(state: EpistemicStateV1) -> str:
    return _canonical_hash(
        "AEGIS_EPISTEMIC_STATE_V1",
        {
            "claims": sorted(state.claims),
            "authority": state.authority.name,
            "uncertainty_bps": state.uncertainty_bps,
        },
    )


def promotion_obligations(
    left: EpistemicStateV1,
    right: EpistemicStateV1,
    candidate: EpistemicStateV1,
) -> tuple[str, ...]:
    baseline = conservative_meet(left, right)
    obligations: list[str] = []

    for claim in sorted(candidate.claims - baseline.claims):
        obligations.append(f"CLAIM_GAIN::{claim}")

    if candidate.authority > baseline.authority:
        obligations.append(
            "AUTHORITY_GAIN::"
            f"{baseline.authority.name}->{candidate.authority.name}"
        )

    if candidate.uncertainty_bps < baseline.uncertainty_bps:
        obligations.append(
            "UNCERTAINTY_REDUCTION::"
            f"{baseline.uncertainty_bps}->{candidate.uncertainty_bps}"
        )

    return tuple(obligations)


@dataclass(frozen=True)
class PromotionReceiptV1:
    obligation_id: str
    left_state_sha256: str
    right_state_sha256: str
    candidate_state_sha256: str
    evidence_sha256: str
    verifier_root: str
    policy_root: str
    status: str = PASS
    authority_effect: str = NO_AUTHORITY
    schema: str = "AEGIS_EPISTEMIC_PROMOTION_RECEIPT_V1"
    receipt_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.obligation_id:
            raise ValueError("OBLIGATION_ID_REQUIRED")
        for value, label in (
            (self.left_state_sha256, "left_state_sha256"),
            (self.right_state_sha256, "right_state_sha256"),
            (self.candidate_state_sha256, "candidate_state_sha256"),
            (self.evidence_sha256, "evidence_sha256"),
            (self.verifier_root, "verifier_root"),
            (self.policy_root, "policy_root"),
        ):
            if SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{label}: invalid digest")
        if self.status != PASS:
            raise ValueError("PROMOTION_RECEIPT_NOT_PASS")
        if self.authority_effect != NO_AUTHORITY:
            raise ValueError("PROMOTION_RECEIPT_AUTHORITY_LEAK")

        material = {
            "obligation_id": self.obligation_id,
            "left_state_sha256": self.left_state_sha256,
            "right_state_sha256": self.right_state_sha256,
            "candidate_state_sha256": self.candidate_state_sha256,
            "evidence_sha256": self.evidence_sha256,
            "verifier_root": self.verifier_root,
            "policy_root": self.policy_root,
            "status": self.status,
            "authority_effect": self.authority_effect,
            "schema": self.schema,
        }
        object.__setattr__(
            self,
            "receipt_sha256",
            _canonical_hash(
                "AEGIS_EPISTEMIC_PROMOTION_RECEIPT_V1",
                material,
            ),
        )


class TrustedPromotionReceiptStore(Protocol):
    def fetch_verified(
        self, receipt_sha256: str
    ) -> PromotionReceiptV1 | None: ...


@dataclass(frozen=True)
class PromotionDecisionV1:
    decision: str
    required_obligations: tuple[str, ...]
    satisfied_obligations: tuple[str, ...]
    reason_codes: tuple[str, ...]
    automatic_promotion: bool = False
    authority_effect: str = NO_AUTHORITY


def evaluate_promotion(
    left: EpistemicStateV1,
    right: EpistemicStateV1,
    candidate: EpistemicStateV1,
    receipt_roots: tuple[str, ...],
    *,
    store: TrustedPromotionReceiptStore,
) -> PromotionDecisionV1:
    baseline = conservative_meet(left, right)
    required = promotion_obligations(left, right, candidate)
    reasons: list[str] = []
    satisfied: list[str] = []

    if len(receipt_roots) != len(set(receipt_roots)):
        reasons.append("DUPLICATE_RECEIPT_ROOT")

    expected_bindings = (
        state_sha256(left),
        state_sha256(right),
        state_sha256(candidate),
    )

    seen_obligations: set[str] = set()
    for root in receipt_roots:
        if SHA256_RE.fullmatch(root) is None:
            reasons.append("MALFORMED_RECEIPT_ROOT")
            continue

        receipt = store.fetch_verified(root)
        if receipt is None or receipt.receipt_sha256 != root:
            reasons.append("UNTRUSTED_RECEIPT")
            continue

        if (
            receipt.left_state_sha256,
            receipt.right_state_sha256,
            receipt.candidate_state_sha256,
        ) != expected_bindings:
            reasons.append("RECEIPT_STATE_BINDING_MISMATCH")
            continue

        if receipt.obligation_id not in required:
            reasons.append("EXTRA_OR_WRONG_OBLIGATION")
            continue

        if receipt.obligation_id in seen_obligations:
            reasons.append("DUPLICATE_OBLIGATION")
            continue

        seen_obligations.add(receipt.obligation_id)
        satisfied.append(receipt.obligation_id)

    missing = tuple(sorted(set(required) - seen_obligations))
    if missing:
        reasons.append("MISSING_PROMOTION_OBLIGATION")

    if not required:
        if receipt_roots:
            reasons.append("UNNEEDED_PROMOTION_RECEIPT")
        if not epistemic_le(candidate, baseline):
            reasons.append("NONCONSERVATIVE_WITHOUT_OBLIGATION")
        decision = (
            "PASS_CANONICAL_CONSERVATIVE"
            if candidate == baseline and not reasons
            else "PASS_CONSERVATIVE_NONCANONICAL"
            if not reasons
            else DENY
        )
    else:
        decision = (
            "ELIGIBLE_FOR_SEPARATE_PROMOTION_ONLY"
            if not reasons
            else DENY
        )

    return PromotionDecisionV1(
        decision=decision,
        required_obligations=tuple(sorted(required)),
        satisfied_obligations=tuple(sorted(satisfied)),
        reason_codes=tuple(sorted(set(reasons))),
    )
