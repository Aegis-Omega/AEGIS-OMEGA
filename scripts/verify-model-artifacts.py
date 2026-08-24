#!/usr/bin/env python3
"""Validate AEGIS model artifact provenance and optional local weight bytes.

The validator separates artifact existence from artifact publicity. A private
operator checkpoint is a first-class artifact when its bytes are digest-bound;
it does not need a public URL or public redistribution license.

Artifact evidence never grants execution, admission, effect, or state-transition
authority.
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
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PUBLIC_READY = "MIRRORED_VERIFIED"
PRIVATE_READY = "PRIVATE_MIRRORED_VERIFIED"
LOCAL_WEIGHT_KINDS = {"PUBLIC_OPEN_WEIGHTS", "PRIVATE_OPERATOR_WEIGHTS"}


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
        while block := handle.read(block_size):
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


def require_checkout(package_id: str, checkout_path: object) -> None:
    if not isinstance(checkout_path, str) or not checkout_path.startswith("models/weights/"):
        fail(f"weight package {package_id!r} requires a models/weights checkout path")


def validate_checkpoint_closure(package_id: str, package: dict[str, Any]) -> None:
    checkpoint = package.get("checkpoint")
    if checkpoint is None:
        return
    declared = checkpoint["declared_shard_count"]
    complete = checkpoint["complete_shard_digest_set"]
    files = package["files"]
    mirror_state = package["mirror"]["state"]
    if complete and len(files) < declared:
        fail(
            f"package {package_id!r} claims complete shard closure but has "
            f"{len(files)} file records for {declared} declared shards"
        )
    if mirror_state in {PUBLIC_READY, PRIVATE_READY} and not complete:
        fail(f"package {package_id!r} cannot be ready without complete shard digest closure")


def validate_semantics(index: dict[str, Any]) -> None:
    if index.get("authority_rule") != "WEIGHTS_AND_MODEL_OUTPUTS_ARE_EVIDENCE_NOT_AUTHORITY":
        fail("artifact authority boundary changed")

    storage = index["storage_policy"]
    for required_true in (
        "ordinary_git_weight_storage_forbidden",
        "require_sha256_for_every_mirrored_asset",
        "require_exact_source_revision_before_mirroring",
        "require_license_before_public_mirroring",
        "public_repository_plaintext_private_weights_forbidden",
        "local_execution_requires_verified_hydration",
    ):
        if storage.get(required_true) is not True:
            fail(f"storage invariant {required_true!r} must remain true")

    registry = load_json(MODEL_REGISTRY_PATH)
    providers = registry.get("providers", {})
    models = registry.get("models", {})
    if not isinstance(providers, dict) or not isinstance(models, dict):
        fail("model capability registry is malformed")

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
        for record in files:
            path = record["path"]
            if path in seen_paths:
                fail(f"package {package_id!r} repeats file {path!r}")
            seen_paths.add(path)

        if availability == "VENDOR_REMOTE_ONLY":
            if files or checkout_path is not None:
                fail(f"vendor-remote package {package_id!r} must not claim repo-local weight bytes")
            if source.get("kind") != "provider_api" or not source.get("model_id"):
                fail(f"vendor-remote package {package_id!r} requires provider_api model_id")
            if license_record.get("redistribution_status") != "NOT_APPLICABLE_VENDOR_REMOTE":
                fail(f"vendor-remote package {package_id!r} has invalid rights classification")
            if mirror["state"] != "NOT_APPLICABLE_VENDOR_REMOTE":
                fail(f"vendor-remote package {package_id!r} has invalid mirror state")
            if any(mirror[field] is not None for field in ("backend", "release_tag", "manifest_path")):
                fail(f"vendor-remote package {package_id!r} must not fabricate mirror coordinates")
            continue

        if availability == "PUBLIC_OPEN_WEIGHTS":
            if source.get("kind") != "huggingface" or not source.get("repo_id"):
                fail(f"public open-weight package {package_id!r} requires a Hugging Face source")
            if not license_record.get("spdx"):
                fail(f"public open-weight package {package_id!r} requires a declared SPDX license")
            if license_record.get("redistribution_status") != "PERMITTED_BY_DECLARED_LICENSE":
                fail(f"public open-weight package {package_id!r} is not declared redistributable")
            require_checkout(package_id, checkout_path)
            if not files:
                fail(f"public open-weight package {package_id!r} requires digest-bound files")
            revision = str(source.get("revision", ""))
            if source.get("revision_kind") != "FULL_COMMIT_SHA" or not FULL_SHA_RE.fullmatch(revision):
                fail(f"public open-weight package {package_id!r} requires an exact 40-char source commit")
            if mirror["state"] == PUBLIC_READY:
                if mirror["backend"] != "repository_release_assets":
                    fail(f"public mirrored package {package_id!r} must use repository release assets")
                if not mirror["release_tag"] or not mirror["manifest_path"]:
                    fail(f"public mirrored package {package_id!r} lacks release coordinates")
                if not (ROOT / mirror["manifest_path"]).is_file():
                    fail(f"public mirrored package {package_id!r} lacks committed release manifest")
            validate_checkpoint_closure(package_id, package)
            continue

        if availability == "PRIVATE_OPERATOR_WEIGHTS":
            if source.get("kind") != "operator_private":
                fail(f"private package {package_id!r} requires operator_private source kind")
            opaque_ref = source.get("opaque_ref")
            content_root = source.get("content_root_sha256")
            if not isinstance(opaque_ref, str) or not opaque_ref.strip():
                fail(f"private package {package_id!r} requires a non-public opaque source reference")
            if source.get("revision_kind") != "PRIVATE_CONTENT_ROOT" or not isinstance(content_root, str) or not SHA256_RE.fullmatch(content_root):
                fail(f"private package {package_id!r} requires a SHA-256 private content root")
            if license_record.get("redistribution_status") != "PRIVATE_OPERATOR_ONLY":
                fail(f"private package {package_id!r} must remain operator-private")
            require_checkout(package_id, checkout_path)
            if not files:
                fail(f"private package {package_id!r} requires digest-bound files")
            if mirror["state"] not in {"PRIVATE_SOURCE_REGISTERED_NOT_YET_MIRRORED", PRIVATE_READY}:
                fail(f"private package {package_id!r} has invalid private mirror state")
            if mirror["state"] == PRIVATE_READY:
                if mirror["backend"] not in {"operator_private_store", "encrypted_repository_release_assets"}:
                    fail(f"private package {package_id!r} uses an unsafe mirror backend")
                if not mirror["manifest_path"] or not (ROOT / mirror["manifest_path"]).is_file():
                    fail(f"private mirrored package {package_id!r} lacks committed non-secret manifest")
                if mirror["backend"] == "encrypted_repository_release_assets" and not mirror["release_tag"]:
                    fail(f"encrypted repo mirror {package_id!r} requires a release tag")
            validate_checkpoint_closure(package_id, package)
            continue

        if availability == "MANIFEST_ONLY_PENDING_PIN":
            if source.get("kind") != "huggingface" or not source.get("repo_id"):
                fail(f"pending public package {package_id!r} requires upstream repository identity")
            revision = str(source.get("revision", ""))
            kind = source.get("revision_kind")
            if kind not in {"FULL_COMMIT_SHA", "VERIFIED_SHORT_COMMIT_PREFIX"}:
                fail(f"pending package {package_id!r} has invalid revision kind")
            if kind == "FULL_COMMIT_SHA" and not FULL_SHA_RE.fullmatch(revision):
                fail(f"pending package {package_id!r} has invalid full commit")
            if kind == "VERIFIED_SHORT_COMMIT_PREFIX" and not SHORT_SHA_RE.fullmatch(revision):
                fail(f"pending package {package_id!r} has invalid short commit prefix")
            continue

        if availability == "UNVERIFIED_UNKNOWN":
            if mirror["state"] in {PUBLIC_READY, PRIVATE_READY}:
                fail(f"unverified package {package_id!r} cannot claim verified mirror readiness")
            continue

        fail(f"package {package_id!r} has unsupported weight availability {availability!r}")

    for model_id, model in sorted(models.items()):
        if not isinstance(model, dict):
            fail(f"model {model_id!r} is malformed")
        artifact_package = model.get("artifact_package")
        if artifact_package is None:
            continue
        package = packages.get(artifact_package)
        if not isinstance(package, dict):
            fail(f"model {model_id!r} references unknown artifact package {artifact_package!r}")
        if package["provider"] != model.get("provider"):
            fail(f"model {model_id!r} provider disagrees with artifact package {artifact_package!r}")

    rules = index["future_package_rule"]
    for key in (
        "unknown_package_denied",
        "open_weight_package_requires_exact_source_revision",
        "open_weight_package_requires_license",
        "private_weight_package_requires_digest_binding",
        "private_weight_package_may_use_opaque_source",
        "private_weight_plaintext_publication_forbidden",
        "vendor_remote_does_not_imply_weights_do_not_exist",
        "mirrored_package_requires_complete_file_digest_set",
        "vendor_remote_package_must_have_zero_repo_weight_files",
        "artifact_presence_does_not_grant_execution_authority",
        "model_output_never_grants_admission_or_effect_authority",
    ):
        if rules.get(key) is not True:
            fail(f"future package invariant {key!r} must remain true")


def verify_local_package(index: dict[str, Any], package_id: str) -> dict[str, Any]:
    package = index["packages"].get(package_id)
    if not isinstance(package, dict):
        raise ArtifactVerificationError(f"unknown package: {package_id}")

    availability = package["weight_availability"]
    if availability not in LOCAL_WEIGHT_KINDS:
        raise ArtifactVerificationError(f"package {package_id} has no admitted local weight artifact")

    expected_ready_state = PRIVATE_READY if availability == "PRIVATE_OPERATOR_WEIGHTS" else PUBLIC_READY
    if package["mirror"]["state"] != expected_ready_state:
        raise ArtifactVerificationError(
            f"package {package_id} has not passed its mirror admission; local execution denied"
        )

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
        "weight_availability": availability,
        "outcome": "LOCAL_VERIFIED",
        "authority": "EVIDENCE_ONLY",
        "verified_files": verified,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-local", metavar="PACKAGE_ID")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    index = load_json(INDEX_PATH)
    schema = load_json(SCHEMA_PATH)
    validate_schema(index, schema)
    validate_semantics(index)

    print(
        "MODEL_ARTIFACT_INDEX_OK "
        f"packages={len(index['packages'])} authority=EVIDENCE_ONLY "
        "private_weights_supported=true"
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
