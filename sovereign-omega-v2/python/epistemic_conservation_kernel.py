"""AEGIS Ω — Epistemic Conservation Kernel V1.

Combines authority conservation with MHP-style semantic accounting.
The kernel emits an evidence-only content-addressed receipt. It never executes a
rewrite and never grants operational authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import re
from typing import Protocol

from epistemic_accounting import (
    AccountingEnvelopeV1,
    AccountingMode,
    composed_uncertainty_bps,
    verify_accounting,
)
from epistemic_authority_conservation import (
    AuthorityLevel,
    TransitionGateV1,
    conservation_certificate,
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


def _accounting_material(envelope: AccountingEnvelopeV1) -> dict[str, object]:
    return {
        "source_claims": sorted(envelope.source_claims),
        "target_claims": sorted(envelope.target_claims),
        "preserved_source": sorted(envelope.preserved_source),
        "preserved_target": sorted(envelope.preserved_target),
        "omissions": sorted(envelope.omissions),
        "additions": sorted(envelope.additions),
        "addition_receipts": sorted(
            [list(item) for item in envelope.addition_receipts]
        ),
        "relation": envelope.relation.value,
        "uncertainty_bps": envelope.uncertainty_bps,
    }


@dataclass(frozen=True)
class ConservationRequestV1:
    parent_state_sha256: str
    semantic_lineage_receipt_sha256: str
    initial_authority: AuthorityLevel
    authority_gates: tuple[TransitionGateV1, ...]
    accounting_envelope: AccountingEnvelopeV1
    accounting_mode: AccountingMode
    left_uncertainty_bps: int | None = None
    right_uncertainty_bps: int | None = None

    def __post_init__(self) -> None:
        for value, label in (
            (self.parent_state_sha256, "parent_state_sha256"),
            (
                self.semantic_lineage_receipt_sha256,
                "semantic_lineage_receipt_sha256",
            ),
        ):
            if SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{label}: invalid digest")
        if self.accounting_mode == AccountingMode.TRANSITIVE_V1:
            if self.left_uncertainty_bps is None or self.right_uncertainty_bps is None:
                raise ValueError("TRANSITIVE_UNCERTAINTY_PREDECESSORS_REQUIRED")


@dataclass(frozen=True)
class EpistemicConservationReceiptV1:
    parent_state_sha256: str
    semantic_lineage_receipt_sha256: str
    authority_final: str
    authority_global_meet: str
    authority_non_amplifying: bool
    semantic_accounting_pass: bool
    uncertainty_accounting_pass: bool
    reason_codes: tuple[str, ...]
    decision: str
    authority_effect: str = NO_AUTHORITY
    schema: str = "AEGIS_EPISTEMIC_CONSERVATION_RECEIPT_V1"
    receipt_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.decision not in {PASS, DENY}:
            raise ValueError("INVALID_CONSERVATION_DECISION")
        if self.authority_effect != NO_AUTHORITY:
            raise ValueError("CONSERVATION_AUTHORITY_LEAK")
        for value, label in (
            (self.parent_state_sha256, "parent_state_sha256"),
            (
                self.semantic_lineage_receipt_sha256,
                "semantic_lineage_receipt_sha256",
            ),
        ):
            if SHA256_RE.fullmatch(value) is None:
                raise ValueError(f"{label}: invalid digest")
        material = asdict(self)
        material.pop("receipt_sha256", None)
        object.__setattr__(
            self,
            "receipt_sha256",
            _canonical_hash("AEGIS_EPISTEMIC_CONSERVATION_RECEIPT_V1", material),
        )


class TrustedEpistemicConservationStore(Protocol):
    def fetch_verified(
        self, receipt_sha256: str
    ) -> EpistemicConservationReceiptV1 | None: ...


def evaluate_conservation(
    request: ConservationRequestV1,
) -> EpistemicConservationReceiptV1:
    reasons: list[str] = []

    authority = conservation_certificate(
        request.initial_authority,
        request.authority_gates,
    )
    if authority["non_amplifying"] is not True:
        reasons.append("AUTHORITY_AMPLIFICATION")
    if authority["equals_global_meet"] is not True:
        reasons.append("AUTHORITY_MEET_MISMATCH")

    accounting = verify_accounting(
        request.accounting_envelope,
        mode=request.accounting_mode,
    )
    accounting_pass = accounting["decision"] == PASS
    if not accounting_pass:
        reasons.extend(
            f"ACCOUNTING:{code}" for code in accounting["reason_codes"]
        )

    uncertainty_pass = True
    if request.accounting_mode == AccountingMode.TRANSITIVE_V1:
        expected = composed_uncertainty_bps(
            has_composite_source_loss=bool(request.accounting_envelope.omissions),
            left_uncertainty_bps=request.left_uncertainty_bps,
            right_uncertainty_bps=request.right_uncertainty_bps,
        )
        uncertainty_pass = (
            request.accounting_envelope.uncertainty_bps == expected
        )
        if not uncertainty_pass:
            reasons.append("UNCERTAINTY_COMPOSITION_MISMATCH")

    return EpistemicConservationReceiptV1(
        parent_state_sha256=request.parent_state_sha256,
        semantic_lineage_receipt_sha256=request.semantic_lineage_receipt_sha256,
        authority_final=str(authority["final"]),
        authority_global_meet=str(authority["global_meet"]),
        authority_non_amplifying=bool(authority["non_amplifying"]),
        semantic_accounting_pass=accounting_pass,
        uncertainty_accounting_pass=uncertainty_pass,
        reason_codes=tuple(sorted(set(reasons))),
        decision=PASS if not reasons else DENY,
    )


def trusted_receipt(
    store: TrustedEpistemicConservationStore,
    receipt_sha256: str,
) -> EpistemicConservationReceiptV1 | None:
    if SHA256_RE.fullmatch(receipt_sha256) is None:
        return None
    receipt = store.fetch_verified(receipt_sha256)
    if receipt is None:
        return None
    if receipt.receipt_sha256 != receipt_sha256:
        return None
    if receipt.decision != PASS:
        return None
    if receipt.authority_effect != NO_AUTHORITY:
        return None
    return receipt
