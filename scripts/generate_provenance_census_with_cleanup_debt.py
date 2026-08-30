#!/usr/bin/env python3
"""Live-census delta adapter for explicitly classified post-baseline refs.

The frozen generator preserves the original 150-head / 95-open-PR source
snapshot and intentionally fails on any unclassified topology drift. This
adapter records two later facts without rewriting that frozen baseline:

- PR #347 / ``proof/weil-constructive-prime-trig-v1`` is a legitimate
  post-baseline proof lane and remains an open draft;
- ``tmp-unused`` is an assistant-created empty tooling ref. Deleting remote
  refs is outside the current no-destructive-action authority boundary, so it
  is classified as cleanup debt with authority NONE until deletion is
  explicitly authorized.

When these deltas are consolidated or the cleanup ref is deleted, collapse the
corresponding overlay entries back into the canonical generator.
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


PRIME_TRIG_BRANCH = "proof/weil-constructive-prime-trig-v1"
PRIME_TRIG_PR_NUMBER = 347
CLEANUP_BRANCH = "tmp-unused"
CLEANUP_DISPOSITION = "TOOLING_ACCIDENT_CLEANUP_PENDING"

# Preserve the frozen source census. Only the live overlay grows.
base.POST_BASELINE_BRANCHES = frozenset(
    set(base.POST_BASELINE_BRANCHES) | {PRIME_TRIG_BRANCH, CLEANUP_BRANCH}
)
base.POST_BASELINE_PRS = frozenset(set(base.POST_BASELINE_PRS) | {PRIME_TRIG_PR_NUMBER})
base.REQUIRED_OPEN_POST_BASELINE_PRS = frozenset(
    set(base.REQUIRED_OPEN_POST_BASELINE_PRS) | {PRIME_TRIG_PR_NUMBER}
)
base.EXPECTED_LIVE_HEAD_COUNT = base.EXPECTED_LIVE_HEAD_COUNT + 2
base.EXPECTED_LIVE_OPEN_PRS = base.EXPECTED_LIVE_OPEN_PRS + 1
base.EXPECTED_LIVE_DRAFT_PRS = base.EXPECTED_LIVE_DRAFT_PRS + 1

_original_generate = base.generate


def generate(token: str | None) -> dict[str, Any]:
    payload = _original_generate(token)
    payload["critical_dispositions"]["PR_347"] = {
        "head_ref": PRIME_TRIG_BRANCH,
        "disposition": "POST_BASELINE_OPEN_PROOF_LANE",
        "authority": "NO_RH_AUTHORITY_PROMOTION",
        "reason": (
            "Created after the frozen census as a constructive prime-trigonometric proof lane. "
            "It is excluded from the 150-head/95-PR source snapshot but remains part of live topology."
        ),
    }
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
