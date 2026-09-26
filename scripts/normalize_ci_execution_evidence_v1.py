#!/usr/bin/env python3
"""AEGIS exact-head CI execution evidence normalizer v1.

Provider status labels are not epistemic conclusions. This module preserves raw
provider metadata while normalizing the execution evidence used by admission,
proof, and runtime consumers.

Core invariant:
    steps_count == 0  =>  NOT_RUN

A stale-head result is HISTORICAL even when it succeeded. Preview/deployment
checks are TRANSPORT_ONLY and can never satisfy repository admission.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Any, Mapping

_HEX40 = re.compile(r"^[0-9a-f]{40}$")


class NormalizedExecution(str, Enum):
    NOT_RUN = "NOT_RUN"
    HISTORICAL = "HISTORICAL"
    EXECUTED_PASS = "EXECUTED_PASS"
    EXECUTED_FAIL = "EXECUTED_FAIL"
    EXECUTED_INCOMPLETE = "EXECUTED_INCOMPLETE"
    TRANSPORT_ONLY = "TRANSPORT_ONLY"


@dataclass(frozen=True)
class NormalizedJob:
    normalized: NormalizedExecution
    expected_head_sha: str
    observed_head_sha: str
    steps_count: int
    raw_conclusion: str | None
    raw_status: str | None
    runner_id: int | None
    source: str = "github_actions_job"

    def as_dict(self) -> dict[str, Any]:
        return {
            "normalized": self.normalized.value,
            "expected_head_sha": self.expected_head_sha,
            "observed_head_sha": self.observed_head_sha,
            "steps_count": self.steps_count,
            "raw_conclusion": self.raw_conclusion,
            "raw_status": self.raw_status,
            "runner_id": self.runner_id,
            "source": self.source,
            "authority_effect": "NONE",
        }


def _hex40(value: str, field: str) -> str:
    if _HEX40.fullmatch(value) is None:
        raise ValueError(f"{field}_MUST_BE_LOWERCASE_HEX40")
    return value


def normalize_github_job(
    *,
    expected_head_sha: str,
    observed_head_sha: str,
    steps_count: int,
    conclusion: str | None,
    status: str | None = None,
    runner_id: int | None = None,
) -> NormalizedJob:
    expected_head_sha = _hex40(expected_head_sha, "EXPECTED_HEAD_SHA")
    observed_head_sha = _hex40(observed_head_sha, "OBSERVED_HEAD_SHA")
    if type(steps_count) is not int or steps_count < 0:
        raise ValueError("STEPS_COUNT_MUST_BE_NONNEGATIVE_INTEGER")

    if observed_head_sha != expected_head_sha:
        normalized = NormalizedExecution.HISTORICAL
    elif steps_count == 0 or conclusion == "skipped":
        normalized = NormalizedExecution.NOT_RUN
    elif conclusion == "success":
        normalized = NormalizedExecution.EXECUTED_PASS
    elif conclusion in {"failure", "action_required"}:
        normalized = NormalizedExecution.EXECUTED_FAIL
    else:
        # cancelled, timed_out, neutral, stale, in_progress, queued, null...
        # The job executed something but did not establish a pass/fail test
        # conclusion suitable for admission.
        normalized = NormalizedExecution.EXECUTED_INCOMPLETE

    return NormalizedJob(
        normalized=normalized,
        expected_head_sha=expected_head_sha,
        observed_head_sha=observed_head_sha,
        steps_count=steps_count,
        raw_conclusion=conclusion,
        raw_status=status,
        runner_id=runner_id,
    )


def normalize_preview_transport(
    raw: Mapping[str, Any],
    *,
    expected_head_sha: str,
    observed_head_sha: str,
) -> dict[str, Any]:
    _hex40(expected_head_sha, "EXPECTED_HEAD_SHA")
    _hex40(observed_head_sha, "OBSERVED_HEAD_SHA")
    return {
        "normalized": NormalizedExecution.TRANSPORT_ONLY.value,
        "expected_head_sha": expected_head_sha,
        "observed_head_sha": observed_head_sha,
        "head_match": expected_head_sha == observed_head_sha,
        "raw": dict(raw),
        "authority_effect": "NONE",
    }


def normalize_job_payload(payload: Mapping[str, Any], expected_head_sha: str) -> dict[str, Any]:
    steps = payload.get("steps")
    if not isinstance(steps, list):
        raise ValueError("JOB_STEPS_MUST_BE_LIST")
    head = payload.get("head_sha") or payload.get("observed_head_sha")
    if not isinstance(head, str):
        raise ValueError("JOB_HEAD_SHA_REQUIRED")
    runner = payload.get("runner_id")
    runner_id = runner if isinstance(runner, int) else None
    return normalize_github_job(
        expected_head_sha=expected_head_sha,
        observed_head_sha=head,
        steps_count=len(steps),
        conclusion=payload.get("conclusion") if isinstance(payload.get("conclusion"), str) else None,
        status=payload.get("status") if isinstance(payload.get("status"), str) else None,
        runner_id=runner_id,
    ).as_dict()


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--input", help="JSON file; stdin when omitted")
    args = parser.parse_args()
    source = open(args.input, encoding="utf-8") if args.input else sys.stdin
    try:
        payload = json.load(source)
    finally:
        if args.input:
            source.close()
    print(json.dumps(normalize_job_payload(payload, args.expected_head), indent=2, sort_keys=True))