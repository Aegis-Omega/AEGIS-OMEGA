#!/usr/bin/env python3
"""Fail-closed semantic validator for AEGIS model-capability-registry.v1.

Schema validity is necessary but not sufficient. This validator enforces
cross-reference, role/capability, provider, execution-surface, and model-artifact
invariants. Model configuration is T2 evidence/configuration only and can never
become authority by being present in the registry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "model-capability-registry.v1.json"
SCHEMA_PATH = ROOT / "schemas" / "model-capability-registry.v1.schema.json"
ARTIFACT_INDEX_PATH = ROOT / "models" / "model-artifacts.v1.json"


def fail(message: str) -> None:
    print(f"MODEL_REGISTRY_INVALID: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing required file: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(value, dict):
        fail(f"expected JSON object in {path.relative_to(ROOT)}")
    return value


def main() -> int:
    registry = load_json(REGISTRY_PATH)
    schema = load_json(SCHEMA_PATH)
    artifact_index = load_json(ARTIFACT_INDEX_PATH)

    errors = sorted(
        Draft202012Validator(schema).iter_errors(registry),
        key=lambda e: [str(p) for p in e.absolute_path],
    )
    if errors:
        first = errors[0]
        path = ".".join(str(p) for p in first.absolute_path) or "<root>"
        fail(f"schema violation at {path}: {first.message}")

    if registry["authority_rule"] != "MODEL_OUTPUT_IS_EVIDENCE_NOT_AUTHORITY":
        fail("authority semantics changed")
    if not registry["selection_policy"]["fail_closed"]:
        fail("selection policy must fail closed")
    if registry["selection_policy"]["allow_unknown_models"]:
        fail("unknown models must never be admitted")

    roles = registry["roles"]
    providers = registry["providers"]
    models = registry["models"]
    artifact_packages = artifact_index.get("packages")
    if not isinstance(artifact_packages, dict):
        fail("model artifact index packages field is malformed")

    for role_name, role in sorted(roles.items()):
        for dependency in role.get("require_provider_diversity_from", []):
            if dependency not in roles:
                fail(f"role {role_name!r} references unknown diversity role {dependency!r}")

    for model_id, model in sorted(models.items()):
        provider_id = model["provider"]
        if provider_id not in providers:
            fail(f"model {model_id!r} references unknown provider {provider_id!r}")

        artifact_package_id = model["artifact_package"]
        artifact_package = artifact_packages.get(artifact_package_id)
        if not isinstance(artifact_package, dict):
            fail(f"model {model_id!r} references unknown artifact package {artifact_package_id!r}")
        if artifact_package.get("provider") != provider_id:
            fail(f"model {model_id!r} provider disagrees with artifact package {artifact_package_id!r}")

        expected_family = providers[provider_id]["model_family"]
        if artifact_package.get("family") != expected_family:
            fail(
                f"model {model_id!r} family mismatch: provider expects {expected_family!r}, "
                f"artifact package declares {artifact_package.get('family')!r}"
            )

        surfaces = set(model["execution_surfaces"])
        availability = artifact_package["weight_availability"]
        if "local_checkpoint" in surfaces and availability != "OPEN_WEIGHTS":
            fail(f"model {model_id!r} claims local_checkpoint without OPEN_WEIGHTS artifact package")
        if availability == "REMOTE_ONLY_NO_PUBLIC_WEIGHTS" and surfaces != {"remote_api"}:
            fail(f"remote-only model {model_id!r} must expose exactly remote_api")
        if "remote_api" in surfaces and provider_id == "google-local":
            fail(f"local provider model {model_id!r} cannot claim remote_api")

        source = artifact_package.get("source", {})
        if availability == "REMOTE_ONLY_NO_PUBLIC_WEIGHTS" and source.get("model_id") != model_id:
            fail(
                f"remote-only model {model_id!r} is not identity-bound to its artifact source "
                f"({source.get('model_id')!r})"
            )

        capabilities = set(model["capabilities"])
        for role_name in model["recommended_roles"]:
            role = roles.get(role_name)
            if role is None:
                fail(f"model {model_id!r} references unknown role {role_name!r}")
            missing = set(role["required_capabilities"]) - capabilities
            if missing:
                fail(
                    f"model {model_id!r} cannot be recommended for {role_name!r}; "
                    f"missing capabilities: {sorted(missing)}"
                )
            if role.get("privacy_requirement") == "local_only":
                if "local_checkpoint" not in surfaces:
                    fail(
                        f"model {model_id!r} is recommended for local-only role {role_name!r} "
                        "without a local_checkpoint execution surface"
                    )
                transport = providers[provider_id]["transport"]
                if transport != "openai_compatible_local":
                    fail(
                        f"model {model_id!r} is recommended for local-only role "
                        f"{role_name!r} but provider transport is {transport!r}"
                    )

    required_fields = set(registry["future_model_rule"]["minimum_fields"])
    canonical_required = {
        "provider",
        "status",
        "capabilities",
        "recommended_roles",
        "artifact_package",
        "execution_surfaces",
    }
    if required_fields != canonical_required:
        fail(
            "future_model_rule.minimum_fields must remain exactly "
            f"{sorted(canonical_required)}"
        )

    print(
        "MODEL_REGISTRY_OK "
        f"providers={len(providers)} models={len(models)} roles={len(roles)} "
        f"artifact_packages={len(artifact_packages)} "
        "authority=EVIDENCE_ONLY fail_closed=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
