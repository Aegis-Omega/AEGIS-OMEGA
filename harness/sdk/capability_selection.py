"""Evidence-aware ordering for *already admitted* AEGIS coordinator candidates.

Advisory only: never grants authority, creates candidates, runs tools or mutates
skill registry. If registry is invalid/unobserved, preserve authority ordering.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from harness.sdk.skill_authority import evaluate_registry, safe_competency_score
from harness.sdk.skill_routing import evidence_violations

RECEIPT_KIND = "AEGIS_CAPABILITY_ORDER_ADVISORY_V1"


def _hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_authority(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    try:
        value = float(value)
    except OverflowError:
        return 0.0
    return value if math.isfinite(value) and value >= 0 else 0.0


def _words(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _capability_relevant(capability: str, task_words: set[str],
                         required: frozenset[str]) -> bool:
    if capability in required:
        return True
    terms = {part for part in _words(capability) if len(part) >= 3}
    return bool(terms & task_words)


def advise_admitted_order(
    candidates: Sequence[tuple[int, str, float]],
    *,
    task_instruction: str,
    agent_defs: Mapping[str, Any],
    capability_map: Mapping[str, str],
    registry_path: str | Path,
    repo_root: str | Path,
    required_capabilities: Sequence[str] = (),
) -> tuple[list[int], dict[str, Any]]:
    """Permute pre-admitted candidate indices; emit deterministic read-only receipt.

    Registry hash/seal establishes consistency, not independent attestation that
    its self-reported runtime observations occurred. Central Automaton-3 remains
    the sole source of operational admission; caller filters first.
    """
    if len({row[0] for row in candidates}) != len(candidates):
        raise ValueError("duplicate candidate index")
    if any(not isinstance(idx, int) or isinstance(idx, bool) or not isinstance(role, str)
           or not role for idx, role, _ in candidates):
        raise ValueError("invalid admitted candidate")

    baseline = sorted(candidates, key=lambda row: (-_safe_authority(row[2]), row[0]))
    ordered = [row[0] for row in baseline]
    status = "INSUFFICIENT_TELEMETRY"
    registry_root: str | None = None
    registry_receipt_hash: str | None = None
    reasons: list[str] = []
    scores: dict[int, float] = {row[0]: 0.0 for row in candidates}
    observations: dict[int, list[str]] = {row[0]: [] for row in candidates}

    try:
        raw = json.loads(Path(registry_path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("registry is not an object")
        verdict = evaluate_registry(raw, repo_root=repo_root)
        registry_root = raw.get("registry_root") if isinstance(raw.get("registry_root"), str) else None
        registry_receipt_hash = verdict.receipt_hash

        if verdict.outcome != "ADMITTED":
            status = "REGISTRY_INVALID"
            reasons.append("REGISTRY_VALIDATION_FAILED")
        else:
            skills = {s["skill_id"]: s for s in raw["skills"]
                      if isinstance(s, dict) and isinstance(s.get("skill_id"), str)}
            task_words = _words(task_instruction)
            requested = frozenset(x for x in required_capabilities
                                  if isinstance(x, str) and x in capability_map)
            for index, role, _ in candidates:
                definition = agent_defs.get(role)
                if not isinstance(definition, Mapping):
                    continue
                caps = definition.get("capabilities", [])
                if not isinstance(caps, (list, tuple)):
                    continue
                for cap in caps:
                    if not isinstance(cap, str) or cap not in capability_map:
                        continue
                    if not _capability_relevant(cap, task_words, requested):
                        continue
                    sid = capability_map[cap]
                    skill = skills.get(sid)
                    if skill is None or evidence_violations(skill, repo_root=repo_root):
                        continue
                    score = safe_competency_score(skill)
                    if score > 0.0 and math.isfinite(score):
                        scores[index] = max(scores[index], score)
                        observations[index].append(sid)

            if any(score > 0 for score in scores.values()):
                ordered = [row[0] for row in sorted(
                    candidates,
                    key=lambda row: (-scores[row[0]], -_safe_authority(row[2]), row[0]),
                )]
                status = "OBSERVED_SKILL_PREFERENCE"
            else:
                reasons.append("NO_RELEVANT_VALIDATED_SKILLS")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        status = "REGISTRY_UNAVAILABLE"
        reasons.append(type(exc).__name__)

    body: dict[str, Any] = {
        "schema_version": "1.0.0",
        "receipt_kind": RECEIPT_KIND,
        "status": status,
        "task_digest": hashlib.sha256(task_instruction.encode("utf-8")).hexdigest(),
        "registry_root": registry_root,
        "registry_receipt_hash": registry_receipt_hash,
        "baseline_indices": [row[0] for row in baseline],
        "selected_indices": ordered,
        "candidates": [
            {"index": idx, "role": role, "observed_score": scores[idx],
             "matched_validated_skill_ids": sorted(set(observations[idx]))}
            for idx, role, _ in sorted(candidates)
        ],
        "reason_codes": sorted(set(reasons)),
        "authority_effect": "NONE_ORDER_ONLY",
        "evidence_limit": "REGISTRY_METADATA_NOT_INDEPENDENT_TOOL_EXECUTION_ATTESTATION",
    }
    body["receipt_hash"] = _hash({"domain": RECEIPT_KIND, "body": body})
    return ordered, body
