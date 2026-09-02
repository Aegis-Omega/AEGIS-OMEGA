#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import stat
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping

from .dag_model import FalsificationSurface


class SurfaceIngestionError(Exception):
    pass


@dataclass(frozen=True)
class RawArtifactMetadata:
    artifact_id: int
    name: str
    size_in_bytes: int
    archive_download_url: str
    workflow_run_id: int
    workflow_run_head_sha: str


class FalsificationSurfaceIngestor:
    """Parse one untrusted Actions artifact into an authority-neutral surface."""

    SCHEMA_VERSION = "AEDR-FALSIFIER-SURFACE-V1"
    DESCRIPTOR_NAME = "aedr-surface.json"
    MAX_ARCHIVE_BYTES = 2 * 1024 * 1024
    MAX_UNCOMPRESSED_BYTES = 10 * 1024 * 1024
    MAX_ENTRY_COUNT = 8
    MAX_COMPRESSION_RATIO = 100.0

    ENVELOPE_FIELDS = frozenset(
        {
            "schema_version",
            "pr_number",
            "head_sha",
            "run_id",
            "surface",
            "payload_digest",
        }
    )
    SURFACE_FIELDS = frozenset(
        {
            "required_behavior_ids",
            "verified_behavior_ids",
            "required_falsifier_ids",
            "verified_falsifier_ids",
            "unique_non_generated_paths",
            "assumption_identities",
            "security_exposure_identities",
        }
    )

    @staticmethod
    def _canonical_json(value: object) -> bytes:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")

    @staticmethod
    def _reject_float(_: str) -> float:
        raise SurfaceIngestionError("FLOAT_NOT_ALLOWED")

    @staticmethod
    def _reject_constant(_: str) -> object:
        raise SurfaceIngestionError("NONFINITE_NUMBER_NOT_ALLOWED")

    @staticmethod
    def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SurfaceIngestionError(f"DUPLICATE_JSON_KEY: {key}")
            result[key] = value
        return result

    @classmethod
    def _parse_json(cls, raw: bytes) -> dict[str, Any]:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SurfaceIngestionError("MALFORMED_UTF8_PAYLOAD") from exc
        if text.startswith("\ufeff"):
            raise SurfaceIngestionError("UTF8_BOM_NOT_ALLOWED")
        try:
            value = json.loads(
                text,
                object_pairs_hook=cls._unique_object,
                parse_float=cls._reject_float,
                parse_constant=cls._reject_constant,
            )
        except SurfaceIngestionError:
            raise
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise SurfaceIngestionError("MALFORMED_JSON_PAYLOAD") from exc
        if not isinstance(value, dict):
            raise SurfaceIngestionError("ENVELOPE_MUST_BE_OBJECT")
        return value

    @staticmethod
    def _validate_normalized_string(value: str, *, field_name: str) -> str:
        if unicodedata.normalize("NFC", value) != value:
            raise SurfaceIngestionError(f"NON_NORMALIZED_STRING: {field_name}")
        if not value or value != value.strip():
            raise SurfaceIngestionError(f"NONCANONICAL_STRING: {field_name}")
        if any(unicodedata.category(char).startswith("C") for char in value):
            raise SurfaceIngestionError(f"CONTROL_CHARACTER_NOT_ALLOWED: {field_name}")
        return value

    @classmethod
    def _extract_set(cls, surface: Mapping[str, Any], field_name: str) -> frozenset[str]:
        raw = surface[field_name]
        if not isinstance(raw, list) or not all(type(item) is str for item in raw):
            raise SurfaceIngestionError(f"INVALID_SET_FIELD: {field_name}")
        normalized = [
            cls._validate_normalized_string(item, field_name=field_name)
            for item in raw
        ]
        if normalized != sorted(normalized) or len(normalized) != len(set(normalized)):
            raise SurfaceIngestionError(f"NONCANONICAL_SET_FIELD: {field_name}")
        return frozenset(normalized)

    @classmethod
    def _validate_paths(cls, paths: frozenset[str]) -> None:
        for raw_path in paths:
            if "\\" in raw_path or raw_path.startswith("/"):
                raise SurfaceIngestionError("UNSAFE_SURFACE_PATH")
            path = PurePosixPath(raw_path)
            if raw_path != path.as_posix() or any(part in ("", ".", "..") for part in path.parts):
                raise SurfaceIngestionError("UNSAFE_SURFACE_PATH")

    @classmethod
    def _read_descriptor(cls, zip_bytes: bytes) -> bytes:
        if not zip_bytes:
            raise SurfaceIngestionError("EMPTY_ARTIFACT_STREAM")
        if len(zip_bytes) > cls.MAX_ARCHIVE_BYTES:
            raise SurfaceIngestionError("ARCHIVE_EXCEEDS_COMPRESSED_SIZE_LIMIT")

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
                infos = archive.infolist()
                if len(infos) > cls.MAX_ENTRY_COUNT:
                    raise SurfaceIngestionError("TOO_MANY_ZIP_ENTRIES")

                total_uncompressed = 0
                descriptor: zipfile.ZipInfo | None = None
                for info in infos:
                    filename = info.filename
                    if (
                        not filename
                        or "\\" in filename
                        or filename.startswith("/")
                        or PurePosixPath(filename).is_absolute()
                        or any(part in ("", ".", "..") for part in PurePosixPath(filename).parts)
                    ):
                        raise SurfaceIngestionError("UNSAFE_ZIP_PATH")
                    if info.flag_bits & 0x1:
                        raise SurfaceIngestionError("ENCRYPTED_ZIP_ENTRY_NOT_ALLOWED")
                    unix_mode = (info.external_attr >> 16) & 0xFFFF
                    if unix_mode and stat.S_ISLNK(unix_mode):
                        raise SurfaceIngestionError("ZIP_SYMLINK_NOT_ALLOWED")
                    if info.is_dir():
                        raise SurfaceIngestionError("ZIP_DIRECTORY_NOT_ALLOWED")

                    total_uncompressed += info.file_size
                    if total_uncompressed > cls.MAX_UNCOMPRESSED_BYTES:
                        raise SurfaceIngestionError("ARTIFACT_EXCEEDS_SIZE_LIMIT")
                    if info.file_size > cls.MAX_UNCOMPRESSED_BYTES:
                        raise SurfaceIngestionError("ARTIFACT_EXCEEDS_SIZE_LIMIT")
                    if info.file_size > 0:
                        if info.compress_size <= 0:
                            raise SurfaceIngestionError("SUSPICIOUS_COMPRESSION_RATIO")
                        ratio = info.file_size / info.compress_size
                        if ratio > cls.MAX_COMPRESSION_RATIO:
                            raise SurfaceIngestionError("SUSPICIOUS_COMPRESSION_RATIO")

                    if filename == cls.DESCRIPTOR_NAME:
                        if descriptor is not None:
                            raise SurfaceIngestionError("DUPLICATE_SURFACE_DESCRIPTOR")
                        descriptor = info
                    else:
                        raise SurfaceIngestionError(f"UNEXPECTED_ZIP_ENTRY: {filename}")

                if descriptor is None:
                    raise SurfaceIngestionError("MISSING_SURFACE_DESCRIPTOR")
                with archive.open(descriptor, "r") as stream:
                    raw = stream.read(cls.MAX_UNCOMPRESSED_BYTES + 1)
                    if len(raw) > cls.MAX_UNCOMPRESSED_BYTES:
                        raise SurfaceIngestionError("ARTIFACT_EXCEEDS_SIZE_LIMIT")
                    return raw
        except SurfaceIngestionError:
            raise
        except zipfile.BadZipFile as exc:
            raise SurfaceIngestionError("CORRUPTED_ZIP_ARCHIVE") from exc
        except (OSError, RuntimeError) as exc:
            raise SurfaceIngestionError("ZIP_READ_FAILURE") from exc

    @classmethod
    def verify_and_parse(
        cls,
        zip_bytes: bytes,
        expected_pr: int,
        expected_head_sha: str,
        expected_run_id: int,
    ) -> FalsificationSurface:
        raw_content = cls._read_descriptor(zip_bytes)
        data = cls._parse_json(raw_content)

        keys = frozenset(data)
        if keys != cls.ENVELOPE_FIELDS:
            unknown = sorted(keys - cls.ENVELOPE_FIELDS)
            missing = sorted(cls.ENVELOPE_FIELDS - keys)
            if unknown:
                raise SurfaceIngestionError(f"UNKNOWN_ENVELOPE_FIELDS: {unknown}")
            raise SurfaceIngestionError(f"MISSING_ENVELOPE_FIELDS: {missing}")

        if data["schema_version"] != cls.SCHEMA_VERSION:
            raise SurfaceIngestionError(f"UNSUPPORTED_SCHEMA: {data['schema_version']}")
        if type(data["pr_number"]) is not int or data["pr_number"] != expected_pr:
            raise SurfaceIngestionError(
                f"PR_MISMATCH: expected {expected_pr}, found {data['pr_number']}"
            )
        if type(data["run_id"]) is not int or data["run_id"] != expected_run_id:
            raise SurfaceIngestionError(
                f"RUN_ID_MISMATCH: expected {expected_run_id}, found {data['run_id']}"
            )
        if type(data["head_sha"]) is not str:
            raise SurfaceIngestionError("INVALID_HEAD_SHA")
        declared_head = data["head_sha"].lower()
        if declared_head != expected_head_sha.lower():
            raise SurfaceIngestionError(
                f"STALE_SURFACE_HEAD: expected {expected_head_sha.lower()}, found {declared_head}"
            )

        surface = data["surface"]
        if not isinstance(surface, dict):
            raise SurfaceIngestionError("MISSING_SURFACE_BODY")
        surface_keys = frozenset(surface)
        if surface_keys != cls.SURFACE_FIELDS:
            unknown = sorted(surface_keys - cls.SURFACE_FIELDS)
            missing = sorted(cls.SURFACE_FIELDS - surface_keys)
            if unknown:
                raise SurfaceIngestionError(f"UNKNOWN_SURFACE_FIELDS: {unknown}")
            raise SurfaceIngestionError(f"MISSING_SURFACE_FIELDS: {missing}")

        if type(data["payload_digest"]) is not str:
            raise SurfaceIngestionError("INVALID_PAYLOAD_DIGEST")
        declared_digest = data["payload_digest"].lower()
        computed_digest = hashlib.sha256(cls._canonical_json(surface)).hexdigest()
        if declared_digest != computed_digest:
            raise SurfaceIngestionError(
                f"TAMPERED_ARTIFACT_DETECTED: computed {computed_digest} != declared {declared_digest}"
            )

        required_behaviors = cls._extract_set(surface, "required_behavior_ids")
        verified_behaviors = cls._extract_set(surface, "verified_behavior_ids")
        required_falsifiers = cls._extract_set(surface, "required_falsifier_ids")
        verified_falsifiers = cls._extract_set(surface, "verified_falsifier_ids")
        paths = cls._extract_set(surface, "unique_non_generated_paths")
        assumptions = cls._extract_set(surface, "assumption_identities")
        exposures = cls._extract_set(surface, "security_exposure_identities")
        cls._validate_paths(paths)

        if not verified_behaviors.issubset(required_behaviors):
            raise SurfaceIngestionError("UNCLAIMED_VERIFIED_BEHAVIORS_FOUND")
        if not verified_falsifiers.issubset(required_falsifiers):
            raise SurfaceIngestionError("UNCLAIMED_VERIFIED_FALSIFIERS_FOUND")

        return FalsificationSurface(
            source_head_sha=expected_head_sha.lower(),
            required_behavior_ids=required_behaviors,
            required_falsifier_ids=required_falsifiers,
            unique_non_generated_paths=paths,
            verified_behavior_ids=verified_behaviors,
            verified_falsifier_ids=verified_falsifiers,
            assumption_debt_ids=assumptions,
            security_exposure_ids=exposures,
            exact_head_receipt_green=True,
        )
