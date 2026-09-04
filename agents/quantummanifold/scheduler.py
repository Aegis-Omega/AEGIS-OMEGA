"""Minimal non-authoritative scheduler module boundary for Phase 1.

Ranking is intentionally not implemented until Phase 2. This module exists only
because QM-RED-001 has established the absence contract and now moves GREEN.
"""
from __future__ import annotations

AUTHORITY_EFFECT = "NONE"


def rank_actions(*_args: object, **_kwargs: object) -> object:
    """Fail closed until the Phase 2 deterministic ranking implementation exists."""
    raise NotImplementedError("QUANTUMMANIFOLD_RANKING_IMPLEMENTATION_OPEN")
