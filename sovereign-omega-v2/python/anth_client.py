"""
AEGIS-Ω Anthropic client factory — EPISTEMIC TIER: T1

Two transport tiers:
  1. Vertex AI (AnthropicVertex) — preferred on Cloud Run / GCP.
     Auth via Application Default Credentials (service account, no key needed).
     GCP-billed quotas are separate from direct-API limits and significantly higher.
     Set AEGIS_VERTEX_PROJECT (default: aegisomegav1) and
         AEGIS_VERTEX_REGION  (default: eu — EU multi-region for data residency).
     Force Vertex with AEGIS_USE_VERTEX=true; disable with AEGIS_USE_VERTEX=false.

  2. Direct Anthropic API (Anthropic) — local dev / non-GCP fallback.
     Requires ANTHROPIC_API_KEY in environment.

Prompt caching (make_cached_system):
  Wraps a system-prompt string as a cache_control=ephemeral content block.
  The Anthropic API caches it for 5 minutes; subsequent calls with the same
  text hit the cache, paying 10% of normal input-token cost and bypassing
  the input-token rate limit bucket for cached tokens.
  Net effect: ~90% reduction in input-token consumption on repeated swarm calls.
"""

from __future__ import annotations

import os
from typing import Union

_VERTEX_PROJECT = os.environ.get('AEGIS_VERTEX_PROJECT', 'aegisomegav1')
_VERTEX_REGION  = os.environ.get('AEGIS_VERTEX_REGION', 'eu')
_USE_VERTEX_ENV = os.environ.get('AEGIS_USE_VERTEX', '').lower()


def get_client():
    """
    Return the best available Anthropic client.

    Priority:
      AEGIS_USE_VERTEX=true  → Vertex AI (raises if ADC unavailable)
      (anything else)        → Direct API key (ANTHROPIC_API_KEY)

    Vertex is opt-in ONLY and is never auto-selected. On Cloud Run, Application
    Default Credentials are always present, and auto-selecting Vertex silently
    routed paid inference through Vertex AI billed to the GCP card. The default
    is now the direct API key; set AEGIS_USE_VERTEX=true to deliberately use
    Vertex.
    """
    if _USE_VERTEX_ENV == 'true':
        from anthropic import AnthropicVertex
        return AnthropicVertex(project_id=_VERTEX_PROJECT, region=_VERTEX_REGION)

    return _direct_client()


def _direct_client():
    """Return a direct Anthropic client using ANTHROPIC_API_KEY."""
    import anthropic
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise RuntimeError(
            'No Anthropic client available: set ANTHROPIC_API_KEY for local dev '
            'or run on Cloud Run with ADC for Vertex AI auth.'
        )
    return anthropic.Anthropic(api_key=api_key)


def is_vertex(client) -> bool:
    """True if client is an AnthropicVertex instance."""
    try:
        from anthropic import AnthropicVertex
        return isinstance(client, AnthropicVertex)
    except ImportError:
        return False


def make_cached_system(text: str) -> list[dict]:
    """
    Wrap a system-prompt string as a cached content block.

    Pass the return value as the `system=` parameter to client.messages.create().
    The API caches this block for 5 minutes; cache hits cost 10% of normal
    input tokens and do not count against the input-token rate-limit bucket.

    Compatible with both Anthropic and AnthropicVertex clients.
    """
    return [{'type': 'text', 'text': text, 'cache_control': {'type': 'ephemeral'}}]


# Convenience: pre-built client for module-level import
# (evaluated lazily to avoid startup failures in environments without ADC or API key)
_client_cache: Union[object, None] = None


def client():
    """Lazy singleton — re-used across requests in the same process."""
    global _client_cache
    if _client_cache is None:
        _client_cache = get_client()
    return _client_cache
