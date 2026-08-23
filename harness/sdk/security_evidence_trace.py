"""Bind independently verified security evidence into ProofTrace.

The base adapter re-runs the SecurityEvidenceSet verifier before any Trace
mutation. The attested adapter goes further: it reads the evidence set from the
attested artifact itself, re-verifies its content commitment, executes GitHub's
cryptographic attestation verifier with locked provenance policy, and only then
records a VERIFIER span.

Neither path grants authority. A caller cannot inject a preasserted verifier or
provenance receipt through these APIs. Resulting spans remain
VERIFIER / NO_AUTHORITY / T2 and cannot advance the control-state root.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from harness.sdk.proof_trace import (
    NO_AUTHORITY,
    OK,
    T2,
    VERIFIER,
    ProofTrace,
    ProofTraceError,
    TraceSpanV1,
    digest_payload,
)
from security.security_evidence_set import (
    SecurityEvidenceSetVerificationV1,
    verify_security_evidence_set,
)
from security.verifier_provenance import (
    VerifierProvenanceReceiptV1,
    verify_attested_artifact_with_gh,
)


@dataclass(frozen=True)
class SecurityEvidenceTraceBindingV1:
    """Evidence-only result of binding one verified security evidence set."""

    span: TraceSpanV1
    verification: SecurityEvidenceSetVerificationV1


@dataclass(frozen=True)
class AttestedSecurityEvidenceTraceBindingV1:
    """Evidence-only result after content and external provenance verification."""

    span: TraceSpanV1
    verification: SecurityEvidenceSetVerificationV1
    provenance: VerifierProvenanceReceiptV1


def _require_verified_set(
    evidence_set_payload: Mapping[str, Any],
) -> tuple[SecurityEvidenceSetVerificationV1, str]:
    verification = verify_security_evidence_set(evidence_set_payload)
    if not verification.integrity_valid:
        raise ProofTraceError("SECURITY_EVIDENCE_SET_INTEGRITY_INVALID")
    set_digest = verification.verified_set_digest
    if set_digest is None:
        raise ProofTraceError("SECURITY_EVIDENCE_SET_VERIFIED_DIGEST_MISSING")
    return verification, set_digest


def bind_verified_security_evidence(
    trace: ProofTrace,
    evidence_set_payload: Mapping[str, Any],
    *,
    name: str = "security-evidence-verifier",
) -> SecurityEvidenceTraceBindingV1:
    """Re-verify a security set and bind its roots into an evidence-only span.

    Integrity failure aborts before ``record_span`` is called. A BLOCKED or
    incomplete/ERROR security disposition is still recordable evidence when
    the serialized set itself is structurally valid; verifier execution
    success must not be confused with admission permission.
    """

    verification, set_digest = _require_verified_set(evidence_set_payload)

    output_digest = digest_payload(
        {
            "schema_version": verification.schema_version,
            "authority": verification.authority,
            "integrity_valid": verification.integrity_valid,
            "complete": verification.complete,
            "aggregate_disposition": verification.aggregate_disposition.value,
            "verified_set_digest": set_digest,
            "verification_root": verification.verification_root,
            "reasons": list(verification.reasons),
            "member_count": verification.member_count,
        }
    )

    span = trace.record_span(
        name=name,
        span_kind=VERIFIER,
        status=OK,
        authority_class=NO_AUTHORITY,
        epistemic_tier=T2,
        input_digest=set_digest,
        output_digest=output_digest,
        evidence_roots=(set_digest, verification.verification_root),
    )

    return SecurityEvidenceTraceBindingV1(
        span=span,
        verification=verification,
    )


def verify_and_bind_attested_security_evidence(
    trace: ProofTrace,
    *,
    artifact_path: str | Path,
    repository: str,
    signer_workflow: str,
    source_commit: str,
    source_ref: str,
    gh_bin: str = "gh",
    name: str = "attested-security-evidence-verifier",
) -> AttestedSecurityEvidenceTraceBindingV1:
    """Verify one attested SecurityEvidenceSet artifact before Trace mutation.

    The artifact is the source of the serialized set; there is no separate
    caller-supplied evidence payload to splice against the attestation. The
    trace source commit must equal the source commit constrained in the GitHub
    attestation policy. Structural verification runs first, then
    ``gh attestation verify``. Any failure occurs before ``record_span``.
    """

    if source_commit != trace.header.source_commit:
        raise ProofTraceError("VERIFIER_PROVENANCE_SOURCE_COMMIT_TRACE_MISMATCH")

    path = Path(artifact_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProofTraceError("SECURITY_EVIDENCE_ARTIFACT_INVALID") from exc
    if not isinstance(payload, Mapping):
        raise ProofTraceError("SECURITY_EVIDENCE_ARTIFACT_INVALID")

    verification, set_digest = _require_verified_set(payload)

    provenance = verify_attested_artifact_with_gh(
        artifact_path=path,
        evidence_digest=set_digest,
        repository=repository,
        signer_workflow=signer_workflow,
        source_commit=source_commit,
        source_ref=source_ref,
        gh_bin=gh_bin,
    )
    if provenance.evidence_digest != set_digest:
        raise ProofTraceError("VERIFIER_PROVENANCE_EVIDENCE_DIGEST_MISMATCH")
    if provenance.source_commit != trace.header.source_commit:
        raise ProofTraceError("VERIFIER_PROVENANCE_SOURCE_COMMIT_TRACE_MISMATCH")

    output_digest = digest_payload(
        {
            "schema_version": verification.schema_version,
            "authority": verification.authority,
            "integrity_valid": verification.integrity_valid,
            "complete": verification.complete,
            "aggregate_disposition": verification.aggregate_disposition.value,
            "verified_set_digest": set_digest,
            "verification_root": verification.verification_root,
            "reasons": list(verification.reasons),
            "member_count": verification.member_count,
            "provenance_schema_version": provenance.schema_version,
            "provenance_receipt_digest": provenance.receipt_digest,
            "verification_mechanism": provenance.verification_mechanism,
        }
    )

    span = trace.record_span(
        name=name,
        span_kind=VERIFIER,
        status=OK,
        authority_class=NO_AUTHORITY,
        epistemic_tier=T2,
        input_digest=set_digest,
        output_digest=output_digest,
        evidence_roots=(
            set_digest,
            verification.verification_root,
            provenance.receipt_digest,
        ),
    )

    return AttestedSecurityEvidenceTraceBindingV1(
        span=span,
        verification=verification,
        provenance=provenance,
    )
