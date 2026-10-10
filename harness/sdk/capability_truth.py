"""Read-only, fail-closed capability assurance for the existing AEGIS catalog.

The skill registry describes evidence, not an authorization to dispatch. A valid
registry or observed skill never proves a deployed endpoint, authorized action,
or successful live execution. Only the existing Automaton-3 gate may admit work.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from harness.sdk.skill_authority import (
    OBSERVED,
    SCHEMA_VERSION,
    canonical_bytes,
    evaluate_registry,
    observation_state,
    safe_competency_score,
    sha256_hex,
)

KIND = "AEGIS_CAPABILITY_TRUTH_SNAPSHOT_V1"
MAX_REGISTRY_BYTES = 2_000_000
SHA_RE = re.compile(r"^[a-f0-9]{40}$")


class CapabilityTruthError(ValueError):
    """The catalog's assurance state cannot be established safely."""


def build_capability_truth(
    registry: Mapping[str, Any], *, runtime_commit: str | None = None
) -> dict[str, Any]:
    """Produce a reproducible, non-authorizing view of an existing registry."""
    if not isinstance(registry, Mapping) or registry.get("schema_version") != SCHEMA_VERSION:
        raise CapabilityTruthError("SKILL_REGISTRY_SCHEMA_INVALID")
    try:
        receipt = evaluate_registry(registry)
    except (TypeError, ValueError) as exc:
        raise CapabilityTruthError("SKILL_REGISTRY_INTEGRITY_INVALID") from exc
    if receipt.outcome != "ADMITTED":
        raise CapabilityTruthError("SKILL_REGISTRY_INTEGRITY_INVALID")
    raw_skills = registry.get("skills")
    if not isinstance(raw_skills, list):
        raise CapabilityTruthError("SKILL_REGISTRY_SKILLS_INVALID")
    source_commit = registry.get("source_commit")
    if not isinstance(source_commit, str) or not SHA_RE.fullmatch(source_commit):
        raise CapabilityTruthError("SKILL_REGISTRY_SOURCE_INVALID")
    if runtime_commit is not None and not SHA_RE.fullmatch(runtime_commit):
        raise CapabilityTruthError("RUNTIME_COMMIT_INVALID")

    seen: set[str] = set()
    skills: list[dict[str, Any]] = []
    for skill in raw_skills:
        if not isinstance(skill, Mapping):
            raise CapabilityTruthError("SKILL_ENTRY_INVALID")
        skill_id = skill.get("skill_id")
        if not isinstance(skill_id, str) or not skill_id or skill_id in seen:
            raise CapabilityTruthError("SKILL_ID_MISSING_OR_DUPLICATE")
        seen.add(skill_id)
        runs = skill.get("validated_runs")
        if isinstance(runs, bool) or not isinstance(runs, int) or runs < 0:
            raise CapabilityTruthError("SKILL_RUN_COUNT_INVALID")
        try:
            observed = observation_state(skill) == OBSERVED
        except (TypeError, ValueError) as exc:
            raise CapabilityTruthError("SKILL_OBSERVATION_INVALID") from exc
        skills.append({
            "skill_id": skill_id,
            "observation_state": "OBSERVED" if observed else "UNOBSERVED",
            "validated_runs": runs,
            # This is a metric, not a grant. A score > 0 does not authorize a tool.
            "competency_evidence_score": safe_competency_score(skill),
            "runtime_admission": "NOT_ESTABLISHED",
        })
    skills.sort(key=lambda x: x["skill_id"])
    alignment = (
        "UNKNOWN" if runtime_commit is None
        else "MATCH" if runtime_commit == source_commit else "MISMATCH"
    )
    body = {
        "schema_version": "1.0.0",
        "kind": KIND,
        "registry_integrity": "VERIFIED",
        "registry_root": receipt.registry_root,
        "registry_receipt_hash": receipt.receipt_hash,
        "registry_source_commit": source_commit,
        "runtime_commit": runtime_commit,
        "source_alignment": alignment,
        "operational_admission": "NOT_ESTABLISHED",
        "authority_granted": False,
        "agent_executability": "UNKNOWN",
        "skill_count": len(skills),
        "observed_skill_count": sum(s["observation_state"] == "OBSERVED" for s in skills),
        "skills": skills,
    }
    return {
        **body,
        "snapshot_sha256": sha256_hex(canonical_bytes({"domain": KIND, "body": body})),
    }


def read_capability_truth(
    registry_path: str | Path, *, runtime_commit: str | None = None
) -> dict[str, Any]:
    """Read only the fixed, local registry; reject absent/oversize/untrusted input."""
    path = Path(registry_path)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REGISTRY_BYTES:
            raise CapabilityTruthError("SKILL_REGISTRY_UNAVAILABLE")
        with path.open("rb") as stream:
            data = stream.read(MAX_REGISTRY_BYTES + 1)
        if len(data) > MAX_REGISTRY_BYTES:
            raise CapabilityTruthError("SKILL_REGISTRY_OVERSIZE")
        registry = json.loads(data)
    except (OSError, ValueError, UnicodeError) as exc:
        if isinstance(exc, CapabilityTruthError):
            raise
        raise CapabilityTruthError("SKILL_REGISTRY_UNREADABLE") from exc
    return build_capability_truth(registry, runtime_commit=runtime_commit)
