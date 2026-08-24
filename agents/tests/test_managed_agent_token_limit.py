"""Regression tests for the Managed Agents per-session token ceiling."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agents.coordinator import ManagedAgentsClient
from agents.managed_agents import MANAGED_AGENT_MAX_TOKENS


@pytest.mark.parametrize("configured_max_tokens", [16_384, 32_768])
def test_managed_session_uses_shared_token_ceiling(configured_max_tokens: int) -> None:
    """Configured department limits cannot reach the Managed Agents API request."""
    stream = MagicMock()
    stream.__enter__.return_value = []
    stream.__exit__.return_value = None

    anthropic_client = MagicMock()
    anthropic_client.beta.sessions.create.return_value = SimpleNamespace(id="session_123")
    anthropic_client.beta.sessions.stream.return_value = stream

    client = object.__new__(ManagedAgentsClient)
    client._client = anthropic_client
    client._registry = {"engineering": "agent_123"}

    asyncio.run(
        client.run(
            "engineering",
            [{"role": "user", "content": "inspect the limit"}],
            "system",
            max_tokens=configured_max_tokens,
        )
    )

    anthropic_client.beta.sessions.create.assert_called_once_with(
        agent="agent_123",
        max_tokens=MANAGED_AGENT_MAX_TOKENS,
    )
