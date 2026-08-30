#!/usr/bin/env python3
"""Temporary live-census adapter for an explicitly classified cleanup ref.

This adapter exists because the assistant created ``tmp-unused`` while working
on the integration branch. Deleting remote refs is intentionally outside the
current no-destructive-action authority boundary. Rather than hiding that ref
or letting it contaminate the frozen 150-head baseline, this adapter classifies
it as post-baseline tooling cleanup debt and raises the live expected count by
exactly one.

When the operator authorizes deletion of ``tmp-unused``, remove this adapter and
restore the canonical workflow to ``generate_provenance_census.py``.
"""
from __future__ import annotations

from typing import Any

from scripts import generate_provenance_census as base


CLEANUP_BRANCH = "tmp-unused"
CLEANUP_DISPOSITION = "TOOLING_ACCIDENT_CLEANUP_PENDING"

base.POST_BASELINE_BRANCHES = frozenset(set(base.POST_BASELINE_BRANCHES) | {CLEANUP_BRANCH})
base.EXPECTED_LIVE_HEAD_COUNT = base.EXPECTED_LIVE_HEAD_COUNT + 1

_original_generate = base.generate


def generate(token: str | None) -> dict[str, Any]:
    payload = _original_generate(token)
    payload["critical_dispositions"]["REF_tmp-unused"] = {
        "head_ref": CLEANUP_BRANCH,
        "disposition": CLEANUP_DISPOSITION,
        "authority": "NONE",
        "reason": (
            "Assistant-created empty tooling ref. It is classified so live census remains exact; "
            "it carries no research, execution, effect, admission, AGI, or RH authority."
        ),
    }
    return payload


base.generate = generate


if __name__ == "__main__":
    raise SystemExit(base.main())
