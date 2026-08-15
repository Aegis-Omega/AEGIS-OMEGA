import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai_runtime.evals import evaluate_runtime_admission
from openai_runtime.types import OmegaManagerOutput, RuntimeErrorCode


def test_trace_bound_structured_output_is_admitted():
    verdict = evaluate_runtime_admission(
        final_output=OmegaManagerOutput(synthesis="grounded"),
        trace_id="trace_" + "a" * 32,
        external_tool_calls=[],
        evidence_digests=[],
    )
    assert verdict.admitted is True
    assert verdict.failed_checks == []


def test_missing_trace_fails_closed():
    verdict = evaluate_runtime_admission(
        final_output=OmegaManagerOutput(synthesis="grounded"),
        trace_id=None,
        external_tool_calls=[],
        evidence_digests=[],
    )
    assert verdict.admitted is False
    assert verdict.code == RuntimeErrorCode.TRACE_MISSING


def test_external_tool_execution_without_evidence_fails_closed():
    verdict = evaluate_runtime_admission(
        final_output=OmegaManagerOutput(synthesis="grounded"),
        trace_id="trace_" + "b" * 32,
        external_tool_calls=["aegis:aegis_platform_status"],
        evidence_digests=[],
    )
    assert verdict.admitted is False
    assert verdict.code == RuntimeErrorCode.EVIDENCE_MISSING
