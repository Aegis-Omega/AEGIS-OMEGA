import importlib
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai_runtime.types import OmegaManagerOutput, SpecialistOutput


class FakeTool:
    def __init__(self, agent, kwargs):
        self.agent = agent
        self.name = kwargs.get("tool_name")
        self.description = kwargs.get("tool_description")
        self.max_turns = kwargs.get("max_turns")
        self.needs_approval = kwargs.get("needs_approval", False)


class FakeAgent:
    def __init__(self, **kwargs):
        self.name = kwargs["name"]
        self.instructions = kwargs.get("instructions", "")
        self.model = kwargs.get("model")
        self.output_type = kwargs.get("output_type")
        self.tools = kwargs.get("tools", [])

    def as_tool(self, **kwargs):
        return FakeTool(self, kwargs)


def _load_module_with_fake_sdk(monkeypatch):
    fake_agents = types.ModuleType("agents")
    fake_agents.Agent = FakeAgent
    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    import openai_runtime.agents as agents_module
    return importlib.reload(agents_module)


def test_specialists_are_three_bounded_structured_agents(monkeypatch):
    mod = _load_module_with_fake_sdk(monkeypatch)
    specialists = mod.build_specialists("gpt-5.6-sol")

    assert specialists.research.name == "AEGIS Research Specialist"
    assert specialists.verification.name == "AEGIS Verification Specialist"
    assert specialists.implementation.name == "AEGIS Implementation Specialist"
    assert {a.model for a in specialists.all()} == {"gpt-5.6-sol"}
    assert all(a.output_type is SpecialistOutput for a in specialists.all())
    assert all(a.tools == [] for a in specialists.all())


def test_manager_retains_final_output_ownership_and_uses_specialists_as_tools(monkeypatch):
    mod = _load_module_with_fake_sdk(monkeypatch)
    specialists = mod.build_specialists("gpt-5.6-sol")
    manager = mod.build_omega_manager("gpt-5.6-sol", specialists)

    assert manager.name == "AEGIS Omega Manager"
    assert manager.model == "gpt-5.6-sol"
    assert manager.output_type is OmegaManagerOutput
    assert len(manager.tools) == 3
    assert {tool.name for tool in manager.tools} == {
        "research_specialist",
        "verification_specialist",
        "implementation_specialist",
    }
    assert all(tool.max_turns == 4 for tool in manager.tools)
    assert all(tool.needs_approval is False for tool in manager.tools)
    assert "final synthesis" in manager.instructions.lower()


def test_missing_sdk_is_reported_as_stable_runtime_error(monkeypatch):
    monkeypatch.delitem(sys.modules, "agents", raising=False)
    import openai_runtime.agents as mod
    mod = importlib.reload(mod)

    original_import = __import__

    def blocking_import(name, *args, **kwargs):
        if name == "agents":
            raise ImportError("not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocking_import)
    try:
        mod.build_specialists("gpt-5.6-sol")
        raise AssertionError("expected AgentsSDKUnavailable")
    except mod.AgentsSDKUnavailable as exc:
        assert "openai-agents" in str(exc)


def test_manager_exposes_only_specialists_authorized_by_declared_capabilities(monkeypatch):
    fake_agents = types.ModuleType("agents")
    fake_agents.Agent = FakeAgent
    monkeypatch.setitem(sys.modules, "agents", fake_agents)

    import openai_runtime.agents as agents_module
    importlib.reload(agents_module)

    specialists = agents_module.build_specialists("gpt-test")
    manager = agents_module.build_omega_manager(
        "gpt-test",
        specialists,
        allowed_capabilities={"research-synthesis"},
    )

    assert [tool.name for tool in manager.tools] == ["research_specialist"]
