from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse


class A2AError(ValueError):
    pass


_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class A2AAgentEndpoint:
    name: str
    agent_card_url: str
    service_url: str
    auth_reference: str | None
    allowed_skills: tuple[str, ...]
    protocol_version: str = "1.0.0"


@dataclass(frozen=True)
class A2ATaskEnvelope:
    task_id: str
    execution_id: str
    sender: str
    recipient: str
    skill: str
    input_digest: str
    stream_owner: str
    stream_generation: int


@dataclass(frozen=True)
class VerifiedA2ATask:
    endpoint: A2AAgentEndpoint
    task: A2ATaskEnvelope
    protocol_version: str


def _https(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _auth_ref(value: str | None) -> bool:
    return value is None or value.startswith(("oauth://", "identity://", "secret://", "env://", "vault://", "keyref://", "oidc://"))


def verify_a2a_task(
    endpoint: A2AAgentEndpoint,
    task: A2ATaskEnvelope,
    *,
    expected_stream_owner: str,
    expected_generation: int,
) -> VerifiedA2ATask:
    if endpoint.protocol_version != "1.0.0":
        raise A2AError("unsupported A2A protocol version")
    if not endpoint.name or not _https(endpoint.agent_card_url) or not _https(endpoint.service_url):
        raise A2AError("A2A endpoint requires a name and https agent-card/service URLs")
    if not _auth_ref(endpoint.auth_reference):
        raise A2AError("A2A auth must be an opaque reference")
    if not endpoint.allowed_skills or "*" in endpoint.allowed_skills:
        raise A2AError("A2A skills must be explicitly allowlisted")
    if task.recipient != endpoint.name:
        raise A2AError("A2A recipient does not match endpoint")
    if task.skill not in endpoint.allowed_skills:
        raise A2AError("A2A skill is not allowlisted")
    if _SHA256_RE.fullmatch(task.input_digest) is None:
        raise A2AError("A2A input must be represented by a SHA-256 digest")
    if task.stream_owner != expected_stream_owner:
        raise A2AError("A2A task stream owner mismatch")
    if task.stream_generation != expected_generation:
        raise A2AError("A2A task stream generation mismatch")
    if task.stream_generation < 0:
        raise A2AError("A2A stream generation must be non-negative")
    if not task.task_id or not task.execution_id or not task.sender:
        raise A2AError("A2A task identity fields are required")
    return VerifiedA2ATask(endpoint=endpoint, task=task, protocol_version=endpoint.protocol_version)
