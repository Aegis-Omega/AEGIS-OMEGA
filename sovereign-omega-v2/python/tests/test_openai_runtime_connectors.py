import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai_runtime.connectors import (
    ConnectorRegistry,
    ConnectorTransport,
    build_aegis_mcp_connector_policy,
)
from openai_runtime.types import ActionClass, OmegaRunRequest, RuntimeErrorCode


def test_aegis_mcp_policy_mirrors_existing_governed_tool_surface():
    policy = build_aegis_mcp_connector_policy()

    assert policy.transport == ConnectorTransport.STDIO
    assert policy.name == "aegis"
    assert policy.tools["aegis_platform_status"].max_action_class == ActionClass.D0
    assert policy.tools["aegis_collaborate"].max_action_class == ActionClass.D2
    assert policy.tools["aegis_start_execution"].mutates is True
    assert policy.tools["aegis_governed_claude_call"].max_action_class == ActionClass.D3


def test_unregistered_connector_fails_closed():
    registry = ConnectorRegistry([build_aegis_mcp_connector_policy()])
    req = OmegaRunRequest(input="x", allowed_capabilities=["mcp.platform.status"])
    decision = registry.authorize("unknown", "tool", req)
    assert decision.admitted is False
    assert decision.code == RuntimeErrorCode.CONNECTOR_NOT_REGISTERED


def test_read_only_connector_tool_requires_explicit_request_allowlist_and_capability():
    registry = ConnectorRegistry([build_aegis_mcp_connector_policy()])
    denied = registry.authorize(
        "aegis",
        "aegis_platform_status",
        OmegaRunRequest(input="x", allowed_capabilities=["mcp.platform.status"]),
    )
    assert denied.admitted is False
    assert denied.code == RuntimeErrorCode.CONNECTOR_TOOL_NOT_ALLOWED

    admitted = registry.authorize(
        "aegis",
        "aegis_platform_status",
        OmegaRunRequest(
            input="x",
            allowed_capabilities=["mcp.platform.status"],
            allowed_tools=["aegis:aegis_platform_status"],
            action_class=ActionClass.D0,
        ),
    )
    assert admitted.admitted is True


def test_mutating_connector_ignores_caller_claimed_approval_and_requires_server_approval():
    policy = build_aegis_mcp_connector_policy()
    approval = "approve:mcp:aegis_collaborate"
    req = OmegaRunRequest(
        input="x",
        allowed_capabilities=["mcp.collaborate"],
        allowed_tools=["aegis:aegis_collaborate"],
        action_class=ActionClass.D2,
        approvals=[approval],
    )

    denied = ConnectorRegistry([policy], approvals=set()).authorize(
        "aegis", "aegis_collaborate", req
    )
    assert denied.admitted is False
    assert denied.code == RuntimeErrorCode.APPROVAL_REQUIRED

    admitted = ConnectorRegistry([policy], approvals={approval}).authorize(
        "aegis", "aegis_collaborate", req
    )
    assert admitted.admitted is True
