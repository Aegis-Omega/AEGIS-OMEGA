import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from openai_runtime.authority import AuthorityGate, ToolPolicy
from openai_runtime.tools import EvidenceValidationError, validate_tool_input, validate_tool_output
from openai_runtime.types import ActionClass, OmegaRunRequest, RuntimeErrorCode, ToolEvidence


def _gate():
    return AuthorityGate(
        registered_capabilities={"research-synthesis"},
        active_grants={"research-synthesis"},
        registered_tools={
            "read-evidence": ToolPolicy(
                name="read-evidence",
                required_capability="research-synthesis",
                max_action_class=ActionClass.D0,
            )
        },
        approvals=set(),
    )


def test_tool_input_rejects_call_not_in_request_allowlist():
    req = OmegaRunRequest(input="x", allowed_capabilities=["research-synthesis"])
    decision = validate_tool_input("read-evidence", req, _gate())
    assert decision.admitted is False
    assert decision.code == RuntimeErrorCode.TOOL_NOT_ALLOWED


def test_tool_input_accepts_governed_allowed_tool():
    req = OmegaRunRequest(
        input="x",
        allowed_capabilities=["research-synthesis"],
        allowed_tools=["read-evidence"],
    )
    decision = validate_tool_input("read-evidence", req, _gate())
    assert decision.admitted is True


def test_successful_tool_output_without_result_digest_is_rejected():
    evidence = ToolEvidence(tool="read-evidence", success=True, evidence_digests=["a" * 64])
    with pytest.raises(EvidenceValidationError) as exc:
        validate_tool_output(evidence)
    assert exc.value.code == RuntimeErrorCode.EVIDENCE_MISSING


def test_successful_tool_output_without_evidence_digest_is_rejected():
    evidence = ToolEvidence(tool="read-evidence", success=True, result_digest="b" * 64)
    with pytest.raises(EvidenceValidationError) as exc:
        validate_tool_output(evidence)
    assert exc.value.code == RuntimeErrorCode.EVIDENCE_MISSING


def test_mutation_requires_target_and_pre_post_state_digests():
    evidence = ToolEvidence(
        tool="apply-patch",
        success=True,
        result_digest="b" * 64,
        evidence_digests=["c" * 64],
        mutates=True,
    )
    with pytest.raises(EvidenceValidationError) as exc:
        validate_tool_output(evidence)
    assert exc.value.code == RuntimeErrorCode.EVIDENCE_MISSING


def test_complete_read_only_tool_evidence_is_admitted():
    evidence = ToolEvidence(
        tool="read-evidence",
        success=True,
        result_digest="b" * 64,
        evidence_digests=["c" * 64],
    )
    assert validate_tool_output(evidence) == evidence
