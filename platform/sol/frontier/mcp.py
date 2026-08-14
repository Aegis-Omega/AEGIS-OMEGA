from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


class MCPError(ValueError):
    pass


@dataclass(frozen=True)
class RemoteMCPServer:
    name: str
    url: str
    allowed_tools: tuple[str, ...]
    approval_policy: str
    auth_reference: str | None
    transport: str = "streamable-http"


def _is_reference(value: str) -> bool:
    return value.startswith(("oauth://", "identity://", "secret://", "env://", "vault://", "keyref://", "oidc://"))


def verify_mcp_server(server: RemoteMCPServer) -> RemoteMCPServer:
    if not server.name:
        raise MCPError("MCP server name is required")
    parsed = urlparse(server.url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise MCPError("remote MCP server must use an absolute https URL")
    if server.transport not in {"streamable-http", "sse"}:
        raise MCPError("unsupported MCP transport")
    if not server.allowed_tools:
        raise MCPError("MCP tools must be explicitly allowlisted")
    if "*" in server.allowed_tools:
        raise MCPError("wildcard MCP tool access is forbidden")
    if len(set(server.allowed_tools)) != len(server.allowed_tools):
        raise MCPError("duplicate MCP tool names are forbidden")
    if server.approval_policy not in {"always", "aegis"}:
        raise MCPError("MCP approval policy must be always or aegis")
    if server.auth_reference is not None and not _is_reference(server.auth_reference):
        raise MCPError("MCP auth must be an opaque reference, never inline credentials")
    return server
