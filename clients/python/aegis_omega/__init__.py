"""
AEGIS-Ω Agent Platform Python SDK
===================================
Constitutional AI governance platform.
39 autonomous Mythos-level agents, replay-certifiable.

Quick start
-----------
    from aegis_omega import Platform

    p = Platform(api_key="sk-...", base_url="https://aegis-vertex.aegisomega.com")

    result  = p.collaborate("Launch a SaaS product", mode="revenue")
    print(result.projection.first_year_arr_usd)

    for event in p.stream("Generate growth strategy"):
        if event.done:
            break
        print(event.role, "→", event.output)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterator

import httpx

from .models import (
    AgentResult,
    CatalogResult,
    CertifyResult,
    CollaborateResult,
    StreamEvent,
)

__all__ = [
    "Platform",
    "PlatformError",
    "AgentResult",
    "CatalogResult",
    "CertifyResult",
    "CollaborateResult",
    "StreamEvent",
]

_DEFAULT_TIMEOUT = 120.0          # seconds — governed pipelines can be slow
_SSE_TIMEOUT     = 300.0          # seconds — streaming sessions


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class PlatformError(Exception):
    """Raised when the AEGIS-Ω platform returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"PlatformError {status_code}: {detail}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _raise_for_status(response: httpx.Response) -> None:
    """Raise PlatformError for any non-2xx response."""
    if response.is_success:
        return
    try:
        body = response.json()
        detail = body.get("detail") or body.get("message") or response.text
    except Exception:
        detail = response.text or "(no body)"
    raise PlatformError(status_code=response.status_code, detail=str(detail))


def _parse_sse_line(line: str) -> dict[str, Any] | None:
    """
    Parse a single SSE line.

    Handles:
        data: {...}
        data: [DONE]
    Returns the parsed JSON dict, {"done": True} sentinel, or None to skip.
    """
    if not line.startswith("data:"):
        return None
    payload = line[len("data:"):].strip()
    if payload in ("[DONE]", ""):
        return {"done": True}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Platform
# ---------------------------------------------------------------------------

class Platform:
    """
    Synchronous client for the AEGIS-Ω Agent Platform.

    Parameters
    ----------
    api_key:
        Bearer API key sent in the ``x-api-key`` header.
    base_url:
        Root URL of the platform deployment, e.g.
        ``"https://aegis-vertex.aegisomega.com"`` or ``"http://localhost:8080"``.
    timeout:
        Default request timeout in seconds (default 120).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://aegis-vertex.aegisomega.com",
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must be a non-empty string.")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(
            headers={
                "x-api-key": api_key,
                "Accept": "application/json",
                "User-Agent": "aegis-omega-python/1.0.0",
            },
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Low-level request helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        response = self._client.get(url, **kwargs)
        _raise_for_status(response)
        return response.json()

    def _post(self, path: str, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        response = self._client.post(url, json=body, **kwargs)
        _raise_for_status(response)
        return response.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collaborate(
        self,
        objective: str,
        mode: str = "revenue",
        live: bool = False,
    ) -> CollaborateResult:
        """
        Run a full governed multi-department collaboration pipeline.

        POST /platform/collaborate

        Parameters
        ----------
        objective:
            Business objective or problem statement for the agent swarm.
        mode:
            Collaboration mode — ``"revenue"`` (default) targets KAN-scored
            revenue projections; other modes are platform-defined.
        live:
            When ``True``, the platform uses live inference rather than cached
            constitutional envelopes.

        Returns
        -------
        CollaborateResult
            Fully typed result including ``projection``, ``stages``, and
            ``chain_valid`` integrity flag.
        """
        body = {"objective": objective, "mode": mode, "live": live}
        data = self._post("/platform/collaborate", body)
        return CollaborateResult.from_dict(data)

    def stream(
        self,
        objective: str,
        live: bool = False,
    ) -> Iterator[StreamEvent]:
        """
        Stream a collaboration pipeline as Server-Sent Events.

        POST /platform/stream

        Yields :class:`StreamEvent` objects as they arrive.  The final event
        will have ``done=True``; callers should stop iterating at that point.

        Parameters
        ----------
        objective:
            Business objective forwarded to the agent swarm.
        live:
            Use live inference when ``True``.

        Yields
        ------
        StreamEvent
        """
        url = f"{self._base_url}/platform/stream"
        body = {"objective": objective, "live": live}

        with self._client.stream(
            "POST",
            url,
            json=body,
            headers={"Accept": "text/event-stream"},
            timeout=_SSE_TIMEOUT,
        ) as response:
            _raise_for_status(response)
            for raw_line in response.iter_lines():
                parsed = _parse_sse_line(raw_line)
                if parsed is None:
                    continue
                event = StreamEvent.from_dict(parsed)
                yield event
                if event.done:
                    return

    def agent(
        self,
        role: str,
        task: str,
        cycles: int = 3,
    ) -> AgentResult:
        """
        Execute a single governed agent by role.

        POST /agents/run

        Parameters
        ----------
        role:
            Mythos-level agent role identifier (e.g. ``"Prometheus"``,
            ``"Athena"``, ``"Hermes"``).
        task:
            Plain-text task description for the agent.
        cycles:
            Number of RALPH loop cycles to run (default 3).

        Returns
        -------
        AgentResult
            Includes ``is_valid``, ``ralph_cycles``, and the full
            ``governance`` metadata envelope.
        """
        body = {"role": role, "task": task, "cycles": cycles}
        data = self._post("/agents/run", body)
        return AgentResult.from_dict(data)

    def catalog(self) -> CatalogResult:
        """
        Retrieve the full agent catalog.

        GET /platform/catalog

        Returns
        -------
        CatalogResult
            Platform metadata, agent roster, and pricing tiers.
        """
        data = self._get("/platform/catalog")
        return CatalogResult.from_dict(data)

    def certify(self) -> CertifyResult:
        """
        Certify the integrity of the platform's governance audit chain.

        GET /v1/audit/certify

        Returns
        -------
        CertifyResult
            ``is_valid`` flag, ``entry_count``, and ``terminal_hash`` of the
            replay-certifiable hash chain.
        """
        data = self._get("/v1/audit/certify")
        return CertifyResult.from_dict(data)

    def status(self) -> dict[str, Any]:
        """
        Return raw platform status.

        GET /platform/status

        Returns
        -------
        dict
            Raw JSON payload from the platform (schema is version-dependent).
        """
        return self._get("/platform/status")

    def schedule_revenue(
        self,
        objective: str | None = None,
        live: bool = True,
    ) -> dict[str, Any]:
        """
        Schedule a recurring revenue-focused collaboration run.

        POST /platform/schedule/revenue

        Parameters
        ----------
        objective:
            Optional override objective; the platform uses its default
            revenue-optimisation objective when ``None``.
        live:
            Run with live inference (default ``True``).

        Returns
        -------
        dict
            Raw JSON response, typically containing a ``schedule_id`` and
            ``next_run`` timestamp.
        """
        body: dict[str, Any] = {"live": live}
        if objective is not None:
            body["objective"] = objective
        return self._post("/platform/schedule/revenue", body)

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "Platform":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
