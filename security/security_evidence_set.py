#!/usr/bin/env python3
"""Producer-neutral, evidence-only security aggregation and offline verification.

This module intentionally stores digest references rather than raw scanner output.
A structurally valid evidence set can still be BLOCKED or incomplete; integrity
verification never grants admission or effect authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from security.glasswing_evidence import (
    EVIDENCE_AUTHORITY,
    SecurityDisposition,
    SecurityEvidenceReport,
)


SET_SCHEMA_VERSION = "SECURITY_EVIDENCE_SET_V1"
VERIFICATION_SCHEMA_VERSION = "SECURITY_EVIDENCE_SET_VERIFICATION_V1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(domain: str, value: Any) -> str:
    payload = f"{domain}\x00{_canonical_json(value)}".encode("utf-8")
    return sha256(payload).hexdigest()


def _require_sha256(name: str, value: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{name}:INVALID_SHA256")
    return value


def _normalize_token(name: str, value: str, *, uppercase: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name}:MISSING")
    normalized = value.upper() if uppercase else value
    if not SAFE_TOKEN_RE.fullmatch(normalized):
        raise ValueError(f"{name}:INVALID")
    return normalized


def _normalize_disposition(value: SecurityDisposition | str) -> SecurityDisposition:
    if isinstance(value, SecurityDisposition):
        return value
    return SecurityDisposition(str(value))


def _member_identity(
    *,
    evidence_kind: str,
    producer_id: str,
    subject_digest: str,
    evidence_digest: str,
    disposition: SecurityDisposition,
    authority: str,
    independence: str,
    metadata_digest: str,
) -> dict[str, str]:
    return {
        "evidence_kind": evidence_kind,
        "producer_id": producer_id,
        "subject_digest": subject_digest,
        "evidence_digest": evidence_digest,
        "disposition": disposition.value,
        "authority": authority,
        "independence": independence,
        "metadata_digest": metadata_digest,
    }


@dataclass(frozen=True)
class SecurityEvidenceReference:
    """Digest-only reference to one detector/checker result."""

    member_id: str
    evidence_kind: str
    producer_id: str
    subject_digest: str
    evidence_digest: str
    disposition: SecurityDisposition
    authority: str
    independence: str
    metadata_digest: str

    @classmethod
    def create(
        cls,
        *,
        evidence_kind: str,
        producer_id: str,
        subject_digest: str,
        evidence_digest: str,
        disposition: SecurityDisposition | str,
        authority: str = EVIDENCE_AUTHORITY,
        independence: str,
        metadata_digest: str,
    ) -> "SecurityEvidenceReference":
        kind = _normalize_token("evidence_kind", evidence_kind, uppercase=True)
        producer = _normalize_token("producer_id", producer_id)
        subject = _require_sha256("subject_digest", subject_digest)
        evidence = _require_sha256("evidence_digest", evidence_digest)
        resolved_disposition = _normalize_disposition(disposition)
        resolved_authority = _normalize_token("authority", authority, uppercase=True)
        resolved_independence = _normalize_token(
            "independence", independence, uppercase=True
        )
        metadata = _require_sha256("metadata_digest", metadata_digest)
        identity = _member_identity(
            evidence_kind=kind,
            producer_id=producer,
            subject_digest=subject,
            evidence_digest=evidence,
            disposition=resolved_disposition,
            authority=resolved_authority,
            independence=resolved_independence,
            metadata_digest=metadata,
        )
        return cls(
            member_id=_digest("AEGIS_SECURITY_EVIDENCE_REFERENCE_V1", identity),
            evidence_kind=kind,
            producer_id=producer,
            subject_digest=subject,
            evidence_digest=evidence,
            disposition=resolved_disposition,
            authority=resolved_authority,
            independence=resolved_independence,
            metadata_digest=metadata,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "member_id": self.member_id,
            **_member_identity(
                evidence_kind=self.evidence_kind,
                producer_id=self.producer_id,
                subject_digest=self.subject_digest,
                evidence_digest=self.evidence_digest,
                disposition=self.disposition,
                authority=self.authority,
                independence=self.independence,
                metadata_digest=self.metadata_digest,
            ),
        }


@dataclass(frozen=True)
class SecurityEvidenceSetV1:
    """Deterministic aggregate of normalized security evidence references."""

    schema_version: str
    authority: str
    subject_root: str
    required_kinds: tuple[str, ...]
    members: tuple[SecurityEvidenceReference, ...]
    complete: bool
    aggregate_disposition: SecurityDisposition
    set_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "authority": self.authority,
            "subject_root": self.subject_root,
            "required_kinds": list(self.required_kinds),
            "members": [member.to_dict() for member in self.members],
            "complete": self.complete,
            "aggregate_disposition": self.aggregate_disposition.value,
            "set_digest": self.set_digest,
        }


@dataclass(frozen=True)
class SecurityEvidenceSetVerificationV1:
    """Offline verification receipt.  It is evidence-only, never authority."""

    schema_version: str
    authority: str
    integrity_valid: bool
    complete: bool
    aggregate_disposition: SecurityDisposition
    verified_set_digest: str | None
    reasons: tuple[str, ...]
    member_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "authority": self.authority,
            "integrity_valid": self.integrity_valid,
            "complete": self.complete,
            "aggregate_disposition": self.aggregate_disposition.value,
            "verified_set_digest": self.verified_set_digest,
            "reasons": list(self.reasons),
            "member_count": self.member_count,
        }


def _aggregate_disposition(
    dispositions: Sequence[SecurityDisposition], *, complete: bool
) -> SecurityDisposition:
    if not complete or SecurityDisposition.ERROR in dispositions:
        return SecurityDisposition.ERROR
    if SecurityDisposition.BLOCKED in dispositions:
        return SecurityDisposition.BLOCKED
    if SecurityDisposition.REVIEW in dispositions:
        return SecurityDisposition.REVIEW
    return SecurityDisposition.CLEAN_WITHIN_COVERAGE


def _set_body(
    *,
    subject_root: str,
    required_kinds: Sequence[str],
    members: Sequence[Mapping[str, Any]],
    complete: bool,
    aggregate_disposition: SecurityDisposition,
) -> dict[str, Any]:
    return {
        "schema_version": SET_SCHEMA_VERSION,
        "authority": EVIDENCE_AUTHORITY,
        "subject_root": subject_root,
        "required_kinds": list(required_kinds),
        "members": list(members),
        "complete": complete,
        "aggregate_disposition": aggregate_disposition.value,
    }


def build_security_evidence_set(
    *,
    subject_root: str,
    members: Sequence[SecurityEvidenceReference],
    required_kinds: Sequence[str] = (),
) -> SecurityEvidenceSetV1:
    """Build an order-independent aggregate without copying raw evidence payloads."""

    root = _require_sha256("subject_root", subject_root)
    required = tuple(
        sorted({_normalize_token("required_kind", kind, uppercase=True) for kind in required_kinds})
    )
    ordered_members = tuple(sorted(members, key=lambda member: member.member_id))
    if len({member.member_id for member in ordered_members}) != len(ordered_members):
        raise ValueError("DUPLICATE_SECURITY_EVIDENCE_MEMBER")
    if any(member.authority != EVIDENCE_AUTHORITY for member in ordered_members):
        raise ValueError("NON_EVIDENCE_AUTHORITY")

    present = {member.evidence_kind for member in ordered_members}
    complete = set(required).issubset(present)
    aggregate = _aggregate_disposition(
        [member.disposition for member in ordered_members], complete=complete
    )
    member_payloads = [member.to_dict() for member in ordered_members]
    body = _set_body(
        subject_root=root,
        required_kinds=required,
        members=member_payloads,
        complete=complete,
        aggregate_disposition=aggregate,
    )
    return SecurityEvidenceSetV1(
        schema_version=SET_SCHEMA_VERSION,
        authority=EVIDENCE_AUTHORITY,
        subject_root=root,
        required_kinds=required,
        members=ordered_members,
        complete=complete,
        aggregate_disposition=aggregate,
        set_digest=_digest("AEGIS_SECURITY_EVIDENCE_SET_V1", body),
    )


def glasswing_reference(
    report: SecurityEvidenceReport, *, independence: str
) -> SecurityEvidenceReference:
    """Project a Glasswing report into one digest-only aggregate member."""

    return SecurityEvidenceReference.create(
        evidence_kind="GLASSWING",
        producer_id=report.detector_id,
        subject_digest=report.source_digest,
        evidence_digest=report.report_digest,
        disposition=report.disposition,
        authority=report.authority,
        independence=independence,
        metadata_digest=report.rulepack_digest,
    )


def verify_security_evidence_set(
    payload: Mapping[str, Any],
) -> SecurityEvidenceSetVerificationV1:
    """Re-derive a serialized evidence set without invoking scanners or models."""

    integrity_errors: list[str] = []
    observations: list[str] = []

    if not isinstance(payload, Mapping):
        return SecurityEvidenceSetVerificationV1(
            schema_version=VERIFICATION_SCHEMA_VERSION,
            authority=EVIDENCE_AUTHORITY,
            integrity_valid=False,
            complete=False,
            aggregate_disposition=SecurityDisposition.ERROR,
            verified_set_digest=None,
            reasons=("SET_ROOT_NOT_OBJECT",),
            member_count=0,
        )

    if payload.get("schema_version") != SET_SCHEMA_VERSION:
        integrity_errors.append("SET_SCHEMA_MISMATCH")
    if payload.get("authority") != EVIDENCE_AUTHORITY:
        integrity_errors.append("SET_NON_EVIDENCE_AUTHORITY")

    subject_root = payload.get("subject_root")
    if not isinstance(subject_root, str) or not SHA256_RE.fullmatch(subject_root):
        integrity_errors.append("SUBJECT_ROOT_INVALID")
        subject_root = "0" * 64

    raw_required = payload.get("required_kinds")
    if not isinstance(raw_required, list) or not all(
        isinstance(kind, str) and kind for kind in raw_required
    ):
        integrity_errors.append("REQUIRED_KINDS_INVALID")
        required: tuple[str, ...] = ()
    else:
        try:
            required = tuple(
                sorted(
                    {
                        _normalize_token("required_kind", kind, uppercase=True)
                        for kind in raw_required
                    }
                )
            )
        except ValueError:
            integrity_errors.append("REQUIRED_KINDS_INVALID")
            required = ()
        if list(required) != raw_required:
            integrity_errors.append("REQUIRED_KINDS_NOT_CANONICAL")

    raw_members = payload.get("members")
    if not isinstance(raw_members, list):
        integrity_errors.append("MEMBERS_INVALID")
        raw_members = []

    reconstructed: list[dict[str, Any]] = []
    dispositions: list[SecurityDisposition] = []
    present_kinds: set[str] = set()
    seen_expected_ids: set[str] = set()

    for raw in raw_members:
        if not isinstance(raw, Mapping):
            integrity_errors.append("MEMBER_NOT_OBJECT")
            continue
        try:
            kind = _normalize_token(
                "evidence_kind", str(raw.get("evidence_kind", "")), uppercase=True
            )
            producer = _normalize_token("producer_id", str(raw.get("producer_id", "")))
            subject = _require_sha256("subject_digest", str(raw.get("subject_digest", "")))
            evidence = _require_sha256(
                "evidence_digest", str(raw.get("evidence_digest", ""))
            )
            disposition = _normalize_disposition(str(raw.get("disposition", "")))
            authority = _normalize_token(
                "authority", str(raw.get("authority", "")), uppercase=True
            )
            independence = _normalize_token(
                "independence", str(raw.get("independence", "")), uppercase=True
            )
            metadata = _require_sha256(
                "metadata_digest", str(raw.get("metadata_digest", ""))
            )
        except (ValueError, TypeError):
            integrity_errors.append("MEMBER_FIELD_INVALID")
            continue

        if authority != EVIDENCE_AUTHORITY:
            integrity_errors.append("NON_EVIDENCE_AUTHORITY")

        identity = _member_identity(
            evidence_kind=kind,
            producer_id=producer,
            subject_digest=subject,
            evidence_digest=evidence,
            disposition=disposition,
            authority=authority,
            independence=independence,
            metadata_digest=metadata,
        )
        expected_id = _digest("AEGIS_SECURITY_EVIDENCE_REFERENCE_V1", identity)
        if raw.get("member_id") != expected_id:
            integrity_errors.append("MEMBER_ID_MISMATCH")
        if expected_id in seen_expected_ids:
            integrity_errors.append("DUPLICATE_SECURITY_EVIDENCE_MEMBER")
        seen_expected_ids.add(expected_id)

        reconstructed.append({"member_id": expected_id, **identity})
        dispositions.append(disposition)
        present_kinds.add(kind)

    reconstructed.sort(key=lambda member: member["member_id"])
    supplied_member_ids = [
        raw.get("member_id") for raw in raw_members if isinstance(raw, Mapping)
    ]
    if supplied_member_ids != sorted(supplied_member_ids):
        integrity_errors.append("MEMBER_ORDER_NOT_CANONICAL")

    missing = sorted(set(required) - present_kinds)
    observations.extend(f"MISSING_REQUIRED_KIND:{kind}" for kind in missing)
    complete = not missing
    aggregate = _aggregate_disposition(dispositions, complete=complete)

    if payload.get("complete") is not complete:
        integrity_errors.append("COMPLETENESS_MISMATCH")
    if payload.get("aggregate_disposition") != aggregate.value:
        integrity_errors.append("AGGREGATE_DISPOSITION_MISMATCH")

    body = _set_body(
        subject_root=subject_root,
        required_kinds=required,
        members=reconstructed,
        complete=complete,
        aggregate_disposition=aggregate,
    )
    expected_set_digest = _digest("AEGIS_SECURITY_EVIDENCE_SET_V1", body)
    if payload.get("set_digest") != expected_set_digest:
        integrity_errors.append("SET_DIGEST_MISMATCH")

    reasons = tuple(dict.fromkeys([*integrity_errors, *observations]))
    return SecurityEvidenceSetVerificationV1(
        schema_version=VERIFICATION_SCHEMA_VERSION,
        authority=EVIDENCE_AUTHORITY,
        integrity_valid=not integrity_errors,
        complete=complete,
        aggregate_disposition=aggregate,
        verified_set_digest=expected_set_digest,
        reasons=reasons,
        member_count=len(reconstructed),
    )
