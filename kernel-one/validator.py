from __future__ import annotations

import hashlib
import hmac
import json
import math
from pathlib import Path
from typing import Any, Dict

import yaml


class ValidationError(Exception):
    pass


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a regular file without changing it."""
    candidate = Path(path)
    if not candidate.is_file():
        raise ValidationError(f"FILE_NOT_FOUND:{candidate}")
    digest = hashlib.sha256()
    with candidate.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_file(path: str | Path, expected_digest: str) -> bool:
    """Verify file bytes against an explicit lowercase SHA-256 digest."""
    if (
        not isinstance(expected_digest, str)
        or len(expected_digest) != 64
        or any(ch not in "0123456789abcdef" for ch in expected_digest)
    ):
        raise ValidationError("INVALID_EXPECTED_SHA256")
    actual = sha256_file(path)
    if not hmac.compare_digest(actual, expected_digest):
        raise ValidationError(
            f"FILE_DIGEST_MISMATCH:expected={expected_digest}:actual={actual}"
        )
    return True


def calculate_residual_delta(metrics):
    weights = {
        "uncertainty": 0.4,
        "tool_failures": 0.2,
        "novelty": 0.2,
        "reviewer_disagreement": 0.2,
    }
    return sum(metrics[k] * weights[k] for k in weights)


def validate_request_structure(req: Any) -> Dict[str, Any]:
    if not isinstance(req, dict):
        raise ValidationError("Request must be a structural dictionary wrapper object.")
    required_keys = {"request_id": str, "task": str, "metrics": dict}
    for key, expected_type in required_keys.items():
        if key not in req:
            raise ValidationError(f"Missing required execution key: '{key}'")
        if not isinstance(req[key], expected_type):
            raise ValidationError(f"Type error on execution tracking key '{key}'")

    request_id = req["request_id"]
    if not request_id.strip():
        raise ValidationError("EMPTY_REQUEST_ID")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in request_id):
        raise ValidationError("CONTROL_CHARACTER_IN_REQUEST_ID")

    metrics = req["metrics"]
    for field in [
        "uncertainty",
        "tool_failures",
        "novelty",
        "reviewer_disagreement",
    ]:
        if field not in metrics:
            raise ValidationError(f"Missing observable signal metric: '{field}'")
        value = metrics[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValidationError(
                f"Type violation on observable field '{field}': Must be numeric primitive."
            )
        if not math.isfinite(float(value)):
            raise ValidationError(f"NON_FINITE_OBSERVABLE:{field}")
    return req


def validate_proposal_schema(
    raw_text: str,
    manifest_path: str = "INDEX.yaml",
    target_file: str = None,
) -> dict:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "Stochastic engine returned unparsable content structures."
        ) from exc

    if not isinstance(data, dict) or set(data.keys()) != {
        "plan",
        "output",
        "tool_calls",
    }:
        raise ValidationError(
            "Payload structural schema layout contains unexpected or missing keys."
        )

    if (
        not isinstance(data["plan"], str)
        or not isinstance(data["output"], str)
        or not isinstance(data["tool_calls"], list)
    ):
        raise ValidationError(
            "Internal proposal properties violated specified typestate values."
        )

    manifest_file = Path(manifest_path)
    if not manifest_file.is_file():
        raise ValidationError("MISSING_CONSTITUTIONAL_MANIFEST")
    with manifest_file.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise ValidationError("MALFORMED_CONSTITUTIONAL_MANIFEST")
    files_registry = manifest["files"]

    if target_file:
        if (
            target_file not in files_registry
            or files_registry[target_file].get("frozen", False)
        ):
            raise ValidationError(
                f"Constitutional mutation error: File '{target_file}' is frozen or unregistered."
            )

    for call in data["tool_calls"]:
        if not isinstance(call, dict):
            raise ValidationError("Tool structure corrupted.")
        file_arg = call.get("file")
        if file_arg and (
            file_arg not in files_registry
            or files_registry[file_arg].get("frozen", False)
        ):
            raise ValidationError(
                f"Constitutional mutation block: Tool call targets frozen or unregistered asset '{file_arg}'"
            )
    return data
