"""AEGIS Ω — Verified Semantic Quotient Consensus V1.

Exact claim identity remains the default. A claim may project to a different
canonical semantic class only when a trusted MHP PreservationProofReceiptV1
proves SEMANTIC_EQUIVALENCE from that exact claim to the canonical
representative.

PARAPHRASE_ABSTRACTION is deliberately insufficient for quotient membership.
A missing equivalence can cause a false negative (two equivalent claims stay in
different classes); it may not cause a false positive semantic merge.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Protocol

from epistemic_authority_conservation import AuthorityLevel
from harness.sdk.meaning_heritage import (
    PreservationRelation,
    PreservationProofReceiptV1,
)
from no_free_epistemic_gain import EpistemicStateV1

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NO_AUTHORITY = "NONE"
PASS = "PASS"


def _hash(domain: str, payload: object) -> str:
    raw = json.dumps(
        {"domain": domain, "payload": payload},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class TrustedPreservationStore(Protocol):
    def fetch_preservation(
        self, root: str
    ) -> PreservationProofReceiptV1 | None: ...


@dataclass(frozen=True)
class SemanticClassMembershipV1:
    claim_digest: str
    claim_semantic_fingerprint: str
    canonical_claim_digest: str
    canonical_semantic_fingerprint: str
    preservation_receipt_root: str | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.claim_digest, "claim_digest"),
            (self.canonical_claim_digest, "canonical_claim_digest"),
        ):
            if SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{label}: invalid digest")
        if not self.claim_semantic_fingerprint:
            raise ValueError("CLAIM_FINGERPRINT_REQUIRED")
        if not self.canonical_semantic_fingerprint:
            raise ValueError("CANONICAL_FINGERPRINT_REQUIRED")
        if self.preservation_receipt_root is not None:
            if SHA256_RE.fullmatch(self.preservation_receipt_root) is None:
                raise ValueError("preservation_receipt_root: invalid digest")

    @property
    def semantic_class_id(self) -> str:
        return self.canonical_claim_digest


@dataclass(frozen=True)
class SemanticProjectionReceiptV1:
    source_claim_digests: tuple[str, ...]
    memberships: tuple[SemanticClassMembershipV1, ...]
    semantic_class_ids: tuple[str, ...]
    status: str = PASS
    authority_effect: str = NO_AUTHORITY
    schema: str = "AEGIS_SEMANTIC_PROJECTION_RECEIPT_V1"
    receipt_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.status != PASS:
            raise ValueError("PROJECTION_NOT_PASS")
        if self.authority_effect != NO_AUTHORITY:
            raise ValueError("PROJECTION_AUTHORITY_LEAK")
        material = {
            "source_claim_digests": list(self.source_claim_digests),
            "memberships": [
                {
                    "claim_digest": item.claim_digest,
                    "claim_semantic_fingerprint": item.claim_semantic_fingerprint,
                    "canonical_claim_digest": item.canonical_claim_digest,
                    "canonical_semantic_fingerprint": item.canonical_semantic_fingerprint,
                    "preservation_receipt_root": item.preservation_receipt_root,
                }
                for item in self.memberships
            ],
            "semantic_class_ids": list(self.semantic_class_ids),
            "status": self.status,
            "authority_effect": self.authority_effect,
            "schema": self.schema,
        }
        object.__setattr__(
            self,
            "receipt_sha256",
            _hash("AEGIS_SEMANTIC_PROJECTION_RECEIPT_V1", material),
        )


def verify_membership(
    membership: SemanticClassMembershipV1,
    *,
    store: TrustedPreservationStore,
) -> bool:
    if membership.claim_digest == membership.canonical_claim_digest:
        return (
            membership.claim_semantic_fingerprint
            == membership.canonical_semantic_fingerprint
            and membership.preservation_receipt_root is None
        )

    root = membership.preservation_receipt_root
    if root is None:
        return False
    receipt = store.fetch_preservation(root)
    if receipt is None or receipt.root != root:
        return False
    if receipt.authority_class != NO_AUTHORITY:
        return False
    if receipt.status != PASS:
        return False
    if receipt.relation != PreservationRelation.SEMANTIC_EQUIVALENCE:
        return False
    return (
        receipt.source_claim_digest == membership.claim_digest
        and receipt.derived_claim_digest == membership.canonical_claim_digest
        and receipt.source_semantic_fingerprint
        == membership.claim_semantic_fingerprint
        and receipt.derived_semantic_fingerprint
        == membership.canonical_semantic_fingerprint
    )


def issue_projection_receipt(
    source_claim_digests: frozenset[str],
    memberships: tuple[SemanticClassMembershipV1, ...],
    *,
    store: TrustedPreservationStore,
) -> SemanticProjectionReceiptV1:
    for digest in source_claim_digests:
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError("SOURCE_CLAIM_DIGEST_INVALID")

    if len({item.claim_digest for item in memberships}) != len(memberships):
        raise ValueError("DUPLICATE_MEMBERSHIP_CLAIM")

    membership_map = {item.claim_digest: item for item in memberships}
    if set(membership_map) != set(source_claim_digests):
        raise ValueError("PROJECTION_COVERAGE_MISMATCH")

    class_fingerprints: dict[str, str] = {}
    for item in memberships:
        if not verify_membership(item, store=store):
            raise ValueError(
                f"UNVERIFIED_SEMANTIC_MEMBERSHIP:{item.claim_digest}"
            )
        prior = class_fingerprints.get(item.canonical_claim_digest)
        if (
            prior is not None
            and prior != item.canonical_semantic_fingerprint
        ):
            raise ValueError("CANONICAL_CLASS_FINGERPRINT_MISMATCH")
        class_fingerprints[
            item.canonical_claim_digest
        ] = item.canonical_semantic_fingerprint

    ordered_memberships = tuple(
        sorted(
            memberships,
            key=lambda item: (
                item.claim_digest,
                item.canonical_claim_digest,
            ),
        )
    )
    semantic_class_ids = tuple(
        sorted(
            {
                item.semantic_class_id
                for item in ordered_memberships
            }
        )
    )
    return SemanticProjectionReceiptV1(
        source_claim_digests=tuple(sorted(source_claim_digests)),
        memberships=ordered_memberships,
        semantic_class_ids=semantic_class_ids,
    )


@dataclass(frozen=True)
class SemanticQuotientStateV1:
    semantic_class_ids: frozenset[str]
    authority: AuthorityLevel
    uncertainty_bps: int
    projection_receipt_sha256: str

    def __post_init__(self) -> None:
        if not self.semantic_class_ids:
            # Empty consensus/state is allowed only through projection; individual
            # projected states should still carry their provenance root.
            pass
        if SHA256_RE.fullmatch(self.projection_receipt_sha256) is None:
            raise ValueError("PROJECTION_RECEIPT_DIGEST_INVALID")
        if (
            isinstance(self.uncertainty_bps, bool)
            or not isinstance(self.uncertainty_bps, int)
            or not 0 <= self.uncertainty_bps <= 10000
        ):
            raise ValueError("UNCERTAINTY_BPS_INVALID")


def project_state(
    raw: EpistemicStateV1,
    receipt: SemanticProjectionReceiptV1,
) -> SemanticQuotientStateV1:
    if set(receipt.source_claim_digests) != set(raw.claims):
        raise ValueError("PROJECTION_SOURCE_STATE_MISMATCH")
    return SemanticQuotientStateV1(
        semantic_class_ids=frozenset(receipt.semantic_class_ids),
        authority=raw.authority,
        uncertainty_bps=raw.uncertainty_bps,
        projection_receipt_sha256=receipt.receipt_sha256,
    )


@dataclass(frozen=True)
class SemanticConsensusV1:
    semantic_class_ids: frozenset[str]
    authority: AuthorityLevel
    uncertainty_bps: int
    left_projection_receipt_sha256: str
    right_projection_receipt_sha256: str
    authority_effect: str = NO_AUTHORITY


def semantic_quotient_consensus(
    left: SemanticQuotientStateV1,
    right: SemanticQuotientStateV1,
) -> SemanticConsensusV1:
    return SemanticConsensusV1(
        semantic_class_ids=(
            left.semantic_class_ids & right.semantic_class_ids
        ),
        authority=AuthorityLevel(
            min(int(left.authority), int(right.authority))
        ),
        uncertainty_bps=max(
            left.uncertainty_bps,
            right.uncertainty_bps,
        ),
        left_projection_receipt_sha256=left.projection_receipt_sha256,
        right_projection_receipt_sha256=right.projection_receipt_sha256,
    )
