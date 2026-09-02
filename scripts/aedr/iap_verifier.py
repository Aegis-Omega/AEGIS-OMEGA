#!/usr/bin/env python3
"""AEGIS AEDR Identity Attestation Protocol (IAP-v1).

IAP-v1 is an authority-neutral three-stage verifier for one AEDR
``aedr-surface.json`` subject:

J1  Recompute and bind the local surface bytes, payload digest, PR, head and run.
J2  Delegate Sigstore/GitHub cryptographic verification to ``gh attestation
    verify`` and independently bind the returned statement/certificate to J1.
J3  Compare the verified workflow signer digest with an externally supplied
    control-plane trust anchor. Candidate code cannot manufacture that anchor.

A J1/J2 PASS does not grant admission authority. Without a trusted signer
anchor, J3 returns ``DEFER_UNTRUSTED_SIGNER_DIGEST`` and authority remains NONE.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .surface_ingestor import FalsificationSurfaceIngestor, SurfaceIngestionError


IAP_PREDICATE_TYPE = "https://aegisomega.com/attestations/aedr-falsification-surface/v1"
IAP_PREDICATE_SCHEMA = "AEGIS-IAP-PREDICATE-V1"
IAP_RECEIPT_SCHEMA = "AEGIS-IAP-RECEIPT-V1"
GITHUB_ACTIONS_OIDC_ISSUER = "https://token.actions.githubusercontent.com"
AUTHORITY_CLASS = "NONE"
AUTHORITY_EFFECT = "NONE"
MAX_SURFACE_BYTES = 1024 * 1024

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_WORKFLOW_PATH = re.compile(r"^\.github/workflows/[A-Za-z0-9_.\-/]+\.(?:yml|yaml)$")


class IAPVerificationError(RuntimeError):
    """IAP verification failed closed; no valid IAP receipt may be emitted."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _require_sha40(name: str, value: str) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise IAPVerificationError(f"{name}_INVALID")
    return value


def _require_repository(repository: str) -> str:
    if type(repository) is not str or _REPOSITORY.fullmatch(repository) is None:
        raise IAPVerificationError("J1_REPOSITORY_INVALID")
    return repository


def _require_workflow_path(workflow_path: str) -> str:
    if type(workflow_path) is not str or _WORKFLOW_PATH.fullmatch(workflow_path) is None:
        raise IAPVerificationError("J1_WORKFLOW_PATH_INVALID")
    if ".." in Path(workflow_path).parts:
        raise IAPVerificationError("J1_WORKFLOW_PATH_INVALID")
    return workflow_path


def _read_surface(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise IAPVerificationError(f"J1_SURFACE_READ_FAILURE: {exc}") from exc
    if not raw:
        raise IAPVerificationError("J1_EMPTY_SURFACE")
    if len(raw) > MAX_SURFACE_BYTES:
        raise IAPVerificationError("J1_SURFACE_SIZE_LIMIT")
    try:
        data = FalsificationSurfaceIngestor._parse_json(raw)
    except SurfaceIngestionError as exc:
        raise IAPVerificationError(f"J1_SURFACE_PARSE_FAILURE: {exc}") from exc
    return raw, data


def _validate_j1(
    path: Path,
    *,
    repository: str,
    workflow_path: str,
    expected_pr: int,
    expected_head_sha: str,
    expected_run_id: int,
) -> dict[str, Any]:
    _require_repository(repository)
    _require_workflow_path(workflow_path)
    _require_sha40("J1_HEAD_SHA", expected_head_sha)
    if type(expected_pr) is not int or expected_pr <= 0:
        raise IAPVerificationError("J1_PR_NUMBER_INVALID")
    if type(expected_run_id) is not int or expected_run_id <= 0:
        raise IAPVerificationError("J1_RUN_ID_INVALID")

    raw, data = _read_surface(path)
    if frozenset(data) != FalsificationSurfaceIngestor.ENVELOPE_FIELDS:
        raise IAPVerificationError("J1_ENVELOPE_FIELDS_MISMATCH")
    if data.get("schema_version") != FalsificationSurfaceIngestor.SCHEMA_VERSION:
        raise IAPVerificationError("J1_SCHEMA_MISMATCH")
    if type(data.get("pr_number")) is not int or data["pr_number"] != expected_pr:
        raise IAPVerificationError("J1_PR_MISMATCH")
    if type(data.get("head_sha")) is not str or data["head_sha"].lower() != expected_head_sha:
        raise IAPVerificationError("J1_HEAD_MISMATCH")
    if type(data.get("run_id")) is not int or data["run_id"] != expected_run_id:
        raise IAPVerificationError("J1_RUN_ID_MISMATCH")

    surface = data.get("surface")
    if not isinstance(surface, dict):
        raise IAPVerificationError("J1_SURFACE_BODY_INVALID")
    if frozenset(surface) != FalsificationSurfaceIngestor.SURFACE_FIELDS:
        raise IAPVerificationError("J1_SURFACE_FIELDS_MISMATCH")

    declared_payload_digest = data.get("payload_digest")
    if type(declared_payload_digest) is not str or _SHA64.fullmatch(declared_payload_digest) is None:
        raise IAPVerificationError("J1_PAYLOAD_DIGEST_INVALID")
    computed_payload_digest = hashlib.sha256(
        FalsificationSurfaceIngestor._canonical_json(surface)
    ).hexdigest()
    if declared_payload_digest != computed_payload_digest:
        raise IAPVerificationError("J1_PAYLOAD_DIGEST_MISMATCH")

    return {
        "raw": raw,
        "subject_sha256": hashlib.sha256(raw).hexdigest(),
        "payload_digest": computed_payload_digest,
        "document": data,
    }


def build_iap_predicate(
    surface_path: Path | str,
    *,
    repository: str,
    workflow_path: str,
    expected_pr: int,
    expected_head_sha: str,
    expected_run_id: int,
) -> dict[str, object]:
    """Build the exact custom predicate that must be signed by GitHub/Sigstore."""
    path = Path(surface_path)
    j1 = _validate_j1(
        path,
        repository=repository,
        workflow_path=workflow_path,
        expected_pr=expected_pr,
        expected_head_sha=expected_head_sha,
        expected_run_id=expected_run_id,
    )
    return {
        "schema_version": IAP_PREDICATE_SCHEMA,
        "repository": repository,
        "workflow_path": workflow_path,
        "pr_number": expected_pr,
        "head_sha": expected_head_sha,
        "run_id": expected_run_id,
        "surface_subject_sha256": j1["subject_sha256"],
        "surface_payload_digest": j1["payload_digest"],
        "authority_class": AUTHORITY_CLASS,
    }


def _parse_gh_json(stdout: str) -> dict[str, Any]:
    try:
        value = json.loads(stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise IAPVerificationError("J2_GH_OUTPUT_INVALID_JSON") from exc
    if not isinstance(value, list):
        raise IAPVerificationError("J2_GH_OUTPUT_NOT_LIST")
    if len(value) != 1:
        raise IAPVerificationError("J2_AMBIGUOUS_ATTESTATIONS")
    item = value[0]
    if not isinstance(item, dict):
        raise IAPVerificationError("J2_GH_OUTPUT_INVALID_ENTRY")
    return item


def _require_mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise IAPVerificationError(code)
    return value


def _verify_j2_result(
    item: dict[str, Any],
    *,
    path: Path,
    expected_predicate: dict[str, object],
    repository: str,
    workflow_path: str,
    expected_run_id: int,
    subject_sha256: str,
) -> dict[str, str]:
    verification = _require_mapping(item.get("verificationResult"), "J2_VERIFICATION_RESULT_MISSING")
    statement = _require_mapping(verification.get("statement"), "J2_STATEMENT_MISSING")

    if statement.get("predicateType") != IAP_PREDICATE_TYPE:
        raise IAPVerificationError("J2_PREDICATE_TYPE_MISMATCH")

    subjects = statement.get("subject")
    if not isinstance(subjects, list) or len(subjects) != 1 or not isinstance(subjects[0], dict):
        raise IAPVerificationError("J2_SUBJECT_AMBIGUOUS")
    subject = subjects[0]
    digest = _require_mapping(subject.get("digest"), "J2_SUBJECT_DIGEST_MISSING")
    if digest.get("sha256") != subject_sha256:
        raise IAPVerificationError("J2_SUBJECT_DIGEST_MISMATCH")
    if subject.get("name") not in (None, path.name):
        raise IAPVerificationError("J2_SUBJECT_NAME_MISMATCH")

    predicate = statement.get("predicate")
    if predicate != expected_predicate:
        raise IAPVerificationError("J2_PREDICATE_MISMATCH")

    signature = _require_mapping(verification.get("signature"), "J2_SIGNATURE_MISSING")
    certificate = _require_mapping(signature.get("certificate"), "J2_CERTIFICATE_MISSING")

    if certificate.get("issuer") != GITHUB_ACTIONS_OIDC_ISSUER:
        raise IAPVerificationError("J2_ISSUER_MISMATCH")
    if certificate.get("githubWorkflowRepository") != repository:
        raise IAPVerificationError("J2_REPOSITORY_MISMATCH")
    if certificate.get("runnerEnvironment") != "github-hosted":
        raise IAPVerificationError("J2_RUNNER_ENVIRONMENT_MISMATCH")
    if certificate.get("sourceRepositoryURI") != f"https://github.com/{repository}":
        raise IAPVerificationError("J2_SOURCE_REPOSITORY_MISMATCH")

    signer_prefix = f"https://github.com/{repository}/{workflow_path}@"
    signer_uri = certificate.get("buildSignerURI")
    signer_san = certificate.get("subjectAlternativeName")
    if type(signer_uri) is not str or not signer_uri.startswith(signer_prefix):
        raise IAPVerificationError("J2_SIGNER_WORKFLOW_MISMATCH")
    if type(signer_san) is not str or not signer_san.startswith(signer_prefix):
        raise IAPVerificationError("J2_SIGNER_SAN_MISMATCH")

    signer_digest = certificate.get("buildSignerDigest")
    if type(signer_digest) is not str or _SHA40.fullmatch(signer_digest) is None:
        raise IAPVerificationError("J2_SIGNER_DIGEST_INVALID")
    source_digest = certificate.get("sourceRepositoryDigest")
    if type(source_digest) is not str or _SHA40.fullmatch(source_digest) is None:
        raise IAPVerificationError("J2_SOURCE_DIGEST_INVALID")
    source_ref = certificate.get("sourceRepositoryRef")
    if type(source_ref) is not str or not source_ref.startswith("refs/"):
        raise IAPVerificationError("J2_SOURCE_REF_INVALID")

    run_uri = certificate.get("runInvocationURI")
    expected_run_prefix = f"https://github.com/{repository}/actions/runs/{expected_run_id}/attempts/"
    if type(run_uri) is not str or not run_uri.startswith(expected_run_prefix):
        raise IAPVerificationError("J2_RUN_ID_MISMATCH")
    attempt = run_uri[len(expected_run_prefix) :]
    if not attempt.isdigit() or int(attempt) <= 0:
        raise IAPVerificationError("J2_RUN_INVOCATION_INVALID")

    timestamps = verification.get("verifiedTimestamps")
    if not isinstance(timestamps, list) or not any(
        isinstance(entry, dict) and entry.get("type") == "Tlog" for entry in timestamps
    ):
        raise IAPVerificationError("J2_TRANSPARENCY_LOG_MISSING")

    return {
        "build_signer_uri": signer_uri,
        "build_signer_digest": signer_digest,
        "source_repository_digest": source_digest,
        "source_repository_ref": source_ref,
        "run_invocation_uri": run_uri,
    }


def verify_iap(
    surface_path: Path | str,
    *,
    repository: str,
    workflow_path: str,
    expected_pr: int,
    expected_head_sha: str,
    expected_run_id: int,
    trusted_signer_digest: str | None = None,
) -> dict[str, object]:
    """Verify one surface and emit an authority-neutral IAP-v1 receipt.

    ``trusted_signer_digest`` is deliberately caller/control-plane supplied. It
    must never be populated from the candidate attestation itself and then
    treated as trusted.
    """
    path = Path(surface_path)
    j1 = _validate_j1(
        path,
        repository=repository,
        workflow_path=workflow_path,
        expected_pr=expected_pr,
        expected_head_sha=expected_head_sha,
        expected_run_id=expected_run_id,
    )
    expected_predicate = {
        "schema_version": IAP_PREDICATE_SCHEMA,
        "repository": repository,
        "workflow_path": workflow_path,
        "pr_number": expected_pr,
        "head_sha": expected_head_sha,
        "run_id": expected_run_id,
        "surface_subject_sha256": j1["subject_sha256"],
        "surface_payload_digest": j1["payload_digest"],
        "authority_class": AUTHORITY_CLASS,
    }

    command = [
        "gh",
        "attestation",
        "verify",
        str(path),
        "--repo",
        repository,
        "--signer-workflow",
        f"{repository}/{workflow_path}",
        "--predicate-type",
        IAP_PREDICATE_TYPE,
        "--deny-self-hosted-runners",
        "--format",
        "json",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise IAPVerificationError("J2_GH_CLI_UNAVAILABLE") from exc
    except OSError as exc:
        raise IAPVerificationError(f"J2_GH_EXECUTION_FAILURE: {exc}") from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        detail = f": {stderr}" if stderr else ""
        raise IAPVerificationError(f"J2_GH_ATTESTATION_VERIFY_FAILED{detail}")

    item = _parse_gh_json(completed.stdout)
    identity = _verify_j2_result(
        item,
        path=path,
        expected_predicate=expected_predicate,
        repository=repository,
        workflow_path=workflow_path,
        expected_run_id=expected_run_id,
        subject_sha256=j1["subject_sha256"],
    )

    if trusted_signer_digest is None:
        j3_status = "DEFER_UNTRUSTED_SIGNER_DIGEST"
        independent_authenticity = "NOT_ESTABLISHED"
    else:
        if type(trusted_signer_digest) is not str or _SHA40.fullmatch(trusted_signer_digest) is None:
            raise IAPVerificationError("J3_TRUSTED_SIGNER_DIGEST_INVALID")
        if trusted_signer_digest != identity["build_signer_digest"]:
            raise IAPVerificationError("J3_SIGNER_DIGEST_MISMATCH")
        j3_status = "PASS"
        independent_authenticity = "CONTROL_PLANE_TRUST_ANCHOR_MATCHED"

    receipt_without_digest: dict[str, object] = {
        "schema_version": IAP_RECEIPT_SCHEMA,
        "predicate_type": IAP_PREDICATE_TYPE,
        "repository": repository,
        "workflow_path": workflow_path,
        "pr_number": expected_pr,
        "head_sha": expected_head_sha,
        "run_id": expected_run_id,
        "surface_subject_sha256": j1["subject_sha256"],
        "surface_payload_digest": j1["payload_digest"],
        "j1_status": "PASS",
        "j2_status": "PASS",
        "j3_status": j3_status,
        "identity_bound_signing": "ESTABLISHED",
        "independent_falsifier_authenticity": independent_authenticity,
        "build_signer_uri": identity["build_signer_uri"],
        "build_signer_digest": identity["build_signer_digest"],
        "trusted_signer_digest": trusted_signer_digest,
        "source_repository_digest": identity["source_repository_digest"],
        "source_repository_ref": identity["source_repository_ref"],
        "run_invocation_uri": identity["run_invocation_uri"],
        "transparency_log_evidence": "VERIFIED",
        "authority_class": AUTHORITY_CLASS,
        "authority_effect": AUTHORITY_EFFECT,
    }
    receipt_digest = hashlib.sha256(_canonical_json(receipt_without_digest)).hexdigest()
    return {**receipt_without_digest, "receipt_digest": receipt_digest}
