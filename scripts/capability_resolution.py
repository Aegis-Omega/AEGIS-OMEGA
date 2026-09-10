#!/usr/bin/env python3
"""Provider-neutral capability admission evaluator.

A capability is effective only when every declared resolution term is true.
Missing terms fail closed. This module evaluates authority; it grants none.
"""
from __future__ import annotations


def law_terms(registry: dict) -> list[str]:
    """Return the ordered conjuncts declared by the canonical policy."""
    terms = registry.get("resolution_law_terms", [])
    if not isinstance(terms, list) or not all(isinstance(term, str) and term for term in terms):
        raise ValueError("resolution_law_terms must be a non-empty-string list")
    if len(terms) != len(set(terms)):
        raise ValueError("resolution_law_terms must not contain duplicates")
    return list(terms)


def resolve(scenario: dict[str, bool], registry: dict) -> tuple[bool, list[str]]:
    """Return (permitted, unmet_terms) under strict fail-closed conjunction."""
    terms = law_terms(registry)
    unmet = [term for term in terms if scenario.get(term) is not True]
    return (not unmet, unmet)
