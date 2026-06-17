"""AEGIS-Ω async client — aiohttp-based, same contract as AegisClient."""
from __future__ import annotations

from typing import Any, AsyncGenerator, Literal

from .client import (
    AegisError, CollaborationResult, ExecutionHandle, Mode,
    PlatformStatus, BASE_URL, CONTRACT_VERSION, _validate_envelope,
)

try:
    import aiohttp
    _AIOHTTP = True
except ImportError:
    _AIOHTTP = False


class AsyncAegisClient:
    """Async AEGIS-Ω Platform client (requires aiohttp).

    Usage::

        async with AsyncAegisClient("aegis_your_key") as client:
            result = await client.collaborate("Enter EU fintech Q4 2026", mode="gtm")
            print(result.constitutional_audit.verdict)
    """

    def __init__(self, api_key: str, base_url: str = BASE_URL, timeout: int = 60) -> None:
        if not _AIOHTTP:
            raise ImportError("aiohttp is required for AsyncAegisClient: pip install aiohttp")
        if not api_key:
            raise ValueError("api_key is required")
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._session: aiohttp.ClientSession | None = None  # type: ignore[name-defined]

    async def __aenter__(self) -> "AsyncAegisClient":
        self._session = aiohttp.ClientSession(  # type: ignore[assignment]
            headers={"x-api-key": self._key, "Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=self._timeout),  # type: ignore[attr-defined]
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._session:
            await self._session.close()

    def _sess(self) -> Any:
        if self._session is None:
            raise RuntimeError("Use AsyncAegisClient as a context manager: async with AsyncAegisClient(...) as c:")
        return self._session

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._sess().request(method, f"{self._base}{path}", json=body) as resp:
            raw = await resp.json()
            if not resp.ok:
                raise AegisError(raw.get("error", str(resp.status)), code=raw.get("code", "INTERNAL"), status=resp.status)
            return raw  # type: ignore[return-value]

    async def status(self) -> PlatformStatus:
        async with self._sess().get(f"{self._base}/platform/status") as resp:
            raw = await resp.json()
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

    async def collaborate(self, objective: str, mode: Mode = "analysis", live: bool = False) -> CollaborationResult:
        raw = await self._request("POST", "/platform/collaborate", {"objective": objective, "mode": mode, "live": live})
        return CollaborationResult._from_dict(_validate_envelope(raw))

    async def start_execution(self, objective: str, mode: Mode = "analysis", live: bool = False) -> ExecutionHandle:
        raw = await self._request("POST", "/platform/executions", {"objective": objective, "mode": mode, "live": live})
        return ExecutionHandle(execution_id=raw["execution_id"], stream_url=raw["stream_url"], _client=None)  # type: ignore[arg-type]

    async def stream_execution(self, execution_id: str) -> AsyncGenerator[dict[str, Any], None]:
        """Async SSE consumer — yields one dict per SSE event until completion or error."""
        url = f"{self._base}/platform/executions/live?id={execution_id}"
        async with self._sess().get(url, headers={"Accept": "text/event-stream"}) as resp:
            buf = ""
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8").rstrip("\n")
                if line.startswith("data: "):
                    buf = line[6:]
                elif line == "" and buf:
                    try:
                        event = __import__("json").loads(buf)
                        yield event
                        if event.get("type") in ("completion", "error"):
                            return
                    except Exception:
                        pass
                    buf = ""
