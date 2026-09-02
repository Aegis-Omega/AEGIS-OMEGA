from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.avd.anchor import AVD00_ANCHOR
from scripts.avd.bundle_commitment import canonical_bundle_bytes
from scripts.avd.crypto_util import CanonicalizationError, avd_digest, canonical_json_bytes, compute_receipt_digest
from scripts.avd.hermetic_guard import HermeticBoundaryError, HermeticBoundaryGuard
from scripts.avd.resource_meter import PrecisionResourceTracker
from scripts.avd.tripartite_enforcer import TripartiteEnforcementError, TripartiteRunner


def test_frozen_anchor_separates_pr_base_from_git_parent() -> None:
    assert AVD00_ANCHOR.anchor_commit_sha == "d98ef00c6d65b45e253aa13eeebb6f9b1f256009"
    assert AVD00_ANCHOR.anchor_tree_sha == "8fa6cc600d75cd78a518a8b5b08cfb9f4e665c30"
    assert AVD00_ANCHOR.pr_base_sha == "88b7b937b90719cc4e05ddca2aa2bcff2894e443"
    assert AVD00_ANCHOR.git_parent_sha == "16769820d37616d319cdee8ad9954d0fda086715"
    assert AVD00_ANCHOR.pr_base_sha != AVD00_ANCHOR.git_parent_sha
    assert AVD00_ANCHOR.red_workflow_run == 33584236075
    assert AVD00_ANCHOR.red_artifact_id == 9829698647
    assert AVD00_ANCHOR.red_artifact_sha256 == "2fb0028dbd763d63430327e93e14747c31b8a882b85a3da2fa008fca04e8db8d"


def test_domain_separation_and_canonical_json_integer_subset() -> None:
    payload = canonical_json_bytes({"b": 2, "a": "x"})
    assert payload == b'{"a":"x","b":2}'
    assert avd_digest("PROBLEM", payload) != avd_digest("VERIFIER", payload)
    assert avd_digest("VERIFIER", payload) != avd_digest("ORACLE", payload)

    with pytest.raises(CanonicalizationError, match="FLOAT_FORBIDDEN"):
        canonical_json_bytes({"x": 1.5})


def test_bundle_commitment_is_path_content_bound_and_git_free(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    root.mkdir()
    (root / "a.txt").write_text("alpha", encoding="utf-8")
    (root / "b.txt").write_text("beta", encoding="utf-8")
    first = canonical_bundle_bytes(root)

    (root / "b.txt").write_text("BETA", encoding="utf-8")
    second = canonical_bundle_bytes(root)
    assert first != second

    (root / ".git").mkdir()
    with pytest.raises(ValueError, match="GIT_METADATA_FORBIDDEN"):
        canonical_bundle_bytes(root)


def test_receipt_digest_is_domain_separated_and_excludes_digest_field() -> None:
    payload = {
        "protocol_version": "AVD_PROTOCOL_V1",
        "authority_class": "NONE",
        "trial_id": "trial-1",
    }
    digest = compute_receipt_digest(payload)
    assert len(digest) == 64
    with pytest.raises(ValueError, match="RECEIPT_DIGEST_ALREADY_PRESENT"):
        compute_receipt_digest({**payload, "receipt_digest": digest})


def test_tripartite_enforcer_has_no_bypass_and_detects_post_start_drift(tmp_path: Path) -> None:
    problem = tmp_path / "problem"
    verifier = tmp_path / "verifier"
    oracle = tmp_path / "oracle"
    for directory, value in ((problem, "p"), (verifier, "v"), (oracle, "o")):
        directory.mkdir()
        (directory / "payload.txt").write_text(value, encoding="utf-8")

    expected = {
        "PROBLEM": avd_digest("PROBLEM", canonical_bundle_bytes(problem)),
        "VERIFIER": avd_digest("VERIFIER", canonical_bundle_bytes(verifier)),
        "ORACLE": avd_digest("ORACLE", canonical_bundle_bytes(oracle)),
    }
    runner = TripartiteRunner(problem, verifier, oracle, expected)
    runner.verify_commitments()

    (oracle / "payload.txt").write_text("captured", encoding="utf-8")
    with pytest.raises(TripartiteEnforcementError, match="H_O_MISMATCH"):
        runner.verify_commitments()


def test_resource_meter_uses_integer_wall_ns_and_cpu_microseconds() -> None:
    tracker = PrecisionResourceTracker(is_human_arm=False)
    tracker.start_tracking()
    tracker.start_active_window()
    tracker.record_tool_invocation()
    tracker.stop_active_window()
    tracker.stop_tracking()
    snap = tracker.compile_snapshot()

    assert isinstance(snap.wall_nanoseconds, int) and snap.wall_nanoseconds >= 0
    assert isinstance(snap.active_nanoseconds, int) and snap.active_nanoseconds >= 0
    assert isinstance(snap.cpu_user_microseconds, int) and snap.cpu_user_microseconds >= 0
    assert isinstance(snap.cpu_system_microseconds, int) and snap.cpu_system_microseconds >= 0
    assert snap.machine_active_nanoseconds == snap.active_nanoseconds
    assert snap.human_active_nanoseconds == 0
    assert snap.gpu_seconds == "UNAVAILABLE"
    assert snap.api_cost_usd == "UNAVAILABLE"


def test_hermetic_guard_rejects_git_metadata_and_prior_solution_exposure(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    guard = HermeticBoundaryGuard(workspace)
    guard.assert_workspace_clean()

    (workspace / ".git").mkdir()
    with pytest.raises(HermeticBoundaryError, match="GIT_METADATA_PRESENT"):
        guard.assert_workspace_clean()

    (workspace / ".git").rmdir()
    with pytest.raises(HermeticBoundaryError, match="PARTICIPANT_CONTEXT_CONTAMINATED"):
        guard.assert_context_clean(fresh_clean_room=False, external_repo_tools_disabled=True)


def test_trial_schema_is_recursive_strict_and_authority_none() -> None:
    schema = json.loads(Path("scripts/avd/trial_receipt.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert "authority_class" in schema["required"]
    assert schema["properties"]["authority_class"]["enum"] == ["NONE"]
    for nested in ("anchor", "submission", "commitment_digests", "resource_telemetry", "oracle_falsifier_outcomes", "isolation_attestation"):
        assert schema["properties"][nested]["additionalProperties"] is False
