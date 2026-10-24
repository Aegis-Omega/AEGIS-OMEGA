"""Versioned, offline-only workflow packs for the AEGIS Python SDK."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .packs import PACKS, READ_ONLY, SCHEMA_V1, get_pack

SCHEMA_V0 = "aegis.workflow-pack/0"
MAX_PACK_BYTES = 262_144
_ID = re.compile(r"^[a-z0-9][a-z0-9.-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PACK_FIELDS = {
    "schema", "pack_id", "domain", "permissions", "objective",
    "steps", "acceptance", "artifacts",
}


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read_pack(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("workflow pack path must be a regular file")
    with path.open("rb") as stream:
        raw = stream.read(MAX_PACK_BYTES + 1)
    if len(raw) > MAX_PACK_BYTES:
        raise ValueError(f"workflow pack exceeds {MAX_PACK_BYTES} bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"invalid workflow pack JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("workflow pack must be a JSON object")
    return value


def load_pack(source: str) -> dict[str, Any]:
    """Load a bundled sample by name or a user-selected local JSON file."""
    if source in PACKS:
        return get_pack(source)
    return _read_pack(Path(source))


def migrate_pack(pack: dict[str, Any]) -> dict[str, Any]:
    """Migrate the read-only v0 shape to v1; never infer additional permissions."""
    if not isinstance(pack, dict):
        raise ValueError("workflow pack must be a JSON object")
    if pack.get("schema") == SCHEMA_V1:
        return dict(pack)
    if pack.get("schema") != SCHEMA_V0:
        raise ValueError(f"unsupported workflow pack schema {pack.get('schema')!r}")
    if "permissions" in pack:
        raise ValueError("v0 migration refuses an explicit permissions field")
    migrated = dict(pack)
    migrated["schema"] = SCHEMA_V1
    migrated["permissions"] = READ_ONLY
    return migrated


def validate_pack(pack: dict[str, Any]) -> dict[str, Any]:
    """Validate pack structure and embedded artifact digests, not task correctness."""
    if not isinstance(pack, dict):
        raise ValueError("workflow pack must be a JSON object")
    if any(not isinstance(key, str) for key in pack):
        raise ValueError("workflow pack keys must be strings")
    if set(pack) != _PACK_FIELDS:
        missing = sorted(_PACK_FIELDS - set(pack))
        extra = sorted(set(pack) - _PACK_FIELDS)
        raise ValueError(f"workflow pack fields invalid (missing={missing}, extra={extra})")
    if pack["schema"] != SCHEMA_V1:
        raise ValueError(f"unsupported workflow pack schema {pack['schema']!r}")
    if not isinstance(pack["pack_id"], str) or not _ID.fullmatch(pack["pack_id"]):
        raise ValueError("pack_id must be a lowercase identifier")
    if not isinstance(pack["domain"], str) or pack["domain"] not in {
        "code", "data", "science",
    }:
        raise ValueError("domain must be code, data, or science")
    if pack["permissions"] != READ_ONLY:
        raise ValueError("only read_only permissions are supported")
    if (not isinstance(pack["objective"], str) or not pack["objective"].strip()
            or len(pack["objective"]) > 2048):
        raise ValueError("objective must be a non-empty string of at most 2048 characters")

    for field, item_name, item_field in (
        ("steps", "step", "description"),
        ("acceptance", "acceptance criterion", "criterion"),
    ):
        items = pack[field]
        if not isinstance(items, list) or not 1 <= len(items) <= 25:
            raise ValueError(f"{field} must contain 1 to 25 entries")
        seen = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != {"id", item_field}:
                raise ValueError(f"each {item_name} must contain only id and {item_field}")
            if not isinstance(item["id"], str) or not _ID.fullmatch(item["id"]):
                raise ValueError(f"{item_name} id must be a lowercase identifier")
            if item["id"] in seen:
                raise ValueError(f"duplicate {item_name} id {item['id']!r}")
            seen.add(item["id"])
            if (not isinstance(item[item_field], str) or not item[item_field].strip()
                    or len(item[item_field]) > 2048):
                raise ValueError(f"{item_field} must be a non-empty string of at most 2048 characters")

    artifacts = pack["artifacts"]
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 25:
        raise ValueError("artifacts must contain 1 to 25 entries")
    seen_artifacts = set()
    total_content_bytes = 0
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != {
            "id", "media_type", "content", "sha256",
        }:
            raise ValueError("each artifact must contain id, media_type, content, and sha256")
        artifact_id = artifact["id"]
        if not isinstance(artifact_id, str) or not _ID.fullmatch(artifact_id):
            raise ValueError("artifact id must be a lowercase identifier")
        if artifact_id in seen_artifacts:
            raise ValueError(f"duplicate artifact id {artifact_id!r}")
        seen_artifacts.add(artifact_id)
        if (not isinstance(artifact["media_type"], str) or not artifact["media_type"]
                or len(artifact["media_type"]) > 128):
            raise ValueError("artifact media_type must be a non-empty string of at most 128 characters")
        content = artifact["content"]
        if not isinstance(content, str):
            raise ValueError("artifact content must be a bounded UTF-8 string")
        try:
            content_bytes = content.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("artifact content must be valid UTF-8 text") from exc
        total_content_bytes += len(content_bytes)
        if total_content_bytes > MAX_PACK_BYTES:
            raise ValueError("total embedded artifact content exceeds the pack size limit")
        digest = artifact["sha256"]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError(f"artifact {artifact_id!r} has an invalid SHA-256")
        actual = hashlib.sha256(content_bytes).hexdigest()
        if digest != actual:
            raise ValueError(f"artifact {artifact_id!r} SHA-256 mismatch")
    return {
        "valid": True,
        "pack_id": pack["pack_id"],
        "schema": SCHEMA_V1,
        "domain": pack["domain"],
        "artifact_count": len(artifacts),
        "permissions": READ_ONLY,
        "assessment": "STRUCTURE_AND_EMBEDDED_DIGESTS_ONLY",
        "task_correctness": "NOT_VERIFIED",
        "authority_effect": "NONE",
    }


def plan_pack(pack: dict[str, Any]) -> dict[str, Any]:
    validation = validate_pack(pack)
    return {
        **validation,
        "execution": "NOT_EXECUTED",
        "steps": [{"id": step["id"], "description": step["description"]}
                  for step in pack["steps"]],
        "acceptance_ids": [item["id"] for item in pack["acceptance"]],
    }


def simulate_pack(pack: dict[str, Any]) -> dict[str, Any]:
    plan = plan_pack(pack)
    plan["simulation"] = "DRY_RUN_ONLY"
    plan["steps"] = [{**step, "status": "NOT_EXECUTED"} for step in plan["steps"]]
    plan["acceptance"] = [
        {"id": item["id"], "status": "NOT_EVALUATED"}
        for item in pack["acceptance"]
    ]
    return plan


def export_pack(pack: dict[str, Any]) -> str:
    validate_pack(pack)
    return json.dumps(pack, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def run_work_command(command: str, source: str) -> str:
    pack = load_pack(source)
    if command == "export":
        return export_pack(pack)
    if command == "validate":
        result = validate_pack(pack)
    elif command == "plan":
        result = plan_pack(pack)
    elif command == "simulate":
        result = simulate_pack(pack)
    elif command == "verify":
        result = validate_pack(pack)
        result["verification"] = "EMBEDDED_ARTIFACT_DIGESTS_VALID"
    else:
        raise ValueError(f"unknown work command {command!r}")
    return json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
