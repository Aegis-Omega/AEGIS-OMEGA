"""Stale-result, replay, and restart guards for QuantumManifold v0.1.

These guards enforce fail-closed boundaries around coordinates and replay state.
They do not implement durable storage; instead, restart admission requires an
externally persisted authoritative root to be supplied and validated.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, MutableSet

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_COORDINATE_FIELDS = (
    "source_head_sha",
    "reality_snapshot_digest",
    "obligation_digest",
)


def _require_digest(value: object, error: str) -> str:
    if not isinstance(value, str) or _HEX64_RE.fullmatch(value) is None:
        raise ValueError(error)
    return value


def _validate_coordinate(coordinate: object) -> Mapping[str, object]:
    if not isinstance(coordinate, Mapping):
        raise ValueError("STALE_RESULT_REQUIRES_REBASE")
    if any(field not in coordinate for field in _COORDINATE_FIELDS):
        raise ValueError("STALE_RESULT_REQUIRES_REBASE")

    head = coordinate.get("source_head_sha")
    if not isinstance(head, str) or _SHA1_RE.fullmatch(head) is None:
        raise ValueError("STALE_RESULT_REQUIRES_REBASE")
    _require_digest(coordinate.get("reality_snapshot_digest"), "STALE_RESULT_REQUIRES_REBASE")
    _require_digest(coordinate.get("obligation_digest"), "STALE_RESULT_REQUIRES_REBASE")
    return coordinate


def validate_result_freshness(*, bound: object, current: object) -> None:
    """Require result coordinates to match the current active coordinate exactly."""
    bound_coord = _validate_coordinate(bound)
    current_coord = _validate_coordinate(current)
    for field in _COORDINATE_FIELDS:
        if bound_coord[field] != current_coord[field]:
            raise ValueError("STALE_RESULT_REQUIRES_REBASE")


def consume_execution_intent(intent_digest: object, *, consumed: MutableSet[str]) -> None:
    """Consume one execution-intent digest exactly once within the supplied state root."""
    digest = _require_digest(intent_digest, "EXECUTION_INTENT_REPLAY")
    if digest in consumed:
        raise ValueError("EXECUTION_INTENT_REPLAY")
    consumed.add(digest)


def validate_replay_state(
    *,
    recorded_reality_digest: object,
    reconstructed_reality_digest: object,
) -> None:
    """Require deterministic replay to reconstruct the same Reality Graph digest."""
    recorded = _require_digest(recorded_reality_digest, "REPLAY_STATE_DIVERGENCE")
    reconstructed = _require_digest(reconstructed_reality_digest, "REPLAY_STATE_DIVERGENCE")
    if recorded != reconstructed:
        raise ValueError("REPLAY_STATE_DIVERGENCE")


def require_persisted_authoritative_root(root_digest: object) -> str:
    """Reject restart when no externally persisted authoritative state root is available."""
    return _require_digest(root_digest, "STATE_RESET_EXPOSURE")
