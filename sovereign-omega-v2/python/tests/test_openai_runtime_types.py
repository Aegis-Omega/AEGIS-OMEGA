import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from pydantic import ValidationError

from openai_runtime.types import (
    ActionClass,
    OmegaManagerOutput,
    OmegaRunRequest,
    OmegaRunResult,
    RunStatus,
)


def test_run_request_rejects_blank_input():
    with pytest.raises(ValidationError):
        OmegaRunRequest(input="   ")


def test_run_request_defaults_to_d0_and_no_fallback():
    req = OmegaRunRequest(input="verify current evidence")
    assert req.action_class == ActionClass.D0
    assert req.fallback_allowed is False
    assert req.allowed_capabilities == []
    assert req.allowed_tools == []


def test_denied_result_cannot_carry_final_output():
    with pytest.raises(ValidationError):
        OmegaRunResult(
            execution_id="e-1",
            status=RunStatus.DENIED,
            model="gpt-5.6-sol",
            final_output=OmegaManagerOutput(synthesis="should not exist"),
            denial_code="CAPABILITY_NOT_GRANTED",
        )


def test_success_result_requires_structured_output():
    result = OmegaRunResult(
        execution_id="e-2",
        status=RunStatus.SUCCEEDED,
        model="gpt-5.6-sol",
        final_output=OmegaManagerOutput(
            synthesis="Evidence supports the bounded claim.",
            evidence=["sha256:abc"],
            unresolved=[],
            recommended_actions=["run replay"],
        ),
        specialists_used=["verification"],
        evidence_digests=["a" * 64],
    )
    assert result.final_output.synthesis.startswith("Evidence")
    assert result.is_replay_reconstructable is True
