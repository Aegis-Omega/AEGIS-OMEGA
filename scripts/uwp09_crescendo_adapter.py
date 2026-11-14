#!/usr/bin/env python3
"""UWP-09 adapter for offline Crescendo V2.1 receipts, not an outcome grader.

This file preserves the existing #757 fixture contract and #758 promotion gates.
It validates 30+ *planned* A/B/C slots, inventories optional unauthenticated
local run reports, and never attests execution, independent review or authority.
No network, model APIs, credentials, skill-tree edits, or production writes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "aegis.crescendo.preregistration.v1"
OBS_SCHEMA = "aegis.crescendo.local-observations.v1"
RECEIPT_SCHEMA = "aegis.uwp09.crescendo-checkpoint.v1"
ARMS = {"A", "B", "C"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_FILE = 2 * 1024 * 1024


class InvalidEvidence(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise InvalidEvidence(reason)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate JSON key: " + key)
        value[key] = item
    return value


def reject_constant(value):
    raise InvalidEvidence("nonfinite JSON number: " + value)


def load_json(path: Path):
    require(path.is_file(), "input file does not exist")
    require(path.stat().st_size <= MAX_FILE, "input exceeds 2 MiB")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def is_sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def validate_prereg(payload):
    require(isinstance(payload, dict), "preregistration must be an object")
    require(payload.get("schema") == SCHEMA, "unknown preregistration schema")
    require(payload.get("status") == "PLAN_ONLY_NOT_RUN", "preregistration must remain NOT_RUN")
    require(isinstance(payload.get("candidate"), str) and 0 < len(payload["candidate"]) <= 128,
            "missing/invalid candidate identity")
    description = payload.get("arms")
    require(isinstance(description, dict) and set(description) == ARMS,
            "expected exactly A/B/C arms")
    require(all(isinstance(x, str) and x.strip() for x in description.values()),
            "arm descriptions required")
    design = payload.get("design")
    require(isinstance(design, dict), "design object missing")
    slots = design.get("trial_slots")
    requested = design.get("paired_cases_per_candidate")
    require(type(requested) is int and 30 <= requested <= 512,
            "at least 30 and at most 512 preregistered pairs required")
    require(isinstance(slots, list) and len(slots) == requested,
            "trial slot count differs from preregistered denominator")
    ids, seeds = set(), set()
    for index, slot in enumerate(slots):
        require(isinstance(slot, dict) and set(slot) == {
            "pair_id", "case_fixture", "variant_seed", "arms", "status"
        }, f"slot[{index}] fields mismatch")
        pair_id, seed = slot["pair_id"], slot["variant_seed"]
        require(isinstance(pair_id, str) and re.fullmatch(r"[A-Za-z0-9-]{4,64}", pair_id)
                and pair_id not in ids, f"slot[{index}] missing/duplicate pair_id")
        require(type(seed) is int and seed >= 0 and seed not in seeds,
                f"slot[{index}] invalid/duplicate seed")
        require(slot["arms"] == ["A", "B", "C"], f"slot[{index}] arms/order mismatch")
        require(slot["status"] == "NOT_RUN" and slot["case_fixture"] == "NOT_ASSIGNED",
                f"slot[{index}] falsely claims an executed/assigned test")
        ids.add(pair_id)
        seeds.add(seed)
    return ids


def validate_observations(payload, candidate, pairs):
    if payload is None:
        return [], 0, 0
    require(isinstance(payload, dict) and set(payload) == {"schema", "candidate", "records"},
            "observations fields mismatch")
    require(payload["schema"] == OBS_SCHEMA and payload["candidate"] == candidate,
            "observations schema/candidate mismatch")
    records = payload["records"]
    require(isinstance(records, list) and len(records) <= 3 * len(pairs),
            "invalid observations count")
    seen = set()
    case_digests = {}
    for i, item in enumerate(records):
        require(isinstance(item, dict) and set(item) == {
            "pair_id", "arm", "case_sha256", "run_sha256", "provider", "model",
            "transcript_integrity", "machine_verdict", "evidence_origin", "review_authentication"
        }, f"record[{i}] fields mismatch")
        key = (item["pair_id"], item["arm"])
        require(item["pair_id"] in pairs and item["arm"] in ARMS and key not in seen,
                f"record[{i}] unknown pair/arm or duplicate")
        seen.add(key)
        require(is_sha(item["case_sha256"]) and is_sha(item["run_sha256"]),
                f"record[{i}] source digests required")
        require(item["evidence_origin"] == "LOCAL_SELF_REPORT"
                and item["review_authentication"] == "UNKNOWN",
                f"record[{i}] unauthenticated evidence may not claim approval")
        require(item["transcript_integrity"] in {"SELF_CONSISTENT", "INVALID"},
                f"record[{i}] invalid transcript status")
        require(item["machine_verdict"] in {
            "PROVISIONAL_RECORD_CONSISTENT", "FAIL", "REVIEW_REQUIRED"
        }, f"record[{i}] invalid local machine verdict")
        for key_name in ("provider", "model"):
            val = item[key_name]
            require(isinstance(val, str) and 0 < len(val.strip()) <= 128,
                    f"record[{i}] {key_name} required")
        old = case_digests.setdefault(item["pair_id"], item["case_sha256"])
        require(old == item["case_sha256"], f"record[{i}] paired case digest mismatch")
    complete_reported_pairs = sum(
        all((pair_id, arm) in seen for arm in ARMS) for pair_id in pairs
    )
    reported_failures = sum(x["machine_verdict"] == "FAIL" or
                            x["transcript_integrity"] == "INVALID" for x in records)
    return records, complete_reported_pairs, reported_failures


def checkpoint(prereg, prereg_hash, observations=None, runner_sha="UNKNOWN"):
    require(is_sha(prereg_hash), "preregistration digest must be SHA-256")
    require(runner_sha == "UNKNOWN" or is_sha(runner_sha),
            "runner digest must be SHA-256 or UNKNOWN")
    ids = validate_prereg(prereg)
    records, complete, failures = validate_observations(
        observations, prereg["candidate"], ids
    )
    return {
        "schema": RECEIPT_SCHEMA,
        "candidate": prereg["candidate"],
        "status": "UNAUTHENTICATED_REPORTS" if records else "PLAN_ONLY_NOT_RUN",
        "preregistration_sha256": prereg_hash,
        "runner_archive_sha256": runner_sha,
        "registered_pairs": len(ids),
        "registered_arm_slots": 3 * len(ids),
        "locally_reported_arm_records": len(records),
        "complete_pairs_locally_reported": complete,
        "reported_failure_records": failures,
        "independently_authenticated_arm_records": 0,
        "verified_execution_denominator": 0,
        "verified_success_rate": None,
        "verified_false_pass_rate": None,
        "verified_cost": None,
        "verified_latency": None,
        "confidence_intervals": None,
        "hidden_holdout": "NOT_PROVIDED_TO_PUBLIC_ADAPTER",
        "independent_reproducibility": "NOT_VERIFIED",
        "promotion_status": "HOLD",
        "world_best": "UNESTABLISHED",
        "authority_effect": "NONE",
        "limitations": [
            "A valid preregistration is not an executed experiment.",
            "Local hash chains and local graders do not authenticate model runs or reviewers.",
            "No metrics, cross-agent robustness, or capability promotion are established."
        ]
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prereg", type=Path, required=True)
    p.add_argument("--expected-prereg-sha256", required=True)
    p.add_argument("--runner-archive-sha256", default="UNKNOWN")
    p.add_argument("--observations", type=Path)
    args = p.parse_args(argv)
    try:
        require(is_sha(args.expected_prereg_sha256), "expected prereg digest is malformed")
        data = args.prereg.read_bytes()
        require(len(data) <= MAX_FILE, "preregistration exceeds 2 MiB")
        observed_hash = hashlib.sha256(data).hexdigest()
        require(observed_hash == args.expected_prereg_sha256,
                "preregistration source digest mismatch")
        prereg = load_json(args.prereg)
        obs = load_json(args.observations) if args.observations else None
        result = checkpoint(prereg, observed_hash, obs, args.runner_archive_sha256)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(json.dumps({"schema": RECEIPT_SCHEMA, "status": "INVALID_INPUT",
                          "authority_effect": "NONE", "promotion_status": "HOLD",
                          "error": str(exc)}, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
