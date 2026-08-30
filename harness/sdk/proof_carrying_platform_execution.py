"""One proof-carrying start-execution vertical slice over the live platform API."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from harness.sdk.authority_client import authorize_from_environment
from harness.sdk.complete_verifier import TRUE, CompleteVerificationResult, CompleteVerifier
from harness.sdk.effect_adapters import EffectAdapterError, EffectWitness
from harness.sdk.effect_verifier import EffectVerificationResult, EffectVerifier
from harness.sdk.platform_effect_adapter import (
    PlatformArtifactProvenance,
    PlatformExecutionEffectAdapter,
    request_platform_json,
)
from harness.sdk.sovereign_execution import canonical_hash
from harness.sdk.transition_receipts import (
    EXECUTION_RECEIPT_KIND,
    EXECUTION_SUCCEEDED,
    PERMIT,
    DecisionReceipt,
    EffectReceipt,
    ExecutionReceipt,
    TransitionIdentity,
)


class ProofCarryingPlatformExecutionError(ValueError):
    """Fail-closed live-transition failure."""

    def __init__(
        self,
        message: str,
        *,
        external_effect: str = "UNKNOWN",
        denial_codes: tuple[str, ...] = (),
        authority_outcome: str = "DENIED",
        decision_receipt_root: str | None = None,
    ) -> None:
        super().__init__(message)
        self.external_effect = external_effect
        self.denial_codes = denial_codes
        self.authority_outcome = authority_outcome
        self.decision_receipt_root = decision_receipt_root


def derive_platform_execution_id(*, action_digest: str, deterministic_nonce: str) -> str:
    digest = canonical_hash(
        "AEGIS_PLATFORM_EXECUTION_INSTANCE_V1",
        {"action_digest": action_digest, "deterministic_nonce": deterministic_nonce},
    )
    return f"aegis-{digest[:32]}"


@dataclass(frozen=True)
class PlatformDispatchResult:
    execution_id: str
    status_code: int
    result_digest: str


class PlatformExecutionDispatcher:
    """Write-only platform client; it does not observe or certify effects."""

    def __init__(self, *, bridge_url: str, api_key: str, timeout_seconds: float = 10.0):
        self.bridge_url = bridge_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def start_execution(
        self,
        *,
        execution_id: str,
        action: Mapping[str, Any],
        source_commit: str,
        contract_version: str,
    ) -> PlatformDispatchResult:
        response = request_platform_json(
            bridge_url=self.bridge_url,
            api_key=self.api_key,
            method="POST",
            path="/platform/executions",
            body={**action, "execution_id": execution_id},
            timeout_seconds=self.timeout_seconds,
        )
        data = response.payload.get("data")
        if (
            response.status_code != 202
            or response.git_sha != source_commit
            or response.contract_version != contract_version
            or response.payload.get("execution_id") != execution_id
            or response.payload.get("contract_version") != response.contract_version
            or not isinstance(data, dict)
            or data.get("execution_id") != execution_id
            or data.get("status") != "pending"
        ):
            raise ProofCarryingPlatformExecutionError("PLATFORM_EXECUTION_DISPATCH_NOT_ACCEPTED")
        return PlatformDispatchResult(
            execution_id=execution_id,
            status_code=response.status_code,
            result_digest=canonical_hash(
                "AEGIS_PLATFORM_EXECUTION_DISPATCH_RESULT_V1",
                {
                    "execution_id": execution_id,
                    "http_status": response.status_code,
                    "response_digest": response.body_digest,
                    "contract_version": response.contract_version,
                    "git_sha": response.git_sha,
                },
            ),
        )


@dataclass(frozen=True)
class ProofCarryingPlatformExecution:
    transition: TransitionIdentity
    decision_receipt: DecisionReceipt
    execution_receipt: ExecutionReceipt
    effect_witness: EffectWitness
    effect_verification: EffectVerificationResult
    effect_receipt: EffectReceipt
    complete_verification: CompleteVerificationResult
    platform_artifact_provenance: PlatformArtifactProvenance

    def as_dict(self) -> dict[str, Any]:
        return {
            "transition": asdict(self.transition),
            "transition_id": self.transition.root,
            "decision_receipt": asdict(self.decision_receipt),
            "decision_receipt_root": self.decision_receipt.root,
            "execution_receipt": asdict(self.execution_receipt),
            "execution_receipt_root": self.execution_receipt.root,
            "effect_witness": asdict(self.effect_witness),
            "effect_witness_digest": self.effect_witness.root,
            "effect_verification": asdict(self.effect_verification),
            "effect_verification_root": self.effect_verification.root,
            "effect_receipt": asdict(self.effect_receipt),
            "effect_receipt_root": self.effect_receipt.root,
            "complete_verification": asdict(self.complete_verification),
            "complete_verification_root": self.complete_verification.root,
            "platform_artifact_provenance": asdict(self.platform_artifact_provenance),
            "admission": "UNAVAILABLE",
        }


def execute_verified_platform_start(
    *,
    transition: TransitionIdentity,
    decision_receipt: DecisionReceipt,
    action: Mapping[str, Any],
    dispatcher: PlatformExecutionDispatcher,
    effect_adapter: PlatformExecutionEffectAdapter,
) -> ProofCarryingPlatformExecution:
    """Execute only after PERMIT, then independently prove the execution record exists."""
    try:
        transition.validate()
        decision_receipt.validate()
    except (TypeError, ValueError) as exc:
        raise ProofCarryingPlatformExecutionError(
            "PLATFORM_EXECUTION_INPUT_RECEIPT_INVALID",
            external_effect="NOT_EXECUTED",
        ) from exc
    if decision_receipt.transition_id != transition.root or decision_receipt.decision_outcome != PERMIT:
        raise ProofCarryingPlatformExecutionError(
            "PLATFORM_EXECUTION_DECISION_NOT_PERMIT",
            external_effect="NOT_EXECUTED",
        )
    action_digest = canonical_hash("AEGIS_REQUESTED_ACTION_V1", action)
    if action_digest != transition.action_digest:
        raise ProofCarryingPlatformExecutionError(
            "PLATFORM_EXECUTION_ACTION_BINDING_MISMATCH",
            external_effect="NOT_EXECUTED",
            authority_outcome="ADMITTED",
            decision_receipt_root=decision_receipt.root,
        )
    execution_id = derive_platform_execution_id(
        action_digest=action_digest,
        deterministic_nonce=transition.deterministic_nonce,
    )
    try:
        handle = effect_adapter.prepare_observation(transition=transition, execution_id=execution_id)
        platform_artifact_provenance = effect_adapter.artifact_provenance(handle=handle)
    except EffectAdapterError as exc:
        raise ProofCarryingPlatformExecutionError(
            f"PLATFORM_EXECUTION_PRE_OBSERVATION_FAILED:{exc}",
            external_effect="NOT_EXECUTED",
            denial_codes=(str(exc),),
            authority_outcome="ADMITTED",
            decision_receipt_root=decision_receipt.root,
        ) from exc
    try:
        dispatch = dispatcher.start_execution(
            execution_id=execution_id,
            action=action,
            source_commit=transition.source_commit,
            contract_version=platform_artifact_provenance.contract_version,
        )
    except Exception as exc:
        detail = str(exc) if isinstance(exc, (EffectAdapterError, ProofCarryingPlatformExecutionError)) else type(exc).__name__
        raise ProofCarryingPlatformExecutionError(
            f"PLATFORM_EXECUTION_DISPATCH_UNVERIFIED:{detail}",
            external_effect="UNKNOWN",
            denial_codes=(detail,),
            authority_outcome="ADMITTED",
            decision_receipt_root=decision_receipt.root,
        ) from exc
    execution_receipt = ExecutionReceipt(
        receipt_kind=EXECUTION_RECEIPT_KIND,
        transition_id=transition.root,
        execution_instance_id=execution_id,
        outcome=EXECUTION_SUCCEEDED,
        result_digest=dispatch.result_digest,
    )
    try:
        effect_witness = effect_adapter.observe_effect(
            transition=transition,
            handle=handle,
            execution_receipt=execution_receipt,
        )
        effect_verifier = EffectVerifier()
        effect_verification = effect_verifier.verify_effect(
            transition=transition,
            execution_receipt=execution_receipt,
            witness=effect_witness,
        )
        if effect_verification.status != TRUE:
            raise ProofCarryingPlatformExecutionError(
                "PLATFORM_EFFECT_VERIFICATION_NOT_TRUE",
                authority_outcome="ADMITTED",
                decision_receipt_root=decision_receipt.root,
            )
        effect_receipt = effect_verifier.issue_effect_receipt(
            transition=transition,
            execution_receipt=execution_receipt,
            witness=effect_witness,
            verification=effect_verification,
        )
        complete_verification = CompleteVerifier().verify_complete(
            transition=transition,
            decision_receipt=decision_receipt,
            execution_receipt=execution_receipt,
            effect_witness=effect_witness,
            effect_verification=effect_verification,
            effect_receipt=effect_receipt,
        )
        if complete_verification.status != TRUE:
            raise ProofCarryingPlatformExecutionError(
                "PLATFORM_COMPLETE_VERIFICATION_NOT_TRUE",
                authority_outcome="ADMITTED",
                decision_receipt_root=decision_receipt.root,
            )
    except ProofCarryingPlatformExecutionError:
        raise
    except Exception as exc:
        detail = str(exc) if isinstance(exc, EffectAdapterError) else type(exc).__name__
        raise ProofCarryingPlatformExecutionError(
            f"PLATFORM_EXECUTION_POST_DISPATCH_UNVERIFIED:{detail}",
            external_effect="UNKNOWN",
            denial_codes=(detail,),
            authority_outcome="ADMITTED",
            decision_receipt_root=decision_receipt.root,
        ) from exc
    return ProofCarryingPlatformExecution(
        transition=transition,
        decision_receipt=decision_receipt,
        execution_receipt=execution_receipt,
        effect_witness=effect_witness,
        effect_verification=effect_verification,
        effect_receipt=effect_receipt,
        complete_verification=complete_verification,
        platform_artifact_provenance=platform_artifact_provenance,
    )


def execute_platform_start_from_environment(
    *,
    action: Mapping[str, Any],
    bridge_url: str,
    api_key: str,
    current_generation: int = 0,
) -> ProofCarryingPlatformExecution:
    """Compose the live Automaton-3 decision with the verified platform effect path."""
    action_value = dict(action)
    try:
        authority = authorize_from_environment(
            action_class="D2",
            authority_domain="workflow:durable",
            requested_capability="mcp.execution.start",
            tool="aegis_start_execution",
            target="/platform/executions",
            action=action_value,
            current_generation=current_generation,
        )
    except Exception as exc:
        raise ProofCarryingPlatformExecutionError(
            "PLATFORM_AUTHORITY_EVALUATION_ERROR",
            external_effect="NOT_EXECUTED",
            denial_codes=("AUTHORITY_EVALUATION_ERROR",),
        ) from exc
    if authority.get("outcome") != "ADMITTED":
        denial_codes = tuple(str(code) for code in authority.get("denial_codes", ["AUTHORITY_DENIED"]))
        raise ProofCarryingPlatformExecutionError(
            f"PLATFORM_EXECUTION_AUTHORITY_DENIED:{','.join(denial_codes)}",
            external_effect="NOT_EXECUTED",
            denial_codes=denial_codes,
        )
    try:
        transition = TransitionIdentity(**authority["transition"])
        decision_receipt = DecisionReceipt(**authority["decision_receipt"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ProofCarryingPlatformExecutionError(
            "PLATFORM_AUTHORITY_RECEIPT_INVALID",
            external_effect="NOT_EXECUTED",
            denial_codes=("AUTHORITY_RECEIPT_INVALID",),
        ) from exc
    return execute_verified_platform_start(
        transition=transition,
        decision_receipt=decision_receipt,
        action=action_value,
        dispatcher=PlatformExecutionDispatcher(bridge_url=bridge_url, api_key=api_key),
        effect_adapter=PlatformExecutionEffectAdapter(bridge_url=bridge_url, api_key=api_key),
    )
