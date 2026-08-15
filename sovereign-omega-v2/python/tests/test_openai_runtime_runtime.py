import importlib
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai_runtime.authority import AuthorityGate
from openai_runtime.config import OpenAIRuntimeConfig
from openai_runtime.runtime import AgentsSDKRunnerAdapter, OpenAIRuntime, SDKRunObservation
from openai_runtime.types import (
    OmegaManagerOutput,
    OmegaRunRequest,
    RunStatus,
    RuntimeErrorCode,
)


def _config():
    return OpenAIRuntimeConfig(
        api_key="test-key-not-real",
        model="gpt-5.6-sol",
        max_turns=7,
        max_tool_concurrency=2,
        trace_sensitive_data=False,
    )


def _admitted_gate():
    return AuthorityGate(
        registered_capabilities={"research-synthesis"},
        active_grants={"research-synthesis"},
        registered_tools={},
        approvals=set(),
    )


class FakeAdapter:
    def __init__(self, observation=None, exc=None):
        self.observation = observation
        self.exc = exc
        self.calls = 0
        self.last = None

    def run(self, *, config, request, context):
        self.calls += 1
        self.last = (config, request, context)
        if self.exc:
            raise self.exc
        return self.observation


def test_authority_denial_happens_before_runner_is_invoked():
    req = OmegaRunRequest(input="x", allowed_capabilities=["research-synthesis"])
    denied_gate = AuthorityGate(
        registered_capabilities={"research-synthesis"},
        active_grants=set(),
        registered_tools={},
        approvals=set(),
    )
    adapter = FakeAdapter()
    result = OpenAIRuntime(_config()).run(
        req,
        gate=denied_gate,
        caller_email="operator@example.invalid",
        caller_tier="sovereign",
        runner=adapter,
    )
    assert result.status == RunStatus.DENIED
    assert result.error_code == RuntimeErrorCode.CAPABILITY_NOT_GRANTED
    assert adapter.calls == 0


def test_success_maps_structured_output_trace_usage_and_specialist_provenance():
    observation = SDKRunObservation(
        final_output=OmegaManagerOutput(
            synthesis="bounded synthesis",
            evidence=["evidence-1"],
            unresolved=[],
            recommended_actions=[],
        ),
        trace_id="trace_" + "a" * 32,
        tool_calls=["verification_specialist"],
        usage={"requests": 2, "input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
    )
    adapter = FakeAdapter(observation=observation)
    req = OmegaRunRequest(input="verify", allowed_capabilities=["research-synthesis"])
    result = OpenAIRuntime(_config()).run(
        req,
        gate=_admitted_gate(),
        caller_email="operator@example.invalid",
        caller_tier="sovereign",
        runner=adapter,
    )
    assert result.status == RunStatus.SUCCEEDED
    assert result.model == "gpt-5.6-sol"
    assert result.trace_id == "trace_" + "a" * 32
    assert result.usage["total_tokens"] == 120
    assert result.specialists_used == ["verification_specialist"]
    assert adapter.calls == 1
    assert adapter.last[2].execution_id == result.execution_id
    assert len(adapter.last[2].request_digest) == 64


def test_invalid_structured_output_fails_closed():
    adapter = FakeAdapter(
        observation=SDKRunObservation(
            final_output="free-form text is not accepted",
            trace_id="trace_" + "b" * 32,
        )
    )
    result = OpenAIRuntime(_config()).run(
        OmegaRunRequest(input="verify", allowed_capabilities=["research-synthesis"]),
        gate=_admitted_gate(),
        caller_email="operator@example.invalid",
        caller_tier="sovereign",
        runner=adapter,
    )
    assert result.status == RunStatus.FAILED
    assert result.error_code == RuntimeErrorCode.INVALID_FINAL_OUTPUT
    assert result.final_output is None


def test_sdk_exception_maps_to_stable_failure_code():
    adapter = FakeAdapter(exc=RuntimeError("provider exploded"))
    result = OpenAIRuntime(_config()).run(
        OmegaRunRequest(input="verify", allowed_capabilities=["research-synthesis"]),
        gate=_admitted_gate(),
        caller_email="operator@example.invalid",
        caller_tier="sovereign",
        runner=adapter,
    )
    assert result.status == RunStatus.FAILED
    assert result.error_code == RuntimeErrorCode.SDK_ERROR
    assert "provider exploded" not in (result.denial_code or "")


class FakeTool:
    def __init__(self, agent, kwargs):
        self.agent = agent
        self.name = kwargs.get("tool_name")
        self.max_turns = kwargs.get("max_turns")


class FakeAgent:
    def __init__(self, **kwargs):
        self.name = kwargs["name"]
        self.model = kwargs.get("model")
        self.output_type = kwargs.get("output_type")
        self.tools = kwargs.get("tools", [])
        self.instructions = kwargs.get("instructions", "")

    def as_tool(self, **kwargs):
        return FakeTool(self, kwargs)


class FakeRunConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeToolExecutionConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeUsage:
    requests = 1
    input_tokens = 12
    output_tokens = 3
    total_tokens = 15


class FakeContextWrapper:
    usage = FakeUsage()


class FakeToolItem:
    type = "tool_call_item"
    tool_name = "research_specialist"


class FakeSDKResult:
    final_output = OmegaManagerOutput(synthesis="ok")
    new_items = [FakeToolItem()]
    context_wrapper = FakeContextWrapper()


class FakeRunner:
    last_call = None

    @classmethod
    def run_sync(cls, manager, input, **kwargs):
        cls.last_call = {"manager": manager, "input": input, **kwargs}
        return FakeSDKResult()


def test_default_sdk_adapter_builds_bounded_run_config(monkeypatch):
    fake_agents = types.ModuleType("agents")
    fake_agents.Agent = FakeAgent
    fake_agents.Runner = FakeRunner
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.ToolExecutionConfig = FakeToolExecutionConfig
    monkeypatch.setitem(sys.modules, "agents", fake_agents)

    fake_tracing = types.ModuleType("agents.tracing")
    fake_tracing.gen_trace_id = lambda: "trace_" + "c" * 32
    monkeypatch.setitem(sys.modules, "agents.tracing", fake_tracing)

    import openai_runtime.agents as agents_module
    importlib.reload(agents_module)

    adapter = AgentsSDKRunnerAdapter()
    runtime = OpenAIRuntime(_config())
    req = OmegaRunRequest(input="verify", allowed_capabilities=["research-synthesis"])
    result = runtime.run(
        req,
        gate=_admitted_gate(),
        caller_email="operator@example.invalid",
        caller_tier="sovereign",
        runner=adapter,
    )

    assert result.status == RunStatus.SUCCEEDED
    call = FakeRunner.last_call
    assert call["max_turns"] == 7
    assert call["run_config"].workflow_name == "AEGIS Omega Runtime v1"
    assert call["run_config"].trace_include_sensitive_data is False
    assert call["run_config"].tool_execution.max_function_tool_concurrency == 2
    assert call["run_config"].tool_execution.pre_approval_tool_input_guardrails is True
    assert call["run_config"].trace_metadata["aegis_execution_id"] == result.execution_id
    assert call["context"].execution_id == result.execution_id
    assert result.specialists_used == ["research_specialist"]
