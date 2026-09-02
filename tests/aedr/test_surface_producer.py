#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import zipfile

import pytest

from scripts.aedr.surface_ingestor import FalsificationSurfaceIngestor
from scripts.aedr.surface_producer import SurfaceProductionError, build_surface_document


HEAD = "f" * 40
PR = 369
RUN = 123456789
UPLOAD_ARTIFACT_SHA = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "AEDR-FALSIFIER-MANIFEST-V1",
        "required_behavior_ids": [
            "BEHAVIOR_ARTIFACT_PINNING",
            "BEHAVIOR_DOUBLE_COLLECT_ISOLATION",
            "BEHAVIOR_EXACT_HEAD_FILTER",
            "BEHAVIOR_STRICT_SURFACE_SCHEMA",
        ],
        "required_falsifier_ids": [
            "FALSIFIER_CREDENTIAL_REDIRECT_LEAK_REJECTED",
            "FALSIFIER_STALE_HEAD_REJECTED",
            "FALSIFIER_TAMPERED_SURFACE_REJECTED",
            "FALSIFIER_ZIP_TRAVERSAL_REJECTED",
        ],
        "unique_non_generated_paths": [
            "scripts/aedr/acquisition_adapter.py",
            "scripts/aedr/artifact_surface_oracle.py",
            "scripts/aedr/live_oracle.py",
            "scripts/aedr/surface_ingestor.py",
        ],
        "assumption_identities": [
            "ASSUMP_AEDR_EXTERNAL_ASSUMPTION_DISCOVERY_NOT_INTEGRATED"
        ],
        "security_exposure_identities": [
            "SECURITY_AEDR_EXTERNAL_SECURITY_SCAN_NOT_INTEGRATED"
        ],
    }


def _zip_raw(raw: bytes) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("aedr-surface.json", raw)
    return stream.getvalue()


def test_producer_binds_runtime_identity_and_round_trips_through_strict_ingestor():
    document = build_surface_document(_manifest(), pr_number=PR, head_sha=HEAD, run_id=RUN)

    assert document["pr_number"] == PR
    assert document["head_sha"] == HEAD
    assert document["run_id"] == RUN
    assert document["surface"]["verified_behavior_ids"] == document["surface"]["required_behavior_ids"]
    assert document["surface"]["verified_falsifier_ids"] == document["surface"]["required_falsifier_ids"]

    surface = document["surface"]
    canonical = json.dumps(surface, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    assert document["payload_digest"] == hashlib.sha256(canonical).hexdigest()

    raw = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    parsed = FalsificationSurfaceIngestor.verify_and_parse(
        zip_bytes=_zip_raw(raw),
        expected_pr=PR,
        expected_head_sha=HEAD,
        expected_run_id=RUN,
    )
    assert parsed.source_head_sha == HEAD
    assert "ASSUMP_AEDR_EXTERNAL_ASSUMPTION_DISCOVERY_NOT_INTEGRATED" in parsed.assumption_debt_ids
    assert "SECURITY_AEDR_EXTERNAL_SECURITY_SCAN_NOT_INTEGRATED" in parsed.security_exposure_ids


def test_producer_rejects_noncanonical_manifest_instead_of_silently_sorting_it():
    manifest = _manifest()
    manifest["required_behavior_ids"] = ["Z", "A"]

    with pytest.raises(SurfaceProductionError, match="NONCANONICAL_MANIFEST_SET"):
        build_surface_document(manifest, pr_number=PR, head_sha=HEAD, run_id=RUN)


def test_workflow_uploads_single_surface_with_sha_pinned_node24_action():
    workflow = pathlib.Path(".github/workflows/aedr-multilayer-dag.yml").read_text(encoding="utf-8")

    assert "python scripts/aedr/surface_producer.py" in workflow
    assert f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}" in workflow
    assert "name: aedr-surface-${{ github.run_id }}-${{ github.event.pull_request.head.sha }}" in workflow
    assert "path: ${{ runner.temp }}/aedr-surface.json" in workflow
    assert "compression-level: 0" in workflow
    assert "if-no-files-found: error" in workflow
