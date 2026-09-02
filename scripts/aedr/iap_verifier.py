#!/usr/bin/env python3
"""AEGIS AEDR Identity Attestation Protocol (IAP-v1).

J1 binds local surface bytes, payload digest, PR, exact head and run.
J2 cryptographically verifies a GitHub/Sigstore attestation and re-checks its
statement/certificate against J1. J3 compares the verified signer digest with
an externally supplied policy anchor. None of these stages grants authority.

A matching J3 signer digest is a policy match, not proof of an independent
falsifier: this workflow is executed from the candidate PR merge ref. True
independent authenticity requires a separately protected trusted builder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.aedr.surface_ingestor import FalsificationSurfaceIngestor, SurfaceIngestionError
else:
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
    pass


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _validate_identity_inputs(repository: str, workflow_path: str, expected_pr: int, expected_head_sha: str, expected_run_id: int) -> None:
    if type(repository) is not str or _REPOSITORY.fullmatch(repository) is None:
        raise IAPVerificationError("J1_REPOSITORY_INVALID")
    if type(workflow_path) is not str or _WORKFLOW_PATH.fullmatch(workflow_path) is None or ".." in Path(workflow_path).parts:
        raise IAPVerificationError("J1_WORKFLOW_PATH_INVALID")
    if type(expected_pr) is not int or expected_pr <= 0:
        raise IAPVerificationError("J1_PR_NUMBER_INVALID")
    if type(expected_head_sha) is not str or _SHA40.fullmatch(expected_head_sha) is None:
        raise IAPVerificationError("J1_HEAD_SHA_INVALID")
    if type(expected_run_id) is not int or expected_run_id <= 0:
        raise IAPVerificationError("J1_RUN_ID_INVALID")


def _validate_j1(path: Path, *, repository: str, workflow_path: str, expected_pr: int, expected_head_sha: str, expected_run_id: int) -> dict[str, Any]:
    _validate_identity_inputs(repository, workflow_path, expected_pr, expected_head_sha, expected_run_id)
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
    declared = data.get("payload_digest")
    if type(declared) is not str or _SHA64.fullmatch(declared) is None:
        raise IAPVerificationError("J1_PAYLOAD_DIGEST_INVALID")
    computed = hashlib.sha256(FalsificationSurfaceIngestor._canonical_json(surface)).hexdigest()
    if declared != computed:
        raise IAPVerificationError("J1_PAYLOAD_DIGEST_MISMATCH")
    return {"subject_sha256": hashlib.sha256(raw).hexdigest(), "payload_digest": computed}


def build_iap_predicate(surface_path: Path | str, *, repository: str, workflow_path: str, expected_pr: int, expected_head_sha: str, expected_run_id: int) -> dict[str, object]:
    j1 = _validate_j1(Path(surface_path), repository=repository, workflow_path=workflow_path, expected_pr=expected_pr, expected_head_sha=expected_head_sha, expected_run_id=expected_run_id)
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


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise IAPVerificationError(code)
    return value


def _parse_gh(stdout: str) -> dict[str, Any]:
    try:
        value = json.loads(stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise IAPVerificationError("J2_GH_OUTPUT_INVALID_JSON") from exc
    if not isinstance(value, list):
        raise IAPVerificationError("J2_GH_OUTPUT_NOT_LIST")
    if len(value) != 1:
        raise IAPVerificationError("J2_AMBIGUOUS_ATTESTATIONS")
    if not isinstance(value[0], dict):
        raise IAPVerificationError("J2_GH_OUTPUT_INVALID_ENTRY")
    return value[0]


def _verify_j2(item: dict[str, Any], *, path: Path, predicate: dict[str, object], repository: str, workflow_path: str, expected_run_id: int, subject_sha256: str) -> dict[str, str]:
    result = _mapping(item.get("verificationResult"), "J2_VERIFICATION_RESULT_MISSING")
    statement = _mapping(result.get("statement"), "J2_STATEMENT_MISSING")
    if statement.get("predicateType") != IAP_PREDICATE_TYPE:
        raise IAPVerificationError("J2_PREDICATE_TYPE_MISMATCH")
    subjects = statement.get("subject")
    if not isinstance(subjects, list) or len(subjects) != 1 or not isinstance(subjects[0], dict):
        raise IAPVerificationError("J2_SUBJECT_AMBIGUOUS")
    digest = _mapping(subjects[0].get("digest"), "J2_SUBJECT_DIGEST_MISSING")
    if digest.get("sha256") != subject_sha256:
        raise IAPVerificationError("J2_SUBJECT_DIGEST_MISMATCH")
    if subjects[0].get("name") not in (None, path.name):
        raise IAPVerificationError("J2_SUBJECT_NAME_MISMATCH")
    if statement.get("predicate") != predicate:
        raise IAPVerificationError("J2_PREDICATE_MISMATCH")

    cert = _mapping(_mapping(result.get("signature"), "J2_SIGNATURE_MISSING").get("certificate"), "J2_CERTIFICATE_MISSING")
    if cert.get("issuer") != GITHUB_ACTIONS_OIDC_ISSUER:
        raise IAPVerificationError("J2_ISSUER_MISMATCH")
    if cert.get("githubWorkflowRepository") != repository:
        raise IAPVerificationError("J2_REPOSITORY_MISMATCH")
    if cert.get("runnerEnvironment") != "github-hosted":
        raise IAPVerificationError("J2_RUNNER_ENVIRONMENT_MISMATCH")
    if cert.get("sourceRepositoryURI") != f"https://github.com/{repository}":
        raise IAPVerificationError("J2_SOURCE_REPOSITORY_MISMATCH")
    prefix = f"https://github.com/{repository}/{workflow_path}@"
    signer_uri = cert.get("buildSignerURI")
    san = cert.get("subjectAlternativeName")
    if type(signer_uri) is not str or not signer_uri.startswith(prefix):
        raise IAPVerificationError("J2_SIGNER_WORKFLOW_MISMATCH")
    if type(san) is not str or not san.startswith(prefix):
        raise IAPVerificationError("J2_SIGNER_SAN_MISMATCH")
    signer_digest = cert.get("buildSignerDigest")
    source_digest = cert.get("sourceRepositoryDigest")
    if type(signer_digest) is not str or _SHA40.fullmatch(signer_digest) is None:
        raise IAPVerificationError("J2_SIGNER_DIGEST_INVALID")
    if type(source_digest) is not str or _SHA40.fullmatch(source_digest) is None:
        raise IAPVerificationError("J2_SOURCE_DIGEST_INVALID")
    source_ref = cert.get("sourceRepositoryRef")
    if type(source_ref) is not str or not source_ref.startswith("refs/"):
        raise IAPVerificationError("J2_SOURCE_REF_INVALID")
    run_uri = cert.get("runInvocationURI")
    run_prefix = f"https://github.com/{repository}/actions/runs/{expected_run_id}/attempts/"
    if type(run_uri) is not str or not run_uri.startswith(run_prefix):
        raise IAPVerificationError("J2_RUN_ID_MISMATCH")
    attempt = run_uri[len(run_prefix):]
    if not attempt.isdigit() or int(attempt) <= 0:
        raise IAPVerificationError("J2_RUN_INVOCATION_INVALID")
    timestamps = result.get("verifiedTimestamps")
    if not isinstance(timestamps, list) or not any(isinstance(x, dict) and x.get("type") == "Tlog" for x in timestamps):
        raise IAPVerificationError("J2_TRANSPARENCY_LOG_MISSING")
    return {"build_signer_uri": signer_uri, "build_signer_digest": signer_digest, "source_repository_digest": source_digest, "source_repository_ref": source_ref, "run_invocation_uri": run_uri}


def verify_iap(surface_path: Path | str, *, repository: str, workflow_path: str, expected_pr: int, expected_head_sha: str, expected_run_id: int, trusted_signer_digest: str | None = None, bundle_path: Path | str | None = None) -> dict[str, object]:
    path = Path(surface_path)
    j1 = _validate_j1(path, repository=repository, workflow_path=workflow_path, expected_pr=expected_pr, expected_head_sha=expected_head_sha, expected_run_id=expected_run_id)
    predicate = build_iap_predicate(path, repository=repository, workflow_path=workflow_path, expected_pr=expected_pr, expected_head_sha=expected_head_sha, expected_run_id=expected_run_id)
    command = ["gh", "attestation", "verify", str(path), "--repo", repository, "--signer-workflow", f"{repository}/{workflow_path}", "--predicate-type", IAP_PREDICATE_TYPE, "--deny-self-hosted-runners", "--format", "json"]
    if bundle_path is not None:
        bundle = Path(bundle_path)
        if not bundle.is_file():
            raise IAPVerificationError("J2_BUNDLE_UNAVAILABLE")
        command.extend(["--bundle", str(bundle)])
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise IAPVerificationError("J2_GH_CLI_UNAVAILABLE") from exc
    except OSError as exc:
        raise IAPVerificationError(f"J2_GH_EXECUTION_FAILURE: {exc}") from exc
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise IAPVerificationError("J2_GH_ATTESTATION_VERIFY_FAILED" + (f": {stderr}" if stderr else ""))
    identity = _verify_j2(_parse_gh(completed.stdout), path=path, predicate=predicate, repository=repository, workflow_path=workflow_path, expected_run_id=expected_run_id, subject_sha256=j1["subject_sha256"])

    if trusted_signer_digest is None:
        j3_status = "DEFER_UNTRUSTED_SIGNER_DIGEST"
        policy_match = "NOT_ESTABLISHED"
    else:
        if type(trusted_signer_digest) is not str or _SHA40.fullmatch(trusted_signer_digest) is None:
            raise IAPVerificationError("J3_TRUSTED_SIGNER_DIGEST_INVALID")
        if trusted_signer_digest != identity["build_signer_digest"]:
            raise IAPVerificationError("J3_SIGNER_DIGEST_MISMATCH")
        j3_status = "PASS"
        policy_match = "ESTABLISHED"

    receipt: dict[str, object] = {
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
        "trusted_signer_policy_match": policy_match,
        "independent_falsifier_authenticity": "NOT_ESTABLISHED",
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
    return {**receipt, "receipt_digest": hashlib.sha256(_canonical_json(receipt)).hexdigest()}


def _atomic_write_json(path: Path, value: object) -> None:
    payload = _canonical_json(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _identity_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--surface", required=True)
    p.add_argument("--repository", required=True)
    p.add_argument("--workflow-path", required=True)
    p.add_argument("--expected-pr", required=True, type=int)
    p.add_argument("--expected-head-sha", required=True)
    p.add_argument("--expected-run-id", required=True, type=int)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AEGIS AEDR IAP-v1")
    subs = p.add_subparsers(dest="command", required=True)
    pred = subs.add_parser("predicate")
    _identity_args(pred)
    pred.add_argument("--output", required=True)
    verify = subs.add_parser("verify")
    _identity_args(verify)
    verify.add_argument("--bundle")
    verify.add_argument("--trusted-signer-digest")
    verify.add_argument("--receipt-output", required=True)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {"repository": args.repository, "workflow_path": args.workflow_path, "expected_pr": args.expected_pr, "expected_head_sha": args.expected_head_sha, "expected_run_id": args.expected_run_id}
    try:
        if args.command == "predicate":
            _atomic_write_json(Path(args.output), build_iap_predicate(args.surface, **common))
            return 0
        receipt = verify_iap(args.surface, **common, trusted_signer_digest=args.trusted_signer_digest, bundle_path=args.bundle)
        _atomic_write_json(Path(args.receipt_output), receipt)
        print(_canonical_json(receipt).decode("ascii"))
        return 0
    except IAPVerificationError as exc:
        print(f"iap_verifier: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
