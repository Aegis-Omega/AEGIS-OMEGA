"""Coordinate and digest binding gates for QuantumManifold Scheduler v0.1.

Repository ancestry is deliberately supplied by an external exact-head resolver;
this module never fabricates network or repository authority.
"""
from __future__ import annotations

import re
from collections.abc import Callable

BASELINE_DIGEST = "457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404"
_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")


def validate_baseline_digest(baseline_digest: str) -> None:
    """Require the immutable AEGIS Master Notebook v0.4 baseline identity."""
    if baseline_digest != BASELINE_DIGEST:
        raise ValueError("BASELINE_BINDING_MISMATCH")


def validate_source_head(
    source_head_sha: str,
    *,
    ancestor_check: Callable[[str], bool],
) -> None:
    """Require lexical SHA validity and a positive external ancestry verdict."""
    if not isinstance(source_head_sha, str) or _SHA1_RE.fullmatch(source_head_sha) is None:
        raise ValueError("SOURCE_HEAD_INVALID")

    try:
        verdict = ancestor_check(source_head_sha)
    except Exception as exc:
        raise ValueError("SOURCE_HEAD_INVALID") from exc

    if verdict is not True:
        raise ValueError("SOURCE_HEAD_INVALID")


def validate_reality_snapshot_digest(recorded_digest: str, recomputed_digest: str) -> None:
    """Require the recorded reality snapshot digest to match recomputation."""
    if recorded_digest != recomputed_digest:
        raise ValueError("REALITY_DIGEST_MISMATCH")


def validate_scheduler_policy_digest(recorded_digest: str, recomputed_digest: str) -> None:
    """Require the recorded scheduler policy digest to match recomputation."""
    if recorded_digest != recomputed_digest:
        raise ValueError("SCHEDULER_POLICY_MISMATCH")
