from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from .agents import AgentsSDKUnavailable, build_omega_manager, build_specialists
from .authority import AuthorityGate
from .chain import OmegaChain
from .config import OpenAIRuntimeConfig
from .evals import evaluate_runtime_admission
from .types import (
    ChainLayer,
    OmegaManagerOutput,
    OmegaRunContext,
    OmegaRunRequest,
    OmegaRunResult,
    RunStatus,
    RuntimeErrorCode,
    ToolCallRecord,
)

_INTERNAL_SPECIALIST_TOOLS = frozenset({
    "research_specialist",
    "verification_specialist",
    "implementation_specialist",
})


@dataclass(frozen=True, slots=True)
class SDKRunObservation:
    final_output: Any
    trace_id: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    evidence_digests: list[str] = field(default_factory=list)
    usage: dict[str, int] | None = None


class AgentsSDKRunnerAdapter:
    """Thin boundary around OpenAI Agents SDK so the runtime stays testable offline."""

    WORKFLOW_NAME = "AEGIS Omega Runtime v1"

    def __init__(self, mcp_servers: list[Any] | tuple[Any, ...] | None = None) -> None:
        self._mcp_servers = list(mcp_servers or [])

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
            config.model,
            specialists,
            allowed_capabilities=set(request.allowed_capabilities),
            mcp_servers=self._mcp_servers,
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
        chain: OmegaChain,
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
            chain=list(chain.receipts),
            chain_root_digest=chain.root_digest(),
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
        chain = OmegaChain()
        chain.admit(
            ChainLayer.INTENT,
            input_artifact={"input": request.input},
            output_artifact=request,
        )

        # Critical invariant: policy admission happens before SDK import/model spend.
        decision = gate.evaluate(request)
        if not decision.admitted:
            assert decision.code is not None
            chain.deny(
                ChainLayer.AUTHORITY,
                input_artifact=request,
                obstruction_code=decision.code,
            )
            return OmegaRunResult(
                execution_id=execution_id,
                status=RunStatus.DENIED,
                model=self.config.model,
                final_output=None,
                denial_code=decision.code.value,
                error_code=decision.code,
                chain=list(chain.receipts),
                chain_root_digest=chain.root_digest(),
            )

        chain.admit(
            ChainLayer.AUTHORITY,
            input_artifact=request,
            output_artifact=decision,
        )
        context = OmegaRunContext(
            execution_id=execution_id,
            caller_email=caller_email,
            caller_tier=caller_tier,
            model=self.config.model,
            request_digest=self._request_digest(request),
        )
        adapter = runner or AgentsSDKRunnerAdapter()

        model_input = {
            "model": self.config.model,
            "request_digest": context.request_digest,
            "max_turns": self.config.max_turns,
        }
        try:
            observation = adapter.run(config=self.config, request=request, context=context)
        except AgentsSDKUnavailable:
            chain.deny(
                ChainLayer.MODEL_RUNTIME,
                input_artifact=model_input,
                obstruction_code=RuntimeErrorCode.SDK_UNAVAILABLE,
            )
            return self._failure(execution_id, RuntimeErrorCode.SDK_UNAVAILABLE, chain=chain)
        except Exception:
            chain.deny(
                ChainLayer.MODEL_RUNTIME,
                input_artifact=model_input,
                obstruction_code=RuntimeErrorCode.SDK_ERROR,
            )
            return self._failure(execution_id, RuntimeErrorCode.SDK_ERROR, chain=chain)

        chain.admit(
            ChainLayer.MODEL_RUNTIME,
            input_artifact=model_input,
            output_artifact={"trace_id": observation.trace_id, "usage": observation.usage},
        )

        try:
            if isinstance(observation.final_output, OmegaManagerOutput):
                final_output = observation.final_output
            elif isinstance(observation.final_output, dict):
                final_output = OmegaManagerOutput.model_validate(observation.final_output)
            else:
                raise TypeError("final output is not structured")
        except (ValidationError, TypeError, ValueError):
            chain.deny(
                ChainLayer.AGENT_ORCHESTRATION,
                input_artifact={"trace_id": observation.trace_id},
                obstruction_code=RuntimeErrorCode.INVALID_FINAL_OUTPUT,
            )
            return self._failure(
                execution_id,
                RuntimeErrorCode.INVALID_FINAL_OUTPUT,
                chain=chain,
                trace_id=observation.trace_id,
                usage=observation.usage,
            )

        specialists_used = [
            name for name in observation.tool_calls if name in _INTERNAL_SPECIALIST_TOOLS
        ]
        external_tool_calls = [
            name for name in observation.tool_calls if name not in _INTERNAL_SPECIALIST_TOOLS
        ]
        chain.admit(
            ChainLayer.AGENT_ORCHESTRATION,
            input_artifact={"trace_id": observation.trace_id},
            output_artifact={
                "final_output": final_output,
                "specialists_used": specialists_used,
            },
        )
        chain.admit(
            ChainLayer.CONNECTORS,
            input_artifact={"allowed_tools": request.allowed_tools},
            output_artifact={"external_tool_calls": external_tool_calls},
        )

        if external_tool_calls and not observation.evidence_digests:
            chain.deny(
                ChainLayer.EVIDENCE,
                input_artifact={"external_tool_calls": external_tool_calls},
                obstruction_code=RuntimeErrorCode.EVIDENCE_MISSING,
            )
            return self._failure(
                execution_id,
                RuntimeErrorCode.EVIDENCE_MISSING,
                chain=chain,
                trace_id=observation.trace_id,
                usage=observation.usage,
            )

        chain.admit(
            ChainLayer.EVIDENCE,
            input_artifact={"external_tool_calls": external_tool_calls},
            output_artifact={
                "trace_id": observation.trace_id,
                "evidence_digests": observation.evidence_digests,
            },
            evidence_digests=observation.evidence_digests,
        )

        eval_verdict = evaluate_runtime_admission(
            final_output=final_output,
            trace_id=observation.trace_id,
            external_tool_calls=external_tool_calls,
            evidence_digests=observation.evidence_digests,
        )
        if not eval_verdict.admitted:
            code = eval_verdict.code or RuntimeErrorCode.EVAL_ADMISSION_FAILED
            chain.deny(
                ChainLayer.EVAL_ADMISSION,
                input_artifact=eval_verdict.failed_checks,
                obstruction_code=code,
            )
            return self._failure(
                execution_id,
                code,
                chain=chain,
                trace_id=observation.trace_id,
                usage=observation.usage,
            )
        chain.admit(
            ChainLayer.EVAL_ADMISSION,
            input_artifact={"trace_id": observation.trace_id},
            output_artifact={"admitted": True, "failed_checks": []},
        )

        tool_calls = [ToolCallRecord(tool=name, status="SUCCEEDED") for name in observation.tool_calls]
        return OmegaRunResult(
            execution_id=execution_id,
            status=RunStatus.SUCCEEDED,
            model=self.config.model,
            final_output=final_output,
            specialists_used=specialists_used,
            tool_calls=tool_calls,
            evidence_digests=list(observation.evidence_digests),
            trace_id=observation.trace_id,
            usage=observation.usage,
            chain=list(chain.receipts),
            chain_root_digest=chain.root_digest(),
        )
