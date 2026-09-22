"""Validate AEGIS Gravity/Quantum model-registry epistemic boundaries V1."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "AEGIS_GQ_MODEL_REGISTRY_V1"
ALLOWED_EVIDENCE_CLASSES = {
    "THEORETICAL_MODEL",
    "PEER_REVIEWED_PUBLISHED_MODEL",
    "PREPRINT_CRITIQUE",
}
SIGNATURE_AXES = {"M", "t", "Delta_x", "d", "R"}

class RegistryError(ValueError):
    pass

def load_registry(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError("registry unreadable") from exc
    if not isinstance(value, dict):
        raise RegistryError("registry top level must be an object")
    return value

def validate_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    if set(registry) != {
        "schema", "observed_date", "authority_effect", "models", "registry_rule"
    }:
        raise RegistryError("registry field mismatch")
    if registry["schema"] != SCHEMA:
        raise RegistryError("unsupported registry schema")
    if registry["authority_effect"] != "NONE":
        raise RegistryError("registry cannot grant authority")
    if not isinstance(registry["models"], list) or not registry["models"]:
        raise RegistryError("registry models missing")

    ids=set()
    dispute_counts={}
    contested_groups=set()
    for model in registry["models"]:
        if not isinstance(model, dict):
            raise RegistryError("model entry must be object")
        model_id=model.get("id")
        if not isinstance(model_id, str) or not model_id:
            raise RegistryError("model id missing")
        if model_id in ids:
            raise RegistryError("duplicate model id")
        ids.add(model_id)

        evidence_class=model.get("evidence_class")
        if evidence_class not in ALLOWED_EVIDENCE_CLASSES:
            raise RegistryError(f"{model_id}: unsupported evidence class {evidence_class!r}")

        status=model.get("interpretation_status")
        if not isinstance(status, str) or not status:
            raise RegistryError(f"{model_id}: interpretation status missing")
        if "ESTABLISHED" in status:
            raise RegistryError(f"{model_id}: registry cannot self-establish disputed physics")

        signature=model.get("scaling_signature")
        if signature is not None:
            if not isinstance(signature, dict) or set(signature) != SIGNATURE_AXES:
                raise RegistryError(f"{model_id}: scaling signature axes mismatch")
            if not all(type(v) is int for v in signature.values()):
                raise RegistryError(f"{model_id}: V1 scaling exponents must be exact integers")

        group=model.get("dispute_group")
        if group is not None:
            if not isinstance(group, str) or not group:
                raise RegistryError(f"{model_id}: invalid dispute group")
            counts=dispute_counts.setdefault(group, {"published":0, "critique":0})
            if evidence_class == "PEER_REVIEWED_PUBLISHED_MODEL":
                counts["published"] += 1
            if evidence_class == "PREPRINT_CRITIQUE":
                counts["critique"] += 1

        if status == "CONTESTED_MODEL_PREDICTION":
            if group is None:
                raise RegistryError(f"{model_id}: contested model missing dispute group")
            contested_groups.add(group)

    for group in contested_groups:
        counts=dispute_counts.get(group,{})
        if counts.get("published",0) < 1:
            raise RegistryError(f"{group}: contested group missing published model")
        if counts.get("critique",0) < 2:
            raise RegistryError(f"{group}: contested group needs at least two counteranalyses")

    return {
        "status":"PASS",
        "model_count":len(ids),
        "contested_groups":tuple(sorted(contested_groups)),
        "authority_effect":"NONE",
    }
