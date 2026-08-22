#!/usr/bin/env python3
"""Validate AEGIS model artifact provenance and optional local weight bytes.

This validator intentionally separates three claims:

1. UPSTREAM_KNOWN      — an upstream open-weight artifact is identified.
2. MIRRORED_VERIFIED  — every required repo-owned mirror asset is digest-bound.
3. LOCAL_VERIFIED     — the current checkout contains bytes matching the manifest.

None of those claims grants execution, admission, effect, or state-transition
authority. Model artifacts remain evidence/capability inputs only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "models" / "model-artifacts.v1.json"
SCHEMA_PATH = ROOT / "schemas" / "model-artifacts.v1.schema.json"
MODEL_REGISTRY_PATH = ROOT / "config" / "model-capability-registry.v1.json"
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHORT_SHA_RE = re.compile(r"^[0-9a-f]{7,39}$")


class ArtifactVerificationError(RuntimeError):
    pass


def fail(message: str) -> None:
    print(f"MODEL_ARTIFACTS_INVALID: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing required file: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"expected JSON object: {path.relative_to(ROOT)}")
    return value


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(block_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def validate_schema(index: dict[str, Any], schema: dict[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(index),
        key=lambda e: [str(p) for p in e.absolute_path],
    )
    if errors:
        error = errors[0]
        location = ".".join(str(p) for p in error.absolute_path) or "<root>"
        fail(f"schema violation at {location}: {error.message}")


def validate_semantics(index: dict[str, Any]) -> None:
    if index.get("authority_rule") != "WEIGHTS_AND_MODEL_OUTPUTS_ARE_EVIDENCE_NOT_AUTHORITY":
        fail("artifact authority boundary changed")

    storage = index["storage_policy"]
    if storage["ordinary_git_weight_storage_forbidden"] is not True:
        fail("raw model weights must not enter ordinary Git history")
    if storage["local_execution_requires_verified_hydration"] is not True:
        fail("local model execution must require verified hydration")

    registry = load_json(MODEL_REGISTRY_PATH)
    providers = registry.get("providers", {})
    if not isinstance(providers, dict):
        fail("model capability registry providers field is malformed")

    packages = index["packages"]
    for package_id, package in sorted(packages.items()):
        provider = package["provider"]
        if provider not in providers:
            fail(f"package {package_id!r} references unregistered provider {provider!r}")

        availability = package["weight_availability"]
        files = package["files"]
        source = package["source"]
        mirror = package["mirror"]
        license_record = package["license"]
        checkout_path = package["checkout_path"]

        seen_paths: set[str] = set()
        for file_record in files:
            file_path = file_record["path"]
            if file_path in seen_paths:
                fail(f"package {package_id!r} repeats file {file_path!r}")
            seen_paths.add(file_path)

        if availability == "REMOTE_ONLY_NO_PUBLIC_WEIGHTS":
            if files:
                fail(f"remote-only package {package_id!r} must declare zero weight files")
            if checkout_path is not None:
                fail(f"remote-only package {package_id!r} must not declare a checkout path")
            if source.get("kind") != "provider_api" or not source.get("model_id"):
                fail(f"remote-only package {package_id!r} requires provider_api model_id")
            if mirror["state"] != "NOT_APPLICABLE_REMOTE_ONLY":
                fail(f"remote-only package {package_id!r} has invalid mirror state")
            if any(mirror[field] is not None for field in ("backend", "release_tag", "manifest_path")):
                fail(f"remote-only package {package_id!r} must not fabricate mirror coordinates")
            continue

        if availability not in {"OPEN_WEIGHTS", "MANIFEST_ONLY_PENDING_PIN"}:
            fail(f"package {package_id!r} has unsupported weight availability")
        if source.get("kind") != "huggingface" or not source.get("repo_id"):
            fail(f"open-weight package {package_id!r} requires a Hugging Face source")
        if not license_record.get("spdx"):
            fail(f"open-weight package {package_id!r} requires a declared SPDX license")
        if license_record.get("redistribution_status") != "PERMITTED_BY_DECLARED_LICENSE":
            fail(f"open-weight package {package_id!r} is not declared redistributable")
        if not checkout_path or not str(checkout_path).startswith("models/weights/"):
            fail(f"open-weight package {package_id!r} requires a repository checkout path")
        if not files:
            fail(f"open-weight package {package_id!r} requires at least one digest-bound file")

        revision = source.get("revision", "")
        revision_kind = source.get("revision_kind")
        if revision_kind == "FULL_COMMIT_SHA":
            if not FULL_SHA_RE.fullmatch(str(revision)):
                fail(f"package {package_id!r} claims FULL_COMMIT_SHA but revision is not 40 hex chars")
        elif revision_kind == "VERIFIED_SHORT_COMMIT_PREFIX":
            if not SHORT_SHA_RE.fullmatch(str(revision)):
                fail(f"package {package_id!r} has invalid short commit prefix")
            if mirror["state"] == "MIRRORED_VERIFIED":
                fail(f"package {package_id!r} cannot be mirrored from a short commit prefix")
        else:
            fail(f"package {package_id!r} has unsupported revision kind {revision_kind!r}")

        checkpoint = package.get("checkpoint")
        if checkpoint is not None:
            declared = checkpoint["declared_shard_count"]
            complete = checkpoint["complete_shard_digest_set"]
            if complete and len(files) < declared:
                fail(
                    f"package {package_id!r} claims complete shard closure but has "
                    f"{len(files)} file records for {declared} declared shards"
                )
            if mirror["state"] == "MIRRORED_VERIFIED" and not complete:
                fail(f"package {package_id!r} cannot be mirrored without complete shard digest closure")

        if mirror["state"] == "MIRRORED_VERIFIED":
            if revision_kind != "FULL_COMMIT_SHA":
                fail(f"mirrored package {package_id!r} requires exact source commit")
            if mirror["backend"] != "repository_release_assets":
                fail(f"mirrored package {package_id!r} must use repo-owned release assets")
            if not mirror["release_tag"] or not mirror["manifest_path"]:
                fail(f"mirrored package {package_id!r} is missing release coordinates")

    rules = index["future_package_rule"]
    for key in (
        "unknown_package_denied",
        "open_weight_package_requires_exact_source_revision",
        "open_weight_package_requires_license",
        "mirrored_package_requires_complete_file_digest_set",
        "remote_only_package_must_have_zero_weight_files",
        "artifact_presence_does_not_grant_execution_authority",
        "model_output_never_grants_admission_or_effect_authority",
    ):
        if rules.get(key) is not True:
            fail(f"future package invariant {key!r} must remain true")


def verify_local_package(index: dict[str, Any], package_id: str) -> dict[str, Any]:
    packages = index["packages"]
    package = packages.get(package_id)
    if not isinstance(package, dict):
        raise ArtifactVerificationError(f"unknown package: {package_id}")
    if package["weight_availability"] == "REMOTE_ONLY_NO_PUBLIC_WEIGHTS":
        raise ArtifactVerificationError(f"package {package_id} has no public/local weights")

    checkout = ROOT / package["checkout_path"]
    if not checkout.is_dir():
        raise ArtifactVerificationError(f"package {package_id} is not hydrated at {checkout}")

    verified: list[dict[str, Any]] = []
    for record in package["files"]:
        if not record.get("required_for_local_execution"):
            continue
        path = checkout / record["path"]
        if not path.is_file():
            raise ArtifactVerificationError(f"missing required weight file: {path}")
        actual = sha256_file(path)
        expected = record["sha256"]
        if actual != expected:
            raise ArtifactVerificationError(
                f"digest mismatch for {path}: expected {expected}, got {actual}"
            )
        verified.append({"path": str(path.relative_to(ROOT)), "sha256": actual})

    checkpoint = package.get("checkpoint")
    if checkpoint is not None and not checkpoint["complete_shard_digest_set"]:
        raise ArtifactVerificationError(
            f"package {package_id} lacks complete shard digest closure; local execution denied"
        )

    return {
        "receipt_kind": "MODEL_HYDRATION_VERIFICATION_V1",
        "package_id": package_id,
        "outcome": "LOCAL_VERIFIED",
        "authority": "EVIDENCE_ONLY",
        "verified_files": verified,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-local",
        metavar="PACKAGE_ID",
        help="also hash-verify required local bytes for one package",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        help="write local verification receipt to this path",
    )
    args = parser.parse_args()

    index = load_json(INDEX_PATH)
    schema = load_json(SCHEMA_PATH)
    validate_schema(index, schema)
    validate_semantics(index)

    print(
        "MODEL_ARTIFACT_INDEX_OK "
        f"packages={len(index['packages'])} "
        "authority=EVIDENCE_ONLY"
    )

    if args.verify_local:
        try:
            receipt = verify_local_package(index, args.verify_local)
        except ArtifactVerificationError as exc:
            fail(str(exc))
        encoded = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(encoded, encoding="utf-8")
        print(encoded, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
