#!/usr/bin/env python3
"""Classify GitHub Actions job execution before interpreting PASS/FAIL.

The run-level conclusion is retained as provenance only. Execution state is
derived from job/step observables so continue-on-error cannot manufacture a
false execution-success signal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = "AEGIS_CI_EXECUTION_SIGNATURE_V1"

EXECUTED = "EXECUTED"
NOT_EXECUTED = "NOT_EXECUTED"
UNKNOWN = "UNKNOWN"

PASS = "PASS"
FAIL = "FAIL"
INCOMPLETE = "INCOMPLETE"
NOT_APPLICABLE = "NOT_APPLICABLE"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _delta_ms(later: Any, earlier: Any) -> int | None:
    a = _parse_time(later)
    b = _parse_time(earlier)
    if a is None or b is None:
        return None
    return int((a - b).total_seconds() * 1000)


def classify_execution(job: dict[str, Any]) -> tuple[str, str]:
    """Never use run.conclusion to decide whether work executed."""
    if "steps" not in job:
        return UNKNOWN, "STEPS_FIELD_MISSING"

    steps = job["steps"]
    if not isinstance(steps, list):
        return UNKNOWN, "STEPS_NOT_ARRAY"

    if len(steps) > 0:
        return EXECUTED, "STEP_RECORDS_OBSERVED"

    conclusion = str(job.get("conclusion") or "").lower()
    status = str(job.get("status") or "").lower()

    if conclusion == "skipped":
        return NOT_EXECUTED, "JOB_SKIPPED"

    if status == "completed":
        return NOT_EXECUTED, "COMPLETED_WITH_ZERO_STEPS"

    return UNKNOWN, "ZERO_STEPS_NONTERMINAL"


def classify_outcome(execution_state: str, job: dict[str, Any]) -> str:
    if execution_state != EXECUTED:
        return NOT_APPLICABLE

    conclusion = str(job.get("conclusion") or "").lower()
    if conclusion == "success":
        return PASS
    if conclusion == "failure":
        return FAIL
    if conclusion in {"cancelled", "timed_out", "action_required", "startup_failure"}:
        return INCOMPLETE
    return INCOMPLETE


def build_signature(
    run: dict[str, Any],
    job: dict[str, Any],
    *,
    log_status: int | None = None,
) -> dict[str, Any]:
    execution_state, execution_reason = classify_execution(job)
    outcome = classify_outcome(execution_state, job)

    steps = job.get("steps")
    step_count = len(steps) if isinstance(steps, list) else None

    queue_delay_ms = _delta_ms(job.get("started_at"), run.get("created_at"))
    execution_duration_ms = _delta_ms(job.get("completed_at"), job.get("started_at"))

    execution_projection = {
        "queue_delay_ms": queue_delay_ms,
        "step_count": step_count,
        "log_status": log_status,
    }
    execution_signature_sha256 = sha256_hex(execution_projection)

    run_conclusion = run.get("conclusion")
    job_conclusion = job.get("conclusion")
    masked_job_failure = (
        str(run_conclusion).lower() == "success"
        and str(job_conclusion).lower() not in {"success", "skipped", "none", ""}
    )

    result = {
        "schema": SCHEMA,
        "run_id": run.get("id"),
        "job_id": job.get("id"),
        "workflow_name": run.get("name"),
        "head_sha": run.get("head_sha"),
        "run_conclusion": run_conclusion,
        "run_conclusion_semantic_role": "PROVENANCE_ONLY",
        "job_conclusion": job_conclusion,
        "execution_state": execution_state,
        "execution_reason": execution_reason,
        "outcome": outcome,
        "masked_job_failure": masked_job_failure,
        "observables": {
            "created_at": run.get("created_at"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "queue_delay_ms": queue_delay_ms,
            "execution_duration_ms": execution_duration_ms,
            "step_count": step_count,
            "log_status": log_status,
        },
        "execution_projection": execution_projection,
        "execution_signature_sha256": execution_signature_sha256,
        "authority_effect": "NONE",
    }
    result["receipt_sha256"] = sha256_hex(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-json", required=True)
    parser.add_argument("--job-json", required=True)
    parser.add_argument("--log-status", type=int, default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    run = json.loads(Path(args.run_json).read_text(encoding="utf-8"))
    job = json.loads(Path(args.job_json).read_text(encoding="utf-8"))
    result = build_signature(run, job, log_status=args.log_status)

    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
