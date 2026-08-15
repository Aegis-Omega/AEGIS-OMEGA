from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from .types import ActionClass, AuthorityDecision, OmegaRunRequest, RuntimeErrorCode

_ACTION_ORDER = {
    ActionClass.D0: 0,
    ActionClass.D1: 1,
    ActionClass.D2: 2,
    ActionClass.D3: 3,
    ActionClass.D4: 4,
}


class ConnectorTransport(str, Enum):
    HOSTED_MCP = "hosted_mcp"
    STREAMABLE_HTTP = "streamable_http"
    SSE = "sse"
    STDIO = "stdio"


@dataclass(frozen=True, slots=True)
class ConnectorToolPolicy:
    name: str
    required_capability: str
    max_action_class: ActionClass
    mutates: bool = False
    requires_approval: bool = False
    approval_id: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.required_capability.strip():
            raise ValueError("connector tool name and capability are required")
        if (self.mutates or self.requires_approval) and not (self.approval_id or "").strip():
            raise ValueError("mutating/approval-gated connector tools require approval_id")


@dataclass(frozen=True, slots=True)
class ConnectorPolicy:
    name: str
    transport: ConnectorTransport
    tools: Mapping[str, ConnectorToolPolicy]
    server_label: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("connector name is required")
        if self.transport == ConnectorTransport.STDIO and not (self.command or "").strip():
            raise ValueError("stdio connector requires command")


class ConnectorRegistry:
    """Server-owned connector authority registry; caller approvals are never trusted."""

    def __init__(self, policies: Iterable[ConnectorPolicy], approvals: set[str] | None = None) -> None:
        self._policies: dict[str, ConnectorPolicy] = {}
        for policy in policies:
            if policy.name in self._policies:
                raise ValueError(f"duplicate connector policy: {policy.name}")
            self._policies[policy.name] = policy
        self._approvals = frozenset(approvals or set())

    @staticmethod
    def _deny(code: RuntimeErrorCode, reason: str) -> AuthorityDecision:
        return AuthorityDecision(admitted=False, code=code, reason=reason)

    def authorize(self, connector: str, tool: str, request: OmegaRunRequest) -> AuthorityDecision:
        policy = self._policies.get(connector)
        if policy is None:
            return self._deny(RuntimeErrorCode.CONNECTOR_NOT_REGISTERED, f"connector is not registered: {connector}")
        tool_policy = policy.tools.get(tool)
        if tool_policy is None:
            return self._deny(RuntimeErrorCode.CONNECTOR_TOOL_NOT_REGISTERED, f"connector tool is not registered: {connector}:{tool}")

        logical_tool = f"{connector}:{tool}"
        if logical_tool not in request.allowed_tools:
            return self._deny(RuntimeErrorCode.CONNECTOR_TOOL_NOT_ALLOWED, f"connector tool is outside request allowlist: {logical_tool}")
        if tool_policy.required_capability not in request.allowed_capabilities:
            return self._deny(RuntimeErrorCode.CAPABILITY_NOT_GRANTED, f"connector capability was not declared: {tool_policy.required_capability}")
        if _ACTION_ORDER[request.action_class] > _ACTION_ORDER[tool_policy.max_action_class]:
            return self._deny(RuntimeErrorCode.ACTION_CLASS_EXCEEDED, f"request action class exceeds connector tool ceiling: {logical_tool}")
        if tool_policy.requires_approval and tool_policy.approval_id not in self._approvals:
            return self._deny(RuntimeErrorCode.APPROVAL_REQUIRED, f"server-side approval required for connector tool: {logical_tool}")
        return AuthorityDecision(admitted=True, reason=f"connector tool admitted: {logical_tool}")


def build_aegis_mcp_connector_policy() -> ConnectorPolicy:
    """Policy mirror of sovereign-omega-v2/mcp-server/src/index.ts.

    The connector is described but not auto-started here. Execution wiring is a
    later stage and must preserve the MCP server's own Automaton-3 admission.
    """
    tools = {
        "aegis_health": ConnectorToolPolicy("aegis_health", "mcp.health.read", ActionClass.D0),
        "aegis_telemetry": ConnectorToolPolicy("aegis_telemetry", "mcp.telemetry.read", ActionClass.D0),
        "aegis_platform_status": ConnectorToolPolicy("aegis_platform_status", "mcp.platform.status", ActionClass.D0),
        "aegis_collaborate": ConnectorToolPolicy(
            "aegis_collaborate", "mcp.collaborate", ActionClass.D2,
            mutates=True, requires_approval=True, approval_id="approve:mcp:aegis_collaborate",
        ),
        "aegis_start_execution": ConnectorToolPolicy(
            "aegis_start_execution", "mcp.execution.start", ActionClass.D2,
            mutates=True, requires_approval=True, approval_id="approve:mcp:aegis_start_execution",
        ),
        "aegis_get_execution": ConnectorToolPolicy("aegis_get_execution", "mcp.execution.read", ActionClass.D0),
        "aegis_governed_claude_call": ConnectorToolPolicy(
            "aegis_governed_claude_call", "mcp.claude.call", ActionClass.D3,
            mutates=True, requires_approval=True, approval_id="approve:mcp:aegis_governed_claude_call",
        ),
    }
    return ConnectorPolicy(
        name="aegis",
        transport=ConnectorTransport.STDIO,
        server_label="aegis-constitutional-swarm",
        command="node",
        args=("sovereign-omega-v2/mcp-server/dist/index.js",),
        tools=tools,
    )


class ConnectorSDKUnavailable(RuntimeError):
    pass


class ConnectorExecutionBlocked(RuntimeError):
    """Raised before MCP connection when effectful execution lacks evidence binding."""
    pass


def build_sdk_stdio_server(policy: ConnectorPolicy, request: OmegaRunRequest):
    """Build a not-yet-connected Agents SDK stdio server from an admitted policy.

    The caller owns lifecycle (`async with`) and must run ConnectorRegistry
    preflight before this object is connected. Only request-allowlisted tools are
    exposed. Approval requirements remain visible to the SDK as a second gate.
    """
    if policy.transport != ConnectorTransport.STDIO:
        raise ValueError("policy is not a stdio connector")
    try:
        from agents.mcp import MCPServerStdio, create_static_tool_filter
    except ImportError as exc:
        raise ConnectorSDKUnavailable("openai-agents MCP support is unavailable") from exc

    allowed_names: list[str] = []
    approval_policy: dict[str, str] = {}
    for logical_name in request.allowed_tools:
        prefix = f"{policy.name}:"
        if not logical_name.startswith(prefix):
            continue
        tool_name = logical_name[len(prefix):]
        tool_policy = policy.tools.get(tool_name)
        if tool_policy is None:
            continue
        if tool_policy.mutates:
            raise ConnectorExecutionBlocked(
                f"effectful connector tool requires a pre-execution evidence/receipt adapter: {policy.name}:{tool_name}"
            )
        allowed_names.append(tool_name)
        approval_policy[tool_name] = "always" if tool_policy.requires_approval else "never"

    return MCPServerStdio(
        name=policy.server_label or policy.name,
        params={"command": policy.command, "args": list(policy.args)},
        tool_filter=create_static_tool_filter(allowed_tool_names=allowed_names),
        require_approval=approval_policy,
        cache_tools_list=True,
    )
