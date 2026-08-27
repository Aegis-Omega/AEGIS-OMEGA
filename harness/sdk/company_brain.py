"""AEGIS Company Brain v1.

Policy-bound front door from an operator/company objective into the existing
MetacognitiveExecutive. This module is deliberately not a scheduler and not an
authority root. It narrows company policy into one GoalEnvelope, executes the
existing bounded executive, and emits an evidence-only receipt.

Raw objective text is never copied into the receipt; only a domain-separated
digest crosses the execution/evidence boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from harness.sdk.metacognitive_executive import (
    GoalEnvelopeV1,
    MetacognitiveExecutive,
    MetacognitiveExecutiveOutcomeV1,
)
from harness.sdk.sovereign_execution import canonical_hash

CONSEQUENCE_ORDER = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4}


class CompanyBrainError(ValueError):
    """Fail-closed Company Brain error with stable machine-readable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CompanyPolicyV1:
    policy_id: str
    policy_commitment: str
    allowed_capabilities: tuple[str, ...]
    allowed_providers: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    max_cost_microunits: int
    max_tokens: int
    max_steps: int
    consequence_ceiling: str


@dataclass(frozen=True)
class CompanyGoalRequestV1:
    goal_id: str
    objective: str
    source_commit: str
    authority_epoch: int
    pre_state_root: str
    requested_capabilities: tuple[str, ...]
    requested_providers: tuple[str, ...]
    requested_tools: tuple[str, ...]
    max_cost_microunits: int
    max_tokens: int
    max_steps: int
    consequence_ceiling: str
    deterministic_nonce: str


@dataclass(frozen=True)
class CompanyBrainReceiptV1:
    receipt_kind: Literal["COMPANY_BRAIN_RUN_RECEIPT_V1"]
    goal_id: str
    objective_digest: str
    policy_commitment: str
    status: Literal["DONE", "WAITING_OPERATOR", "HALTED"]
    executive_status: Literal["COMPLETE", "ESCALATE", "HALT"]
    operator_attention_required: bool
    total_cost_microunits: int
    total_tokens: int
    autonomy_mode: str
    executive_receipt_digest: str
    trace_bundle_root: str
    authority: Literal["EVIDENCE_ONLY"]
    receipt_digest: str


@dataclass(frozen=True)
class CompanyBrainOutcomeV1:
    receipt: CompanyBrainReceiptV1
    executive_outcome: MetacognitiveExecutiveOutcomeV1


class CompanyBrain:
    """Narrow company policy into a bounded metacognitive execution.

    The Company Brain may only contract the operator-provided policy envelope.
    It cannot add providers, tools, capabilities, budget, steps or consequence
    authority. D4 is structurally unavailable.
    """

    def __init__(self, policy: CompanyPolicyV1, executive: MetacognitiveExecutive) -> None:
        self._validate_policy(policy)
        self._policy = policy
        self._executive = executive

    @property
    def policy(self) -> CompanyPolicyV1:
        return self._policy

    def run(self, request: CompanyGoalRequestV1) -> CompanyBrainOutcomeV1:
        self._validate_request(request)

        objective_digest = canonical_hash(
            "AEGIS_COMPANY_OBJECTIVE_V1",
            {"goal_id": request.goal_id, "objective": request.objective},
        )

        goal = GoalEnvelopeV1(
            goal_id=request.goal_id,
            objective_digest=objective_digest,
            source_commit=request.source_commit,
            policy_commitment=self._policy.policy_commitment,
            authority_epoch=request.authority_epoch,
            pre_state_root=request.pre_state_root,
            allowed_capabilities=request.requested_capabilities,
            allowed_providers=request.requested_providers,
            allowed_tools=request.requested_tools,
            max_cost_microunits=request.max_cost_microunits,
            max_tokens=request.max_tokens,
            max_steps=request.max_steps,
            consequence_ceiling=request.consequence_ceiling,
            deterministic_nonce=request.deterministic_nonce,
        )

        executive_outcome = self._executive.run(goal)
        executive_receipt = executive_outcome.receipt

        if executive_receipt.status == "COMPLETE":
            status = "DONE"
            operator_attention_required = False
        elif executive_receipt.status == "ESCALATE":
            status = "WAITING_OPERATOR"
            operator_attention_required = True
        else:
            status = "HALTED"
            operator_attention_required = False

        body = {
            "receipt_kind": "COMPANY_BRAIN_RUN_RECEIPT_V1",
            "goal_id": request.goal_id,
            "objective_digest": objective_digest,
            "policy_commitment": self._policy.policy_commitment,
            "status": status,
            "executive_status": executive_receipt.status,
            "operator_attention_required": operator_attention_required,
            "total_cost_microunits": executive_receipt.total_cost_microunits,
            "total_tokens": executive_receipt.total_tokens,
            "autonomy_mode": executive_receipt.autonomy_mode,
            "executive_receipt_digest": executive_receipt.receipt_digest,
            "trace_bundle_root": executive_receipt.trace_bundle_root,
            "authority": "EVIDENCE_ONLY",
        }
        receipt_digest = canonical_hash("AEGIS_COMPANY_BRAIN_RUN_RECEIPT_V1", body)

        receipt = CompanyBrainReceiptV1(
            receipt_kind="COMPANY_BRAIN_RUN_RECEIPT_V1",
            goal_id=request.goal_id,
            objective_digest=objective_digest,
            policy_commitment=self._policy.policy_commitment,
            status=status,  # type: ignore[arg-type]
            executive_status=executive_receipt.status,
            operator_attention_required=operator_attention_required,
            total_cost_microunits=executive_receipt.total_cost_microunits,
            total_tokens=executive_receipt.total_tokens,
            autonomy_mode=executive_receipt.autonomy_mode,
            executive_receipt_digest=executive_receipt.receipt_digest,
            trace_bundle_root=executive_receipt.trace_bundle_root,
            authority="EVIDENCE_ONLY",
            receipt_digest=receipt_digest,
        )
        return CompanyBrainOutcomeV1(receipt=receipt, executive_outcome=executive_outcome)

    @staticmethod
    def _validate_policy(policy: CompanyPolicyV1) -> None:
        if not policy.policy_id:
            raise CompanyBrainError("POLICY_ID_REQUIRED")
        if policy.consequence_ceiling not in CONSEQUENCE_ORDER:
            raise CompanyBrainError("POLICY_CONSEQUENCE_CEILING_UNSUPPORTED")
        if policy.consequence_ceiling == "D4":
            raise CompanyBrainError("POLICY_D4_FORBIDDEN")
        if not policy.allowed_capabilities:
            raise CompanyBrainError("POLICY_CAPABILITIES_EMPTY")
        if not policy.allowed_providers:
            raise CompanyBrainError("POLICY_PROVIDERS_EMPTY")
        if not policy.allowed_tools:
            raise CompanyBrainError("POLICY_TOOLS_EMPTY")
        for name, values in (
            ("POLICY_CAPABILITIES_DUPLICATE", policy.allowed_capabilities),
            ("POLICY_PROVIDERS_DUPLICATE", policy.allowed_providers),
            ("POLICY_TOOLS_DUPLICATE", policy.allowed_tools),
        ):
            if len(set(values)) != len(values):
                raise CompanyBrainError(name)
        if isinstance(policy.max_cost_microunits, bool) or policy.max_cost_microunits < 0:
            raise CompanyBrainError("POLICY_COST_BUDGET_INVALID")
        if isinstance(policy.max_tokens, bool) or policy.max_tokens < 0:
            raise CompanyBrainError("POLICY_TOKEN_BUDGET_INVALID")
        if isinstance(policy.max_steps, bool) or policy.max_steps < 1:
            raise CompanyBrainError("POLICY_STEP_BUDGET_INVALID")

    def _validate_request(self, request: CompanyGoalRequestV1) -> None:
        if not request.goal_id:
            raise CompanyBrainError("GOAL_ID_REQUIRED")
        if not isinstance(request.objective, str) or not request.objective.strip():
            raise CompanyBrainError("OBJECTIVE_REQUIRED")
        if not request.requested_capabilities:
            raise CompanyBrainError("REQUEST_CAPABILITIES_EMPTY")
        if not request.requested_providers:
            raise CompanyBrainError("REQUEST_PROVIDERS_EMPTY")
        if not request.requested_tools:
            raise CompanyBrainError("REQUEST_TOOLS_EMPTY")

        if any(value not in self._policy.allowed_capabilities for value in request.requested_capabilities):
            raise CompanyBrainError("REQUEST_CAPABILITY_NOT_ALLOWED")
        if any(value not in self._policy.allowed_providers for value in request.requested_providers):
            raise CompanyBrainError("REQUEST_PROVIDER_NOT_ALLOWED")
        if any(value not in self._policy.allowed_tools for value in request.requested_tools):
            raise CompanyBrainError("REQUEST_TOOL_NOT_ALLOWED")

        if request.max_cost_microunits > self._policy.max_cost_microunits:
            raise CompanyBrainError("REQUEST_COST_BUDGET_EXCEEDED")
        if request.max_tokens > self._policy.max_tokens:
            raise CompanyBrainError("REQUEST_TOKEN_BUDGET_EXCEEDED")
        if request.max_steps > self._policy.max_steps:
            raise CompanyBrainError("REQUEST_STEP_BUDGET_EXCEEDED")

        if request.consequence_ceiling not in CONSEQUENCE_ORDER:
            raise CompanyBrainError("REQUEST_CONSEQUENCE_CEILING_UNSUPPORTED")
        if request.consequence_ceiling == "D4" or (
            CONSEQUENCE_ORDER[request.consequence_ceiling]
            > CONSEQUENCE_ORDER[self._policy.consequence_ceiling]
        ):
            raise CompanyBrainError("REQUEST_CONSEQUENCE_CEILING_EXCEEDED")
