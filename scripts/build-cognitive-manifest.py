#!/usr/bin/env python3
"""Build a deterministic, content-addressed AEGIS cognitive manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
SCHEMA_ID = "https://aegisomega.com/schemas/cognitive-state.v1.schema.json"
SYSTEM_IDENTIFIER = "AEGIS-OMEGA-LIVING-ANCHOR"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SKIP_DIRS = {
    ".git",
    ".next",
    ".venv",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "vendor",
}
DIMENSIONS = (
    "agents",
    "tools",
    "skills",
    "tasks",
    "behavior",
    "steps",
    "interactions",
    "actions",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    """AEGIS JSON v1: UTF-8, sorted keys, compact separators, no ASCII escaping."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def parse_skill_name(data: bytes, fallback: str) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return fallback

    if not text.startswith("---"):
        return fallback

    lines = text.splitlines()
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^name\s*:\s*(.+?)\s*$", line)
        if match:
            return match.group(1).strip().strip("'\"") or fallback
    return fallback


def discover_skills(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("SKILL.md"), key=lambda p: p.as_posix()):
        relative = path.relative_to(root)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        data = path.read_bytes()
        entries.append(
            {
                "name": parse_skill_name(data, path.parent.name),
                "path": relative.as_posix(),
                "sha256": sha256_bytes(data),
                "size_bytes": len(data),
            }
        )
    return entries


def axis_hash(axis: str, focus: str, skills_root_hash: str) -> str:
    return sha256_bytes(
        canonical_bytes(
            {
                "axis": axis,
                "focus": focus,
                "skills_root_hash": skills_root_hash,
            }
        )
    )


def build_manifest(root: Path, source_ref: str) -> tuple[dict[str, Any], str]:
    entries = discover_skills(root)
    if not entries:
        raise RuntimeError("No SKILL.md files found; refusing to emit an empty manifest")

    skills_index = [
        {
            "path": entry["path"],
            "sha256": entry["sha256"],
            "size_bytes": entry["size_bytes"],
        }
        for entry in entries
    ]
    skills_root_hash = sha256_bytes(canonical_bytes(skills_index))

    manifest: dict[str, Any] = {
        "schema": {
            "id": SCHEMA_ID,
            "local_path": "schemas/cognitive-state.v1.schema.json",
            "version": SCHEMA_VERSION,
        },
        "system_identifier": SYSTEM_IDENTIFIER,
        "ontology_dimensions": 8,
        "provenance": {
            "generator": "scripts/build-cognitive-manifest.py",
            "repository": "Aegis-Omega/AEGIS-OMEGA",
            "source_ref": source_ref,
        },
        "hashing": {
            "algorithm": "sha256",
            "canonicalization": "aegis-json-v1",
            "skill_hash_scope": "raw file bytes",
            "skills_root_scope": "canonical ordered array of path, sha256, and size_bytes",
            "state_hash_scope": "canonical manifest with state_hash omitted",
        },
        "skills_root_hash": skills_root_hash,
        "rotational_axis": {
            "axis_3": {
                "focus": "kinetic_entropy",
                "manifest_hash": axis_hash("axis_3", "kinetic_entropy", skills_root_hash),
            },
            "axis_6": {
                "focus": "dynamic_mutation",
                "manifest_hash": axis_hash("axis_6", "dynamic_mutation", skills_root_hash),
            },
            "axis_9": {
                "focus": "immutable_truth",
                "manifest_hash": axis_hash("axis_9", "immutable_truth", skills_root_hash),
            },
        },
        "cognitive_state": {
            "agents": {
                "aegis_core": {
                    "identity": "system-2-orchestrator",
                    "pacing": "phi-frequency",
                    "privilege_model": "least-privilege",
                },
                "automaton_2": {
                    "identity": "independent-verifier",
                    "phase_shift_degrees": 108,
                    "chain_id": "sha256-observed-ledger",
                    "constitutional_filter": {
                        "mode": "adversarial-verification",
                        "fail_closed": True,
                        "require_parent_state_hash": True,
                        "require_skill_hash_match": True,
                        "max_replay_divergence": 0,
                    },
                },
            },
            "tools": {
                "ingress_gateway": {
                    "declared_endpoint": "/v1/open-hands/ingress",
                    "policy": "least-privilege",
                    "isolation_tier": "sandbox-unprivileged",
                    "validation_protocol": "EventEnvelope",
                },
                "egress_stream": {
                    "declared_endpoint": "/v1/open-hands/egress",
                    "format": "cryptographic-event-stream",
                    "filtering": "verified-state-projection",
                },
            },
            "skills": {
                "count": len(entries),
                "root_hash": skills_root_hash,
                "entries": entries,
            },
            "tasks": {
                "state_stabilization": {
                    "rules": [
                        "verify_all_skill_hashes",
                        "require_parent_state_hash",
                        "rollback_on_any_replay_divergence",
                    ]
                }
            },
            "behavior": {
                "pacing_ledger": {
                    "step_interval_multiplier": 1.6180339887,
                    "max_queue_depth": 3,
                    "overflow_policy": "reject-and-record",
                }
            },
            "steps": {
                "sequence": [
                    "ingest_unverified_envelope",
                    "verify_parent_state_hash",
                    "evaluate_against_immutable_truth_9",
                    "execute_independent_automaton_2_verification",
                    "generate_verified_egress_projection",
                    "commit_state_hash",
                ]
            },
            "interactions": {
                "ingress_rules": {
                    "allow_mutating_queries": False,
                    "allow_direct_commit": False,
                    "required_event_envelope": True,
                    "required_parent_state_hash": True,
                }
            },
            "actions": {
                "on_violation": "reject-record-and-trigger-rollback-consensus",
                "on_success": "broadcast-verified-event-stream",
            },
        },
    }

    if tuple(manifest["cognitive_state"].keys()) != DIMENSIONS:
        raise AssertionError("cognitive_state must contain exactly the eight declared dimensions")

    manifest["state_hash"] = sha256_bytes(canonical_bytes(manifest))
    validate_manifest(manifest)

    hash_lines = "".join(
        f"{entry['sha256']}  {entry['path']}\n" for entry in entries
    )
    return manifest, hash_lines


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("ontology_dimensions") != 8:
        raise ValueError("ontology_dimensions must equal 8")
    if tuple(manifest["cognitive_state"].keys()) != DIMENSIONS:
        raise ValueError("cognitive_state dimensions are invalid or out of order")
    if not HASH_RE.fullmatch(manifest["state_hash"]):
        raise ValueError("state_hash is not a SHA-256 hex digest")
    if not HASH_RE.fullmatch(manifest["skills_root_hash"]):
        raise ValueError("skills_root_hash is not a SHA-256 hex digest")
    for entry in manifest["cognitive_state"]["skills"]["entries"]:
        if not HASH_RE.fullmatch(entry["sha256"]):
            raise ValueError(f"invalid skill hash: {entry['path']}")

    state_hash = manifest["state_hash"]
    unhashed = dict(manifest)
    unhashed.pop("state_hash")
    expected = sha256_bytes(canonical_bytes(unhashed))
    if expected != state_hash:
        raise ValueError("state_hash verification failed")


def render_manifest(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def write_or_check(root: Path, source_ref: str, check: bool) -> int:
    manifest, hash_lines = build_manifest(root, source_ref)
    outputs = {
        root / ".claude.json": render_manifest(manifest),
        root / "skill-hashes.sha256": hash_lines,
    }

    if check:
        stale: list[str] = []
        for path, expected in outputs.items():
            actual = path.read_text(encoding="utf-8") if path.exists() else None
            if actual != expected:
                stale.append(path.relative_to(root).as_posix())
        if stale:
            print("Stale or missing generated files:", file=sys.stderr)
            for path in stale:
                print(f"  - {path}", file=sys.stderr)
            return 1
        print(f"Manifest verified: {len(manifest['cognitive_state']['skills']['entries'])} skills")
        return 0

    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8", newline="\n")
    print(
        f"Wrote .claude.json and skill-hashes.sha256 for "
        f"{len(manifest['cognitive_state']['skills']['entries'])} skills"
    )
    print(f"skills_root_hash={manifest['skills_root_hash']}")
    print(f"state_hash={manifest['state_hash']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--ref",
        default=os.environ.get("GITHUB_REF_NAME", "local"),
        help="Source branch/ref recorded in the manifest",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    return write_or_check(root, args.ref, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
