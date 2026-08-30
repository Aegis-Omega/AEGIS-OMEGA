"""Exact counterexample to the density-only finite-to-global positivity shortcut.

This module does **not** refute the standard continuity theorem saying that a
continuous quadratic form which is nonnegative on a dense subspace is
nonnegative on its closure. It refutes only the invalid shortcut that omits a
continuity / lower-semicontinuity / closed-form hypothesis.

Construction
------------
Let H = l2(N), let c00 be the finitely-supported sequences, and let

    u* = (2^-1, 2^-2, 2^-3, ...).

Then u* is in H but not in c00. On the algebraic direct sum

    D = c00 (+) span{u*}

define the quadratic form

    Q(v + alpha u*) = ||v||_2^2 - alpha^2.

The decomposition is unique because u* is not finitely supported. Every finite
coordinate stage V_N = span(e_1,...,e_N) lies in c00, hence Q|V_N = ||.||^2 >= 0.
Yet Q(u*) = -1. The truncations p_N of u* belong to V_N and converge to u* in
H because

    ||u* - p_N||_2^2 = sum_{k>N} 4^-k = 1 / (3 * 4^N).

Therefore density of positive finite stages alone cannot justify positivity of
Q at the closure point u*. The missing load-bearing premise is continuity (or
an appropriate closed/lower-semicontinuous form theorem).
"""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any

REFUTATION_ID = "FTG-DENSITY-ALONE-COUNTEREXAMPLE-V1"


def _require_stage(n: int) -> None:
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("stage n must be an integer >= 1")


def truncation_q(n: int) -> Fraction:
    """Exact Q(p_N) for the N-coordinate truncation of u*."""
    _require_stage(n)
    return Fraction(1, 3) * (1 - Fraction(1, 4**n))


def tail_norm_sq(n: int) -> Fraction:
    """Exact squared l2 distance ||u* - p_N||^2."""
    _require_stage(n)
    return Fraction(1, 3 * (4**n))


def limit_witness_q() -> Fraction:
    """Exact value Q(u*) showing failure of density-only promotion."""
    return Fraction(-1, 1)


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _receipt_payload() -> dict[str, Any]:
    stages = (1, 2, 4, 8, 16)
    return {
        "schema_version": "1.0.0",
        "refutation_id": REFUTATION_ID,
        "classification": "REFUTED_SHORTCUT",
        "authority": "EXACT_RATIONAL_REGRESSION_NOT_PROOF_ASSISTANT",
        "refutes": "DENSITY_ALONE_FINITE_STAGE_POSITIVITY_IMPLIES_CLOSURE_POSITIVITY",
        "does_not_refute": [
            "CONTINUOUS_Q_EXTENDS_POSITIVITY_FROM_DENSE_SUBSPACE",
            "LOWER_SEMICONTINUOUS_CLOSED_FORM_EXTENDS_POSITIVITY_UNDER_ITS_HYPOTHESES",
        ],
        "space": "H = l2(N)",
        "dense_union": "union_N span(e_1,...,e_N) = c00, dense in H",
        "limit_vector": "u*_k = 2^-k",
        "domain": "D = c00 (+) span{u*}",
        "quadratic_form": "Q(v + alpha*u*) = ||v||_2^2 - alpha^2",
        "finite_stage_property": "for x in V_N, Q(x)=||x||_2^2 >= 0",
        "limit_witness_q": _fraction_text(limit_witness_q()),
        "exact_stage_checks": [
            {
                "N": n,
                "Q_pN": _fraction_text(truncation_q(n)),
                "tail_norm_sq": _fraction_text(tail_norm_sq(n)),
            }
            for n in stages
        ],
        "load_bearing_missing_premise": "CONTINUITY_OR_APPROPRIATE_CLOSED_FORM_LIMIT_THEOREM",
        "rh_authority": "NONE",
        "global_weil_positivity_proven": False,
        "rh_proven": False,
    }


def build_refutation_receipt() -> dict[str, Any]:
    """Return a deterministic content-addressed refutation receipt."""
    payload = _receipt_payload()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    receipt_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {**payload, "receipt_sha256": receipt_sha256}


if __name__ == "__main__":
    print(json.dumps(build_refutation_receipt(), indent=2, sort_keys=True))
