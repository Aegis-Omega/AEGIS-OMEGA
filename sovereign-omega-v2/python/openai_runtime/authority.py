from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .types import ActionClass, AuthorityDecision, OmegaRunRequest, RuntimeErrorCode


_ACTION_ORDER = {
    ActionClass.D0: 0,
    ActionClass.D1: 1,
    ActionClass.D2: 2,
    ActionClass.D3: 3,
    ActionClass.D4: 4,
}


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    name: str
    required_capability: str
    max_action_class: ActionClass
    requires_approval: bool = False
    approval_id: str | None = None
    mutates: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("tool policy name must not be blank")
        if not self.required_capability.strip():
            raise ValueError("tool policy required_capability must not be blank")
        if self.requires_approval and not (self.approval_id or "").strip():
            raise ValueError("approval_id is required when requires_approval is true")


class AuthorityGate:
    """Pure, deterministic pre-model authority evaluator.

    The gate does not call a model, network, filesystem, or external service. It only
    evaluates declared capabilities/tools against an already-resolved AEGIS authority
    snapshot. A denial is terminal for this run and must never be interpreted as a
    provider-fallback condition.
    """

    def __init__(
        self,
        *,
        registered_capabilities: set[str],
        active_grants: set[str],
        registered_tools: Mapping[str, ToolPolicy],
        approvals: set[str],
        max_action_class: ActionClass = ActionClass.D4,
    ) -> None:
        self._registered_capabilities = frozenset(registered_capabilities)
        self._active_grants = frozenset(active_grants)
        self._registered_tools = dict(registered_tools)
        self._approvals = frozenset(approvals)
        self._max_action_class = max_action_class

    @staticmethod
    def _deny(code: RuntimeErrorCode, reason: str) -> AuthorityDecision:
        return AuthorityDecision(admitted=False, code=code, reason=reason)

    def evaluate(self, request: OmegaRunRequest) -> AuthorityDecision:
        if _ACTION_ORDER[request.action_class] > _ACTION_ORDER[self._max_action_class]:
            return self._deny(
                RuntimeErrorCode.ACTION_CLASS_EXCEEDED,
                f"request action class exceeds execution ceiling: {self._max_action_class.value}",
            )

        requested_capabilities = frozenset(request.allowed_capabilities)

        for capability in request.allowed_capabilities:
            if capability not in self._registered_capabilities:
                return self._deny(
                    RuntimeErrorCode.UNKNOWN_CAPABILITY,
                    f"capability is not registered: {capability}",
                )
            if capability not in self._active_grants:
                return self._deny(
                    RuntimeErrorCode.CAPABILITY_NOT_GRANTED,
                    f"capability has no active grant: {capability}",
                )

        for tool_name in request.allowed_tools:
            policy = self._registered_tools.get(tool_name)
            if policy is None:
                return self._deny(
                    RuntimeErrorCode.TOOL_NOT_REGISTERED,
                    f"tool is not registered: {tool_name}",
                )

            if policy.required_capability not in requested_capabilities:
                return self._deny(
                    RuntimeErrorCode.TOOL_NOT_ALLOWED,
                    f"tool capability was not declared by the request: {tool_name}",
                )

            if policy.required_capability not in self._active_grants:
                return self._deny(
                    RuntimeErrorCode.CAPABILITY_NOT_GRANTED,
                    f"tool capability has no active grant: {policy.required_capability}",
                )

            if _ACTION_ORDER[request.action_class] > _ACTION_ORDER[policy.max_action_class]:
                return self._deny(
                    RuntimeErrorCode.ACTION_CLASS_EXCEEDED,
                    f"request action class exceeds tool ceiling: {tool_name}",
                )

            if policy.requires_approval and policy.approval_id not in self._approvals:
                return self._deny(
                    RuntimeErrorCode.APPROVAL_REQUIRED,
                    f"explicit approval required for tool: {tool_name}",
                )

        return AuthorityDecision(admitted=True, reason="authority preflight admitted")
