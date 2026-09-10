#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "aegis.skill-factory.v1"
SAFE = re.compile(r"^[a-z0-9_]+$")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_axis(name: str, values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{name} must be a non-empty list")
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or SAFE.fullmatch(value) is None:
            raise ValueError(f"invalid {name} value: {value!r}")
        if value in seen:
            raise ValueError(f"duplicate {name} value: {value}")
        seen.add(value); out.append(value)
    return out


def build_registry(taxonomy: dict[str, Any]) -> dict[str, Any]:
    domains = _validate_axis("domains", taxonomy.get("domains"))
    capabilities = _validate_axis("capabilities", taxonomy.get("capabilities"))
    modalities = _validate_axis("modalities", taxonomy.get("modalities"))
    policy = taxonomy.get("promotion_policy") or {}
    minimum_runs = int(policy.get("minimum_validated_runs", 3))
    minimum_refs = int(policy.get("minimum_evidence_refs", 1))
    if minimum_runs < 1 or minimum_refs < 1:
        raise ValueError("promotion thresholds must be positive")

    taxonomy_hash = sha256(canonical_bytes(taxonomy))
    skills: list[dict[str, Any]] = []
    for domain in domains:
        for capability in capabilities:
            for modality in modalities:
                semantic = {
                    "domain": domain,
                    "capability": capability,
                    "modality": modality,
                    "taxonomy_hash": taxonomy_hash,
                }
                skill_id = f"skill:{domain}:{capability}:{modality}"
                skill_hash = sha256(canonical_bytes(semantic))
                skills.append({
                    "skill_id": skill_id,
                    "name": f"{domain}.{capability}.{modality}",
                    "domain": domain,
                    "capability": capability,
                    "modality": modality,
                    "status": "CANDIDATE",
                    "epistemic_status": "UNVERIFIED_CANDIDATE",
                    "authority_effect": "NONE",
                    "validated_runs": 0,
                    "evidence_refs": [],
                    "minimum_validated_runs": minimum_runs,
                    "minimum_evidence_refs": minimum_refs,
                    "skill_hash": skill_hash,
                })

    registry_body = {
        "schema": SCHEMA,
        "taxonomy_hash": taxonomy_hash,
        "candidate_count": len(skills),
        "admitted_count": 0,
        "skills": skills,
    }
    registry_body["registry_hash"] = sha256(canonical_bytes(registry_body))
    return registry_body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--taxonomy", default="knowledge/skill-taxonomy.v1.json")
    parser.add_argument("--output", default="knowledge/skill-registry.v1.json")
    parser.add_argument("--expect-count", type=int, default=None)
    args = parser.parse_args()

    taxonomy = json.loads(Path(args.taxonomy).read_text(encoding="utf-8"))
    registry = build_registry(taxonomy)
    if args.expect_count is not None and registry["candidate_count"] != args.expect_count:
        raise SystemExit(f"candidate count mismatch: expected {args.expect_count}, got {registry['candidate_count']}")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"SKILL_FACTORY candidate_count={registry['candidate_count']} admitted_count={registry['admitted_count']} registry_hash={registry['registry_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
