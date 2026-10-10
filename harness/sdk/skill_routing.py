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
        registry_receipt = evaluate_registry(registry)
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

    score = safe_competency_score(skill, minimum_runs=minimum_runs)
    # `safe_competency_score` is a metric over mutable registry fields,
    # NOT proof that an independent run actually happened. Until an external
    # attestation verifier is implemented, no positive routing may arise
    # from mutable JSON counters, even if a caller re-hashes the registry.
    if score > 0.0:
        reasons.append("INDEPENDENT_RUN_ATTESTATION_NOT_VERIFIED")
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
    registry: Mapping[str, Any], *,
    skill_id: str,
    success: bool,
    observed_at: str,
    repo_root: str | Path,
) -> dict[str, Any]:
    """REJECT unattested, actor-supplied event promotion.

    The historical interface let any caller claim success=True three times,
    increment `validated_runs`, then re-seal the modified registry. Hash
    integrity proves only *consistency*, not independent observation.

    Reintroduction of capability promotion requires a verifier independent
    of the agent, signed upstream run provenance, exact source/artifact hashes,
    failure-inclusive history, anti-replay, and explicit admission authority.
    No such verifier is configured here; fail closed rather than treating a
    caller's bool as trusted evidence.
    """
    raise ValueError("INDEPENDENT_EXECUTION_ATTESTATION_REQUIRED")


def propose_skill_observation(
    *, skill_id: str, success: bool, observed_at: str, source_commit: str
) -> dict[str, Any]:
    """Record an untrusted attempt for later review, never mutate skill state."""
    if not isinstance(skill_id, str) or not skill_id or len(skill_id) > 128:
        raise ValueError("SKILL_ID_INVALID")
    if type(success) is not bool or not isinstance(observed_at, str) or not observed_at:
        raise ValueError("OBSERVATION_EVENT_INVALID")
    if not isinstance(source_commit, str) or len(source_commit) != 40 or any(
        c not in "0123456789abcdef" for c in source_commit
    ):
        raise ValueError("OBSERVATION_SOURCE_INVALID")
    body = {
        "schema_version": "1.0.0",
        "kind": "AEGIS_UNTRUSTED_SKILL_ATTEMPT_V1",
        "skill_id": skill_id,
        "claimed_success": success,
        "observed_at_claim": observed_at,
        "source_commit_claim": source_commit,
        "verification": "PENDING_EXTERNAL_ATTESTATION",
        "authority_granted": False,
        "validated_run_increment": 0,
    }
    return {
        **body,
        "proposal_sha256": sha256_hex(canonical_bytes({
            "domain": "AEGIS_UNTRUSTED_SKILL_ATTEMPT_V1",
            "body": body,
        })),
    }


def receipt_dict(receipt: SkillRoutingReceipt) -> dict[str, Any]:
    """JSON-compatible deterministic receipt representation."""
    return asdict(receipt)
