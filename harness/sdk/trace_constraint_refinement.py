"""AEGIS KG-004 semantic refinement layer for Proof Trace bundles.

A ProofTraceBundleV1 proves structural/hash/state properties of a trace.  It does
not, by itself, assign semantic meaning to arbitrary evidence/receipt digests.
This module adds a separate evidence-only certificate that binds selected trace
spans to explicit provenance, restriction, and authority commitments and checks
that constraint-carrying transforms preserve those commitments along the actual
causal graph.

The certificate is never authority.  It cannot advance control state and it does
not create grants.  In v1, MEMORY/HANDOFF/HERITAGE edges are strictly
non-amplifying: provenance and restrictions may only accumulate, while authority
may only stay equal or contract.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

from harness.sdk.proof_trace import (
    HANDOFF,
    HERITAGE,
    MEMORY,
    ProofTraceBundleV1,
    verify_trace_bundle,
)
from harness.sdk.sovereign_execution import canonical_hash

CONSTRAINT_CERTIFICATE_KIND = "AEGIS_TRACE_CONSTRAINT_CERTIFICATE_V1"
CONSTRAINT_CERTIFICATE_SEMANTICS = "CONSTRAINT_BINDINGS_ARE_EVIDENCE_NOT_AUTHORITY"
CONSTRAINT_CARRYING_KINDS = {MEMORY, HANDOFF, HERITAGE}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")


class TraceConstraintError(ValueError):
    """Fail-closed semantic refinement error with a stable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise TraceConstraintError(f"{name}:INVALID_SHA256")


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise TraceConstraintError(f"{name}:INVALID_ID")


def _require_unique_hashes(name: str, values: Sequence[str]) -> None:
    for value in values:
        _require_hash(name, value)
    if len(values) != len(set(values)):
        raise TraceConstraintError(f"{name}:DUPLICATE")


def constraint_causal_root(binding_roots: Iterable[str]) -> str:
    roots = tuple(binding_roots)
    _require_unique_hashes("causal_binding_root", roots)
    return canonical_hash(
        "AEGIS_TRACE_CONSTRAINT_CAUSAL_CLOSURE_V1",
        {"binding_roots": list(roots)},
    )


@dataclass(frozen=True)
class ConstraintBindingV1:
    trace_root: str
    span_id: str
    span_root: str
    provenance_roots: tuple[str, ...]
    restriction_roots: tuple[str, ...]
    authority_roots: tuple[str, ...]
    causal_binding_roots: tuple[str, ...]
    captured_control_state_root: str
    causal_closure_root: str

    def __post_init__(self) -> None:
        _require_hash("trace_root", self.trace_root)
        _require_id("span_id", self.span_id)
        _require_hash("span_root", self.span_root)
        _require_unique_hashes("provenance_root", self.provenance_roots)
        _require_unique_hashes("restriction_root", self.restriction_roots)
        _require_unique_hashes("authority_root", self.authority_roots)
        _require_unique_hashes("causal_binding_root", self.causal_binding_roots)
        _require_hash("captured_control_state_root", self.captured_control_state_root)
        _require_hash("causal_closure_root", self.causal_closure_root)

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_TRACE_CONSTRAINT_BINDING_V1", asdict(self))


@dataclass(frozen=True)
class TraceConstraintCertificateV1:
    certificate_kind: str
    certificate_semantics: str
    bundle_root: str
    bindings: tuple[ConstraintBindingV1, ...]
    binding_manifest_root: str

    def __post_init__(self) -> None:
        if self.certificate_kind != CONSTRAINT_CERTIFICATE_KIND:
            raise TraceConstraintError("CONSTRAINT_CERTIFICATE_KIND_MISMATCH")
        if self.certificate_semantics != CONSTRAINT_CERTIFICATE_SEMANTICS:
            raise TraceConstraintError("CONSTRAINT_CERTIFICATE_SEMANTICS_MISMATCH")
        _require_hash("bundle_root", self.bundle_root)
        _require_hash("binding_manifest_root", self.binding_manifest_root)
        span_ids = [binding.span_id for binding in self.bindings]
        if len(span_ids) != len(set(span_ids)):
            raise TraceConstraintError("CONSTRAINT_BINDING_SPAN_ID_DUPLICATE")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_TRACE_CONSTRAINT_CERTIFICATE_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["certificate_root"] = self.root
        return payload

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )


@dataclass(frozen=True)
class TraceConstraintVerificationV1:
    valid: bool
    errors: tuple[str, ...]
    binding_count: int
    constraint_edge_count: int
    certificate_root: str


def _binding_manifest_root(bindings: Sequence[ConstraintBindingV1]) -> str:
    return canonical_hash(
        "AEGIS_TRACE_CONSTRAINT_BINDING_MANIFEST_V1",
        {"binding_roots": sorted(binding.root for binding in bindings)},
    )


def make_constraint_certificate(
    bundle: ProofTraceBundleV1,
    bindings: Iterable[ConstraintBindingV1],
) -> TraceConstraintCertificateV1:
    resolved = tuple(bindings)
    return TraceConstraintCertificateV1(
        certificate_kind=CONSTRAINT_CERTIFICATE_KIND,
        certificate_semantics=CONSTRAINT_CERTIFICATE_SEMANTICS,
        bundle_root=bundle.root,
        bindings=resolved,
        binding_manifest_root=_binding_manifest_root(resolved),
    )


def verify_constraint_certificate(
    bundle: ProofTraceBundleV1,
    certificate: TraceConstraintCertificateV1,
) -> TraceConstraintVerificationV1:
    errors: list[str] = []
    trace_verification = verify_trace_bundle(bundle)
    if not trace_verification.valid:
        errors.extend(f"TRACE_BUNDLE_INVALID:{code}" for code in trace_verification.errors)

    if certificate.bundle_root != bundle.root:
        errors.append("CERTIFICATE_BUNDLE_ROOT_MISMATCH")

    expected_manifest = _binding_manifest_root(certificate.bindings)
    if certificate.binding_manifest_root != expected_manifest:
        errors.append("CONSTRAINT_BINDING_MANIFEST_MISMATCH")

    spans_by_id = {span.span_id: span for span in bundle.spans}
    bindings_by_span = {binding.span_id: binding for binding in certificate.bindings}

    for binding in certificate.bindings:
        if binding.trace_root != bundle.header.root:
            errors.append(f"BINDING_TRACE_ROOT_MISMATCH:{binding.span_id}")
        span = spans_by_id.get(binding.span_id)
        if span is None:
            errors.append(f"BINDING_SPAN_MISSING:{binding.span_id}")
            continue
        if binding.span_root != span.root:
            errors.append(f"BINDING_SPAN_ROOT_MISMATCH:{binding.span_id}")
        if binding.captured_control_state_root != span.control_state_before:
            errors.append(f"BINDING_STATE_ROOT_MISMATCH:{binding.span_id}")

    constraint_edge_count = 0
    for span in bundle.spans:
        if span.span_kind not in CONSTRAINT_CARRYING_KINDS:
            continue

        child = bindings_by_span.get(span.span_id)
        if child is None:
            errors.append(f"CONSTRAINT_SPAN_BINDING_MISSING:{span.span_id}")
            continue
        if not span.causal_parent_ids:
            errors.append(f"CONSTRAINT_SPAN_CAUSAL_PARENT_REQUIRED:{span.span_id}")
            continue

        parent_bindings: list[ConstraintBindingV1] = []
        missing_parent = False
        for parent_id in span.causal_parent_ids:
            parent = bindings_by_span.get(parent_id)
            if parent is None:
                errors.append(f"CAUSAL_PARENT_BINDING_MISSING:{span.span_id}:{parent_id}")
                missing_parent = True
            else:
                parent_bindings.append(parent)
        if missing_parent:
            continue

        expected_parent_roots = tuple(parent.root for parent in parent_bindings)
        if child.causal_binding_roots != expected_parent_roots:
            errors.append(f"CAUSAL_BINDING_ROOT_MISMATCH:{span.span_id}")
        expected_closure = constraint_causal_root(expected_parent_roots)
        if child.causal_closure_root != expected_closure:
            errors.append(f"CAUSAL_CLOSURE_ROOT_MISMATCH:{span.span_id}")

        child_provenance = set(child.provenance_roots)
        child_restrictions = set(child.restriction_roots)
        child_authority = set(child.authority_roots)
        for parent in parent_bindings:
            constraint_edge_count += 1
            if not set(parent.provenance_roots).issubset(child_provenance):
                errors.append(f"PROVENANCE_NOT_PRESERVED:{parent.span_id}:{span.span_id}")
            if not set(parent.restriction_roots).issubset(child_restrictions):
                errors.append(f"RESTRICTION_NOT_PRESERVED:{parent.span_id}:{span.span_id}")
            if not child_authority.issubset(set(parent.authority_roots)):
                errors.append(f"AUTHORITY_AMPLIFICATION:{parent.span_id}:{span.span_id}")

    return TraceConstraintVerificationV1(
        valid=not errors,
        errors=tuple(errors),
        binding_count=len(certificate.bindings),
        constraint_edge_count=constraint_edge_count,
        certificate_root=certificate.root,
    )


def constraint_certificate_from_json(payload: str) -> TraceConstraintCertificateV1:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise TraceConstraintError("CONSTRAINT_CERTIFICATE_JSON_INVALID") from exc
    if not isinstance(raw, dict):
        raise TraceConstraintError("CONSTRAINT_CERTIFICATE_JSON_ROOT_NOT_OBJECT")

    supplied_root = raw.pop("certificate_root", None)
    binding_items = raw.get("bindings")
    if not isinstance(binding_items, list):
        raise TraceConstraintError("CONSTRAINT_CERTIFICATE_JSON_STRUCTURE_INVALID")

    try:
        bindings = tuple(
            ConstraintBindingV1(
                **{
                    **item,
                    "provenance_roots": tuple(item.get("provenance_roots", ())),
                    "restriction_roots": tuple(item.get("restriction_roots", ())),
                    "authority_roots": tuple(item.get("authority_roots", ())),
                    "causal_binding_roots": tuple(item.get("causal_binding_roots", ())),
                }
            )
            for item in binding_items
        )
        certificate = TraceConstraintCertificateV1(
            certificate_kind=raw["certificate_kind"],
            certificate_semantics=raw["certificate_semantics"],
            bundle_root=raw["bundle_root"],
            bindings=bindings,
            binding_manifest_root=raw["binding_manifest_root"],
        )
    except (KeyError, TypeError, TraceConstraintError) as exc:
        if isinstance(exc, TraceConstraintError):
            raise
        raise TraceConstraintError("CONSTRAINT_CERTIFICATE_JSON_STRUCTURE_INVALID") from exc

    if supplied_root is not None and supplied_root != certificate.root:
        raise TraceConstraintError("CONSTRAINT_CERTIFICATE_ROOT_MISMATCH")
    return certificate
