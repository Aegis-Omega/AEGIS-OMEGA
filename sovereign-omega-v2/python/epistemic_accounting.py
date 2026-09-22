"""AEGIS Ω — Epistemic Accounting V1.

Formalizes accounting invariants already implicit in MHP-1:
source claims = preserved-source claims disjoint-union declared omissions;
target claims = preserved-target claims disjoint-union declared additions.

Single-step additions require derivation receipts.
Transitive V1 admits no final additions because derivation-proof composition has
not yet been ratified.

This is semantic accounting, not Shannon-information conservation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class Relation(str, Enum):
    IDENTITY = "IDENTITY"
    LOSSLESS = "LOSSLESS"
    LOSSY = "LOSSY"
    AUGMENTING = "AUGMENTING"


class AccountingMode(str, Enum):
    SINGLE_STEP = "SINGLE_STEP"
    TRANSITIVE_V1 = "TRANSITIVE_V1"


@dataclass(frozen=True)
class AccountingEnvelopeV1:
    source_claims: frozenset[str]
    target_claims: frozenset[str]
    preserved_source: frozenset[str]
    preserved_target: frozenset[str]
    omissions: frozenset[str]
    additions: frozenset[str]
    addition_receipts: tuple[tuple[str, str], ...]
    relation: Relation
    uncertainty_bps: int

    def __post_init__(self) -> None:
        all_claim_sets = (
            self.source_claims,
            self.target_claims,
            self.preserved_source,
            self.preserved_target,
            self.omissions,
            self.additions,
        )
        if not all(isinstance(item, frozenset) for item in all_claim_sets):
            raise ValueError("CLAIM_SETS_MUST_BE_FROZEN")
        if (
            isinstance(self.uncertainty_bps, bool)
            or not isinstance(self.uncertainty_bps, int)
            or not 0 <= self.uncertainty_bps <= 10000
        ):
            raise ValueError("UNCERTAINTY_BPS_INVALID")
        seen = set()
        for claim, receipt in self.addition_receipts:
            if claim in seen:
                raise ValueError("DUPLICATE_ADDITION_RECEIPT")
            seen.add(claim)
            if SHA256_RE.fullmatch(receipt) is None:
                raise ValueError("ADDITION_RECEIPT_DIGEST_INVALID")


def verify_accounting(
    envelope: AccountingEnvelopeV1,
    *,
    mode: AccountingMode,
) -> dict[str, object]:
    reasons: list[str] = []

    def fail(code: str) -> None:
        if code not in reasons:
            reasons.append(code)

    if envelope.preserved_source & envelope.omissions:
        fail("SOURCE_PARTITION_OVERLAP")
    if envelope.preserved_target & envelope.additions:
        fail("TARGET_PARTITION_OVERLAP")
    if envelope.source_claims != envelope.preserved_source | envelope.omissions:
        fail("SOURCE_PARTITION_INCOMPLETE")
    if envelope.target_claims != envelope.preserved_target | envelope.additions:
        fail("TARGET_PARTITION_INCOMPLETE")

    receipt_map = dict(envelope.addition_receipts)
    if set(receipt_map) != set(envelope.additions):
        fail("ADDITION_RECEIPT_COVERAGE_MISMATCH")

    if mode == AccountingMode.TRANSITIVE_V1 and envelope.additions:
        fail("TRANSITIVE_FINAL_ADDITION_UNPROVEN")

    if envelope.relation in {Relation.IDENTITY, Relation.LOSSLESS}:
        if envelope.omissions or envelope.additions or envelope.uncertainty_bps != 0:
            fail("LOSSLESS_CONTRACT_INCONSISTENT")
    elif envelope.relation == Relation.AUGMENTING:
        if envelope.omissions or envelope.uncertainty_bps != 0:
            fail("AUGMENTING_CONTRACT_INCONSISTENT")
    elif envelope.relation == Relation.LOSSY:
        if not envelope.omissions:
            fail("LOSSY_WITHOUT_DECLARED_OMISSION")
    else:
        fail("UNKNOWN_RELATION")

    return {
        "decision": "PASS" if not reasons else "DENY",
        "reason_codes": tuple(reasons),
        "source_balance": len(envelope.source_claims)
        == len(envelope.preserved_source) + len(envelope.omissions),
        "target_balance": len(envelope.target_claims)
        == len(envelope.preserved_target) + len(envelope.additions),
        "authority_effect": "NONE",
    }


def composed_uncertainty_bps(
    *,
    has_composite_source_loss: bool,
    left_uncertainty_bps: int,
    right_uncertainty_bps: int,
) -> int:
    for value in (left_uncertainty_bps, right_uncertainty_bps):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10000:
            raise ValueError("UNCERTAINTY_BPS_INVALID")
    if not isinstance(has_composite_source_loss, bool):
        raise ValueError("LOSS_FLAG_MUST_BE_BOOL")
    return (
        max(left_uncertainty_bps, right_uncertainty_bps)
        if has_composite_source_loss
        else 0
    )
