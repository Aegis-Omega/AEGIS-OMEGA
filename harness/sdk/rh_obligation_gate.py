"""Executable fail-closed obligation ledger for the RH proofline.

The gate is intentionally unable to infer mathematical closure from numerical,
empirical, CI, or prose evidence. Only obligations carrying a verifier-issued
formal proof receipt can enter ``FORMALLY_VERIFIED`` and count toward the final
verdict.

This module is an authority-boundary API, not a proof assistant. Syntactic
receipt validation and an in-process verifier seal prevent naked programmatic
state promotion; they do not replace checking the referenced proof artifact in
its proof kernel or validating the external exact-head provenance chain.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


class ObligationState(str, Enum):
    OPEN = "OPEN"
    BLOCKED = "BLOCKED"
    PARTIALLY_FORMALIZED = "PARTIALLY_FORMALIZED"
    FORMALLY_VERIFIED = "FORMALLY_VERIFIED"
    REFUTED = "REFUTED"


_FORMAL_RECEIPT_SEAL = object()


@dataclass(frozen=True)
class ProofKernelReceiptV1:
    """Untrusted proof-kernel receipt payload presented to the RH gate."""

    exact_head: str
    source_sha256: str
    kind: str = "PROOF_KERNEL_RECEIPT_V1"
    axiom_free: bool = True
    closed_under_global_context: bool = True

    def validate(self) -> None:
        if self.kind != "PROOF_KERNEL_RECEIPT_V1":
            raise ValueError("invalid proof receipt kind")
        if self.axiom_free is not True:
            raise ValueError("formal receipt is not axiom-free")
        if self.closed_under_global_context is not True:
            raise ValueError("formal receipt is not globally closed")
        if not isinstance(self.exact_head, str) or re.fullmatch(r"[0-9a-f]{40}", self.exact_head) is None:
            raise ValueError("invalid exact_head in formal receipt")
        if not isinstance(self.source_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", self.source_sha256) is None:
            raise ValueError("invalid source_sha256 in formal receipt")


@dataclass(frozen=True, init=False)
class VerifiedFormalReceiptV1:
    """Receipt accepted by the local verifier boundary.

    ``init=False`` deliberately prevents ordinary caller construction through
    the public dataclass constructor. Instances are issued only by
    :func:`verify_proof_kernel_receipt` and carry a process-local seal checked
    again whenever a ledger is constructed.
    """

    exact_head: str
    source_sha256: str
    kind: str
    axiom_free: bool
    closed_under_global_context: bool
    _seal: object = field(repr=False, compare=False)

    def validate(self) -> None:
        try:
            sealed = self._seal is _FORMAL_RECEIPT_SEAL
            raw = ProofKernelReceiptV1(
                exact_head=self.exact_head,
                source_sha256=self.source_sha256,
                kind=self.kind,
                axiom_free=self.axiom_free,
                closed_under_global_context=self.closed_under_global_context,
            )
        except AttributeError as exc:
            raise ValueError("verified formal receipt is not verifier-issued") from exc
        if not sealed:
            raise ValueError("verified formal receipt is not verifier-issued")
        raw.validate()


def verify_proof_kernel_receipt(receipt: ProofKernelReceiptV1) -> VerifiedFormalReceiptV1:
    """Validate an untrusted receipt and issue a sealed formal-receipt token."""

    if not isinstance(receipt, ProofKernelReceiptV1):
        raise TypeError("receipt must be ProofKernelReceiptV1")
    receipt.validate()
    verified = object.__new__(VerifiedFormalReceiptV1)
    object.__setattr__(verified, "exact_head", receipt.exact_head)
    object.__setattr__(verified, "source_sha256", receipt.source_sha256)
    object.__setattr__(verified, "kind", receipt.kind)
    object.__setattr__(verified, "axiom_free", receipt.axiom_free)
    object.__setattr__(verified, "closed_under_global_context", receipt.closed_under_global_context)
    object.__setattr__(verified, "_seal", _FORMAL_RECEIPT_SEAL)
    verified.validate()
    return verified


@dataclass(frozen=True)
class Obligation:
    obligation_id: str
    state: ObligationState
    depends_on: tuple[str, ...] = ()
    authority_note: str = ""
    formal_receipt: VerifiedFormalReceiptV1 | None = None


DEFAULT_OBLIGATIONS: tuple[Obligation, ...] = (
    Obligation("W0_XiFormulation", ObligationState.PARTIALLY_FORMALIZED,
               authority_note="Xi/Weil setup exists, but final concrete criterion closure is not machine-bound."),
    Obligation("W1_FinitePrimePhaseBoundary", ObligationState.BLOCKED,
               depends_on=("W0_XiFormulation",),
               authority_note="Reflection/index-set boundary requires an explicit term-wise or boundary-corrected theorem."),
    Obligation("W2_ConstructiveTrigCalculus", ObligationState.OPEN,
               depends_on=("W0_XiFormulation",),
               authority_note="Prime-diagonal constructive trig/calculus witness remains open."),
    Obligation("W3_ArchimedeanSingularity", ObligationState.PARTIALLY_FORMALIZED,
               depends_on=("W0_XiFormulation",),
               authority_note="Analytic removable-singularity reasoning is not promoted here to proof-kernel closure."),
    Obligation("W4_GaussianTailTheorem", ObligationState.OPEN,
               depends_on=("W0_XiFormulation",),
               authority_note="QForm constant arithmetic exists; the real-analysis theorem remains open."),
    Obligation("W5_CompositeTrapezoidTheorem", ObligationState.OPEN,
               depends_on=("W0_XiFormulation",),
               authority_note="Composite-trapezoid remainder theorem remains open in the authority lane."),
    Obligation("W6_GuinandWeilOperatorIdentity", ObligationState.OPEN,
               depends_on=("W1_FinitePrimePhaseBoundary", "W2_ConstructiveTrigCalculus", "W3_ArchimedeanSingularity"),
               authority_note="Concrete formula-to-Weil operator identity is not machine-bound."),
    Obligation("W7_ContinuousArchimedeanOrder", ObligationState.OPEN,
               depends_on=("W3_ArchimedeanSingularity",),
               authority_note="Finite exact Gram PSD does not establish the continuous representation/order theorem."),
    Obligation("W8_DensityContinuityCoverage", ObligationState.OPEN,
               depends_on=("W4_GaussianTailTheorem", "W5_CompositeTrapezoidTheorem", "W6_GuinandWeilOperatorIdentity", "W7_ContinuousArchimedeanOrder"),
               authority_note="Density, continuity, approximation, and universal coverage remain load-bearing."),
    Obligation("W9_ConcreteWeilCriterion", ObligationState.OPEN,
               depends_on=("W8_DensityContinuityCoverage",),
               authority_note="Global positivity for the actual Weil form and the concrete criterion are not machine-bound."),
    Obligation("W10_FinalRiemannHypothesis", ObligationState.BLOCKED,
               depends_on=("W9_ConcreteWeilCriterion",),
               authority_note="Final RH theorem is blocked until every dependency is formally verified."),
)


class RHObligationLedger:
    def __init__(self, obligations: tuple[Obligation, ...] = DEFAULT_OBLIGATIONS):
        self._obligations = {o.obligation_id: o for o in obligations}
        if len(self._obligations) != len(obligations):
            raise ValueError("duplicate obligation_id")
        self._validate_dependencies()
        self._validate_formal_authority()

    @property
    def obligations(self) -> Mapping[str, Obligation]:
        return dict(self._obligations)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "RHObligationLedger":
        """Load a machine-readable ledger without trusting its claimed verdict."""
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("schema_version") != "1.0.0":
            raise ValueError("unsupported RH obligation ledger schema")
        rows = payload.get("proof_obligations")
        if not isinstance(rows, list) or not rows:
            raise ValueError("proof_obligations must be a non-empty list")

        obligations: list[Obligation] = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("obligation row must be an object")
            obligation_id = row.get("id")
            if not isinstance(obligation_id, str) or not obligation_id:
                raise ValueError("obligation id must be a non-empty string")
            try:
                state = ObligationState(row.get("status"))
            except ValueError as exc:
                raise ValueError(f"invalid state for {obligation_id}") from exc
            depends_on = row.get("depends_on", [])
            if not isinstance(depends_on, list) or not all(isinstance(dep, str) and dep for dep in depends_on):
                raise ValueError(f"invalid depends_on for {obligation_id}")
            authority_note = row.get("authority_note", "")
            if not isinstance(authority_note, str) or not authority_note.strip():
                raise ValueError(f"authority_note required for {obligation_id}")
            formal_receipt = None
            if state is ObligationState.FORMALLY_VERIFIED:
                formal_receipt = cls._verify_formal_receipt_payload(
                    obligation_id,
                    row.get("proof_receipt"),
                )
            obligations.append(
                Obligation(
                    obligation_id,
                    state,
                    tuple(depends_on),
                    authority_note,
                    formal_receipt,
                )
            )
        return cls(tuple(obligations))

    @staticmethod
    def _verify_formal_receipt_payload(
        obligation_id: str,
        receipt: Any,
    ) -> VerifiedFormalReceiptV1:
        if not isinstance(receipt, dict):
            raise ValueError(f"FORMALLY_VERIFIED {obligation_id} requires proof_receipt")
        raw = ProofKernelReceiptV1(
            exact_head=receipt.get("exact_head"),
            source_sha256=receipt.get("source_sha256"),
            kind=receipt.get("kind"),
            axiom_free=receipt.get("axiom_free"),
            closed_under_global_context=receipt.get("closed_under_global_context"),
        )
        try:
            return verify_proof_kernel_receipt(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid proof receipt for {obligation_id}: {exc}") from exc

    def _validate_dependencies(self) -> None:
        ids = set(self._obligations)
        for obligation in self._obligations.values():
            missing = set(obligation.depends_on) - ids
            if missing:
                raise ValueError(f"{obligation.obligation_id} has unknown dependencies: {sorted(missing)}")

    def _validate_formal_authority(self) -> None:
        for obligation in self._obligations.values():
            if obligation.state is ObligationState.FORMALLY_VERIFIED:
                if not isinstance(obligation.formal_receipt, VerifiedFormalReceiptV1):
                    raise ValueError(
                        f"FORMALLY_VERIFIED {obligation.obligation_id} requires verified formal receipt"
                    )
                try:
                    obligation.formal_receipt.validate()
                except ValueError as exc:
                    raise ValueError(
                        f"FORMALLY_VERIFIED {obligation.obligation_id} requires verified formal receipt"
                    ) from exc
            elif obligation.formal_receipt is not None:
                raise ValueError(
                    f"non-formal obligation {obligation.obligation_id} cannot carry verified formal receipt"
                )

    def with_state(
        self,
        obligation_id: str,
        state: ObligationState,
        authority_note: str,
        *,
        formal_receipt: VerifiedFormalReceiptV1 | None = None,
    ) -> "RHObligationLedger":
        if obligation_id not in self._obligations:
            raise KeyError(obligation_id)
        if not isinstance(state, ObligationState):
            raise TypeError("state must be ObligationState")
        if not authority_note.strip():
            raise ValueError("authority_note is required for every state transition")
        if state is ObligationState.FORMALLY_VERIFIED:
            if not isinstance(formal_receipt, VerifiedFormalReceiptV1):
                raise ValueError("FORMALLY_VERIFIED transition requires verified formal receipt")
            formal_receipt.validate()
        elif formal_receipt is not None:
            raise ValueError("formal_receipt is only valid for FORMALLY_VERIFIED transitions")

        updated: list[Obligation] = []
        for obligation in self._obligations.values():
            if obligation.obligation_id == obligation_id:
                updated.append(
                    Obligation(
                        obligation_id,
                        state,
                        obligation.depends_on,
                        authority_note,
                        formal_receipt,
                    )
                )
            else:
                updated.append(obligation)
        return RHObligationLedger(tuple(updated))

    def verify_final_closure(self) -> dict[str, Any]:
        unresolved = [
            o.obligation_id
            for o in self._obligations.values()
            if o.state is not ObligationState.FORMALLY_VERIFIED
        ]
        dependency_violations = []
        for obligation in self._obligations.values():
            if obligation.state is ObligationState.FORMALLY_VERIFIED:
                open_dependencies = [
                    dep for dep in obligation.depends_on
                    if self._obligations[dep].state is not ObligationState.FORMALLY_VERIFIED
                ]
                if open_dependencies:
                    dependency_violations.append({
                        "obligation": obligation.obligation_id,
                        "unverified_dependencies": open_dependencies,
                    })

        if unresolved or dependency_violations:
            return {
                "verdict": "RH_NOT_PROVEN",
                "gate_status": "FAIL_CLOSED",
                "open_obligations": unresolved,
                "dependency_violations": dependency_violations,
                "highest_leverage_blocker": unresolved[0] if unresolved else None,
            }

        return {
            "verdict": "RH_PROVEN_FORMALLY",
            "gate_status": "ADMITTED",
            "open_obligations": [],
            "dependency_violations": [],
            "highest_leverage_blocker": None,
        }


__all__ = [
    "DEFAULT_OBLIGATIONS",
    "Obligation",
    "ObligationState",
    "ProofKernelReceiptV1",
    "RHObligationLedger",
    "VerifiedFormalReceiptV1",
    "verify_proof_kernel_receipt",
]
