"""Bind independently verified security evidence into ProofTrace.

This adapter deliberately re-runs the SecurityEvidenceSet verifier before any
Trace mutation. A caller cannot inject a preasserted verifier receipt through
this API. The resulting VERIFIER span is evidence-only and cannot advance the
control-state root.
"""
from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class SecurityEvidenceTraceBindingV1:
    """Evidence-only result of binding one verified security evidence set."""

    span: TraceSpanV1
    verification: SecurityEvidenceSetVerificationV1


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

    verification = verify_security_evidence_set(evidence_set_payload)
    if not verification.integrity_valid:
        raise ProofTraceError("SECURITY_EVIDENCE_SET_INTEGRITY_INVALID")

    set_digest = verification.verified_set_digest
    if set_digest is None:
        raise ProofTraceError("SECURITY_EVIDENCE_SET_VERIFIED_DIGEST_MISSING")

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
