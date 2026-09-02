#!/usr/bin/env python3
from __future__ import annotations

from typing import Dict, Optional, Protocol, Tuple

from .dag_model import FalsificationSurface, PRNode
from .live_oracle import GitHubLiveOracleError
from .surface_ingestor import (
    FalsificationSurfaceIngestor,
    RawArtifactMetadata,
    SurfaceIngestionError,
)


class ArtifactOracle(Protocol):
    def list_run_artifacts(self, run_id: int) -> list[RawArtifactMetadata]: ...
    def download_artifact_zip(self, artifact_id: int) -> bytes: ...


class ArtifactBackedSurfaceOracle:
    """Authority-neutral exact-head falsification-surface oracle.

    The cache key includes the PR's exact head. Any integrity or binding failure
    quarantines that key instead of falling through to a different artifact.
    """

    ARTIFACT_PREFIX = "aedr-surface-"
    RECEIPT_PREFIX = "github-actions-run:"

    def __init__(self, oracle: ArtifactOracle, nodes: Dict[int, PRNode]):
        self.oracle = oracle
        self.nodes = dict(nodes)
        self._cache: Dict[Tuple[int, str], Optional[FalsificationSurface]] = {}
        self._quarantine: Dict[Tuple[int, str], str] = {}

    @staticmethod
    def _github_run_id(receipt_id: str) -> int | None:
        if not receipt_id.startswith(ArtifactBackedSurfaceOracle.RECEIPT_PREFIX):
            return None
        raw = receipt_id[len(ArtifactBackedSurfaceOracle.RECEIPT_PREFIX) :]
        if not raw.isdigit():
            return None
        value = int(raw)
        return value if value > 0 else None

    def quarantine_reason(self, pr_number: int) -> str | None:
        node = self.nodes.get(pr_number)
        if node is None:
            return None
        return self._quarantine.get((pr_number, node.head_sha.lower()))

    def _quarantine_key(self, key: tuple[int, str], reason: str) -> None:
        self._quarantine[key] = reason
        self._cache[key] = None

    def get_surface(self, pr_number: int) -> Optional[FalsificationSurface]:
        node = self.nodes.get(pr_number)
        if node is None:
            return None

        exact_head = node.head_sha.lower()
        key = (pr_number, exact_head)
        if key in self._cache:
            return self._cache[key]

        candidate_runs: list[int] = []
        for receipt in node.evidence_receipts:
            if (
                not receipt.terminal_green
                or receipt.source_head_sha.lower() != exact_head
                or receipt.authority_class != "NONE"
            ):
                continue
            run_id = self._github_run_id(receipt.receipt_id)
            if run_id is not None:
                candidate_runs.append(run_id)

        candidate_runs = sorted(set(candidate_runs))
        if not candidate_runs:
            self._cache[key] = None
            return None

        valid_surfaces: list[FalsificationSurface] = []
        for run_id in candidate_runs:
            try:
                artifacts = sorted(
                    self.oracle.list_run_artifacts(run_id),
                    key=lambda artifact: (artifact.name, artifact.artifact_id),
                )
            except GitHubLiveOracleError as exc:
                self._quarantine_key(key, f"ORACLE_ARTIFACT_LIST_FAILURE: {exc}")
                return None

            candidates = [
                artifact
                for artifact in artifacts
                if artifact.name.startswith(self.ARTIFACT_PREFIX)
            ]
            if not candidates:
                continue
            if len(candidates) != 1:
                self._quarantine_key(key, "AMBIGUOUS_SURFACE_ARTIFACTS")
                return None

            artifact = candidates[0]
            if artifact.workflow_run_id != run_id:
                self._quarantine_key(key, "ARTIFACT_RUN_ID_MISMATCH")
                return None
            if artifact.workflow_run_head_sha.lower() != exact_head:
                self._quarantine_key(key, "ARTIFACT_HEAD_MISMATCH")
                return None
            if artifact.size_in_bytes <= 0:
                self._quarantine_key(key, "INVALID_ARTIFACT_SIZE")
                return None
            if artifact.size_in_bytes > FalsificationSurfaceIngestor.MAX_ARCHIVE_BYTES:
                self._quarantine_key(key, "ARTIFACT_METADATA_SIZE_LIMIT")
                return None

            try:
                zip_bytes = self.oracle.download_artifact_zip(artifact.artifact_id)
                surface = FalsificationSurfaceIngestor.verify_and_parse(
                    zip_bytes=zip_bytes,
                    expected_pr=pr_number,
                    expected_head_sha=exact_head,
                    expected_run_id=run_id,
                )
            except SurfaceIngestionError as exc:
                self._quarantine_key(key, str(exc))
                return None
            except GitHubLiveOracleError as exc:
                self._quarantine_key(key, f"ORACLE_ARTIFACT_DOWNLOAD_FAILURE: {exc}")
                return None

            valid_surfaces.append(surface)

        if not valid_surfaces:
            self._cache[key] = None
            return None

        canonical = valid_surfaces[0]
        if any(surface != canonical for surface in valid_surfaces[1:]):
            self._quarantine_key(key, "AMBIGUOUS_VALID_SURFACES")
            return None

        self._cache[key] = canonical
        return canonical
