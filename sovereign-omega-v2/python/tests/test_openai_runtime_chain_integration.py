import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai_runtime.authority import AuthorityGate
from openai_runtime.config import OpenAIRuntimeConfig
from openai_runtime.runtime import OpenAIRuntime, SDKRunObservation
from openai_runtime.types import ChainLayer, OmegaManagerOutput, OmegaRunRequest, RunStatus, RuntimeErrorCode


class FakeAdapter:
    def __init__(self, observation):
        self.observation = observation
        self.calls = 0

    def run(self, **kwargs):
        self.calls += 1
        return self.observation


def _config():
    return OpenAIRuntimeConfig(api_key="not-real", model="gpt-5.6-sol")


def _gate(granted=True):
    return AuthorityGate(
        registered_capabilities={"research-synthesis"},
        active_grants={"research-synthesis"} if granted else set(),
        registered_tools={},
        approvals=set(),
    )


def test_success_traverses_l0_through_l6_and_emits_chain_root():
    adapter = FakeAdapter(SDKRunObservation(
        final_output=OmegaManagerOutput(synthesis="verified"),
        trace_id="trace_" + "a" * 32,
        tool_calls=["verification_specialist"],
    ))
    result = OpenAIRuntime(_config()).run(
        OmegaRunRequest(input="verify", allowed_capabilities=["research-synthesis"]),
        gate=_gate(), caller_email="operator@example.invalid", caller_tier="sovereign", runner=adapter,
    )
    assert result.status == RunStatus.SUCCEEDED
    assert [r.layer for r in result.chain] == list(ChainLayer)[:7]
    assert all(r.admitted for r in result.chain)
    assert result.chain_root_digest is not None and len(result.chain_root_digest) == 64
    assert result.specialists_used == ["verification_specialist"]


def test_authority_denial_terminates_at_l1_before_model_spend():
    adapter = FakeAdapter(None)
    result = OpenAIRuntime(_config()).run(
        OmegaRunRequest(input="verify", allowed_capabilities=["research-synthesis"]),
        gate=_gate(granted=False), caller_email="operator@example.invalid", caller_tier="sovereign", runner=adapter,
    )
    assert result.status == RunStatus.DENIED
    assert result.error_code == RuntimeErrorCode.CAPABILITY_NOT_GRANTED
    assert [r.layer for r in result.chain] == [ChainLayer.INTENT, ChainLayer.AUTHORITY]
    assert result.chain[-1].admitted is False
    assert adapter.calls == 0


def test_external_tool_without_digest_bound_evidence_is_blocked_at_l5():
    adapter = FakeAdapter(SDKRunObservation(
        final_output=OmegaManagerOutput(synthesis="unverified external result"),
        trace_id="trace_" + "b" * 32,
        tool_calls=["aegis:aegis_platform_status"],
        evidence_digests=[],
    ))
    result = OpenAIRuntime(_config()).run(
        OmegaRunRequest(input="read", allowed_capabilities=["research-synthesis"]),
        gate=_gate(), caller_email="operator@example.invalid", caller_tier="sovereign", runner=adapter,
    )
    assert result.status == RunStatus.FAILED
    assert result.error_code == RuntimeErrorCode.EVIDENCE_MISSING
    assert result.chain[-1].layer == ChainLayer.EVIDENCE
    assert result.chain[-1].admitted is False
