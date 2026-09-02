#!/usr/bin/env python3
"""Fail-closed Automaton-2 validator for the AEGIS cognitive manifest."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

RECEIPT_KIND = "AEGIS_AUTOMATON2_RECEIPT_V1"
SCHEMA_VERSION = "1.0.0"
ZERO_HASH = "0" * 64


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_generator(path: Path):
    spec = importlib.util.spec_from_file_location("aegis_cognitive_manifest", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_parent_hash(parent_manifest: Path | None, explicit_hash: str | None) -> str:
    if explicit_hash:
        return explicit_hash
    if parent_manifest is None or not parent_manifest.is_file():
        return ZERO_HASH
    parent = load_json(parent_manifest)
    value = parent.get("state_hash")
    if not isinstance(value, str):
        raise ValueError("parent manifest has no state_hash")
    return value


def validate_schema(manifest: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(manifest),
        key=lambda error: list(error.absolute_path),
    )
    return [
        "schema:" + "/".join(str(part) for part in error.absolute_path) + f": {error.message}"
        for error in errors
    ]


def validate_state_hash(manifest: dict[str, Any]) -> list[str]:
    state_hash = manifest.get("state_hash")
    unhashed = dict(manifest)
    unhashed.pop("state_hash", None)
    expected = sha256_hex(canonical_bytes(unhashed))
    return [] if state_hash == expected else ["state_hash mismatch"]


def validate_parent_state(manifest: dict[str, Any], expected: str) -> list[str]:
    actual = manifest.get("provenance", {}).get("parent_state_hash")
    return [] if actual == expected else [
        f"parent_state_hash mismatch: expected {expected}, got {actual}"
    ]


def validate_signature_contract(manifest: dict[str, Any], require_oidc: bool) -> list[str]:
    errors: list[str] = []
    mode = manifest.get("provenance", {}).get("signature_mode")
    if mode != "GITHUB_OIDC_ATTESTATION":
        errors.append("signature_mode is not GITHUB_OIDC_ATTESTATION")
    if require_oidc:
        required = (
            "GITHUB_ACTIONS",
            "ACTIONS_ID_TOKEN_REQUEST_URL",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        )
        missing = [name for name in required if not os.environ.get(name)]
        if os.environ.get("GITHUB_ACTIONS") != "true":
            errors.append("unsigned transition: GITHUB_ACTIONS is not true")
        if missing:
            errors.append("unsigned transition: missing OIDC environment: " + ",".join(missing))
    return errors


def validate_skill_evidence(root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    entries = manifest.get("cognitive_state", {}).get("skills", {}).get("entries", [])
    if not isinstance(entries, list):
        return ["skills entries are not an array"]
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("skill entry is not an object")
            continue
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative:
            errors.append("skill entry has invalid path")
            continue
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            errors.append(f"skill path escapes repository: {relative}")
            continue
        if not candidate.is_file():
            errors.append(f"skill evidence missing: {relative}")
            continue
        data = candidate.read_bytes()
        if entry.get("sha256") != sha256_hex(data):
            errors.append(f"skill digest mismatch: {relative}")
        if entry.get("size_bytes") != len(data):
            errors.append(f"skill size mismatch: {relative}")
    return errors


def validate_replay(
    root: Path,
    manifest: dict[str, Any],
    generator_path: Path,
    hashes_path: Path,
) -> list[str]:
    errors: list[str] = []
    generator = load_generator(generator_path)
    source_ref = manifest.get("provenance", {}).get("source_ref")
    parent_hash = manifest.get("provenance", {}).get("parent_state_hash")
    if not isinstance(source_ref, str) or not source_ref:
        return ["replay source_ref is missing"]
    if not isinstance(parent_hash, str):
        return ["replay parent_state_hash is missing"]

    first_manifest, first_hashes = generator.build_manifest(
        root,
        source_ref=source_ref,
        parent_state_hash=parent_hash,
    )
    second_manifest, second_hashes = generator.build_manifest(
        root,
        source_ref=source_ref,
        parent_state_hash=parent_hash,
    )
    first_bytes = generator.render_manifest(first_manifest).encode("utf-8")
    second_bytes = generator.render_manifest(second_manifest).encode("utf-8")
    if first_bytes != second_bytes or first_hashes != second_hashes:
        errors.append("replay divergence: identical inputs produced different outputs")
    if canonical_bytes(first_manifest) != canonical_bytes(manifest):
        errors.append("replay divergence: committed manifest does not regenerate")
    actual_hashes = hashes_path.read_text(encoding="utf-8") if hashes_path.is_file() else None
    if actual_hashes != first_hashes:
        errors.append("skill-hashes.sha256 does not regenerate")
    return errors


def build_receipt(
    *,
    outcome: str,
    candidate_sha: str,
    expected_parent_state_hash: str,
    manifest: dict[str, Any] | None,
    violations: list[str],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_kind": RECEIPT_KIND,
        "outcome": outcome,
        "candidate_sha": candidate_sha,
        "expected_parent_state_hash": expected_parent_state_hash,
        "manifest_state_hash": manifest.get("state_hash") if manifest else None,
        "skills_root_hash": manifest.get("skills_root_hash") if manifest else None,
        "signature_mode": (
            manifest.get("provenance", {}).get("signature_mode") if manifest else None
        ),
        "violation_count": len(violations),
        "violations": sorted(set(violations)),
    }
    body["receipt_hash"] = sha256_hex(
        canonical_bytes({"domain": RECEIPT_KIND, "receipt": body})
    )
    return body


def evaluate(
    *,
    root: Path,
    manifest_path: Path,
    schema_path: Path,
    generator_path: Path,
    hashes_path: Path,
    expected_parent_state_hash: str,
    candidate_sha: str,
    require_oidc: bool,
) -> dict[str, Any]:
    violations: list[str] = []
    manifest: dict[str, Any] | None = None
    try:
        manifest_value = load_json(manifest_path)
        if not isinstance(manifest_value, dict):
            raise ValueError("manifest root is not an object")
        manifest = manifest_value
        schema = load_json(schema_path)
        if not isinstance(schema, dict):
            raise ValueError("schema root is not an object")
        violations.extend(validate_schema(manifest, schema))
        violations.extend(validate_state_hash(manifest))
        violations.extend(validate_parent_state(manifest, expected_parent_state_hash))
        violations.extend(validate_signature_contract(manifest, require_oidc))
        violations.extend(validate_skill_evidence(root, manifest))
        violations.extend(validate_replay(root, manifest, generator_path, hashes_path))
    except Exception as exc:
        violations.append(f"validator exception: {type(exc).__name__}: {exc}")

    violations = sorted(set(violations))
    return build_receipt(
        outcome="ADMITTED" if not violations else "DENIED",
        candidate_sha=candidate_sha,
        expected_parent_state_hash=expected_parent_state_hash,
        manifest=manifest,
        violations=violations,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--manifest", default=".claude.json")
    parser.add_argument("--schema", default="schemas/cognitive-state.v1.schema.json")
    parser.add_argument("--generator", default="scripts/build-cognitive-manifest.py")
    parser.add_argument("--skill-hashes", default="skill-hashes.sha256")
    parser.add_argument("--parent-manifest", default=None)
    parser.add_argument("--expected-parent-state-hash", default=None)
    parser.add_argument("--candidate-sha", default=os.environ.get("GITHUB_SHA", "local"))
    parser.add_argument("--require-oidc", action="store_true")
    parser.add_argument("--output", default="AUTOMATON2_RECEIPT.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    parent_manifest = Path(args.parent_manifest).resolve() if args.parent_manifest else None
    expected = expected_parent_hash(parent_manifest, args.expected_parent_state_hash)
    receipt = evaluate(
        root=root,
        manifest_path=(root / args.manifest).resolve(),
        schema_path=(root / args.schema).resolve(),
        generator_path=(root / args.generator).resolve(),
        hashes_path=(root / args.skill_hashes).resolve(),
        expected_parent_state_hash=expected,
        candidate_sha=args.candidate_sha,
        require_oidc=args.require_oidc,
    )
    Path(args.output).write_bytes(canonical_bytes(receipt))
    print(f"{receipt['outcome']} {receipt['receipt_hash']}")
    for violation in receipt["violations"]:
        print(f"DENIAL: {violation}", file=sys.stderr)
    return 0 if receipt["outcome"] == "ADMITTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
