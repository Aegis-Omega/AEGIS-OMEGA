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
RUNTIME_STATE_SUFFIXES = (".log", ".tmp", ".jsonl")


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


def discover_epistemic_substrate(root: Path) -> list[dict[str, Any]]:
    """Independently rediscover the bounded repository epistemic substrate."""
    candidates: list[Path] = []
    settings = root / ".claude" / "settings.json"
    if settings.is_file():
        candidates.append(settings)

    hooks_root = root / ".claude" / "hooks"
    if hooks_root.is_dir():
        candidates.extend(
            path
            for path in hooks_root.rglob("*")
            if path.is_file()
            and not path.name.endswith(RUNTIME_STATE_SUFFIXES)
        )

    metacog_root = root / ".claude" / "metacog"
    if metacog_root.is_dir():
        candidates.extend(path for path in metacog_root.glob("*.mjs") if path.is_file())

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(candidates, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        if path.is_symlink():
            raise ValueError(f"epistemic substrate may not contain symlinks: {relative}")
        data = path.read_bytes()
        entries.append({
            "path": relative,
            "sha256": sha256_hex(data),
            "size_bytes": len(data),
        })
    return entries


def _discover_domain_files(root: Path, relative_root: str) -> list[dict[str, Any]]:
    base = root / relative_root
    if not base.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(base.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if path.name.endswith(RUNTIME_STATE_SUFFIXES):
            continue
        if path.is_symlink():
            raise ValueError(f"epistemic domain may not contain symlinks: {relative.as_posix()}")
        data = path.read_bytes()
        entries.append({
            "path": relative.as_posix(),
            "sha256": sha256_hex(data),
            "size_bytes": len(data),
        })
    return entries


def discover_genomics_domain(root: Path) -> dict[str, list[dict[str, Any]]]:
    source_entries = _discover_domain_files(root, "genomics")
    verification_entries = _discover_domain_files(root, "verifiable")
    workflow = root / ".github" / "workflows" / "verifiable-proofs.yml"
    if workflow.is_file():
        data = workflow.read_bytes()
        verification_entries.append({
            "path": workflow.relative_to(root).as_posix(),
            "sha256": sha256_hex(data),
            "size_bytes": len(data),
        })
        verification_entries.sort(key=lambda entry: entry["path"])
    return {
        "source": source_entries,
        "verification": verification_entries,
    }


def validate_epistemic_substrate(root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    substrate = (
        manifest.get("cognitive_state", {})
        .get("tools", {})
        .get("epistemic_substrate", {})
    )
    if not isinstance(substrate, dict):
        return ["epistemic substrate is missing"]
    entries = substrate.get("entries", [])
    if not isinstance(entries, list):
        return ["epistemic substrate entries are not an array"]

    if substrate.get("count") != len(entries):
        errors.append("epistemic substrate count mismatch")

    manifest_index: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("epistemic substrate entry is not an object")
            continue
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative:
            errors.append("epistemic substrate entry has invalid path")
            continue
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            errors.append(f"epistemic substrate path escapes repository: {relative}")
            continue
        if not candidate.is_file():
            errors.append(f"epistemic substrate evidence missing: {relative}")
            continue
        data = candidate.read_bytes()
        if entry.get("sha256") != sha256_hex(data):
            errors.append(f"epistemic substrate digest mismatch: {relative}")
        if entry.get("size_bytes") != len(data):
            errors.append(f"epistemic substrate size mismatch: {relative}")
        manifest_index.append({
            "path": relative,
            "sha256": entry.get("sha256"),
            "size_bytes": entry.get("size_bytes"),
        })

    actual_index = discover_epistemic_substrate(root)
    if manifest_index != actual_index:
        errors.append("epistemic substrate entry set mismatch")

    actual_control_plane_root = sha256_hex(canonical_bytes(actual_index))
    if substrate.get("control_plane_root_hash") != actual_control_plane_root:
        errors.append("epistemic substrate control-plane root mismatch")

    domains = substrate.get("domains", {})
    genomics = domains.get("genomics", {}) if isinstance(domains, dict) else {}
    if not isinstance(genomics, dict):
        errors.append("epistemic genomics domain is missing")
        genomics = {}

    discovered = discover_genomics_domain(root)
    for section_name in ("source", "verification"):
        section = genomics.get(section_name, {}) if isinstance(genomics, dict) else {}
        manifest_entries = section.get("entries", []) if isinstance(section, dict) else []
        actual_entries = discovered[section_name]
        if manifest_entries != actual_entries:
            errors.append(f"genomics {section_name} entry set mismatch")
        actual_section_root = sha256_hex(canonical_bytes(actual_entries))
        if not isinstance(section, dict) or section.get("root_hash") != actual_section_root:
            errors.append(f"genomics {section_name} root mismatch")

    boundary = genomics.get("authority_boundary", {}) if isinstance(genomics, dict) else {}
    source_root = (
        genomics.get("source", {}).get("root_hash")
        if isinstance(genomics.get("source", {}), dict) else None
    )
    verification_root = (
        genomics.get("verification", {}).get("root_hash")
        if isinstance(genomics.get("verification", {}), dict) else None
    )
    expected_genomics_root = sha256_hex(canonical_bytes({
        "source_root_hash": source_root,
        "verification_root_hash": verification_root,
        "authority_boundary": boundary,
    }))
    if genomics.get("root_hash") != expected_genomics_root:
        errors.append("genomics domain root mismatch")

    expected_substrate_root = sha256_hex(canonical_bytes({
        "control_plane_root_hash": actual_control_plane_root,
        "domains": {"genomics": expected_genomics_root},
    }))
    if substrate.get("root_hash") != expected_substrate_root:
        errors.append("epistemic substrate root mismatch")
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
        "epistemic_substrate_root_hash": (
            manifest.get("cognitive_state", {})
            .get("tools", {})
            .get("epistemic_substrate", {})
            .get("root_hash")
            if manifest else None
        ),
        "genomics_epistemic_root_hash": (
            manifest.get("cognitive_state", {})
            .get("tools", {})
            .get("epistemic_substrate", {})
            .get("domains", {})
            .get("genomics", {})
            .get("root_hash")
            if manifest else None
        ),
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
        violations.extend(validate_epistemic_substrate(root, manifest))
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
