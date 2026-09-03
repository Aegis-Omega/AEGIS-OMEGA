#!/usr/bin/env python3
"""Evaluable form of the capability resolution law.

The registry states the law as prose. Prose is checked by spelling, which is
why `scripts/test_agent_capability_lineage.py` could only assert that certain
words appear in it. This module makes the law a function, so a scenario can be
run against it and a missing term becomes a failing evaluation rather than a
missing substring.

The term list is read from the registry, not hard-coded here: dropping a term
from the registry changes what this function requires, and the accompanying
test asserts which terms must be present.
"""
from __future__ import annotations

import json
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / "security" / "agent-capability-lineage.json"


def law_terms(registry: dict | None = None) -> list[str]:
    """The conjuncts the law is made of, in registry order."""
    if registry is None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return list(registry["resolution_law_terms"])


def resolve(scenario: dict[str, bool], registry: dict | None = None) -> tuple[bool, list[str]]:
    """Evaluate one requested mutation against the law.

    Returns ``(permitted, unmet_terms)``. A term the scenario does not mention
    is treated as unmet: silence is not permission, so an incompletely
    described scenario can never resolve to permitted.
    """
    unmet = [term for term in law_terms(registry) if not scenario.get(term, False)]
    return (not unmet, unmet)
