#!/usr/bin/env python3
"""Fail-closed semantic validator for AEGIS model fabric configuration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config/model-capability-registry.v1.json"
SCHEMA_PATH = ROOT / "schemas/model-capability-registry.v1.schema.json"
ARTIFACT_INDEX_PATH = ROOT / "models/model-artifacts.v1.json"
EVIDENCE_PATHS = (
    ROOT / "models/evidence/model-source-evidence.v1.json",
    ROOT / "models/evidence/model-source-evidence.supplement.v1.json",
)

CAPABILITY_EVIDENCE_ALIASES: dict[str, frozenset[str]] = {
    "reasoning": frozenset({"reasoning"}),
    "long_context": frozenset({"long_context"}),
    "tool_use": frozenset({"tool_use", "function_calling"}),
    "multimodal": frozenset({"multimodal"}),
    "local_execution": frozenset({"open_weights", "public_weights", "edge_deployment", "private_weights"}),
}
LOCAL_WEIGHT_KINDS = {"PUBLIC_OPEN_WEIGHTS", "PRIVATE_OPERATOR_WEIGHTS"}


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


def build_source_claim_index(
    evidence_docs: list[dict], known_models: set[str]
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    claims_by_model: dict[str, set[str]] = {model_id: set() for model_id in known_models}
    source_types_by_model: dict[str, set[str]] = {model_id: set() for model_id in known_models}
    saw_future_rules = False

    for evidence in evidence_docs:
        if evidence.get("authority_rule") != "SOURCE_EVIDENCE_DOES_NOT_GRANT_MODEL_AUTHORITY":
            fail("model source evidence authority boundary changed")
        rules = evidence.get("future_source_rule")
        if rules is not None:
            if not isinstance(rules, dict):
                fail("model source evidence future_source_rule is malformed")
            saw_future_rules = True
            for key in (
                "every_registered_model_requires_bound_source_evidence",
                "public_or_vendor_model_requires_primary_source",
                "private_model_may_use_operator_private_source",
                "private_source_must_not_require_public_url",
                "source_record_is_evidence_only",
                "capability_claims_require_source_or_evaluation_support",
                "related_open_checkpoint_must_not_be_equated_with_managed_api_model",
                "license_or_rights_review_required_before_weight_mirroring",
            ):
                if rules.get(key) is not True:
                    fail(f"model source invariant {key!r} must remain true")

        sources = evidence.get("sources")
        if not isinstance(sources, dict) or not sources:
            fail("model source evidence document must contain source records")
        for source_id, source in sorted(sources.items()):
            if not isinstance(source, dict):
                fail(f"source record {source_id!r} is malformed")
            source_type = source.get("source_type")
            model_ids = source.get("model_ids")
            claims = source.get("supports_claims")
            if not isinstance(source_type, str) or not source_type:
                fail(f"source record {source_id!r} lacks source_type")
            if not isinstance(model_ids, list) or not model_ids or not all(isinstance(x, str) for x in model_ids):
                fail(f"source record {source_id!r} has invalid model_ids")
            if not isinstance(claims, list) or not all(isinstance(x, str) for x in claims):
                fail(f"source record {source_id!r} has invalid supports_claims")

            if source_type.startswith("PRIMARY_"):
                url = source.get("url")
                if not isinstance(url, str) or not url.startswith("https://"):
                    fail(f"primary source record {source_id!r} lacks an HTTPS URL")
            elif source_type.startswith("OPERATOR_PRIVATE_"):
                opaque_ref = source.get("opaque_ref")
                if not isinstance(opaque_ref, str) or not opaque_ref:
                    fail(f"private source record {source_id!r} lacks opaque_ref")
                if source.get("url") is not None:
                    fail(f"private source record {source_id!r} must not disclose a URL")
            else:
                fail(f"source record {source_id!r} has unsupported source_type {source_type!r}")

            for model_id in model_ids:
                if model_id not in known_models:
                    fail(f"source record {source_id!r} references unknown model {model_id!r}")
                claims_by_model[model_id].update(claims)
                source_types_by_model[model_id].add(source_type)

    if not saw_future_rules:
        fail("no model source evidence document carries future-source invariants")
    return claims_by_model, source_types_by_model


def main() -> int:
    registry = load_json(REGISTRY_PATH)
    schema = load_json(SCHEMA_PATH)
    artifact_index = load_json(ARTIFACT_INDEX_PATH)
    evidence_docs = [load_json(path) for path in EVIDENCE_PATHS]

    errors = sorted(
        Draft202012Validator(schema).iter_errors(registry),
        key=lambda e: [str(p) for p in e.absolute_path],
    )
    if errors:
        first = errors[0]
        location = ".".join(str(p) for p in first.absolute_path) or "<root>"
        fail(f"schema violation at {location}: {first.message}")

    if registry["authority_rule"] != "MODEL_OUTPUT_IS_EVIDENCE_NOT_AUTHORITY":
        fail("authority semantics changed")
    policy = registry["selection_policy"]
    if policy["fail_closed"] is not True or policy["allow_unknown_models"] is not False:
        fail("selection policy must fail closed and deny unknown models")

    roles = registry["roles"]
    providers = registry["providers"]
    models = registry["models"]
    artifact_packages = artifact_index.get("packages")
    if not isinstance(artifact_packages, dict):
        fail("model artifact index packages field is malformed")
    claims_by_model, source_types_by_model = build_source_claim_index(evidence_docs, set(models))

    for role_name, role in sorted(roles.items()):
        for dependency in role.get("require_provider_diversity_from", []):
            if dependency not in roles:
                fail(f"role {role_name!r} references unknown diversity role {dependency!r}")

    for model_id, model in sorted(models.items()):
        provider_id = model["provider"]
        if provider_id not in providers:
            fail(f"model {model_id!r} references unknown provider {provider_id!r}")

        package_id = model["artifact_package"]
        package = artifact_packages.get(package_id)
        if not isinstance(package, dict):
            fail(f"model {model_id!r} references unknown artifact package {package_id!r}")
        if package.get("provider") != provider_id:
            fail(f"model {model_id!r} provider disagrees with artifact package {package_id!r}")
        expected_family = providers[provider_id]["model_family"]
        if package.get("family") != expected_family:
            fail(
                f"model {model_id!r} family mismatch: provider expects {expected_family!r}, "
                f"artifact package declares {package.get('family')!r}"
            )

        surfaces = set(model["execution_surfaces"])
        availability = package["weight_availability"]
        if "local_checkpoint" in surfaces and availability not in LOCAL_WEIGHT_KINDS:
            fail(f"model {model_id!r} claims local_checkpoint without an admitted local-weight artifact kind")
        if availability == "VENDOR_REMOTE_ONLY" and surfaces != {"remote_api"}:
            fail(f"vendor-remote model {model_id!r} must expose exactly remote_api")
        if "remote_api" in surfaces and provider_id in {"google-local", "operator-local"}:
            fail(f"local provider model {model_id!r} cannot claim remote_api")
        source = package.get("source", {})
        if availability == "VENDOR_REMOTE_ONLY" and source.get("model_id") != model_id:
            fail(f"vendor-remote model {model_id!r} is not identity-bound to its provider source")

        source_types = source_types_by_model[model_id]
        if not source_types:
            fail(f"registered model {model_id!r} has no bound source evidence")
        if availability == "PRIVATE_OPERATOR_WEIGHTS":
            if not any(source_type.startswith("OPERATOR_PRIVATE_") for source_type in source_types):
                fail(f"private model {model_id!r} lacks operator-private source evidence")
        else:
            if not any(source_type.startswith("PRIMARY_") for source_type in source_types):
                fail(f"public/vendor model {model_id!r} lacks primary source evidence")

        capabilities = set(model["capabilities"])
        source_claims = claims_by_model[model_id]
        for capability in sorted(capabilities):
            aliases = CAPABILITY_EVIDENCE_ALIASES.get(capability)
            if aliases is not None and source_claims.isdisjoint(aliases):
                fail(
                    f"model {model_id!r} declares capability {capability!r} without "
                    f"bound source/evaluation support; aliases={sorted(aliases)}"
                )

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
                    fail(f"model {model_id!r} has local-only role without local checkpoint surface")
                transport = providers[provider_id]["transport"]
                if transport != "openai_compatible_local":
                    fail(f"model {model_id!r} local-only role uses non-local provider transport")

    canonical_required = {
        "provider", "status", "capabilities", "recommended_roles", "artifact_package", "execution_surfaces"
    }
    if set(registry["future_model_rule"]["minimum_fields"]) != canonical_required:
        fail(f"future_model_rule.minimum_fields must remain exactly {sorted(canonical_required)}")

    print(
        "MODEL_REGISTRY_OK "
        f"providers={len(providers)} models={len(models)} roles={len(roles)} "
        f"artifact_packages={len(artifact_packages)} source_evidence_coverage=complete "
        "private_weights_supported=true authority=EVIDENCE_ONLY fail_closed=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
