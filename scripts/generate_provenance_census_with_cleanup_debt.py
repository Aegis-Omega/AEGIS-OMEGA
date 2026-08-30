#!/usr/bin/env python3
"""Temporary live-census adapter for an explicitly classified cleanup ref.

The canonical generator owns legitimate post-baseline repository topology,
including the open PR #347 constructive-prime-trig proof lane. This adapter
exists only because the assistant created ``tmp-unused`` while working on the
integration branch.

Deleting remote refs is intentionally outside the current no-destructive-action
authority boundary. Rather than hiding that ref or letting it contaminate the
frozen 150-head baseline, this adapter classifies it as post-baseline tooling
cleanup debt and raises the live expected head count by exactly one.

When the operator authorizes deletion of ``tmp-unused``, remove this adapter and
restore the canonical workflow to ``generate_provenance_census.py``.
"""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

# This file is intentionally executable both as a script and as a module. When
# invoked as ``python scripts/<name>.py``, Python puts ``scripts/`` rather than
# the repository root on sys.path, so the namespace-package import below would
# otherwise fail before the census can run.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import generate_provenance_census as base


CLEANUP_BRANCH = "tmp-unused"
CLEANUP_DISPOSITION = "TOOLING_ACCIDENT_CLEANUP_PENDING"

# Preserve the canonical frozen baseline and legitimate post-baseline topology;
# overlay only the one cleanup ref.
base.POST_BASELINE_BRANCHES = frozenset(
    set(base.POST_BASELINE_BRANCHES) | {CLEANUP_BRANCH}
)
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
