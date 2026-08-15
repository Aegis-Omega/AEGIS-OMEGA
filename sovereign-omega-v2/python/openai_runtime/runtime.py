from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from .agents import AgentsSDKUnavailable, build_omega_manager, build_specialists
from .authority import AuthorityGate
from .config import OpenAIRuntimeConfig
from .types import (
    OmegaManagerOutput,
    OmegaRunContext,
    OmegaRunRequest,
    OmegaRunResult,
    RunStatus,
    RuntimeErrorCode,
    ToolCallRecord,
)


@dataclass(frozen=True, slots=True)
class SDKRunObservation:
    final_output: Any
    trace_id: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    usage: dict[str, int] | None = None


class AgentsSDKRunnerAdapter:
    """Thin boundary around OpenAI Agents SDK so the runtime stays testable offline."""

    WORKFLOW_NAME = "AEGIS Omega Runtime v1"

    def run(
        self,
        *,
        config: OpenAIRuntimeConfig,
        request: OmegaRunRequest,
        context: OmegaRunContext,
    ) -> SDKRunObservation:
        try:
            from agents import Runner, RunConfig, ToolExecutionConfig
            from agents.tracing import gen_trace_id
        except ImportError as exc:
            raise AgentsSDKUnavailable(
                "openai-agents is required for live AEGIS OpenAI orchestration"
            ) from exc

        specialists = build_specialists(config.model)
        manager = build_omega_manager(
            config.model, specialists, allowed_capabilities=set(request.allowed_capabilities)
        )
        trace_id = gen_trace_id()
        run_config = RunConfig(
            workflow_name=self.WORKFLOW_NAME,
            trace_id=trace_id,
            group_id=context.execution_id,
            trace_metadata={
                "aegis_execution_id": context.execution_id,
                "aegis_request_digest": context.request_digest,
                "aegis_model": config.model,
            },
            trace_include_sensitive_data=config.trace_sensitive_data,
            tool_execution=ToolExecutionConfig(
                max_function_tool_concurrency=config.max_tool_concurrency,
                pre_approval_tool_input_guardrails=True,
            ),
        )
        result = Runner.run_sync(
            manager,
            request.input,
            context=context,
            max_turns=config.max_turns,
            run_config=run_config,
        )

        tool_calls: list[str] = []
        for item in getattr(result, "new_items", []) or []:
            if getattr(item, "type", None) != "tool_call_item":
                continue
            tool_name = getattr(item, "tool_name", None)
            if isinstance(tool_name, str) and tool_name and tool_name not in tool_calls:
                tool_calls.append(tool_name)

        usage_obj = getattr(getattr(result, "context_wrapper", None), "usage", None)
        usage: dict[str, int] | None = None
        if usage_obj is not None:
            usage = {
                "requests": int(getattr(usage_obj, "requests", 0) or 0),
                "input_tokens": int(getattr(usage_obj, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(usage_obj, "output_tokens", 0) or 0),
                "total_tokens": int(getattr(usage_obj, "total_tokens", 0) or 0),
            }

        return SDKRunObservation(
            final_output=getattr(result, "final_output", None),
            trace_id=trace_id,
            tool_calls=tool_calls,
            usage=usage,
        )


class OpenAIRuntime:
    def __init__(self, config: OpenAIRuntimeConfig):
        self.config = config

    @staticmethod
    def _execution_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _request_digest(request: OmegaRunRequest) -> str:
        payload = json.dumps(
            request.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _failure(
        self,
        execution_id: str,
        code: RuntimeErrorCode,
        *,
        trace_id: str | None = None,
        usage: dict[str, int] | None = None,
    ) -> OmegaRunResult:
        return OmegaRunResult(
            execution_id=execution_id,
            status=RunStatus.FAILED,
            model=self.config.model,
            final_output=None,
            trace_id=trace_id,
            error_code=code,
            usage=usage,
        )

    def run(
        self,
        request: OmegaRunRequest,
        *,
        gate: AuthorityGate,
        caller_email: str,
        caller_tier: str,
        runner: Any | None = None,
    ) -> OmegaRunResult:
        execution_id = self._execution_id()

        # Critical invariant: policy admission happens before SDK import/model spend.
        decision = gate.evaluate(request)
        if not decision.admitted:
            assert decision.code is not None
            return OmegaRunResult(
                execution_id=execution_id,
                status=RunStatus.DENIED,
                model=self.config.model,
                final_output=None,
                denial_code=decision.code.value,
                error_code=decision.code,
            )

        context = OmegaRunContext(
            execution_id=execution_id,
            caller_email=caller_email,
            caller_tier=caller_tier,
            model=self.config.model,
            request_digest=self._request_digest(request),
        )
        adapter = runner or AgentsSDKRunnerAdapter()

        try:
            observation = adapter.run(config=self.config, request=request, context=context)
        except AgentsSDKUnavailable:
            return self._failure(execution_id, RuntimeErrorCode.SDK_UNAVAILABLE)
        except Exception:
            # Provider/SDK details stay out of the stable public contract.
            return self._failure(execution_id, RuntimeErrorCode.SDK_ERROR)

        try:
            if isinstance(observation.final_output, OmegaManagerOutput):
                final_output = observation.final_output
            elif isinstance(observation.final_output, dict):
                final_output = OmegaManagerOutput.model_validate(observation.final_output)
            else:
                raise TypeError("final output is not structured")
        except (ValidationError, TypeError, ValueError):
            return self._failure(
                execution_id,
                RuntimeErrorCode.INVALID_FINAL_OUTPUT,
                trace_id=observation.trace_id,
                usage=observation.usage,
            )

        tool_calls = [
            ToolCallRecord(tool=name, status="SUCCEEDED")
            for name in observation.tool_calls
        ]
        return OmegaRunResult(
            execution_id=execution_id,
            status=RunStatus.SUCCEEDED,
            model=self.config.model,
            final_output=final_output,
            specialists_used=list(observation.tool_calls),
            tool_calls=tool_calls,
            trace_id=observation.trace_id,
            usage=observation.usage,
        )
