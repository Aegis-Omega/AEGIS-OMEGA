"""PR-3 effect verifier and verifier-gated EffectReceipt producer.

This module verifies the integrity and binding of EffectEvidence relative to the
version-bound PR-3 policy. It does not establish ontological causality,
CompleteVerification, AtomicAdmission, or EffectBoundAdmission.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from harness.sdk.effect_adapters import EffectAdapterError, EffectWitness, FilesystemEffectAdapter, is_adapter_bound_effect_evidence
from harness.sdk.sovereign_execution import ZERO_HASH, canonical_hash
from harness.sdk.transition_receipts import (
    EFFECT_RECEIPT_KIND,
    EffectReceipt,
    ExecutionReceipt,
    TransitionIdentity,
    TransitionReceiptError,
    verifier_policy_commitment,
)

TRUE = "TRUE"
FALSE = "FALSE"
UNKNOWN = "UNKNOWN"
ERROR = "ERROR"
MISSING = "MISSING"
VERIFY_STATUSES = (TRUE, FALSE, UNKNOWN, ERROR, MISSING)
EFFECT_VERIFICATION_RESULT_KIND = "EFFECT_VERIFICATION_RESULT_V1"

OBLIGATION_ORDER = (
    "V_effect_evidence",
    "V_transition_binding",
    "V_execution_binding",
    "V_prestate_binding",
    "V_adapter_binding",
    "V_verifier_policy_binding",
)


class EffectVerificationError(ValueError):
    """Raised when a verified-effect receipt cannot be issued safely."""


@dataclass(frozen=True)
class EffectVerificationResult:
    result_kind: str
    status: str
    transition_id: str
    execution_instance_id: str
    effect_witness_digest: str
    verifier_policy_commitment: str
    obligations: tuple[tuple[str, str], ...]
    denial_code: str

    def validate(self) -> None:
        if self.result_kind != EFFECT_VERIFICATION_RESULT_KIND:
            raise EffectVerificationError("EFFECT_VERIFICATION_RESULT_KIND_MISMATCH")
        if self.status not in VERIFY_STATUSES:
            raise EffectVerificationError("EFFECT_VERIFICATION_STATUS_INVALID")
        if not isinstance(self.transition_id, str) or len(self.transition_id) != 64:
            raise EffectVerificationError("EFFECT_VERIFICATION_TRANSITION_INVALID")
        if not isinstance(self.effect_witness_digest, str) or len(self.effect_witness_digest) != 64:
            raise EffectVerificationError("EFFECT_VERIFICATION_WITNESS_DIGEST_INVALID")
        if not isinstance(self.verifier_policy_commitment, str) or len(self.verifier_policy_commitment) != 64:
            raise EffectVerificationError("EFFECT_VERIFICATION_POLICY_COMMITMENT_INVALID")
        if not isinstance(self.execution_instance_id, str) or not self.execution_instance_id:
            raise EffectVerificationError("EFFECT_VERIFICATION_EXECUTION_INSTANCE_INVALID")
        if tuple(name for name, _ in self.obligations) != OBLIGATION_ORDER:
            raise EffectVerificationError("EFFECT_VERIFICATION_OBLIGATION_SET_INVALID")
        if any(status not in VERIFY_STATUSES for _, status in self.obligations):
            raise EffectVerificationError("EFFECT_VERIFICATION_OBLIGATION_STATUS_INVALID")
        if not isinstance(self.denial_code, str) or not self.denial_code:
            raise EffectVerificationError("EFFECT_VERIFICATION_DENIAL_CODE_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_EFFECT_VERIFICATION_RESULT_V1", asdict(self))


class EffectVerifier:
    """Reference VerifyEffect gate for the PR-3 filesystem observation surface."""

    supported_adapters = {(FilesystemEffectAdapter.identity, FilesystemEffectAdapter.version)}

    @staticmethod
    def _obligations(default: str = MISSING) -> dict[str, str]:
        return {name: default for name in OBLIGATION_ORDER}

    @staticmethod
    def _result(
        *,
        status: str,
        transition_id: str,
        execution_instance_id: str,
        witness_digest: str,
        policy_commitment: str,
        obligations: dict[str, str],
        denial_code: str,
    ) -> EffectVerificationResult:
        result = EffectVerificationResult(
            result_kind=EFFECT_VERIFICATION_RESULT_KIND,
            status=status,
            transition_id=transition_id,
            execution_instance_id=execution_instance_id,
            effect_witness_digest=witness_digest,
            verifier_policy_commitment=policy_commitment,
            obligations=tuple((name, obligations[name]) for name in OBLIGATION_ORDER),
            denial_code=denial_code,
        )
        result.validate()
        return result

    def verify_effect(
        self,
        *,
        transition: TransitionIdentity,
        execution_receipt: ExecutionReceipt,
        witness: EffectWitness | None,
    ) -> EffectVerificationResult:
        policy_commitment = verifier_policy_commitment()
        obligations = self._obligations()
        try:
            transition.validate()
            execution_receipt.validate()
            transition_id = transition.root
            execution_instance_id = execution_receipt.execution_instance_id
        except Exception:
            return self._result(
                status=ERROR,
                transition_id=ZERO_HASH,
                execution_instance_id="unresolved-execution",
                witness_digest=ZERO_HASH,
                policy_commitment=policy_commitment,
                obligations=obligations,
                denial_code="EFFECT_VERIFICATION_INPUT_ERROR",
            )

        obligations["V_verifier_policy_binding"] = (
            TRUE if transition.verifier_policy_commitment == policy_commitment else FALSE
        )

        if witness is None:
            obligations["V_effect_evidence"] = MISSING
            return self._result(
                status=MISSING,
                transition_id=transition_id,
                execution_instance_id=execution_instance_id,
                witness_digest=ZERO_HASH,
                policy_commitment=policy_commitment,
                obligations=obligations,
                denial_code="EFFECT_EVIDENCE_MISSING",
            )

        try:
            witness.validate()
            witness_digest = witness.root
        except (EffectAdapterError, ValueError, TypeError, AttributeError):
            obligations["V_effect_evidence"] = FALSE
            return self._result(
                status=FALSE,
                transition_id=transition_id,
                execution_instance_id=execution_instance_id,
                witness_digest=ZERO_HASH,
                policy_commitment=policy_commitment,
                obligations=obligations,
                denial_code="EFFECT_EVIDENCE_INVALID",
            )
        except Exception:
            obligations["V_effect_evidence"] = ERROR
            return self._result(
                status=ERROR,
                transition_id=transition_id,
                execution_instance_id=execution_instance_id,
                witness_digest=ZERO_HASH,
                policy_commitment=policy_commitment,
                obligations=obligations,
                denial_code="EFFECT_VERIFICATION_INTERNAL_ERROR",
            )

        obligations["V_transition_binding"] = (
            TRUE
            if witness.transition_id == transition_id and execution_receipt.transition_id == transition_id
            else FALSE
        )
        obligations["V_execution_binding"] = (
            TRUE if witness.execution_instance_id == execution_instance_id else FALSE
        )
        obligations["V_prestate_binding"] = (
            TRUE if witness.observed_pre_state_commitment == transition.pre_state_commitment else FALSE
        )

        adapter_key = (witness.adapter_identity, witness.adapter_version)
        adapter_supported = adapter_key in self.supported_adapters
        obligations["V_adapter_binding"] = TRUE if adapter_supported else UNKNOWN
        if adapter_supported:
            obligations["V_effect_evidence"] = (
                TRUE if is_adapter_bound_effect_evidence(witness=witness) else FALSE
            )
        else:
            obligations["V_effect_evidence"] = UNKNOWN

        if any(obligations[name] == FALSE for name in OBLIGATION_ORDER):
            return self._result(
                status=FALSE,
                transition_id=transition_id,
                execution_instance_id=execution_instance_id,
                witness_digest=witness_digest,
                policy_commitment=policy_commitment,
                obligations=obligations,
                denial_code="EFFECT_VERIFICATION_CONTRADICTED",
            )
        if any(obligations[name] in (UNKNOWN, MISSING) for name in OBLIGATION_ORDER):
            return self._result(
                status=UNKNOWN,
                transition_id=transition_id,
                execution_instance_id=execution_instance_id,
                witness_digest=witness_digest,
                policy_commitment=policy_commitment,
                obligations=obligations,
                denial_code="EFFECT_VERIFICATION_UNRESOLVABLE",
            )
        if any(obligations[name] == ERROR for name in OBLIGATION_ORDER):
            return self._result(
                status=ERROR,
                transition_id=transition_id,
                execution_instance_id=execution_instance_id,
                witness_digest=witness_digest,
                policy_commitment=policy_commitment,
                obligations=obligations,
                denial_code="EFFECT_VERIFICATION_INTERNAL_ERROR",
            )

        return self._result(
            status=TRUE,
            transition_id=transition_id,
            execution_instance_id=execution_instance_id,
            witness_digest=witness_digest,
            policy_commitment=policy_commitment,
            obligations=obligations,
            denial_code="NONE",
        )

    def issue_effect_receipt(
        self,
        *,
        transition: TransitionIdentity,
        execution_receipt: ExecutionReceipt,
        witness: EffectWitness | None,
        verification: EffectVerificationResult,
    ) -> EffectReceipt:
        if verification.status != TRUE:
            raise EffectVerificationError("EFFECT_VERIFICATION_NOT_TRUE")
        if witness is None:
            raise EffectVerificationError("EFFECT_EVIDENCE_MISSING")

        recomputed = self.verify_effect(
            transition=transition,
            execution_receipt=execution_receipt,
            witness=witness,
        )
        if recomputed.status != TRUE or recomputed.root != verification.root:
            raise EffectVerificationError("EFFECT_VERIFICATION_RECOMPUTE_MISMATCH")

        receipt = object.__new__(EffectReceipt)
        fields: dict[str, Any] = {
            "receipt_kind": EFFECT_RECEIPT_KIND,
            "transition_id": transition.root,
            "execution_instance_id": execution_receipt.execution_instance_id,
            "effect_witness_digest": witness.root,
            "effect_verification_root": verification.root,
            "verifier_policy_commitment": verification.verifier_policy_commitment,
            "pre_state_commitment": witness.observed_pre_state_commitment,
            "post_state_commitment": witness.observed_post_state_commitment,
            "observation_provenance": canonical_hash(
                "AEGIS_EFFECT_OBSERVATION_BUNDLE_V1",
                {
                    "pre": witness.pre_observation_provenance,
                    "post": witness.post_observation_provenance,
                },
            ),
            "adapter_identity": witness.adapter_identity,
            "adapter_version": witness.adapter_version,
        }
        for name, value in fields.items():
            object.__setattr__(receipt, name, value)
        try:
            receipt.validate()
        except TransitionReceiptError as exc:
            raise EffectVerificationError("EFFECT_RECEIPT_CONSTRUCTION_INVALID") from exc
        return receipt
