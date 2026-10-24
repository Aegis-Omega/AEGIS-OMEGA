#!/usr/bin/env python3
"""Validate an offline UWP benchmark manifest without scoring unrun tasks."""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

SCHEMA = "aegis.uwp.benchmark/1"
DOMAINS = {
    "code", "formal_math", "biology_science", "research_citations",
    "data_statistics", "ui_ux", "accessibility", "cybersecurity",
    "operations", "business_finance", "documentation_education",
    "media_creative", "agent_collaboration", "long_horizon_memory",
    "security_accessibility",
}
ARMS = {
    "aegis_candidate", "existing_internal", "external_reference",
    "no_change", "single_agent",
}
AXES = {
    "visual", "typography", "motion", "sonic", "narrative",
    "product_utility", "usability", "accessibility", "performance",
    "reliability", "privacy_safety", "originality_rights", "business_value",
}
STANDARD_FIELDS = {
    "id", "issuer", "publisher_url", "document_id", "edition_date",
    "status_at_observation", "domain_scope", "applicability_decision",
    "measurement_method", "checked_at",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_INPUT = 1024 * 1024


class InvalidManifest(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise InvalidManifest(reason)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise InvalidManifest(f"invalid JSON number: {value}")


def bounded_text(value, field, limit=1000):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit,
            f"{field}: bounded nonempty string required")


def digest(value, field):
    require(isinstance(value, str) and SHA256.fullmatch(value) is not None,
            f"{field}: SHA-256 digest required")


def validate_standard(item):
    require(isinstance(item, dict) and set(item) == STANDARD_FIELDS,
            "standard record fields mismatch")
    for key in STANDARD_FIELDS:
        bounded_text(item[key], f"standard.{key}")
    if item["publisher_url"] != "UNKNOWN":
        try:
            parsed = urlsplit(item["publisher_url"])
            require(parsed.scheme == "https" and bool(parsed.hostname)
                    and not parsed.username and not parsed.password
                    and parsed.port in (None, 443) and not parsed.fragment,
                    "standard.publisher_url must be HTTPS or UNKNOWN")
        except ValueError as exc:
            raise InvalidManifest("standard.publisher_url must be valid HTTPS or UNKNOWN") from exc
    if item["edition_date"] != "UNKNOWN":
        try:
            date.fromisoformat(item["edition_date"])
        except ValueError as exc:
            raise InvalidManifest("standard.edition_date must be ISO date or UNKNOWN") from exc
    if item["checked_at"] != "UNKNOWN":
        try:
            date.fromisoformat(item["checked_at"])
        except ValueError as exc:
            raise InvalidManifest("standard.checked_at must be ISO date or UNKNOWN") from exc


def validate_axis(axis, item, task_digest):
    require(isinstance(item, dict) and set(item) == {
        "status", "reason", "measurement_method", "evidence_sha256", "reviewer_ref"
    }, f"{axis}: axis fields mismatch")
    bounded_text(item["reason"], f"{axis}.reason")
    require(isinstance(item["status"], str)
            and item["status"] in {"MEASURED", "UNMEASURED", "NOT_APPLICABLE"},
            f"{axis}: invalid status")
    if item["status"] == "MEASURED":
        bounded_text(item["measurement_method"], f"{axis}.measurement_method")
        bounded_text(item["reviewer_ref"], f"{axis}.reviewer_ref")
        digest(item["evidence_sha256"], f"{axis}.evidence_sha256")
    elif item["status"] == "NOT_APPLICABLE":
        bounded_text(item["measurement_method"], f"{axis}.measurement_method")
        require(item["evidence_sha256"] == task_digest,
                f"{axis}: not-applicable rationale must bind to task bytes")
        require(item["reviewer_ref"] == "UNKNOWN",
                f"{axis}: reviewer identity is not authenticated")
    else:
        require(item["measurement_method"] == "UNKNOWN"
                and item["evidence_sha256"] == "UNKNOWN"
                and item["reviewer_ref"] == "UNKNOWN",
                f"{axis}: unmeasured disposition cannot carry measurement evidence")


def validate_case(case, ids):
    required = {
        "id", "domain", "difficulty", "task_text", "task_sha256", "expected_action",
        "abstention_correct", "fixture_source", "budget", "arm_revisions", "quality_axes",
        "standards", "run_state",
    }
    require(isinstance(case, dict) and set(case) == required, "task fields mismatch")
    bounded_text(case["id"], "task.id", 96)
    require(case["id"] not in ids, f"duplicate task id: {case['id']}")
    ids.add(case["id"])
    require(isinstance(case["domain"], str) and case["domain"] in DOMAINS,
            f"{case['id']}: unsupported domain")
    bounded_text(case["difficulty"], f"{case['id']}.difficulty", 96)
    digest(case["task_sha256"], f"{case['id']}.task_sha256")
    bounded_text(case["task_text"], f"{case['id']}.task_text", MAX_INPUT)
    task_bytes = case["task_text"].encode("utf-8")
    require(len(task_bytes) <= MAX_INPUT, f"{case['id']}: task text exceeds 1 MiB")
    require(hashlib.sha256(task_bytes).hexdigest()
            == case["task_sha256"], f"{case['id']}: task text digest mismatch")
    require(isinstance(case["expected_action"], str)
            and case["expected_action"] in {"ACT", "ABSTAIN"},
            f"{case['id']}: expected_action must be ACT or ABSTAIN")
    require(type(case["abstention_correct"]) is bool,
            f"{case['id']}: abstention_correct must be boolean")
    require(case["abstention_correct"] == (case["expected_action"] == "ABSTAIN"),
            f"{case['id']}: abstention truth conflicts with expected action")
    source = case["fixture_source"]
    require(isinstance(source, dict) and set(source) == {
        "reference", "baseline_blob", "candidate_blob", "test_blob", "review_state"
    }, f"{case['id']}: fixture source fields mismatch")
    bounded_text(source["reference"], f"{case['id']}.fixture_source.reference")
    for field in ("baseline_blob", "candidate_blob", "test_blob"):
        require(isinstance(source[field], str) and GIT_SHA.fullmatch(source[field]) is not None,
                f"{case['id']}.fixture_source.{field}: Git blob SHA required")
    require(source["review_state"] == "REPORTED_NOT_REVERIFIED",
            f"{case['id']}: fixture source must remain marked not reverified")
    budget = case["budget"]
    require(isinstance(budget, dict) and set(budget) == {
        "status", "wall_ms", "model_calls", "cost_microusd", "manual_interventions"
    }, f"{case['id']}: budget fields mismatch")
    require(isinstance(budget["status"], str)
            and budget["status"] in {"PREREGISTERED", "UNKNOWN"},
            f"{case['id']}: invalid budget status")
    if budget["status"] == "UNKNOWN":
        require(all(budget[key] == "UNKNOWN" for key in (
            "wall_ms", "model_calls", "cost_microusd", "manual_interventions"
        )), f"{case['id']}: unknown budget must be explicit")
    else:
        for key in ("wall_ms", "model_calls", "cost_microusd", "manual_interventions"):
            value = budget[key]
            require(type(value) is int and value >= 0,
                    f"{case['id']}.{key}: nonnegative integer required")
    revisions = case["arm_revisions"]
    require(isinstance(revisions, dict) and set(revisions) == ARMS,
            f"{case['id']}: all five comparison arms are required")
    for arm, revision in revisions.items():
        bounded_text(revision, f"{case['id']}.{arm}.revision", 128)
        require(revision == "UNKNOWN" or GIT_SHA.fullmatch(revision) is not None,
                f"{case['id']}.{arm}.revision must be exact Git SHA or UNKNOWN")
    axes = case["quality_axes"]
    require(isinstance(axes, dict) and set(axes) == AXES,
            f"{case['id']}: all 13 quality axes are required")
    for axis, item in axes.items():
        validate_axis(axis, item, case["task_sha256"])
    standards = case["standards"]
    require(isinstance(standards, list), f"{case['id']}: standards must be a list")
    standard_ids = set()
    for item in standards:
        validate_standard(item)
        require(item["id"] not in standard_ids, f"{case['id']}: duplicate standard id")
        standard_ids.add(item["id"])
    require(isinstance(case["run_state"], str) and case["run_state"] == "NOT_RUN",
            f"{case['id']}: this manifest validator does not accept execution claims")


def validate_manifest(payload):
    require(isinstance(payload, dict) and set(payload) == {
        "schema", "benchmark_id", "status", "comparison_arms", "cases"
    }, "manifest fields mismatch")
    require(payload["schema"] == SCHEMA, "unsupported benchmark schema")
    bounded_text(payload["benchmark_id"], "benchmark_id", 96)
    require(payload["status"] == "FIXTURE_ONLY", "only fixture-only manifests are accepted")
    require(payload["comparison_arms"] == sorted(ARMS),
            "comparison arms must be the five declared baselines")
    cases = payload["cases"]
    require(isinstance(cases, list) and 0 < len(cases) <= 512,
            "benchmark population must contain 1..512 task definitions")
    ids = set()
    for case in cases:
        validate_case(case, ids)
    return {
        "schema": "aegis.uwp.benchmark.receipt/1",
        "benchmark_id": payload["benchmark_id"],
        "status": "FIXTURE_ONLY_NOT_RUN",
        "population_denominator": len(cases),
        "executed_denominator": 0,
        "success_rate": None,
        "false_passes": None,
        "crash_recovery": None,
        "budget": None,
        "latency": None,
        "manual_interventions": None,
        "confidence_intervals": None,
        "hidden_holdout": "NOT_PROVIDED",
        "world_best": "UNESTABLISHED",
        "independent_reproducibility": "NOT_VERIFIED",
        "authority_effect": "NONE",
        "paired_evaluator": "NOT_AVAILABLE_IN_BASE",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    try:
        path = Path(args.input)
        require(path.stat().st_size <= MAX_INPUT, "manifest exceeds 1 MiB")
        payload = json.loads(path.read_text(encoding="utf-8"),
                             object_pairs_hook=unique_object,
                             parse_constant=reject_constant)
        result = validate_manifest(payload)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "schema": "aegis.uwp.benchmark.receipt/1",
            "status": "INVALID_INPUT",
            "error": str(exc),
            "authority_effect": "NONE",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
