#!/usr/bin/env python3
from __future__ import annotations

from scripts.aedr.live_oracle import GitHubLiveOracle, GitHubLiveOracleError


HEAD = "d" * 40
RUN = 700


def _artifact(artifact_id: int, *, expired: bool = False, run_id: int = RUN, head: str = HEAD):
    return {
        "id": artifact_id,
        "name": f"aedr-surface-{artifact_id}",
        "size_in_bytes": 1234,
        "archive_download_url": f"https://api.github.com/repos/Aegis-Omega/AEGIS-OMEGA/actions/artifacts/{artifact_id}/zip",
        "expired": expired,
        "workflow_run": {"id": run_id, "head_sha": head},
    }


def test_run_artifact_listing_is_paginated_filtered_and_canonicalized():
    oracle = GitHubLiveOracle("Aegis-Omega", "AEGIS-OMEGA")
    calls = []

    def fake_get(endpoint, params=None):
        calls.append((endpoint, dict(params or {})))
        page = int((params or {}).get("page", "1"))
        if page == 1:
            return {
                "artifacts": [_artifact(2), _artifact(99, expired=True)] + [
                    _artifact(1000 + index) for index in range(98)
                ]
            }
        if page == 2:
            return {"artifacts": [_artifact(1)]}
        raise AssertionError("unexpected page")

    oracle._get = fake_get  # type: ignore[method-assign]
    artifacts = oracle.list_run_artifacts(RUN)

    assert len(artifacts) == 100
    assert [artifact.artifact_id for artifact in artifacts][:2] == [1, 2]
    assert all(not artifact.name.endswith("99") for artifact in artifacts)
    assert calls[0][1] == {"per_page": "100", "page": "1"}
    assert calls[1][1] == {"per_page": "100", "page": "2"}


def test_artifact_missing_workflow_binding_is_rejected():
    oracle = GitHubLiveOracle("Aegis-Omega", "AEGIS-OMEGA")
    item = _artifact(1)
    item.pop("workflow_run")
    oracle._get = lambda endpoint, params=None: {"artifacts": [item]}  # type: ignore[method-assign]

    try:
        oracle.list_run_artifacts(RUN)
    except GitHubLiveOracleError as exc:
        assert "ARTIFACT_MISSING_WORKFLOW_BINDING" in str(exc)
    else:
        raise AssertionError("missing workflow binding must fail closed")


def test_cross_origin_artifact_redirect_strips_authorization_header():
    oracle = GitHubLiveOracle("Aegis-Omega", "AEGIS-OMEGA", token="secret-token")

    same_origin = oracle._artifact_download_headers("https://api.github.com/repos/Aegis-Omega/AEGIS-OMEGA/actions/artifacts/1/zip")
    cross_origin = oracle._artifact_download_headers("https://objects.githubusercontent.com/presigned/blob?sig=x")

    assert same_origin["Authorization"] == "Bearer secret-token"
    assert "Authorization" not in cross_origin
    assert cross_origin["User-Agent"] == "AEDR-Live-Acquisition-v1"
