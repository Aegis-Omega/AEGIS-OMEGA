"""AEGIS-Ω synchronous client — constitutional audit on every call."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Generator, Literal

BASE_URL = "https://aegis-vertex.aegisomega.com"
CONTRACT_VERSION = "1.0.0"

Mode = Literal["revenue", "analysis", "gtm", "retention", "competitive", "technical", "regulatory", "fundraising"]


class AegisError(Exception):
    """Raised when the platform returns an error or an invalid envelope."""

    def __init__(self, message: str, code: str = "INTERNAL", status: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.status = status

    def __repr__(self) -> str:
        return f"AegisError(code={self.code!r}, status={self.status}, message={str(self)!r})"


@dataclass
class ConstitutionalAudit:
    verdict: Literal["APPROVED", "FLAG", "QUARANTINE"]
    concerns: list[str] = field(default_factory=list)


@dataclass
class Artifact:
    role: str
    output: str


@dataclass
class CollaborationResult:
    cycle_id: str
    objective: str
    mode: str
    departments_collaborated: int
    artifacts: list[Artifact]
    constitutional_audit: ConstitutionalAudit
    chain_valid: bool
    audit_chain_hash: str
    execution_id: str
    projection: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> "CollaborationResult":
        return cls(
            cycle_id=d["cycle_id"],
            objective=d["objective"],
            mode=d["mode"],
            departments_collaborated=d["departments_collaborated"],
            artifacts=[Artifact(role=a["role"], output=a["output"]) for a in d.get("artifacts", [])],
            constitutional_audit=ConstitutionalAudit(
                verdict=d["constitutional_audit"]["verdict"],
                concerns=d["constitutional_audit"].get("concerns", []),
            ),
            chain_valid=d["chain_valid"],
            audit_chain_hash=d["audit_chain_hash"],
            execution_id=d["execution_id"],
            projection=d.get("projection", {}),
        )


@dataclass
class PlatformStatus:
    version: str
    contract_version: str
    total_agents: int
    chain_valid: bool
    audit_chain_hash: str
    available: bool
    reason: str | None = None


@dataclass
class ExecutionHandle:
    """Returned by start_execution(); call stream() to consume SSE events."""
    execution_id: str
    stream_url: str
    _client: "AegisClient"

    def stream(self) -> Generator[dict[str, Any], None, None]:
        yield from self._client._stream_events(self.execution_id)

    def result(self) -> CollaborationResult:
        return self._client.get_execution(self.execution_id)


def _validate_envelope(raw: dict[str, Any]) -> Any:
    if raw.get("contract_version") != CONTRACT_VERSION:
        raise AegisError(
            f"contract_version mismatch: expected {CONTRACT_VERSION!r}, got {raw.get('contract_version')!r}",
            code="INTERNAL",
        )
    for field_name in ("execution_id", "timestamp"):
        if field_name not in raw:
            raise AegisError(f"PlatformEnvelope missing field: {field_name!r}", code="INTERNAL")
    if raw.get("is_replay_reconstructable") is not True:
        raise AegisError("is_replay_reconstructable must be exactly true", code="INTERNAL")
    return raw["data"]


class AegisClient:
    """Synchronous AEGIS-Ω Platform client.

    Usage::

        client = AegisClient("aegis_your_key")
        result = client.collaborate("Enter EU fintech market Q4 2026", mode="gtm")
        print(result.constitutional_audit.verdict)   # "APPROVED"
        print(result.departments_collaborated)        # 39
    """

    def __init__(self, api_key: str, base_url: str = BASE_URL, timeout: int = 60) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                err = json.loads(exc.read().decode())
            except Exception:
                err = {"error": str(exc), "code": "INTERNAL"}
            raise AegisError(err.get("error", str(exc)), code=err.get("code", "INTERNAL"), status=exc.code) from exc

    # ── Public API ────────────────────────────────────────────────────────────

    def status(self) -> PlatformStatus:
        """GET /platform/status — public health check, no API key needed."""
        url = f"{self._base}/platform/status"
        req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            err = json.loads(exc.read().decode()) if exc.read else {"error": str(exc), "code": "INTERNAL"}
            raise AegisError(err.get("error", str(exc)), code=err.get("code", "INTERNAL"), status=exc.code) from exc
        data = _validate_envelope(raw)
        return PlatformStatus(
            version=data["version"],
            contract_version=data["contract_version"],
            total_agents=data["total_agents"],
            chain_valid=data["chain_valid"],
            audit_chain_hash=data["audit_chain_hash"],
            available=data["available"],
            reason=data.get("reason"),
        )

    def collaborate(self, objective: str, mode: Mode = "analysis", live: bool = False) -> CollaborationResult:
        """POST /platform/collaborate — synchronous 39-dept swarm.

        Args:
            objective: Business objective to analyse (e.g. "Enter EU fintech Q4 2026").
            mode: One of revenue | analysis | gtm | retention | competitive | technical |
                  regulatory | fundraising.
            live: True = live Claude Opus 4.8 inference; False = demo mode (free, fast).

        Returns:
            CollaborationResult with 39 artifacts, constitutional audit, and audit_chain_hash.

        Raises:
            AegisError: On HTTP error or malformed envelope.
        """
        raw = self._request("POST", "/platform/collaborate", {"objective": objective, "mode": mode, "live": live})
        return CollaborationResult._from_dict(_validate_envelope(raw))

    def start_execution(self, objective: str, mode: Mode = "analysis", live: bool = False) -> ExecutionHandle:
        """POST /platform/executions — async initiation.  Returns immediately; stream or poll for result."""
        raw = self._request("POST", "/platform/executions", {"objective": objective, "mode": mode, "live": live})
        return ExecutionHandle(
            execution_id=raw["execution_id"],
            stream_url=raw["stream_url"],
            _client=self,
        )

    def get_execution(self, execution_id: str) -> CollaborationResult:
        """GET /platform/executions/{id} — retrieve a completed execution."""
        raw = self._request("GET", f"/platform/executions/{execution_id}")
        return CollaborationResult._from_dict(_validate_envelope(raw))

    def delete_execution(self, execution_id: str) -> None:
        """DELETE /platform/executions/{id} — remove a stored execution result."""
        url = f"{self._base}/platform/executions/{execution_id}"
        req = urllib.request.Request(url, headers=self._headers(), method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout):
                pass
        except urllib.error.HTTPError as exc:
            err = {"error": str(exc), "code": "INTERNAL"}
            raise AegisError(err["error"], code=err["code"], status=exc.code) from exc

    def _stream_events(self, execution_id: str) -> Generator[dict[str, Any], None, None]:
        """Internal SSE consumer for ExecutionHandle.stream()."""
        url = f"{self._base}/platform/executions/live?id={execution_id}"
        headers = {**self._headers(), "Accept": "text/event-stream"}
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                buf = ""
                for raw_line in resp:
                    line = raw_line.decode("utf-8").rstrip("\n")
                    if line.startswith("data: "):
                        buf = line[6:]
                    elif line == "" and buf:
                        try:
                            event = json.loads(buf)
                            yield event
                            if event.get("type") in ("completion", "error"):
                                return
                        except json.JSONDecodeError:
                            pass
                        buf = ""
        except urllib.error.HTTPError as exc:
            err = {"error": str(exc), "code": "INTERNAL"}
            raise AegisError(err["error"], code=err["code"], status=exc.code) from exc
