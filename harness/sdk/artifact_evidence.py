#!/usr/bin/env python3
"""Provider-neutral artifact evidence classification for repository cognition.

Collectors may be Git, forge, filesystem, archive, or other adapters. This module
only classifies already-observed evidence. It never performs network access,
mutates repository state, grants execution authority, or converts a bounded miss
into a global absence claim.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

IMPLEMENTATION_EVIDENCE_FOUND = "IMPLEMENTATION_EVIDENCE_FOUND"
NAMED_REFERENCE_FOUND = "NAMED_REFERENCE_FOUND"
INCOMPLETE = "INCOMPLETE"
NO_MATCHES_IN_COMPLETE_REPO_SCAN = "NO_MATCHES_IN_COMPLETE_REPO_SCAN"

ABSENCE_CLAIM_BOUNDARY = (
    "no_match_in_declared_repo_scan_only; external_or_unobserved_absence_not_established"
)


def _normalize_scopes(values: Iterable[str]) -> list[str]:
    return sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})


def _normalize_references(values: Iterable[str]) -> list[str]:
    return sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})


def _canonical_evidence(item: Mapping[str, Any] | str) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, Mapping):
        return json.dumps(
            dict(item),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    raise TypeError("implementation evidence must be a string or mapping")


def classify_artifact_evidence(
    *,
    implementation_evidence: Iterable[Mapping[str, Any] | str] = (),
    named_references: Iterable[str] = (),
    required_scopes: Iterable[str] = (),
    completed_scopes: Iterable[str] = (),
) -> dict[str, Any]:
    """Classify bounded artifact evidence without promoting authority or global absence."""
    implementations = sorted({_canonical_evidence(item) for item in implementation_evidence})
    references = _normalize_references(named_references)
    required = _normalize_scopes(required_scopes)
    completed = _normalize_scopes(completed_scopes)
    incomplete = sorted(set(required) - set(completed))

    if implementations:
        status = IMPLEMENTATION_EVIDENCE_FOUND
    elif references:
        status = NAMED_REFERENCE_FOUND
    elif not required or incomplete:
        status = INCOMPLETE
    else:
        status = NO_MATCHES_IN_COMPLETE_REPO_SCAN

    return {
        "status": status,
        "implementation_evidence_count": len(implementations),
        "named_reference_count": len(references),
        "required_scopes": required,
        "completed_scopes": completed,
        "incomplete_scopes": incomplete,
        "global_absence_established": False,
        "claim_effect": "EVIDENCE_ONLY",
        "authority_effect": "NONE",
        "absence_claim_boundary": ABSENCE_CLAIM_BOUNDARY,
    }


__all__ = [
    "ABSENCE_CLAIM_BOUNDARY",
    "IMPLEMENTATION_EVIDENCE_FOUND",
    "INCOMPLETE",
    "NAMED_REFERENCE_FOUND",
    "NO_MATCHES_IN_COMPLETE_REPO_SCAN",
    "classify_artifact_evidence",
]
