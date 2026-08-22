#!/usr/bin/env python3
"""Fail-closed semantic validator for AEGIS model-capability-registry.v1.

Schema validity is necessary but not sufficient. This validator enforces
cross-reference and role/capability invariants that JSON Schema cannot express
concisely. Model configuration is T2 evidence/configuration only and can never
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


def fail(message: str) -> None:
    print(f"MODEL_REGISTRY_INVALID: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing required file: {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")


def main() -> int:
    registry = load_json(REGISTRY_PATH)
    schema = load_json(SCHEMA_PATH)

    errors = sorted(
        Draft202012Validator(schema).iter_errors(registry),
        key=lambda e: list(e.absolute_path),
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

    for role_name, role in sorted(roles.items()):
        for dependency in role.get("require_provider_diversity_from", []):
            if dependency not in roles:
                fail(f"role {role_name!r} references unknown diversity role {dependency!r}")

    for model_id, model in sorted(models.items()):
        provider_id = model["provider"]
        if provider_id not in providers:
            fail(f"model {model_id!r} references unknown provider {provider_id!r}")

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
                transport = providers[provider_id]["transport"]
                if transport != "openai_compatible_local":
                    fail(
                        f"model {model_id!r} is recommended for local-only role "
                        f"{role_name!r} but provider transport is {transport!r}"
                    )

    required_fields = set(registry["future_model_rule"]["minimum_fields"])
    canonical_required = {"provider", "status", "capabilities", "recommended_roles"}
    if required_fields != canonical_required:
        fail(
            "future_model_rule.minimum_fields must remain exactly "
            f"{sorted(canonical_required)}"
        )

    print(
        "MODEL_REGISTRY_OK "
        f"providers={len(providers)} models={len(models)} roles={len(roles)} "
        "authority=EVIDENCE_ONLY fail_closed=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
