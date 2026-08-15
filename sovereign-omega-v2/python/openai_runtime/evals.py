from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .types import OmegaManagerOutput, RuntimeErrorCode


class RuntimeAdmissionVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    admitted: bool
    code: RuntimeErrorCode | None = None
    failed_checks: list[str] = Field(default_factory=list)


def evaluate_runtime_admission(
    *,
    final_output: OmegaManagerOutput,
    trace_id: str | None,
    external_tool_calls: list[str],
    evidence_digests: list[str],
) -> RuntimeAdmissionVerdict:
    """Deterministic macro-admission checks before a run can be promoted."""
    if not isinstance(final_output, OmegaManagerOutput):
        return RuntimeAdmissionVerdict(
            admitted=False,
            code=RuntimeErrorCode.INVALID_FINAL_OUTPUT,
            failed_checks=["structured_output"],
        )
    if not (trace_id or "").strip():
        return RuntimeAdmissionVerdict(
            admitted=False,
            code=RuntimeErrorCode.TRACE_MISSING,
            failed_checks=["trace_bound"],
        )
    if external_tool_calls and not evidence_digests:
        return RuntimeAdmissionVerdict(
            admitted=False,
            code=RuntimeErrorCode.EVIDENCE_MISSING,
            failed_checks=["external_tool_evidence"],
        )
    return RuntimeAdmissionVerdict(admitted=True)
