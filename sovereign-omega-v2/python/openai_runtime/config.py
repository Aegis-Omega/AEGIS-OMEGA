from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .types import RuntimeErrorCode


class RuntimeConfigError(ValueError):
    def __init__(self, code: RuntimeErrorCode, message: str):
        super().__init__(message)
        self.code = code


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name, str(default)).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeConfigError(RuntimeErrorCode.INVALID_CONFIG, f"{name} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeConfigError(RuntimeErrorCode.INVALID_CONFIG, f"{name} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class OpenAIRuntimeConfig:
    api_key: str
    model: str
    max_turns: int = 12
    max_tool_concurrency: int = 2
    trace_sensitive_data: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "OpenAIRuntimeConfig":
        if env.get("AEGIS_OPENAI_RUNTIME_ENABLED", "").strip().lower() != "true":
            raise RuntimeConfigError(RuntimeErrorCode.RUNTIME_DISABLED, "OpenAI runtime is disabled")

        api_key = env.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeConfigError(RuntimeErrorCode.API_KEY_MISSING, "OPENAI_API_KEY is required")

        model = env.get("OPENAI_PRIMARY_MODEL", "").strip()
        if not model:
            raise RuntimeConfigError(RuntimeErrorCode.MODEL_MISSING, "OPENAI_PRIMARY_MODEL is required")

        max_turns = _positive_int(env, "AEGIS_OPENAI_MAX_TURNS", 12)
        max_tool_concurrency = _positive_int(env, "AEGIS_OPENAI_MAX_TOOL_CONCURRENCY", 2)
        trace_sensitive_data = env.get("AEGIS_OPENAI_TRACE_SENSITIVE_DATA", "false").strip().lower() == "true"

        return cls(
            api_key=api_key,
            model=model,
            max_turns=max_turns,
            max_tool_concurrency=max_tool_concurrency,
            trace_sensitive_data=trace_sensitive_data,
        )
