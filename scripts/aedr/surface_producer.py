#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Mapping


_SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")


class SurfaceProductionError(Exception):
    pass


MANIFEST_SCHEMA = "AEDR-FALSIFIER-MANIFEST-V1"
SURFACE_SCHEMA = "AEDR-FALSIFIER-SURFACE-V1"
MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "required_behavior_ids",
        "required_falsifier_ids",
        "unique_non_generated_paths",
        "assumption_identities",
        "security_exposure_identities",
    }
)
SET_FIELDS = (
    "required_behavior_ids",
    "required_falsifier_ids",
    "unique_non_generated_paths",
    "assumption_identities",
    "security_exposure_identities",
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _validate_manifest_set(manifest: Mapping[str, Any], field: str) -> list[str]:
    raw = manifest.get(field)
    if not isinstance(raw, list) or not all(type(value) is str for value in raw):
        raise SurfaceProductionError(f"INVALID_MANIFEST_SET: {field}")
    for value in raw:
        if (
            not value
            or value != value.strip()
            or unicodedata.normalize("NFC", value) != value
            or any(unicodedata.category(char).startswith("C") for char in value)
        ):
            raise SurfaceProductionError(f"INVALID_MANIFEST_STRING: {field}")
    if raw != sorted(raw) or len(raw) != len(set(raw)):
        raise SurfaceProductionError(f"NONCANONICAL_MANIFEST_SET: {field}")
    return list(raw)


def _validate_manifest(manifest: Mapping[str, Any]) -> dict[str, list[str]]:
    if frozenset(manifest) != MANIFEST_FIELDS:
        unknown = sorted(frozenset(manifest) - MANIFEST_FIELDS)
        missing = sorted(MANIFEST_FIELDS - frozenset(manifest))
        if unknown:
            raise SurfaceProductionError(f"UNKNOWN_MANIFEST_FIELDS: {unknown}")
        raise SurfaceProductionError(f"MISSING_MANIFEST_FIELDS: {missing}")
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise SurfaceProductionError("UNSUPPORTED_MANIFEST_SCHEMA")
    return {field: _validate_manifest_set(manifest, field) for field in SET_FIELDS}


def build_surface_document(
    manifest: Mapping[str, Any],
    *,
    pr_number: int,
    head_sha: str,
    run_id: int,
) -> dict[str, object]:
    if type(pr_number) is not int or pr_number <= 0:
        raise SurfaceProductionError("INVALID_PR_NUMBER")
    if type(run_id) is not int or run_id <= 0:
        raise SurfaceProductionError("INVALID_RUN_ID")
    if type(head_sha) is not str or not _SHA40.fullmatch(head_sha):
        raise SurfaceProductionError("INVALID_HEAD_SHA")
    head_sha = head_sha.lower()

    fields = _validate_manifest(manifest)
    surface = {
        "required_behavior_ids": fields["required_behavior_ids"],
        # This producer is invoked only after the complete AEDR contract step succeeds.
        # Terminal run success is still independently required by the consumer binder.
        "verified_behavior_ids": fields["required_behavior_ids"],
        "required_falsifier_ids": fields["required_falsifier_ids"],
        "verified_falsifier_ids": fields["required_falsifier_ids"],
        "unique_non_generated_paths": fields["unique_non_generated_paths"],
        "assumption_identities": fields["assumption_identities"],
        "security_exposure_identities": fields["security_exposure_identities"],
    }
    payload_digest = hashlib.sha256(_canonical_json(surface)).hexdigest()
    return {
        "schema_version": SURFACE_SCHEMA,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "run_id": run_id,
        "surface": surface,
        "payload_digest": payload_digest,
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SurfaceProductionError(f"MANIFEST_READ_FAILURE: {path}") from exc
    try:
        text = raw.decode("utf-8")
        value = json.loads(text, parse_float=lambda _: (_ for _ in ()).throw(SurfaceProductionError("FLOAT_NOT_ALLOWED")))
    except SurfaceProductionError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SurfaceProductionError("MALFORMED_MANIFEST_JSON") from exc
    if not isinstance(value, dict):
        raise SurfaceProductionError("MANIFEST_MUST_BE_OBJECT")
    return value


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Produce one exact-run AEDR falsification surface")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    document = build_surface_document(
        _load_manifest(Path(args.manifest)),
        pr_number=args.pr_number,
        head_sha=args.head_sha,
        run_id=args.run_id,
    )
    _atomic_write(Path(args.output), _canonical_json(document) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
