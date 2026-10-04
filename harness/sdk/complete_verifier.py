"""PR-4 CompleteVerification gate over the exact PR-3 effect lineage.

CompleteVerification is a verifier artifact for one exact transition bundle. It is
not CausalClaimAdmission, AtomicAdmission, EffectBoundAdmission, production
admission, or an AGI claim.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from harness.sdk.effect_adapters import EffectWitness, is_adapter_bound_effect_evidence
from harness.sdk.effect_verifier import EffectVerificationResult, EffectVerifier
from harness.sdk.sovereign_execution import ZERO_HASH, canonical_hash
from harness.sdk.transition_receipts import (
    PERMIT,
    DecisionReceipt,
    EffectReceipt,
    ExecutionReceipt,
    TransitionIdentity,
    admission_policy_commitment,
    verifier_policy_commitment,
)

TRUE = "TRUE"
FALSE = "FALSE"
UNKNOWN = "UNKNOWN"
ERROR = "ERROR"
MISSING = "MISSING"
VERIFY_STATUSES = (TRUE, FALSE, UNKNOWN, ERROR, MISSING)
COMPLETE_VERIFICATION_RESULT_KIND = "COMPLETE_VERIFICATION_RESULT_V1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

OBLIGATION_ORDER = (
    "V_transition_identity",
    "V_decision_receipt",
    "V_decision_authority",
    "V_decision_binding",
    "V_execution_receipt",
    "V_execution_binding",
    "V_effect_evidence",
    "V_effect_verification",
    "V_effect_receipt",
    "V_effect_binding",
    "V_effect_verification_binding",
    "V_verifier_policy_binding",
    "V_admission_policy_binding",
)

PR4_COMPLETE_VERIFIER_POLICY = {
    "policy_id": "AEGIS_PR4_COMPLETE_VERIFIER_POLICY_V1",
    "safe_incompleteness": True,
    "required_inputs": [
        "TransitionIdentity",
        "DecisionReceipt",
        "ExecutionReceipt",
        "EffectWitness",
        "EffectVerificationResult",
        "EffectReceipt",
    ],
    "required_obligations": list(OBLIGATION_ORDER),
    "effect_verification_recompute": "REQUIRED",
    "effect_receipt_source": "PR3_VERIFIER_GATED_ONLY",
    "causal_claim_admission": "NOT_IMPLEMENTED",
    "atomic_admission": "UNAVAILABLE",
    "effect_bound_admission": "UNAVAILABLE",
    "production_admission": "NOT_ESTABLISHED",
}


class CompleteVerificationError(ValueError):
    """Raised only when a CompleteVerification result cannot be represented safely."""


def complete_verifier_policy_commitment() -> str:
    return canonical_hash(
        "AEGIS_COMPLETE_VERIFIER_POLICY_COMMITMENT_V1",
        PR4_COMPLETE_VERIFIER_POLICY,
    )


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise CompleteVerificationError(f"{name}:INVALID_SHA256")


@dataclass(frozen=True)
class CompleteVerificationResult:
    result_kind: str
    status: str
    transition_id: str
    decision_receipt_root: str
    execution_receipt_root: str
    effect_witness_digest: str
    effect_verification_root: str
    effect_receipt_root: str
    complete_verifier_policy_commitment: str
    obligations: tuple[tuple[str, str], ...]
    denial_code: str

    def validate(self) -> None:
        if self.result_kind != COMPLETE_VERIFICATION_RESULT_KIND:
            raise CompleteVerificationError("COMPLETE_VERIFICATION_RESULT_KIND_MISMATCH")
        if self.status not in VERIFY_STATUSES:
            raise CompleteVerificationError("COMPLETE_VERIFICATION_STATUS_INVALID")
        for name in (
            "transition_id",
            "decision_receipt_root",
            "execution_receipt_root",
            "effect_witness_digest",
            "effect_verification_root",
            "effect_receipt_root",
            "complete_verifier_policy_commitment",
        ):
            _require_hash(name, getattr(self, name))
        if tuple(name for name, _ in self.obligations) != OBLIGATION_ORDER:
            raise CompleteVerificationError("COMPLETE_VERIFICATION_OBLIGATION_SET_INVALID")
        if any(status not in VERIFY_STATUSES for _, status in self.obligations):
            raise CompleteVerificationError("COMPLETE_VERIFICATION_OBLIGATION_STATUS_INVALID")
        if not isinstance(self.denial_code, str) or not self.denial_code:
            raise CompleteVerificationError("COMPLETE_VERIFICATION_DENIAL_CODE_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_COMPLETE_VERIFICATION_RESULT_V1", asdict(self))


class CompleteVerifier:
    """Fail-closed PR-4 verifier for one exact decision/execution/effect bundle."""

    @staticmethod
    def _obligations(default: str = MISSING) -> dict[str, str]:
        return {name: default for name in OBLIGATION_ORDER}

    @staticmethod
    def _safe_root(value: Any, expected_type: type[Any]) -> str:
        if type(value) is not expected_type:
            return ZERO_HASH
        try:
            value.validate()
            return value.root
        except Exception:
            return ZERO_HASH

    @staticmethod
    def _result(
        *,
        status: str,
        transition: Any,
        decision_receipt: Any,
        execution_receipt: Any,
        effect_witness: Any,
        effect_verification: Any,
        effect_receipt: Any,
        obligations: dict[str, str],
        denial_code: str,
    ) -> CompleteVerificationResult:
        result = CompleteVerificationResult(
            result_kind=COMPLETE_VERIFICATION_RESULT_KIND,
            status=status,
            transition_id=CompleteVerifier._safe_root(transition, TransitionIdentity),
            decision_receipt_root=CompleteVerifier._safe_root(decision_receipt, DecisionReceipt),
            execution_receipt_root=CompleteVerifier._safe_root(execution_receipt, ExecutionReceipt),
            effect_witness_digest=CompleteVerifier._safe_root(effect_witness, EffectWitness),
            effect_verification_root=CompleteVerifier._safe_root(effect_verification, EffectVerificationResult),
            effect_receipt_root=CompleteVerifier._safe_root(effect_receipt, EffectReceipt),
            complete_verifier_policy_commitment=complete_verifier_policy_commitment(),
            obligations=tuple((name, obligations[name]) for name in OBLIGATION_ORDER),
            denial_code=denial_code,
        )
        result.validate()
        return result

    @staticmethod
    def _status_and_code(obligations: dict[str, str]) -> tuple[str, str]:
        if all(obligations[name] == TRUE for name in OBLIGATION_ORDER):
            return TRUE, "NONE"
        if obligations["V_decision_authority"] == FALSE:
            return FALSE, "COMPLETE_VERIFICATION_DECISION_NOT_PERMIT"
        if obligations["V_decision_binding"] == FALSE:
            return FALSE, "COMPLETE_VERIFICATION_TRANSITION_MISMATCH"
        if obligations["V_execution_binding"] == FALSE:
            return FALSE, "COMPLETE_VERIFICATION_TRANSITION_MISMATCH"
        if obligations["V_effect_evidence"] == FALSE:
            return FALSE, "COMPLETE_VERIFICATION_EFFECT_EVIDENCE_MISMATCH"
        if obligations["V_effect_binding"] == FALSE:
            return FALSE, "COMPLETE_VERIFICATION_EFFECT_RECEIPT_MISMATCH"
        if obligations["V_effect_verification_binding"] == FALSE:
            return FALSE, "COMPLETE_VERIFICATION_EFFECT_VERIFICATION_MISMATCH"
        if obligations["V_verifier_policy_binding"] == FALSE or obligations["V_admission_policy_binding"] == FALSE:
            return FALSE, "COMPLETE_VERIFICATION_POLICY_MISMATCH"
        if any(obligations[name] == FALSE for name in OBLIGATION_ORDER):
            return FALSE, "COMPLETE_VERIFICATION_CONTRADICTED"
        if any(obligations[name] == ERROR for name in OBLIGATION_ORDER):
            return ERROR, "COMPLETE_VERIFICATION_INTERNAL_ERROR"
        if any(obligations[name] == MISSING for name in OBLIGATION_ORDER):
            return MISSING, "COMPLETE_VERIFICATION_MISSING_ARTIFACT"
        return UNKNOWN, "COMPLETE_VERIFICATION_UNRESOLVABLE"

    def verify_complete(
        self,
        *,
        transition: TransitionIdentity,
        decision_receipt: DecisionReceipt | None,
        execution_receipt: ExecutionReceipt | None,
        effect_witness: EffectWitness | None,
        effect_verification: EffectVerificationResult | None,
        effect_receipt: EffectReceipt | None,
    ) -> CompleteVerificationResult:
        obligations = self._obligations()
        inputs = (
            transition,
            decision_receipt,
            execution_receipt,
            effect_witness,
            effect_verification,
            effect_receipt,
        )
        if any(value is None for value in inputs):
            return self._result(
                status=MISSING,
                transition=transition,
                decision_receipt=decision_receipt,
                execution_receipt=execution_receipt,
                effect_witness=effect_witness,
                effect_verification=effect_verification,
                effect_receipt=effect_receipt,
                obligations=obligations,
                denial_code="COMPLETE_VERIFICATION_MISSING_ARTIFACT",
            )

        expected_types = (
            TransitionIdentity,
            DecisionReceipt,
            ExecutionReceipt,
            EffectWitness,
            EffectVerificationResult,
            EffectReceipt,
        )
        if any(type(value) is not expected for value, expected in zip(inputs, expected_types)):
            obligations = self._obligations(FALSE)
            return self._result(
                status=FALSE,
                transition=transition,
                decision_receipt=decision_receipt,
                execution_receipt=execution_receipt,
                effect_witness=effect_witness,
                effect_verification=effect_verification,
                effect_receipt=effect_receipt,
                obligations=obligations,
                denial_code="COMPLETE_VERIFICATION_INPUT_ERROR",
            )

        assert decision_receipt is not None
        assert execution_receipt is not None
        assert effect_witness is not None
        assert effect_verification is not None
        assert effect_receipt is not None

        try:
            transition.validate()
            transition_id = transition.root
            obligations["V_transition_identity"] = TRUE
        except Exception:
            obligations["V_transition_identity"] = FALSE
            return self._result(
                status=FALSE,
                transition=transition,
                decision_receipt=decision_receipt,
                execution_receipt=execution_receipt,
                effect_witness=effect_witness,
                effect_verification=effect_verification,
                effect_receipt=effect_receipt,
                obligations=obligations,
                denial_code="COMPLETE_VERIFICATION_INPUT_ERROR",
            )

        try:
            decision_receipt.validate()
            decision_receipt.root
            obligations["V_decision_receipt"] = TRUE
        except Exception:
            obligations["V_decision_receipt"] = FALSE

        obligations["V_decision_authority"] = TRUE if decision_receipt.decision_outcome == PERMIT else FALSE
        obligations["V_decision_binding"] = TRUE if decision_receipt.transition_id == transition_id else FALSE

        try:
            execution_receipt.validate()
            execution_receipt.root
            obligations["V_execution_receipt"] = TRUE
        except Exception:
            obligations["V_execution_receipt"] = FALSE
        obligations["V_execution_binding"] = TRUE if execution_receipt.transition_id == transition_id else FALSE

        try:
            effect_witness.validate()
            witness_adapter_bound = is_adapter_bound_effect_evidence(witness=effect_witness)
            witness_bound = (
                effect_witness.transition_id == transition_id
                and effect_witness.execution_instance_id == execution_receipt.execution_instance_id
                and effect_witness.observed_pre_state_commitment == transition.pre_state_commitment
            )
            obligations["V_effect_evidence"] = TRUE if witness_adapter_bound and witness_bound else FALSE
        except Exception:
            obligations["V_effect_evidence"] = FALSE

        try:
            effect_verification.validate()
            obligations["V_effect_verification"] = effect_verification.status
        except Exception:
            obligations["V_effect_verification"] = FALSE

        try:
            effect_receipt.validate()
            effect_receipt.root
            obligations["V_effect_receipt"] = TRUE
        except Exception:
            obligations["V_effect_receipt"] = FALSE

        try:
            expected_observation_provenance = canonical_hash(
                "AEGIS_EFFECT_OBSERVATION_BUNDLE_V1",
                {
                    "pre": effect_witness.pre_observation_provenance,
                    "post": effect_witness.post_observation_provenance,
                },
            )
            effect_binding = (
                effect_receipt.transition_id == transition_id
                and effect_receipt.execution_instance_id == execution_receipt.execution_instance_id
                and effect_receipt.effect_witness_digest == effect_witness.root
                and effect_receipt.pre_state_commitment == transition.pre_state_commitment
                and effect_receipt.post_state_commitment == effect_witness.observed_post_state_commitment
                and effect_receipt.observation_provenance == expected_observation_provenance
                and effect_receipt.adapter_identity == effect_witness.adapter_identity
                and effect_receipt.adapter_version == effect_witness.adapter_version
            )
            obligations["V_effect_binding"] = TRUE if effect_binding else FALSE
        except Exception:
            obligations["V_effect_binding"] = FALSE

        recomputed = None
        try:
            recomputed = EffectVerifier().verify_effect(
                transition=transition,
                execution_receipt=execution_receipt,
                witness=effect_witness,
            )
            if recomputed.status == TRUE:
                verification_binding = (
                    effect_verification.status == TRUE
                    and recomputed.root == effect_verification.root
                    and effect_receipt.effect_verification_root == effect_verification.root
                )
                obligations["V_effect_verification_binding"] = TRUE if verification_binding else FALSE
            elif recomputed.status in VERIFY_STATUSES:
                obligations["V_effect_verification_binding"] = recomputed.status
            else:
                obligations["V_effect_verification_binding"] = ERROR
        except Exception:
            obligations["V_effect_verification_binding"] = ERROR

        try:
            active_effect_policy = verifier_policy_commitment()
            policy_bound = (
                transition.verifier_policy_commitment == active_effect_policy
                and effect_verification.verifier_policy_commitment == active_effect_policy
                and effect_receipt.verifier_policy_commitment == active_effect_policy
                and recomputed is not None
                and recomputed.verifier_policy_commitment == active_effect_policy
            )
            obligations["V_verifier_policy_binding"] = TRUE if policy_bound else FALSE
        except Exception:
            obligations["V_verifier_policy_binding"] = ERROR

        try:
            obligations["V_admission_policy_binding"] = (
                TRUE
                if transition.admission_policy_commitment == admission_policy_commitment()
                else FALSE
            )
        except Exception:
            obligations["V_admission_policy_binding"] = ERROR

        status, denial_code = self._status_and_code(obligations)
        return self._result(
            status=status,
            transition=transition,
            decision_receipt=decision_receipt,
            execution_receipt=execution_receipt,
            effect_witness=effect_witness,
            effect_verification=effect_verification,
            effect_receipt=effect_receipt,
            obligations=obligations,
            denial_code=denial_code,
        )
