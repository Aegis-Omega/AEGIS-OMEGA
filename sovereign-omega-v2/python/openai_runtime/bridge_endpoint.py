from __future__ import annotations

from typing import Any, Callable, Mapping

from pydantic import ValidationError

from .authority import AuthorityGate
from .config import OpenAIRuntimeConfig, RuntimeConfigError
from .runtime import OpenAIRuntime
from .types import ActionClass, OmegaRunRequest, RunStatus, RuntimeErrorCode


_REGISTERED_CAPABILITIES = frozenset({
    "research-synthesis",
    "adversarial-verification",
    "implementation-proposal",
})

_TIER_GRANTS: dict[str, frozenset[str]] = {
    "explorer": frozenset({"research-synthesis"}),
    "operator": frozenset({"research-synthesis", "adversarial-verification"}),
    "sovereign": _REGISTERED_CAPABILITIES,
}


def _error(code: RuntimeErrorCode, *, status: str = "FAILED") -> dict[str, Any]:
    return {
        "status": status,
        "error_code": code.value,
        "is_replay_reconstructable": True,
    }


def handle_omega_run(
    *,
    data: Any,
    api_key: str,
    verify_api_key: Callable[[str], tuple[str, str]],
    env: Mapping[str, str],
    runner: Any | None = None,
) -> tuple[int, dict[str, Any]]:
    """Pure-ish HTTP adapter for POST /v1/omega/run.

    Authentication and local policy resolution happen before SDK/model invocation.
    Caller-supplied approvals are never treated as server authority in v1.
    """
    try:
        caller_email, caller_tier = verify_api_key(api_key)
    except ValueError:
        return 401, _error(RuntimeErrorCode.UNAUTHORIZED)

    try:
        request = OmegaRunRequest.model_validate(data)
    except (ValidationError, TypeError, ValueError):
        return 400, _error(RuntimeErrorCode.INVALID_REQUEST)

    try:
        config = OpenAIRuntimeConfig.from_env(env)
    except RuntimeConfigError as exc:
        return 503, _error(exc.code)

    active_grants = set(_TIER_GRANTS.get(caller_tier, frozenset()))
    gate = AuthorityGate(
        registered_capabilities=set(_REGISTERED_CAPABILITIES),
        active_grants=active_grants,
        registered_tools={},
        approvals=set(),
        max_action_class=ActionClass.D0,
    )

    result = OpenAIRuntime(config).run(
        request,
        gate=gate,
        caller_email=caller_email,
        caller_tier=caller_tier,
        runner=runner,
    )
    body = result.model_dump(mode="json")
    if result.status == RunStatus.SUCCEEDED:
        return 200, body
    if result.status == RunStatus.DENIED:
        return 403, body
    if result.error_code in {
        RuntimeErrorCode.RUNTIME_DISABLED,
        RuntimeErrorCode.API_KEY_MISSING,
        RuntimeErrorCode.MODEL_MISSING,
        RuntimeErrorCode.INVALID_CONFIG,
        RuntimeErrorCode.SDK_UNAVAILABLE,
    }:
        return 503, body
    return 502, body
