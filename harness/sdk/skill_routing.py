"""Fail-closed routing decisions for the AEGIS coordinator.

The V2 skill registry separates declared capability from observed competence.
This module binds that rule to repository evidence and emits deterministic,
content-addressed routing receipts. It contains no model or network dependency.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from harness.sdk.skill_authority import (
    EvidenceVerifier,
    MIN_VALIDATED_RUNS,
    OBSERVED,
    UNOBSERVED,
    canonical_bytes,
    compute_registry_root,
    evaluate_registry,
    observation_state,
    safe_competency_score,
    sha256_hex,
)

ROUTING_RECEIPT_KIND = "AEGIS_COORDINATOR_ROUTING_RECEIPT_V1"
ADMITTED = "ADMITTED"
DENIED = "DENIED"


@dataclass(frozen=True)
class SkillRoutingReceipt:
    schema_version: str
    receipt_kind: str
    capability: str
    skill_id: str | None
    outcome: str
    authority_score: float
    observation_state: str
    validated_runs: int
    registry_root: str | None
    registry_receipt_hash: str | None
    reason_codes: tuple[str, ...]
    receipt_hash: str


def evidence_violations(
    skill: Mapping[str, Any] | None,
    *,
    repo_root: str | Path,
) -> tuple[str, ...]:
    """Validate the selected skill's evidence paths against the repository root."""
    if skill is None:
        return ("UNKNOWN_SKILL",)

    root = Path(repo_root).resolve()
    refs = skill.get("evidence_refs")
    violations: list[str] = []
    if not isinstance(refs, list) or not refs:
        return ("EVIDENCE_MISSING",)

    for ref in refs:
        if not isinstance(ref, str) or not ref.strip():
            violations.append("EVIDENCE_MALFORMED")
            continue
        candidate = (root / ref).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            violations.append(f"EVIDENCE_OUTSIDE_REPOSITORY:{ref}")
            continue
        if not candidate.is_file():
            violations.append(f"EVIDENCE_UNRESOLVED:{ref}")

    return tuple(sorted(set(violations)))


def _safe_runs(skill: Mapping[str, Any] | None) -> int:
    if skill is None:
        return 0
    runs = skill.get("validated_runs", 0)
    if isinstance(runs, bool) or not isinstance(runs, int) or runs < 0:
        return 0
    return runs


def decide_skill_routing(
    *,
    capability: str,
    skill_id: str | None,
    skill: Mapping[str, Any] | None,
    registry: Mapping[str, Any] | None,
    repo_root: str | Path,
    load_reason_codes: tuple[str, ...] = (),
    minimum_runs: int = MIN_VALIDATED_RUNS,
    evidence_verifier: EvidenceVerifier | None = None,
) -> SkillRoutingReceipt:
    """Return a deterministic authority decision for one capability.

    Any missing mapping, malformed registry, invalid evidence, unobserved state,
    insufficient run count, or malformed metric results in score 0 and DENIED.
    """
    reasons = list(load_reason_codes)
    registry_root: str | None = None
    registry_receipt_hash: str | None = None

    if registry is None:
        reasons.append("REGISTRY_UNAVAILABLE")
    else:
        registry_root_value = registry.get("registry_root")
        registry_root = registry_root_value if isinstance(registry_root_value, str) else None
        registry_receipt = evaluate_registry(registry, evidence_verifier=evidence_verifier)
        registry_receipt_hash = registry_receipt.receipt_hash
        if registry_receipt.outcome != ADMITTED:
            reasons.append("REGISTRY_INVALID")
            reasons.extend(f"REGISTRY:{item}" for item in registry_receipt.violations)

    if skill_id is None:
        reasons.append("UNMAPPED_CAPABILITY")
    elif skill is None:
        reasons.append("UNKNOWN_SKILL")

    runs = _safe_runs(skill)
    state = "UNKNOWN"
    if skill is not None:
        try:
            state = observation_state(skill)
        except (TypeError, ValueError):
            state = "MALFORMED"
            reasons.append("MALFORMED_OBSERVATION_STATE")

        reasons.extend(evidence_violations(skill, repo_root=repo_root))
        if state == UNOBSERVED:
            reasons.append("UNOBSERVED")
        if runs < minimum_runs:
            reasons.append("INSUFFICIENT_VALIDATED_RUNS")

    score = safe_competency_score(
        skill, minimum_runs=minimum_runs, evidence_verifier=evidence_verifier
    )
    if score <= 0.0:
        reasons.append("ZERO_AUTHORITY")

    reasons = sorted(set(reasons))
    outcome = ADMITTED if not reasons else DENIED
    if outcome == DENIED:
        score = 0.0

    body = {
        "schema_version": "1.0.0",
        "receipt_kind": ROUTING_RECEIPT_KIND,
        "capability": capability,
        "skill_id": skill_id,
        "outcome": outcome,
        "authority_score": score,
        "observation_state": state,
        "validated_runs": runs,
        "registry_root": registry_root,
        "registry_receipt_hash": registry_receipt_hash,
        "reason_codes": tuple(reasons),
    }
    receipt_hash = sha256_hex(canonical_bytes({
        "domain": ROUTING_RECEIPT_KIND,
        "receipt": body,
    }))
    return SkillRoutingReceipt(**body, receipt_hash=receipt_hash)


def record_skill_observation(
    registry: Mapping[str, Any],
    *,
    skill_id: str,
    success: bool,
    observed_at: str,
    repo_root: str | Path,
    independent_receipt: Mapping[str, Any] | None = None,
    evidence_verifier: EvidenceVerifier | None = None,
) -> dict[str, Any]:
    """Update telemetry only with a host-admitted, source-bound independent receipt.

    A local success bool is not proof and cannot mint an observation. Both a
    receipt and trusted host verification are mandatory, including for failures.
    """
    if not isinstance(success, bool):
        raise ValueError("success must be boolean")
    if not isinstance(independent_receipt, Mapping) or evidence_verifier is None:
        raise ValueError("independently authenticated observation required")
    if independent_receipt.get("skill_id") != skill_id:
        raise ValueError("receipt skill does not match requested skill")
    if independent_receipt.get("observed_at") != observed_at:
        raise ValueError("receipt observation timestamp mismatch")
    expected_outcome = "SUCCEEDED" if success else "FAILED"
    if independent_receipt.get("outcome") != expected_outcome:
        raise ValueError("receipt outcome does not match observed result")
    current_receipt = evaluate_registry(
        registry, evidence_verifier=evidence_verifier
    )
    if current_receipt.outcome != ADMITTED:
        raise ValueError("cannot mutate an invalid or unverified skill registry")

    updated = copy.deepcopy(dict(registry))
    skills = updated.get("skills")
    if not isinstance(skills, list):
        raise ValueError("skills must be an array")

    target: dict[str, Any] | None = None
    for raw in skills:
        if isinstance(raw, dict) and raw.get("skill_id") == skill_id:
            target = raw
            break
    if target is None:
        raise ValueError(f"unknown skill_id: {skill_id}")

    evidence_errors = evidence_violations(target, repo_root=repo_root)
    if evidence_errors:
        raise ValueError("invalid skill evidence: " + ",".join(evidence_errors))

    previous_runs = _safe_runs(target)
    previous_failure_rate = target.get("failure_rate", 0.0)
    if isinstance(previous_failure_rate, bool) or not isinstance(previous_failure_rate, (int, float)):
        previous_failure_rate = 0.0
    previous_failures = round(float(previous_failure_rate) * previous_runs)

    total = previous_runs + 1
    failures = previous_failures + (0 if success else 1)
    failure_rate = failures / total

    previous_recency = target.get("recency_score", 0.0)
    if isinstance(previous_recency, bool) or not isinstance(previous_recency, (int, float)):
        previous_recency = 0.0

    target.setdefault("observation_receipts", [])
    if not isinstance(target["observation_receipts"], list):
        raise ValueError("observation receipts must be a list")
    target["observation_receipts"].append(copy.deepcopy(dict(independent_receipt)))
    target["observation_state"] = OBSERVED
    target["validated_runs"] = total
    target["failure_rate"] = failure_rate
    target["failure_rate_observed"] = failure_rate
    target["last_validated"] = observed_at

    # The agent's success flag cannot self-assign confidence. Confidence
    # originates in the independently admitted evaluation receipt.
    target["confidence"] = independent_receipt.get("adjudicated_confidence")
    if success:
        target["recency_score"] = min(1.0, float(previous_recency) * 0.95 + 0.05)
    else:
        target["recency_score"] = max(0.0, float(previous_recency) * 0.9)

    updated.pop("registry_root", None)
    updated.pop("genesis_seal", None)
    root = compute_registry_root(updated)
    updated["registry_root"] = root
    updated["genesis_seal"] = root
    admitted = evaluate_registry(
        updated, repo_root=repo_root, evidence_verifier=evidence_verifier
    )
    if admitted.outcome != ADMITTED:
        raise ValueError("new observation not independently admitted: "
                         + ",".join(admitted.violations))
    return updated


def receipt_dict(receipt: SkillRoutingReceipt) -> dict[str, Any]:
    """JSON-compatible deterministic receipt representation."""
    return asdict(receipt)
