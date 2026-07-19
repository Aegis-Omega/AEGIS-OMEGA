"""Evidence-bound authority rules for the AEGIS documentation skill registry.

Documentation may declare a capability, but it cannot establish operational
competence. A skill remains non-authoritative until runtime observations exist.
The module is standard-library only so it can run in CI and deployment images.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "2.0.0"
RECEIPT_KIND = "AEGIS_SKILL_AUTHORITY_RECEIPT_V2"
UNOBSERVED = "UNOBSERVED"
OBSERVED = "OBSERVED"
MIN_VALIDATED_RUNS = 3
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class SkillAuthorityError(ValueError):
    """Raised when a registry cannot be interpreted safely."""


def canonical_bytes(value: Any) -> bytes:
    """Deterministic UTF-8 JSON used for registry and receipt digests."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _root_payload(tree: Mapping[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(dict(tree))
    payload.pop("registry_root", None)
    payload.pop("genesis_seal", None)
    return payload


def compute_registry_root(tree: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_bytes({
        "domain": "AEGIS_SKILL_REGISTRY_V2",
        "registry": _root_payload(tree),
    }))


def _bounded_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if 0.0 <= value <= 1.0 else None


def observation_state(skill: Mapping[str, Any]) -> str:
    runs = skill.get("validated_runs", 0)
    if not isinstance(runs, int) or isinstance(runs, bool) or runs < 0:
        raise SkillAuthorityError("validated_runs must be a non-negative integer")
    declared = skill.get("observation_state")
    if declared in {UNOBSERVED, OBSERVED}:
        return str(declared)
    return OBSERVED if runs > 0 else UNOBSERVED


def safe_competency_score(
    skill: Mapping[str, Any] | None,
    *,
    minimum_runs: int = MIN_VALIDATED_RUNS,
) -> float:
    """Return an authority-safe score.

    Unknown, malformed, or under-observed skills score 0.0. Documentation tier
    and prose-derived priors never contribute to operational routing authority.
    """
    if skill is None:
        return 0.0
    try:
        runs = skill.get("validated_runs", 0)
        if not isinstance(runs, int) or isinstance(runs, bool) or runs < minimum_runs:
            return 0.0
        if observation_state(skill) != OBSERVED:
            return 0.0
        confidence = _bounded_float(skill.get("confidence"))
        recency = _bounded_float(skill.get("recency_score"))
        failure = _bounded_float(skill.get("failure_rate"))
        if None in {confidence, recency, failure}:
            return 0.0
        return float(confidence * recency * (1.0 - failure))
    except (SkillAuthorityError, TypeError, ValueError):
        return 0.0


def sanitize_legacy_tree(
    legacy_tree: Mapping[str, Any],
    *,
    source_commit: str,
) -> dict[str, Any]:
    """Convert a Phase-1 prose registry into a non-authoritative V2 registry.

    Existing observed telemetry is retained. Zero-run records lose all positive
    operational score while preserving their old prose prior as metadata only.
    No wall-clock timestamp is added, so identical inputs are byte-identical.
    """
    if not source_commit or not isinstance(source_commit, str):
        raise SkillAuthorityError("source_commit must be a non-empty string")

    raw_skills = legacy_tree.get("skills")
    if not isinstance(raw_skills, list):
        raise SkillAuthorityError("skills must be an array")

    skills: list[dict[str, Any]] = []
    for raw in raw_skills:
        if not isinstance(raw, Mapping):
            raise SkillAuthorityError("every skill must be an object")
        skill = copy.deepcopy(dict(raw))
        skill_id = skill.get("skill_id")
        if not isinstance(skill_id, str) or not skill_id:
            raise SkillAuthorityError("skill_id must be a non-empty string")

        runs = skill.get("validated_runs", 0)
        if not isinstance(runs, int) or isinstance(runs, bool) or runs < 0:
            raise SkillAuthorityError(f"{skill_id}: invalid validated_runs")

        refs = skill.get("evidence_refs", [])
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref for ref in refs):
            raise SkillAuthorityError(f"{skill_id}: evidence_refs must contain non-empty paths")
        skill["evidence_refs"] = sorted(set(refs))
        skill["declared_tier"] = skill.get("tier")

        if runs == 0:
            prior = _bounded_float(skill.get("confidence"))
            skill["documentation_prior"] = prior
            skill["observation_state"] = UNOBSERVED
            skill["confidence"] = 0.0
            skill["failure_rate"] = 0.0
            skill["failure_rate_observed"] = None
            skill["recency_score"] = 0.0
            skill["last_validated"] = None
        else:
            skill["observation_state"] = OBSERVED
            skill["failure_rate_observed"] = skill.get("failure_rate")

        skills.append(skill)

    skills.sort(key=lambda item: str(item["skill_id"]))
    tree: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "version": SCHEMA_VERSION,
        "phase": legacy_tree.get("phase", 1),
        "authority_state": "NON_AUTHORITATIVE_UNTIL_OBSERVED",
        "source_commit": source_commit,
        "source_generated_at": legacy_tree.get("generated_at"),
        "doc_count": legacy_tree.get("doc_count", 0),
        "skills": skills,
    }
    root = compute_registry_root(tree)
    tree["registry_root"] = root
    tree["genesis_seal"] = root
    return tree


@dataclass(frozen=True)
class SkillAuthorityReceipt:
    schema_version: str
    receipt_kind: str
    outcome: str
    authority_state: str
    skill_count: int
    observed_skill_count: int
    violation_count: int
    violations: tuple[str, ...]
    registry_root: str | None
    receipt_hash: str


def evaluate_registry(
    tree: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
) -> SkillAuthorityReceipt:
    violations: list[str] = []
    skills = tree.get("skills")
    if not isinstance(skills, list):
        skills = []
        violations.append("TREE: skills must be an array")

    observed = 0
    root_path = Path(repo_root).resolve() if repo_root is not None else None

    for index, raw in enumerate(skills):
        if not isinstance(raw, Mapping):
            violations.append(f"SKILL[{index}]: record must be an object")
            continue
        sid = raw.get("skill_id", f"index-{index}")
        if not isinstance(sid, str) or not sid:
            sid = f"index-{index}"
            violations.append(f"SKILL[{index}]: missing skill_id")

        try:
            state = observation_state(raw)
        except SkillAuthorityError as exc:
            violations.append(f"{sid}: {exc}")
            continue

        runs = raw.get("validated_runs", 0)
        if state == OBSERVED:
            observed += 1
            if runs < 1:
                violations.append(f"{sid}: OBSERVED requires validated_runs > 0")
            for field in ("confidence", "failure_rate", "recency_score"):
                if _bounded_float(raw.get(field)) is None:
                    violations.append(f"{sid}: observed {field} must be in [0,1]")
            if not raw.get("last_validated"):
                violations.append(f"{sid}: observed skill requires last_validated")
        else:
            if runs != 0:
                violations.append(f"{sid}: UNOBSERVED requires validated_runs == 0")
            if raw.get("confidence") != 0.0:
                violations.append(f"{sid}: unobserved confidence must be 0.0")
            if raw.get("recency_score") != 0.0:
                violations.append(f"{sid}: unobserved recency_score must be 0.0")
            if raw.get("last_validated") not in (None, ""):
                violations.append(f"{sid}: unobserved last_validated must be null")

        refs = raw.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            violations.append(f"{sid}: at least one evidence_ref is required")
        elif root_path is not None:
            for ref in refs:
                if not isinstance(ref, str) or not ref:
                    violations.append(f"{sid}: malformed evidence_ref")
                    continue
                candidate = (root_path / ref).resolve()
                try:
                    candidate.relative_to(root_path)
                except ValueError:
                    violations.append(f"{sid}: evidence_ref escapes repository: {ref}")
                    continue
                if not candidate.is_file():
                    violations.append(f"{sid}: unresolved evidence_ref: {ref}")

    expected_root = compute_registry_root(tree)
    stored_root = tree.get("registry_root")
    if stored_root != expected_root:
        violations.append("TREE: registry_root mismatch")
    if tree.get("genesis_seal") in {None, EMPTY_SHA256, "0" * 64}:
        violations.append("TREE: genesis_seal is not content-bound")
    elif tree.get("genesis_seal") != expected_root:
        violations.append("TREE: genesis_seal must equal registry_root")

    violations = sorted(set(violations))
    outcome = "ADMITTED" if not violations else "DENIED"
    body = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "outcome": outcome,
        "authority_state": tree.get("authority_state", "UNKNOWN"),
        "skill_count": len(skills),
        "observed_skill_count": observed,
        "violation_count": len(violations),
        "violations": tuple(violations),
        "registry_root": stored_root if isinstance(stored_root, str) else None,
    }
    receipt_hash = sha256_hex(canonical_bytes({
        "domain": RECEIPT_KIND,
        "receipt": body,
    }))
    return SkillAuthorityReceipt(**body, receipt_hash=receipt_hash)


def render_authority_markdown(tree: Mapping[str, Any]) -> str:
    lines = [
        "# SOVEREIGN AGI OS — EVIDENCE-BOUND SKILLS REGISTRY",
        "",
        f"**Schema:** {tree.get('schema_version', 'unknown')}  ",
        f"**Source commit:** `{tree.get('source_commit', 'UNBOUND')}`  ",
        f"**Registry root:** `{tree.get('registry_root', 'UNBOUND')}`  ",
        f"**Authority:** {tree.get('authority_state', 'UNKNOWN')}  ",
        f"**Skills:** {len(tree.get('skills', []))}",
        "",
        "> Documentation establishes a declared capability only. Operational competence",
        "> remains zero until runtime evidence is recorded.",
        "",
    ]
    by_domain: dict[str, list[Mapping[str, Any]]] = {}
    for skill in tree.get("skills", []):
        by_domain.setdefault(str(skill.get("domain", "unknown")), []).append(skill)
    for domain in sorted(by_domain):
        lines.extend([f"## Domain: `{domain}`", ""])
        for skill in sorted(by_domain[domain], key=lambda item: str(item.get("skill_id", ""))):
            lines.extend([
                f"### SKILL: {skill.get('skill_id')}",
                f"- **Label:** {skill.get('label')}",
                f"- **Declared tier:** {skill.get('declared_tier', skill.get('tier'))}",
                f"- **Observation state:** {skill.get('observation_state', UNOBSERVED)}",
                f"- **Authority-safe confidence:** {skill.get('confidence', 0.0):.2f}",
                f"- **Validated runs:** {skill.get('validated_runs', 0)}",
                f"- **Failure rate:** {skill.get('failure_rate_observed') if skill.get('failure_rate_observed') is not None else 'UNOBSERVED'}",
                f"- **Recency score:** {skill.get('recency_score', 0.0):.2f}",
                f"- **Evidence refs:** {', '.join(skill.get('evidence_refs', [])) or 'none'}",
                f"- **Description:** {skill.get('description', '')}",
                "",
            ])
    return "\n".join(lines)
