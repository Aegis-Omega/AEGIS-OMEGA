#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import io
import json
import zipfile

from scripts.aedr.artifact_surface_oracle import ArtifactBackedSurfaceOracle
from scripts.aedr.dag_model import AuthorityDomain, EvidenceReceiptRef, PRNode
from scripts.aedr.surface_ingestor import RawArtifactMetadata


PR = 369
HEAD = "a" * 40
STALE = "b" * 40
RUN = 500


def _node(*receipts: EvidenceReceiptRef) -> PRNode:
    return PRNode(
        number=PR,
        head_sha=HEAD,
        base_sha="c" * 40,
        base_ref="main",
        draft=True,
        mergeable="clean",
        authority_domains=frozenset([AuthorityDomain.T0_STRUCTURAL]),
        git_parents=(),
        semantic_dependencies=(),
        evidence_receipts=tuple(receipts),
    )


def _receipt(run_id: int, *, head: str = HEAD, green: bool = True) -> EvidenceReceiptRef:
    return EvidenceReceiptRef(
        receipt_id=f"github-actions-run:{run_id}",
        source_head_sha=head,
        terminal_green=green,
        authority_class="NONE",
    )


def _surface_zip(*, run_id: int = RUN, head: str = HEAD, tamper: bool = False) -> bytes:
    surface = {
        "required_behavior_ids": ["BEHAVIOR_A"],
        "verified_behavior_ids": ["BEHAVIOR_A"],
        "required_falsifier_ids": ["FALSIFIER_A"],
        "verified_falsifier_ids": ["FALSIFIER_A"],
        "unique_non_generated_paths": ["scripts/aedr/a.py"],
        "assumption_identities": [],
        "security_exposure_identities": [],
    }
    digest = hashlib.sha256(
        json.dumps(surface, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if tamper:
        surface["verified_behavior_ids"] = ["BEHAVIOR_TAMPERED"]
    document = {
        "schema_version": "AEDR-FALSIFIER-SURFACE-V1",
        "pr_number": PR,
        "head_sha": head,
        "run_id": run_id,
        "surface": surface,
        "payload_digest": digest,
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "aedr-surface.json",
            json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        )
    return stream.getvalue()


class FakeArtifactOracle:
    def __init__(self):
        self.artifacts_by_run: dict[int, list[RawArtifactMetadata]] = {}
        self.bytes_by_artifact: dict[int, bytes] = {}
        self.download_calls: list[int] = []

    def list_run_artifacts(self, run_id: int) -> list[RawArtifactMetadata]:
        return list(self.artifacts_by_run.get(run_id, ()))

    def download_artifact_zip(self, artifact_id: int) -> bytes:
        self.download_calls.append(artifact_id)
        return self.bytes_by_artifact[artifact_id]


def _metadata(artifact_id: int, run_id: int = RUN, *, head: str = HEAD, name: str | None = None) -> RawArtifactMetadata:
    return RawArtifactMetadata(
        artifact_id=artifact_id,
        name=name or f"aedr-surface-{run_id}",
        size_in_bytes=1000,
        archive_download_url=f"https://api.github.com/artifacts/{artifact_id}",
        workflow_run_id=run_id,
        workflow_run_head_sha=head,
    )


def test_terminal_green_exact_head_receipt_can_supply_surface_and_is_cached():
    oracle = FakeArtifactOracle()
    oracle.artifacts_by_run[RUN] = [_metadata(10)]
    oracle.bytes_by_artifact[10] = _surface_zip()
    surfaces = ArtifactBackedSurfaceOracle(oracle, {PR: _node(_receipt(RUN))})

    first = surfaces.get_surface(PR)
    second = surfaces.get_surface(PR)

    assert first is not None
    assert first.source_head_sha == HEAD
    assert second == first
    assert oracle.download_calls == [10]
    assert surfaces.quarantine_reason(PR) is None


def test_non_green_and_stale_receipts_are_not_artifact_candidates():
    oracle = FakeArtifactOracle()
    oracle.artifacts_by_run[RUN] = [_metadata(10)]
    oracle.bytes_by_artifact[10] = _surface_zip()
    surfaces = ArtifactBackedSurfaceOracle(
        oracle,
        {PR: _node(_receipt(RUN, green=False), _receipt(RUN + 1, head=STALE, green=True))},
    )

    assert surfaces.get_surface(PR) is None
    assert oracle.download_calls == []


def test_artifact_metadata_run_or_head_mismatch_quarantines_without_download():
    oracle = FakeArtifactOracle()
    oracle.artifacts_by_run[RUN] = [_metadata(10, run_id=RUN + 1)]
    surfaces = ArtifactBackedSurfaceOracle(oracle, {PR: _node(_receipt(RUN))})

    assert surfaces.get_surface(PR) is None
    assert oracle.download_calls == []
    assert surfaces.quarantine_reason(PR) == "ARTIFACT_RUN_ID_MISMATCH"

    oracle = FakeArtifactOracle()
    oracle.artifacts_by_run[RUN] = [_metadata(11, head=STALE)]
    surfaces = ArtifactBackedSurfaceOracle(oracle, {PR: _node(_receipt(RUN))})
    assert surfaces.get_surface(PR) is None
    assert surfaces.quarantine_reason(PR) == "ARTIFACT_HEAD_MISMATCH"


def test_ambiguous_surface_artifacts_on_same_run_fail_closed():
    oracle = FakeArtifactOracle()
    oracle.artifacts_by_run[RUN] = [_metadata(10), _metadata(11)]
    surfaces = ArtifactBackedSurfaceOracle(oracle, {PR: _node(_receipt(RUN))})

    assert surfaces.get_surface(PR) is None
    assert surfaces.quarantine_reason(PR) == "AMBIGUOUS_SURFACE_ARTIFACTS"
    assert oracle.download_calls == []


def test_tampered_candidate_quarantines_head_and_does_not_fall_through_to_other_run():
    oracle = FakeArtifactOracle()
    oracle.artifacts_by_run[RUN] = [_metadata(10)]
    oracle.bytes_by_artifact[10] = _surface_zip(tamper=True)
    oracle.artifacts_by_run[RUN + 1] = [_metadata(11, run_id=RUN + 1)]
    oracle.bytes_by_artifact[11] = _surface_zip(run_id=RUN + 1)
    surfaces = ArtifactBackedSurfaceOracle(
        oracle,
        {PR: _node(_receipt(RUN), _receipt(RUN + 1))},
    )

    assert surfaces.get_surface(PR) is None
    assert surfaces.quarantine_reason(PR).startswith("TAMPERED_ARTIFACT_DETECTED")
    assert oracle.download_calls == [10]
