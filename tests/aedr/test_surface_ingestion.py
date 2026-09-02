#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import unicodedata
import zipfile

import pytest

from scripts.aedr.surface_ingestor import FalsificationSurfaceIngestor, SurfaceIngestionError


PR = 368
HEAD = "2" * 40
STALE = "3" * 40
RUN_ID = 33583632929


def _surface() -> dict[str, object]:
    return {
        "required_behavior_ids": [
            "BEHAVIOR_DOUBLE_COLLECT_ISOLATION",
            "BEHAVIOR_EXACT_HEAD_FILTER",
        ],
        "verified_behavior_ids": [
            "BEHAVIOR_DOUBLE_COLLECT_ISOLATION",
            "BEHAVIOR_EXACT_HEAD_FILTER",
        ],
        "required_falsifier_ids": [
            "FALSIFIER_MUTATION_RACE_DETECTED",
            "FALSIFIER_STALE_RUN_REJECTED",
        ],
        "verified_falsifier_ids": [
            "FALSIFIER_MUTATION_RACE_DETECTED",
            "FALSIFIER_STALE_RUN_REJECTED",
        ],
        "unique_non_generated_paths": [
            "scripts/aedr/acquisition_types.py",
            "scripts/aedr/live_oracle.py",
            "scripts/aedr/snapshot_builder.py",
        ],
        "assumption_identities": [],
        "security_exposure_identities": [],
    }


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _document(*, head: str = HEAD, run_id: int = RUN_ID, surface: dict[str, object] | None = None) -> dict[str, object]:
    body = surface if surface is not None else _surface()
    return {
        "schema_version": "AEDR-FALSIFIER-SURFACE-V1",
        "pr_number": PR,
        "head_sha": head,
        "run_id": run_id,
        "surface": body,
        "payload_digest": hashlib.sha256(_canonical(body)).hexdigest(),
    }


def _zip_document(document: dict[str, object], *, filename: str = "aedr-surface.json") -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, _canonical(document))
    return stream.getvalue()


def _verify(zip_bytes: bytes):
    return FalsificationSurfaceIngestor.verify_and_parse(
        zip_bytes=zip_bytes,
        expected_pr=PR,
        expected_head_sha=HEAD,
        expected_run_id=RUN_ID,
    )


def test_valid_surface_is_exact_head_bound_and_authority_neutral():
    surface = _verify(_zip_document(_document()))

    assert surface.source_head_sha == HEAD
    assert surface.exact_head_receipt_green is True
    assert surface.required_behavior_ids == frozenset(
        ["BEHAVIOR_DOUBLE_COLLECT_ISOLATION", "BEHAVIOR_EXACT_HEAD_FILTER"]
    )
    assert surface.assumption_debt_ids == frozenset()
    assert surface.security_exposure_ids == frozenset()


def test_tampered_payload_digest_rejection():
    document = _document()
    document["surface"]["verified_behavior_ids"][0] = "BEHAVIOR_TAMPERED"  # type: ignore[index]

    with pytest.raises(SurfaceIngestionError, match="TAMPERED_ARTIFACT_DETECTED"):
        _verify(_zip_document(document))


def test_stale_head_sha_mismatch_rejection():
    with pytest.raises(SurfaceIngestionError, match="STALE_SURFACE_HEAD"):
        _verify(_zip_document(_document(head=STALE)))


def test_run_id_mismatch_rejection():
    with pytest.raises(SurfaceIngestionError, match="RUN_ID_MISMATCH"):
        _verify(_zip_document(_document(run_id=RUN_ID + 1)))


def test_path_traversal_archive_rejected_even_if_valid_descriptor_also_exists():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../../evil.json", b"{}")
        archive.writestr("aedr-surface.json", _canonical(_document()))

    with pytest.raises(SurfaceIngestionError, match="UNSAFE_ZIP_PATH"):
        _verify(stream.getvalue())


def test_zip_bomb_compression_ratio_rejected_without_disk_extraction():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("aedr-surface.json", b"A" * (2 * 1024 * 1024))

    with pytest.raises(SurfaceIngestionError, match="SUSPICIOUS_COMPRESSION_RATIO"):
        _verify(stream.getvalue())


def test_unclaimed_verified_falsifier_rejection():
    body = _surface()
    body["verified_falsifier_ids"] = [
        "FALSIFIER_MUTATION_RACE_DETECTED",
        "FALSIFIER_STALE_RUN_REJECTED",
        "FALSIFIER_UNCLAIMED",
    ]

    with pytest.raises(SurfaceIngestionError, match="UNCLAIMED_VERIFIED_FALSIFIERS_FOUND"):
        _verify(_zip_document(_document(surface=body)))


def test_unknown_schema_field_is_rejected():
    document = _document()
    document["authority_class"] = "T0_FORMAL"

    with pytest.raises(SurfaceIngestionError, match="UNKNOWN_ENVELOPE_FIELDS"):
        _verify(_zip_document(document))


def test_float_anywhere_in_json_is_rejected():
    document = _document()
    document["pr_number"] = float(PR)

    with pytest.raises(SurfaceIngestionError, match="FLOAT_NOT_ALLOWED"):
        _verify(_zip_document(document))


def test_duplicate_json_key_is_rejected():
    document = _document()
    canonical = _canonical(document).decode("utf-8")
    malicious = canonical[:-1] + ',"run_id":999}'
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("aedr-surface.json", malicious.encode("utf-8"))

    with pytest.raises(SurfaceIngestionError, match="DUPLICATE_JSON_KEY"):
        _verify(stream.getvalue())


def test_set_fields_must_be_lexicographically_sorted_and_unique():
    body = _surface()
    body["required_behavior_ids"] = [
        "BEHAVIOR_EXACT_HEAD_FILTER",
        "BEHAVIOR_DOUBLE_COLLECT_ISOLATION",
    ]

    with pytest.raises(SurfaceIngestionError, match="NONCANONICAL_SET_FIELD"):
        _verify(_zip_document(_document(surface=body)))

    body = _surface()
    body["assumption_identities"] = ["ASSUMP_X", "ASSUMP_X"]
    with pytest.raises(SurfaceIngestionError, match="NONCANONICAL_SET_FIELD"):
        _verify(_zip_document(_document(surface=body)))


def test_non_nfc_string_rejected():
    body = _surface()
    decomposed = "SECURITY_CAFE\u0301"
    assert unicodedata.normalize("NFC", decomposed) != decomposed
    body["security_exposure_identities"] = [decomposed]

    with pytest.raises(SurfaceIngestionError, match="NON_NORMALIZED_STRING"):
        _verify(_zip_document(_document(surface=body)))
