import importlib
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from openai_runtime.connectors import (
    ConnectorExecutionBlocked,
    build_aegis_mcp_connector_policy,
    build_sdk_stdio_server,
)
from openai_runtime.types import ActionClass, OmegaRunRequest


class FakeFilter:
    def __init__(self, allowed):
        self.allowed = allowed


class FakeMCPServerStdio:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_sdk_stdio_builder_exposes_only_read_only_allowlisted_tools(monkeypatch):
    fake_mcp = types.ModuleType("agents.mcp")
    fake_mcp.MCPServerStdio = FakeMCPServerStdio
    fake_mcp.create_static_tool_filter = lambda *, allowed_tool_names: FakeFilter(allowed_tool_names)
    monkeypatch.setitem(sys.modules, "agents.mcp", fake_mcp)

    request = OmegaRunRequest(
        input="inspect",
        allowed_capabilities=["mcp.platform.status"],
        allowed_tools=["aegis:aegis_platform_status"],
        action_class=ActionClass.D0,
    )
    server = build_sdk_stdio_server(build_aegis_mcp_connector_policy(), request)

    assert server.kwargs["params"]["command"] == "node"
    assert server.kwargs["tool_filter"].allowed == ["aegis_platform_status"]
    assert server.kwargs["require_approval"] == {"aegis_platform_status": "never"}
    assert server.kwargs["cache_tools_list"] is True


def test_sdk_stdio_builder_blocks_mutating_tools_until_evidence_adapter_exists(monkeypatch):
    fake_mcp = types.ModuleType("agents.mcp")
    fake_mcp.MCPServerStdio = FakeMCPServerStdio
    fake_mcp.create_static_tool_filter = lambda *, allowed_tool_names: FakeFilter(allowed_tool_names)
    monkeypatch.setitem(sys.modules, "agents.mcp", fake_mcp)

    request = OmegaRunRequest(
        input="collaborate",
        allowed_capabilities=["mcp.collaborate"],
        allowed_tools=["aegis:aegis_collaborate"],
        action_class=ActionClass.D2,
    )
    with pytest.raises(ConnectorExecutionBlocked):
        build_sdk_stdio_server(build_aegis_mcp_connector_policy(), request)


def test_manager_can_receive_preconnected_mcp_servers_with_strict_failure_config(monkeypatch):
    class FakeTool:
        def __init__(self, kwargs):
            self.name = kwargs.get("tool_name")

    class FakeAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
        def as_tool(self, **kwargs):
            return FakeTool(kwargs)

    fake_agents = types.ModuleType("agents")
    fake_agents.Agent = FakeAgent
    monkeypatch.setitem(sys.modules, "agents", fake_agents)

    import openai_runtime.agents as mod
    mod = importlib.reload(mod)
    specialists = mod.build_specialists("gpt-5.6-sol")
    marker = object()
    manager = mod.build_omega_manager(
        "gpt-5.6-sol", specialists,
        allowed_capabilities={"research-synthesis"},
        mcp_servers=[marker],
    )

    assert manager.mcp_servers == [marker]
    assert manager.mcp_config == {
        "convert_schemas_to_strict": True,
        "failure_error_function": None,
        "include_server_in_tool_names": True,
    }
