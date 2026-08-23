#!/usr/bin/env python3
"""Content-bound provenance receipt for independently verified security evidence.

This module does not verify signatures, OIDC tokens, certificates, or GitHub
artifact attestations. The cryptographic verification step is performed by
``gh attestation verify`` in CI. This receipt records only a deterministic,
digest-only summary of that already-executed verification and therefore remains
EVIDENCE_ONLY. It is never an admission, execution, or effect authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from security.glasswing_evidence import EVIDENCE_AUTHORITY


SCHEMA_VERSION = "VERIFIER_PROVENANCE_RECEIPT_V1"
VERIFICATION_MECHANISM = "GH_ATTESTATION_VERIFY"
GITHUB_ACTIONS_OIDC_ISSUER = "https://token.actions.githubusercontent.com"
SLSA_PROVENANCE_V1 = "https://slsa.dev/provenance/v1"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
WORKFLOW_RE = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$"
)
SOURCE_REF_RE = re.compile(r"^refs/(heads|tags)/[A-Za-z0-9._/+-]+$")
VERIFIER_ID_RE = re.compile(r"^[A-Za-z0-9._:+/-]+$")
GH_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[-+][A-Za-z0-9._-]+)?$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(domain: str, value: Any) -> str:
    payload = f"{domain}\x00{_canonical_json(value)}".encode("utf-8")
    return sha256(payload).hexdigest()


def _require_sha256(name: str, value: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{name}:INVALID_SHA256")
    return value


def _require_match(name: str, value: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{name}:INVALID")
    return value


def _body(
    *,
    verifier_id: str,
    repository: str,
    signer_workflow: str,
    source_commit: str,
    source_ref: str,
    subject_digest: str,
    evidence_digest: str,
    verification_output_digest: str,
    gh_cli_version: str,
    oidc_issuer: str,
    predicate_type: str,
) -> dict[str, str]:
    return {
        "schema_version": SCHEMA_VERSION,
        "authority": EVIDENCE_AUTHORITY,
        "verifier_id": verifier_id,
        "verification_mechanism": VERIFICATION_MECHANISM,
        "repository": repository,
        "signer_workflow": signer_workflow,
        "source_commit": source_commit,
        "source_ref": source_ref,
        "subject_digest": subject_digest,
        "evidence_digest": evidence_digest,
        "verification_output_digest": verification_output_digest,
        "gh_cli_version": gh_cli_version,
        "oidc_issuer": oidc_issuer,
        "predicate_type": predicate_type,
    }


@dataclass(frozen=True)
class VerifierProvenanceReceiptV1:
    """Digest-only evidence describing one successful external attestation check."""

    schema_version: str
    authority: str
    verifier_id: str
    verification_mechanism: str
    repository: str
    signer_workflow: str
    source_commit: str
    source_ref: str
    subject_digest: str
    evidence_digest: str
    verification_output_digest: str
    gh_cli_version: str
    oidc_issuer: str
    predicate_type: str
    receipt_digest: str

    def to_dict(self) -> dict[str, str]:
        return {
            **_body(
                verifier_id=self.verifier_id,
                repository=self.repository,
                signer_workflow=self.signer_workflow,
                source_commit=self.source_commit,
                source_ref=self.source_ref,
                subject_digest=self.subject_digest,
                evidence_digest=self.evidence_digest,
                verification_output_digest=self.verification_output_digest,
                gh_cli_version=self.gh_cli_version,
                oidc_issuer=self.oidc_issuer,
                predicate_type=self.predicate_type,
            ),
            "receipt_digest": self.receipt_digest,
        }


def build_verifier_provenance_receipt(
    *,
    verifier_id: str,
    repository: str,
    signer_workflow: str,
    source_commit: str,
    source_ref: str,
    subject_digest: str,
    evidence_digest: str,
    verification_output_digest: str,
    gh_cli_version: str,
    oidc_issuer: str,
    predicate_type: str,
) -> VerifierProvenanceReceiptV1:
    """Record an already-successful ``gh attestation verify`` result.

    The caller must supply only digests and public provenance identifiers; raw
    tokens, certificates, signatures, bundles, and verifier output are omitted.
    This function validates GitHub/SLSA policy constants and creates a content
    commitment. It intentionally does not claim to perform signature checking.
    """

    verifier = _require_match("verifier_id", verifier_id, VERIFIER_ID_RE)
    repo = _require_match("repository", repository, REPOSITORY_RE)
    workflow = _require_match("signer_workflow", signer_workflow, WORKFLOW_RE)
    commit = _require_match("source_commit", source_commit, COMMIT_RE)
    ref = _require_match("source_ref", source_ref, SOURCE_REF_RE)
    subject = _require_sha256("subject_digest", subject_digest)
    evidence = _require_sha256("evidence_digest", evidence_digest)
    verification_output = _require_sha256(
        "verification_output_digest", verification_output_digest
    )
    version = _require_match("gh_cli_version", gh_cli_version, GH_VERSION_RE)

    if oidc_issuer != GITHUB_ACTIONS_OIDC_ISSUER:
        raise ValueError("OIDC_ISSUER_MISMATCH")
    if predicate_type != SLSA_PROVENANCE_V1:
        raise ValueError("PREDICATE_TYPE_MISMATCH")

    body = _body(
        verifier_id=verifier,
        repository=repo,
        signer_workflow=workflow,
        source_commit=commit,
        source_ref=ref,
        subject_digest=subject,
        evidence_digest=evidence,
        verification_output_digest=verification_output,
        gh_cli_version=version,
        oidc_issuer=oidc_issuer,
        predicate_type=predicate_type,
    )
    return VerifierProvenanceReceiptV1(
        **body,
        receipt_digest=_digest("AEGIS_VERIFIER_PROVENANCE_RECEIPT_V1", body),
    )


def verify_verifier_provenance_receipt(payload: Mapping[str, Any]) -> bool:
    """Verify receipt structure and deterministic content commitment only.

    Authenticity still requires independent verification of the referenced
    GitHub artifact attestation. Receipt integrity must not be promoted into
    signer authenticity or admission authority.
    """

    if not isinstance(payload, Mapping):
        return False

    expected_keys = {
        "schema_version",
        "authority",
        "verifier_id",
        "verification_mechanism",
        "repository",
        "signer_workflow",
        "source_commit",
        "source_ref",
        "subject_digest",
        "evidence_digest",
        "verification_output_digest",
        "gh_cli_version",
        "oidc_issuer",
        "predicate_type",
        "receipt_digest",
    }
    if set(payload) != expected_keys:
        return False
    if payload.get("schema_version") != SCHEMA_VERSION:
        return False
    if payload.get("authority") != EVIDENCE_AUTHORITY:
        return False
    if payload.get("verification_mechanism") != VERIFICATION_MECHANISM:
        return False

    try:
        verifier = _require_match("verifier_id", payload["verifier_id"], VERIFIER_ID_RE)
        repo = _require_match("repository", payload["repository"], REPOSITORY_RE)
        workflow = _require_match("signer_workflow", payload["signer_workflow"], WORKFLOW_RE)
        commit = _require_match("source_commit", payload["source_commit"], COMMIT_RE)
        ref = _require_match("source_ref", payload["source_ref"], SOURCE_REF_RE)
        subject = _require_sha256("subject_digest", payload["subject_digest"])
        evidence = _require_sha256("evidence_digest", payload["evidence_digest"])
        verification_output = _require_sha256(
            "verification_output_digest", payload["verification_output_digest"]
        )
        version = _require_match("gh_cli_version", payload["gh_cli_version"], GH_VERSION_RE)
    except (KeyError, TypeError, ValueError):
        return False

    if payload.get("oidc_issuer") != GITHUB_ACTIONS_OIDC_ISSUER:
        return False
    if payload.get("predicate_type") != SLSA_PROVENANCE_V1:
        return False
    receipt_digest = payload.get("receipt_digest")
    if not isinstance(receipt_digest, str) or not SHA256_RE.fullmatch(receipt_digest):
        return False

    body = _body(
        verifier_id=verifier,
        repository=repo,
        signer_workflow=workflow,
        source_commit=commit,
        source_ref=ref,
        subject_digest=subject,
        evidence_digest=evidence,
        verification_output_digest=verification_output,
        gh_cli_version=version,
        oidc_issuer=GITHUB_ACTIONS_OIDC_ISSUER,
        predicate_type=SLSA_PROVENANCE_V1,
    )
    return receipt_digest == _digest("AEGIS_VERIFIER_PROVENANCE_RECEIPT_V1", body)
