"""Deterministic non-authoritative QuantumManifold scheduler primitives.

This module implements only the v0.1 ranking order established by QM-RED-013.
It emits recommendations and never grants execution or epistemic authority.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .fixed_point import require_canonical_metric

AUTHORITY_EFFECT = "NONE"
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_METRICS = (
    "ranking_score_ppm",
    "closure_leverage_ppm",
    "falsification_value_ppm",
    "cost_ppm",
)


def _validate_candidate(candidate: object) -> dict[str, Any]:
    if not isinstance(candidate, Mapping):
        raise ValueError("INVALID_CANDIDATE_ACTION")

    normalized = dict(candidate)
    digest = normalized.get("candidate_action_digest")
    if not isinstance(digest, str) or _DIGEST_RE.fullmatch(digest) is None:
        raise ValueError("INVALID_CANDIDATE_ACTION_DIGEST")

    for field in _REQUIRED_METRICS:
        if field not in normalized:
            raise ValueError("INVALID_CANDIDATE_ACTION")
        normalized[field] = require_canonical_metric(normalized[field])
    return normalized


def rank_actions(candidates: object) -> dict[str, Any]:
    """Select one candidate using the normative total deterministic order.

    Ordering key: (-score, -closure leverage, -falsification value, cost, digest).
    The selected object is a detached dictionary and carries no authority effect.
    """
    if isinstance(candidates, (str, bytes, bytearray)) or not isinstance(candidates, Sequence):
        raise ValueError("INVALID_CANDIDATE_SET")
    if not candidates:
        raise ValueError("EMPTY_CANDIDATE_SET")

    validated: list[dict[str, Any]] = []
    by_digest: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        normalized = _validate_candidate(candidate)
        digest = normalized["candidate_action_digest"]
        previous = by_digest.get(digest)
        if previous is not None:
            if previous != normalized:
                raise ValueError("CANDIDATE_DIGEST_COLLISION")
            raise ValueError("DUPLICATE_CANDIDATE_DIGEST")
        by_digest[digest] = normalized
        validated.append(normalized)

    selected = min(
        validated,
        key=lambda item: (
            -item["ranking_score_ppm"],
            -item["closure_leverage_ppm"],
            -item["falsification_value_ppm"],
            item["cost_ppm"],
            item["candidate_action_digest"],
        ),
    )
    return dict(selected)
