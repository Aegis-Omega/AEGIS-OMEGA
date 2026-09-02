from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from pathlib import Path

import pytest

from scripts.aedr.surface_producer import _canonical_json, build_surface_document
from scripts.aedr.iap_verifier import (
    IAP_PREDICATE_TYPE,
    IAPVerificationError,
    build_iap_predicate,
    verify_iap,
)


REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
WORKFLOW = ".github/workflows/aedr-multilayer-dag.yml"
PR_NUMBER = 369
HEAD_SHA = "a" * 40
RUN_ID = 33584738980
SIGNER_DIGEST = "b" * 40
SOURCE_DIGEST = "c" * 40


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "AEDR-FALSIFIER-MANIFEST-V1",
        "required_behavior_ids": ["BEHAVIOR_A"],
        "required_falsifier_ids": ["FALSIFIER_A"],
        "unique_non_generated_paths": ["scripts/aedr/example.py"],
        "assumption_identities": ["ASSUMP_A"],
        "security_exposure_identities": ["SECURITY_A"],
    }


def _surface_file(tmp_path: Path) -> Path:
    document = build_surface_document(
        _manifest(),
        pr_number=PR_NUMBER,
        head_sha=HEAD_SHA,
        run_id=RUN_ID,
    )
    path = tmp_path / "aedr-surface.json"
    path.write_bytes(_canonical_json(document) + b"\n")
    return path


def _verification_output(path: Path, *, predicate: dict[str, object] | None = None) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if predicate is None:
        predicate = build_iap_predicate(
            path,
            repository=REPOSITORY,
            workflow_path=WORKFLOW,
            expected_pr=PR_NUMBER,
            expected_head_sha=HEAD_SHA,
            expected_run_id=RUN_ID,
        )
    result = [{
        "attestation": {"bundle": "verified-by-gh"},
        "verificationResult": {
            "statement": {
                "_type": "https://in-toto.io/Statement/v1",
                "predicateType": IAP_PREDICATE_TYPE,
                "subject": [{
                    "name": "aedr-surface.json",
                    "digest": {"sha256": digest},
                }],
                "predicate": predicate,
            },
            "signature": {
                "certificate": {
                    "issuer": "https://token.actions.githubusercontent.com",
                    "subjectAlternativeName": (
                        f"https://github.com/{REPOSITORY}/{WORKFLOW}@refs/pull/999/merge"
                    ),
                    "githubWorkflowRepository": REPOSITORY,
                    "buildSignerURI": (
                        f"https://github.com/{REPOSITORY}/{WORKFLOW}@refs/pull/999/merge"
                    ),
                    "buildSignerDigest": SIGNER_DIGEST,
                    "runnerEnvironment": "github-hosted",
                    "sourceRepositoryURI": f"https://github.com/{REPOSITORY}",
                    "sourceRepositoryDigest": SOURCE_DIGEST,
                    "sourceRepositoryRef": "refs/pull/999/merge",
                    "runInvocationURI": (
                        f"https://github.com/{REPOSITORY}/actions/runs/{RUN_ID}/attempts/1"
                    ),
                }
            },
            "verifiedTimestamps": [
                {"type": "Tlog", "uri": "https://rekor.sigstore.dev", "timestamp": "2026-09-02T00:00:00Z"}
            ],
        },
    }]
    return json.dumps(result)


def _patch_gh_success(monkeypatch: pytest.MonkeyPatch, stdout: str, calls: list[list[str]]) -> None:
    def fake_run(command, **kwargs):
        calls.append(list(command))
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)


def test_predicate_binds_exact_surface_identity(tmp_path: Path) -> None:
    path = _surface_file(tmp_path)
    predicate = build_iap_predicate(
        path,
        repository=REPOSITORY,
        workflow_path=WORKFLOW,
        expected_pr=PR_NUMBER,
        expected_head_sha=HEAD_SHA,
        expected_run_id=RUN_ID,
    )

    assert predicate["schema_version"] == "AEGIS-IAP-PREDICATE-V1"
    assert predicate["repository"] == REPOSITORY
    assert predicate["workflow_path"] == WORKFLOW
    assert predicate["pr_number"] == PR_NUMBER
    assert predicate["head_sha"] == HEAD_SHA
    assert predicate["run_id"] == RUN_ID
    assert predicate["authority_class"] == "NONE"
    assert predicate["surface_subject_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(predicate["surface_payload_digest"]) == 64


def test_j1_rejects_exact_head_mismatch_before_crypto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _surface_file(tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: pytest.fail("gh must not run"))

    with pytest.raises(IAPVerificationError, match="J1_HEAD_MISMATCH"):
        verify_iap(
            path,
            repository=REPOSITORY,
            workflow_path=WORKFLOW,
            expected_pr=PR_NUMBER,
            expected_head_sha="d" * 40,
            expected_run_id=RUN_ID,
        )


def test_verify_invokes_gh_with_identity_policy_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _surface_file(tmp_path)
    calls: list[list[str]] = []
    _patch_gh_success(monkeypatch, _verification_output(path), calls)

    verify_iap(
        path,
        repository=REPOSITORY,
        workflow_path=WORKFLOW,
        expected_pr=PR_NUMBER,
        expected_head_sha=HEAD_SHA,
        expected_run_id=RUN_ID,
    )

    command = calls[0]
    assert command[:3] == ["gh", "attestation", "verify"]
    assert "--repo" in command and REPOSITORY in command
    assert "--signer-workflow" in command
    assert f"{REPOSITORY}/{WORKFLOW}" in command
    assert "--predicate-type" in command and IAP_PREDICATE_TYPE in command
    assert "--deny-self-hosted-runners" in command
    assert "--format" in command and "json" in command


def test_j1_j2_pass_but_j3_defers_without_external_trust_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _surface_file(tmp_path)
    _patch_gh_success(monkeypatch, _verification_output(path), [])

    receipt = verify_iap(
        path,
        repository=REPOSITORY,
        workflow_path=WORKFLOW,
        expected_pr=PR_NUMBER,
        expected_head_sha=HEAD_SHA,
        expected_run_id=RUN_ID,
    )

    assert receipt["j1_status"] == "PASS"
    assert receipt["j2_status"] == "PASS"
    assert receipt["j3_status"] == "DEFER_UNTRUSTED_SIGNER_DIGEST"
    assert receipt["identity_bound_signing"] == "ESTABLISHED"
    assert receipt["independent_falsifier_authenticity"] == "NOT_ESTABLISHED"
    assert receipt["authority_effect"] == "NONE"
    assert receipt["build_signer_digest"] == SIGNER_DIGEST
    assert len(receipt["receipt_digest"]) == 64


def test_j3_pass_requires_control_plane_trusted_signer_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _surface_file(tmp_path)
    _patch_gh_success(monkeypatch, _verification_output(path), [])

    receipt = verify_iap(
        path,
        repository=REPOSITORY,
        workflow_path=WORKFLOW,
        expected_pr=PR_NUMBER,
        expected_head_sha=HEAD_SHA,
        expected_run_id=RUN_ID,
        trusted_signer_digest=SIGNER_DIGEST,
    )

    assert receipt["j3_status"] == "PASS"
    assert receipt["trusted_signer_digest"] == SIGNER_DIGEST
    assert receipt["authority_effect"] == "NONE"


def test_j3_rejects_trusted_signer_digest_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _surface_file(tmp_path)
    _patch_gh_success(monkeypatch, _verification_output(path), [])

    with pytest.raises(IAPVerificationError, match="J3_SIGNER_DIGEST_MISMATCH"):
        verify_iap(
            path,
            repository=REPOSITORY,
            workflow_path=WORKFLOW,
            expected_pr=PR_NUMBER,
            expected_head_sha=HEAD_SHA,
            expected_run_id=RUN_ID,
            trusted_signer_digest="e" * 40,
        )


def test_j2_rejects_subject_digest_splice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _surface_file(tmp_path)
    raw = json.loads(_verification_output(path))
    raw[0]["verificationResult"]["statement"]["subject"][0]["digest"]["sha256"] = "0" * 64
    _patch_gh_success(monkeypatch, json.dumps(raw), [])

    with pytest.raises(IAPVerificationError, match="J2_SUBJECT_DIGEST_MISMATCH"):
        verify_iap(
            path,
            repository=REPOSITORY,
            workflow_path=WORKFLOW,
            expected_pr=PR_NUMBER,
            expected_head_sha=HEAD_SHA,
            expected_run_id=RUN_ID,
        )


def test_j2_rejects_signed_predicate_head_splice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _surface_file(tmp_path)
    predicate = build_iap_predicate(
        path,
        repository=REPOSITORY,
        workflow_path=WORKFLOW,
        expected_pr=PR_NUMBER,
        expected_head_sha=HEAD_SHA,
        expected_run_id=RUN_ID,
    )
    predicate["head_sha"] = "f" * 40
    _patch_gh_success(monkeypatch, _verification_output(path, predicate=predicate), [])

    with pytest.raises(IAPVerificationError, match="J2_PREDICATE_MISMATCH"):
        verify_iap(
            path,
            repository=REPOSITORY,
            workflow_path=WORKFLOW,
            expected_pr=PR_NUMBER,
            expected_head_sha=HEAD_SHA,
            expected_run_id=RUN_ID,
        )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("issuer", "https://evil.example", "J2_ISSUER_MISMATCH"),
        ("githubWorkflowRepository", "evil/repo", "J2_REPOSITORY_MISMATCH"),
        ("runnerEnvironment", "self-hosted", "J2_RUNNER_ENVIRONMENT_MISMATCH"),
        ("runInvocationURI", "https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/999/attempts/1", "J2_RUN_ID_MISMATCH"),
    ],
)
def test_j2_rejects_certificate_identity_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
    error: str,
) -> None:
    path = _surface_file(tmp_path)
    raw = json.loads(_verification_output(path))
    raw[0]["verificationResult"]["signature"]["certificate"][field] = value
    _patch_gh_success(monkeypatch, json.dumps(raw), [])

    with pytest.raises(IAPVerificationError, match=error):
        verify_iap(
            path,
            repository=REPOSITORY,
            workflow_path=WORKFLOW,
            expected_pr=PR_NUMBER,
            expected_head_sha=HEAD_SHA,
            expected_run_id=RUN_ID,
        )


def test_j2_requires_public_transparency_log_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _surface_file(tmp_path)
    raw = json.loads(_verification_output(path))
    raw[0]["verificationResult"]["verifiedTimestamps"] = []
    _patch_gh_success(monkeypatch, json.dumps(raw), [])

    with pytest.raises(IAPVerificationError, match="J2_TRANSPARENCY_LOG_MISSING"):
        verify_iap(
            path,
            repository=REPOSITORY,
            workflow_path=WORKFLOW,
            expected_pr=PR_NUMBER,
            expected_head_sha=HEAD_SHA,
            expected_run_id=RUN_ID,
        )


def test_j2_rejects_ambiguous_verified_attestations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _surface_file(tmp_path)
    raw = json.loads(_verification_output(path))
    raw.append(raw[0])
    _patch_gh_success(monkeypatch, json.dumps(raw), [])

    with pytest.raises(IAPVerificationError, match="J2_AMBIGUOUS_ATTESTATIONS"):
        verify_iap(
            path,
            repository=REPOSITORY,
            workflow_path=WORKFLOW,
            expected_pr=PR_NUMBER,
            expected_head_sha=HEAD_SHA,
            expected_run_id=RUN_ID,
        )


def test_gh_verification_failure_is_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _surface_file(tmp_path)

    def fail_run(command, **_kwargs):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="verification failed")

    monkeypatch.setattr(subprocess, "run", fail_run)
    with pytest.raises(IAPVerificationError, match="J2_GH_ATTESTATION_VERIFY_FAILED"):
        verify_iap(
            path,
            repository=REPOSITORY,
            workflow_path=WORKFLOW,
            expected_pr=PR_NUMBER,
            expected_head_sha=HEAD_SHA,
            expected_run_id=RUN_ID,
        )


def test_public_api_exposes_no_command_runner_injection() -> None:
    assert "runner" not in inspect.signature(verify_iap).parameters
    assert "executor" not in inspect.signature(verify_iap).parameters
