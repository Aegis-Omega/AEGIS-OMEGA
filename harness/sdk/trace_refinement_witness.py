"""AEGIS KG-005 proof-producing correspondence witness.

The Python producer is not the proof authority. It emits a deterministic,
hash-bound candidate witness from an already valid KG-004 constraint
certificate. A separate fixed checker (formalized in Coq) validates the finite
provenance/restriction/authority relations.

This module therefore narrows the implementation/model gap without claiming
Python interpreter equivalence with Coq.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

from harness.sdk.proof_trace import ProofTraceBundleV1
from harness.sdk.sovereign_execution import canonical_hash
from harness.sdk.trace_constraint_refinement import (
    CONSTRAINT_CARRYING_KINDS,
    TraceConstraintCertificateV1,
    verify_constraint_certificate,
)

WITNESS_KIND = "AEGIS_TRACE_REFINEMENT_WITNESS_V1"
WITNESS_SEMANTICS = "CANDIDATE_WITNESS_REQUIRES_INDEPENDENT_CHECKER"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")
COQ_MODULE_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")


class TraceRefinementWitnessError(ValueError):
    """Fail-closed KG-005 witness error with a stable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise TraceRefinementWitnessError(f"{name}:INVALID_SHA256")


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise TraceRefinementWitnessError(f"{name}:INVALID_ID")


def _require_unique_hashes(name: str, values: Sequence[str]) -> None:
    for value in values:
        _require_hash(name, value)
    if len(values) != len(set(values)):
        raise TraceRefinementWitnessError(f"{name}:DUPLICATE")


@dataclass(frozen=True)
class TraceRefinementEdgeV1:
    parent_span_id: str
    child_span_id: str
    parent_binding_root: str
    child_binding_root: str
    parent_provenance_roots: tuple[str, ...]
    child_provenance_roots: tuple[str, ...]
    parent_restriction_roots: tuple[str, ...]
    child_restriction_roots: tuple[str, ...]
    parent_authority_roots: tuple[str, ...]
    child_authority_roots: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_id("parent_span_id", self.parent_span_id)
        _require_id("child_span_id", self.child_span_id)
        _require_hash("parent_binding_root", self.parent_binding_root)
        _require_hash("child_binding_root", self.child_binding_root)
        _require_unique_hashes("parent_provenance_root", self.parent_provenance_roots)
        _require_unique_hashes("child_provenance_root", self.child_provenance_roots)
        _require_unique_hashes("parent_restriction_root", self.parent_restriction_roots)
        _require_unique_hashes("child_restriction_root", self.child_restriction_roots)
        _require_unique_hashes("parent_authority_root", self.parent_authority_roots)
        _require_unique_hashes("child_authority_root", self.child_authority_roots)

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_TRACE_REFINEMENT_EDGE_V1", asdict(self))


@dataclass(frozen=True)
class TraceRefinementWitnessV1:
    witness_kind: str
    witness_semantics: str
    bundle_root: str
    certificate_root: str
    edges: tuple[TraceRefinementEdgeV1, ...]
    edge_manifest_root: str

    def __post_init__(self) -> None:
        if self.witness_kind != WITNESS_KIND:
            raise TraceRefinementWitnessError("WITNESS_KIND_MISMATCH")
        if self.witness_semantics != WITNESS_SEMANTICS:
            raise TraceRefinementWitnessError("WITNESS_SEMANTICS_MISMATCH")
        _require_hash("bundle_root", self.bundle_root)
        _require_hash("certificate_root", self.certificate_root)
        _require_hash("edge_manifest_root", self.edge_manifest_root)
        keys = [(edge.parent_span_id, edge.child_span_id) for edge in self.edges]
        if len(keys) != len(set(keys)):
            raise TraceRefinementWitnessError("WITNESS_EDGE_DUPLICATE")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_TRACE_REFINEMENT_WITNESS_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["witness_root"] = self.root
        return payload

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )


@dataclass(frozen=True)
class TraceRefinementWitnessVerificationV1:
    valid: bool
    errors: tuple[str, ...]
    edge_count: int
    witness_root: str


def _edge_manifest_root(edges: Sequence[TraceRefinementEdgeV1]) -> str:
    return canonical_hash(
        "AEGIS_TRACE_REFINEMENT_EDGE_MANIFEST_V1",
        {"edge_roots": sorted(edge.root for edge in edges)},
    )


def _expected_edges(
    bundle: ProofTraceBundleV1,
    certificate: TraceConstraintCertificateV1,
) -> tuple[TraceRefinementEdgeV1, ...]:
    bindings = {binding.span_id: binding for binding in certificate.bindings}
    edges: list[TraceRefinementEdgeV1] = []
    for span in bundle.spans:
        if span.span_kind not in CONSTRAINT_CARRYING_KINDS:
            continue
        child = bindings.get(span.span_id)
        if child is None:
            continue
        for parent_id in span.causal_parent_ids:
            parent = bindings.get(parent_id)
            if parent is None:
                continue
            edges.append(
                TraceRefinementEdgeV1(
                    parent_span_id=parent_id,
                    child_span_id=span.span_id,
                    parent_binding_root=parent.root,
                    child_binding_root=child.root,
                    parent_provenance_roots=parent.provenance_roots,
                    child_provenance_roots=child.provenance_roots,
                    parent_restriction_roots=parent.restriction_roots,
                    child_restriction_roots=child.restriction_roots,
                    parent_authority_roots=parent.authority_roots,
                    child_authority_roots=child.authority_roots,
                )
            )
    return tuple(sorted(edges, key=lambda edge: (edge.child_span_id, edge.parent_span_id)))


def make_refinement_witness(
    bundle: ProofTraceBundleV1,
    certificate: TraceConstraintCertificateV1,
) -> TraceRefinementWitnessV1:
    verification = verify_constraint_certificate(bundle, certificate)
    if not verification.valid:
        raise TraceRefinementWitnessError("CONSTRAINT_CERTIFICATE_INVALID")
    edges = _expected_edges(bundle, certificate)
    return TraceRefinementWitnessV1(
        witness_kind=WITNESS_KIND,
        witness_semantics=WITNESS_SEMANTICS,
        bundle_root=bundle.root,
        certificate_root=certificate.root,
        edges=edges,
        edge_manifest_root=_edge_manifest_root(edges),
    )


def verify_refinement_witness(
    bundle: ProofTraceBundleV1,
    certificate: TraceConstraintCertificateV1,
    witness: TraceRefinementWitnessV1,
) -> TraceRefinementWitnessVerificationV1:
    errors: list[str] = []
    certificate_verification = verify_constraint_certificate(bundle, certificate)
    if not certificate_verification.valid:
        errors.extend(
            f"CONSTRAINT_CERTIFICATE_INVALID:{code}"
            for code in certificate_verification.errors
        )

    if witness.bundle_root != bundle.root:
        errors.append("WITNESS_BUNDLE_ROOT_MISMATCH")
    if witness.certificate_root != certificate.root:
        errors.append("WITNESS_CERTIFICATE_ROOT_MISMATCH")

    expected_edges = _expected_edges(bundle, certificate)
    expected_by_key = {
        (edge.parent_span_id, edge.child_span_id): edge for edge in expected_edges
    }
    actual_by_key = {
        (edge.parent_span_id, edge.child_span_id): edge for edge in witness.edges
    }

    for key in sorted(set(expected_by_key) | set(actual_by_key)):
        expected = expected_by_key.get(key)
        actual = actual_by_key.get(key)
        if expected is None or actual is None or expected != actual:
            errors.append(f"WITNESS_EDGE_MISMATCH:{key[0]}:{key[1]}")

    expected_manifest = _edge_manifest_root(witness.edges)
    if witness.edge_manifest_root != expected_manifest:
        errors.append("WITNESS_EDGE_MANIFEST_MISMATCH")

    return TraceRefinementWitnessVerificationV1(
        valid=not errors,
        errors=tuple(errors),
        edge_count=len(witness.edges),
        witness_root=witness.root,
    )


def _coq_string(value: str) -> str:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise TraceRefinementWitnessError("COQ_LITERAL_INVALID")
    return f'"{value}"'


def _coq_list(values: Iterable[str]) -> str:
    return "[" + "; ".join(_coq_string(value) for value in values) + "]"


def emit_coq_witness_facts(
    witness: TraceRefinementWitnessV1,
    *,
    module_name: str,
) -> str:
    """Emit data-only Coq facts consumed by the fixed TraceRefinementWitness checker."""
    if not isinstance(module_name, str) or not COQ_MODULE_RE.fullmatch(module_name):
        raise TraceRefinementWitnessError("COQ_MODULE_NAME_INVALID")

    edge_terms = []
    for edge in witness.edges:
        edge_terms.append(
            "{| edge_parent_id := %s; edge_child_id := %s; "
            "edge_parent_provenance := %s; edge_child_provenance := %s; "
            "edge_parent_restrictions := %s; edge_child_restrictions := %s; "
            "edge_parent_authority := %s; edge_child_authority := %s |}"
            % (
                _coq_string(edge.parent_span_id),
                _coq_string(edge.child_span_id),
                _coq_list(edge.parent_provenance_roots),
                _coq_list(edge.child_provenance_roots),
                _coq_list(edge.parent_restriction_roots),
                _coq_list(edge.child_restriction_roots),
                _coq_list(edge.parent_authority_roots),
                _coq_list(edge.child_authority_roots),
            )
        )

    edges = "[\n  " + ";\n  ".join(edge_terms) + "\n]" if edge_terms else "[]"
    return "\n".join(
        [
            "From Coq Require Import List String.",
            "Require Import TraceRefinementWitness.",
            "Import ListNotations.",
            "Open Scope string_scope.",
            f"Module {module_name}.",
            f"Definition witness_root : string := {_coq_string(witness.root)}.",
            f"Definition edges : list ConcreteEdge := {edges}.",
            "Example checker_accepts : all_edges_okb edges = true.",
            "Proof. vm_compute; reflexivity. Qed.",
            "Example checker_sound : Forall edge_refines_cct edges.",
            "Proof. apply all_edges_refine_cct. exact checker_accepts. Qed.",
            f"End {module_name}.",
            "",
        ]
    )
