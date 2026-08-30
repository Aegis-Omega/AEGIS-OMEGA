"""Fail-closed authority-preserving fiber refinement kernel.

This module verifies one deliberately narrow constitutional statement:
refining an epistemic/observational partition may improve resolution, but the
refinement cannot widen the previously admitted effect scope.

A VALID receipt is non-expansion evidence only. It never authorizes execution,
verifies an external effect, or admits a mutation. Those transitions remain the
responsibility of the independently validated authorization/effect chain.

The kernel is intentionally domain-agnostic. Deductive closures, spectral
cluster refinements, observer partitions, memory updates, and other epistemic
systems can instantiate the same contract without gaining authority merely by
being more informative.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from typing import Any


_CANONICALIZATION = "AEGIS_CANONICAL_JSON_V1"
_SPEC_DOMAIN = "AEGIS_FIBER_REFINEMENT_SPEC_V1"
_REJECTED_SPEC_DOMAIN = "AEGIS_FIBER_REFINEMENT_REJECTED_SPEC_V1"
_RECEIPT_DOMAIN = "AEGIS_FIBER_REFINEMENT_RECEIPT_V1"
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


class FiberRefinementVerdict(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"


@dataclass(frozen=True)
class FiberRefinementSpec:
    """Immutable proposal for refining observational fibers.

    ``refined_parent`` is an explicit child -> base-cell map. A valid proposal
    must cover every base cell and every child must map to exactly one known
    parent. Effect scopes are sets because ordering has no authority meaning.
    """

    base_cells: tuple[str, ...]
    refined_parent: tuple[tuple[str, str], ...]
    base_effect_scope: frozenset[str]
    refined_effect_scope: frozenset[str]
    context_digest: str


@dataclass(frozen=True)
class FiberRefinementReceipt:
    """Deterministic non-expansion evidence; never an authorization receipt."""

    spec_digest: str
    verdict: FiberRefinementVerdict
    reason_codes: tuple[str, ...]
    certifies_non_expansion: bool
    grants_execution_authority: bool
    grants_effect_authority: bool
    grants_atomic_admission_authority: bool
    requires_external_authorization: bool
    receipt_sha256: str


def _canonical_json(value: Any) -> bytes:
    """AEGIS-local canonical JSON, not an RFC 8785 claim."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _digest(domain: str, value: Any) -> str:
    envelope = {
        "canonicalization": _CANONICALIZATION,
        "domain": domain,
        "value": value,
    }
    return "sha256:" + hashlib.sha256(_canonical_json(envelope)).hexdigest()


def _normalized_spec_payload(spec: FiberRefinementSpec) -> dict[str, Any]:
    """Canonical semantic projection used only after strict runtime validation."""

    return {
        "schema_version": "1.0.0",
        "base_cells": sorted(spec.base_cells),
        "refined_parent": [list(item) for item in sorted(spec.refined_parent)],
        "base_effect_scope": sorted(spec.base_effect_scope),
        "refined_effect_scope": sorted(spec.refined_effect_scope),
        "context_digest": spec.context_digest,
    }


def _rejected_spec_payload(reasons: tuple[str, ...]) -> dict[str, Any]:
    """Safe rejection-class projection for malformed runtime inputs.

    Malformed containers are deliberately not iterated, sorted, repr'd, or
    serialized. The resulting digest identifies the rejection class, not the
    attacker-controlled malformed object. INVALID receipts carry no authority,
    so this avoids executing hostile iterator/repr behavior before validation.
    """

    return {
        "schema_version": "1.0.0",
        "validation_status": "INVALID_PRE_NORMALIZATION",
        "reason_codes": list(reasons),
    }


def _is_nonempty_builtin_string(value: object) -> bool:
    return type(value) is str and bool(value.strip())


def _validate(spec: FiberRefinementSpec) -> tuple[str, ...]:
    """Validate exact builtin runtime shapes before any unsafe normalization.

    ``type(...) is ...`` is intentional. Subclasses can override iteration,
    hashing, comparison, or string methods; an authority boundary must not run
    those behaviors merely to decide that an input is malformed.
    """

    reasons: list[str] = []

    base_cells = spec.base_cells
    if type(base_cells) is not tuple:
        reasons.append("EMPTY_OR_MALFORMED_BASE_PARTITION")
        safe_base_cells: tuple[str, ...] = ()
    else:
        if not base_cells:
            reasons.append("EMPTY_OR_MALFORMED_BASE_PARTITION")
        malformed_base = any(not _is_nonempty_builtin_string(cell) for cell in base_cells)
        if malformed_base:
            reasons.append("MALFORMED_BASE_CELL")
            safe_base_cells = tuple(
                cell for cell in base_cells if _is_nonempty_builtin_string(cell)
            )
        else:
            safe_base_cells = base_cells
            if len(base_cells) != len(set(base_cells)):
                reasons.append("DUPLICATE_BASE_CELL")

    refined_parent = spec.refined_parent
    if type(refined_parent) is not tuple:
        reasons.append("MALFORMED_REFINEMENT_MAP")
        refined_pairs: tuple[tuple[str, str], ...] = ()
    else:
        refined_pairs = refined_parent

    malformed_pair = False
    child_ids: list[str] = []
    parent_ids: list[str] = []
    for pair in refined_pairs:
        if (
            type(pair) is not tuple
            or len(pair) != 2
            or not _is_nonempty_builtin_string(pair[0])
            or not _is_nonempty_builtin_string(pair[1])
        ):
            malformed_pair = True
            continue
        child_ids.append(pair[0])
        parent_ids.append(pair[1])

    if malformed_pair:
        reasons.append("MALFORMED_REFINEMENT_MAP")

    if len(child_ids) != len(set(child_ids)):
        reasons.append("DUPLICATE_REFINED_CELL")

    known_base = set(safe_base_cells)
    if any(parent not in known_base for parent in parent_ids):
        reasons.append("UNKNOWN_PARENT_CELL")

    covered_base = {parent for parent in parent_ids if parent in known_base}
    if known_base and covered_base != known_base:
        reasons.append("BASE_CELL_WITHOUT_REFINED_CHILD")

    base_scope = spec.base_effect_scope
    refined_scope = spec.refined_effect_scope
    scopes_are_exact_sets = type(base_scope) is frozenset and type(refined_scope) is frozenset
    if not scopes_are_exact_sets:
        reasons.append("MALFORMED_EFFECT_SCOPE")
    else:
        malformed_scope = any(
            not _is_nonempty_builtin_string(scope)
            for scope in base_scope
        ) or any(
            not _is_nonempty_builtin_string(scope)
            for scope in refined_scope
        )
        if malformed_scope:
            reasons.append("MALFORMED_EFFECT_SCOPE")
        elif not refined_scope.issubset(base_scope):
            reasons.append("EFFECT_SCOPE_EXPANSION")

    context_digest = spec.context_digest
    if type(context_digest) is not str or _SHA256_RE.fullmatch(context_digest) is None:
        reasons.append("MALFORMED_CONTEXT_DIGEST")

    # Preserve first-occurrence priority while collapsing repeated structural
    # failures to one stable reason code.
    return tuple(dict.fromkeys(reasons))


def evaluate_fiber_refinement(spec: FiberRefinementSpec) -> FiberRefinementReceipt:
    """Verify partition refinement and effect-scope non-expansion fail closed.

    Validation runs before canonicalization. Malformed runtime values therefore
    cannot trigger comparison, hashing, iteration, repr, or JSON serialization
    through the normalization path. The result is evidence about a proposed
    refinement only; even VALID cannot mint execution/effect/admission authority.
    """

    if type(spec) is not FiberRefinementSpec:
        reasons = ("MALFORMED_SPEC_TYPE",)
        spec_digest = _digest(_REJECTED_SPEC_DOMAIN, _rejected_spec_payload(reasons))
    else:
        reasons = _validate(spec)
        if reasons:
            spec_digest = _digest(_REJECTED_SPEC_DOMAIN, _rejected_spec_payload(reasons))
        else:
            spec_digest = _digest(_SPEC_DOMAIN, _normalized_spec_payload(spec))

    verdict = FiberRefinementVerdict.VALID if not reasons else FiberRefinementVerdict.INVALID
    certifies_non_expansion = verdict is FiberRefinementVerdict.VALID

    receipt_statement = {
        "schema_version": "1.0.0",
        "spec_digest": spec_digest,
        "verdict": verdict.value,
        "reason_codes": list(reasons),
        "certifies_non_expansion": certifies_non_expansion,
        "grants_execution_authority": False,
        "grants_effect_authority": False,
        "grants_atomic_admission_authority": False,
        "requires_external_authorization": True,
    }
    receipt_sha256 = _digest(_RECEIPT_DOMAIN, receipt_statement)

    return FiberRefinementReceipt(
        spec_digest=spec_digest,
        verdict=verdict,
        reason_codes=reasons,
        certifies_non_expansion=certifies_non_expansion,
        grants_execution_authority=False,
        grants_effect_authority=False,
        grants_atomic_admission_authority=False,
        requires_external_authorization=True,
        receipt_sha256=receipt_sha256,
    )


__all__ = [
    "FiberRefinementReceipt",
    "FiberRefinementSpec",
    "FiberRefinementVerdict",
    "evaluate_fiber_refinement",
]
