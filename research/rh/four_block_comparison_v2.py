#!/usr/bin/env python3
"""Exact 4x4 SOS verification; NOT Lean execution or actual Weil positivity.

Only the Python standard library is required. No floats, sampled eigenvalues,
assert statements, network access, or repository mutations are used.
"""
from __future__ import annotations

import json
from fractions import Fraction as Q
from typing import Sequence

Matrix = tuple[tuple[Q, ...], ...]
Term = tuple[Q, tuple[Q, ...]]
BOUND = Q(158, 125)
DIAGONAL_TARGET = Q(32, 25)


def comparison_matrix(a: Q = Q(51, 100), b: Q = Q(9, 25), r: Q = Q(13, 50)) -> Matrix:
    if not all(isinstance(v, Q) for v in (a, b, r)):
        raise TypeError("Comparison constants must be exact fractions")
    zero = Q(0)
    return ((zero, a, b, r), (a, zero, a, b),
            (b, a, zero, a), (r, b, a, zero))


def sos_terms() -> tuple[Term, ...]:
    rows = (
        (Q(17, 6500), (15, -13, 0, 0)),
        (Q(17, 6500), (0, 0, 13, -15)),
        (Q(3, 1625), (15, 0, -13, 0)),
        (Q(3, 1625), (0, 13, 0, -15)),
        (Q(51, 100), (0, 1, -1, 0)),
        (Q(13, 50), (1, 0, 0, -1)),
        (Q(1, 6500), (1, 0, 0, 0)),
        (Q(1, 6500), (0, 0, 0, 1)),
    )
    return tuple((c, tuple(Q(v) for v in row)) for c, row in rows)


def validate_sos(matrix: Matrix, bound: Q, terms: Sequence[Term]) -> bool:
    """Prove bound*I - matrix is the supplied sum of positive rank-one forms.

    Equality of all 16 rational matrix entries checks the polynomial identity
    for EVERY real vector, not only finitely many test vectors.
    """
    if not isinstance(bound, Q):
        raise TypeError("The bound must be an exact fraction")
    if len(matrix) != 4 or any(len(row) != 4 for row in matrix):
        raise ValueError("Expected a 4x4 matrix")
    if any(not isinstance(v, Q) for row in matrix for v in row):
        raise TypeError("Matrix entries must be exact fractions")
    if any(matrix[i][j] != matrix[j][i] for i in range(4) for j in range(4)):
        raise ValueError("Expected a symmetric comparison matrix")
    accumulated = [[Q(0) for _ in range(4)] for _ in range(4)]
    for coefficient, row in terms:
        if not isinstance(coefficient, Q) or any(not isinstance(v, Q) for v in row):
            raise TypeError("SOS data must use exact fractions")
        if len(row) != 4 or coefficient < 0:
            raise ValueError("SOS terms require four entries and a nonnegative coefficient")
        for i in range(4):
            for j in range(4):
                accumulated[i][j] += coefficient * row[i] * row[j]
    for i in range(4):
        for j in range(4):
            target = (bound if i == j else Q(0)) - matrix[i][j]
            if accumulated[i][j] != target:
                raise ValueError(f"Coefficient identity mismatch at ({i},{j})")
    return True


def quadratic(matrix: Matrix, x: Sequence[Q]) -> Q:
    if len(x) != 4 or any(not isinstance(v, Q) for v in x):
        raise ValueError("Expected four exact rational coefficients")
    return sum((x[i] * matrix[i][j] * x[j]
                for i in range(4) for j in range(4)), Q(0))


def receipt() -> dict[str, object]:
    matrix = comparison_matrix()
    validate_sos(matrix, BOUND, sos_terms())
    x = tuple(map(Q, (4, 5, 5, 4)))
    energy = sum((v*v for v in x), Q(0))
    counterexample = Q(9, 8)*energy - quadratic(comparison_matrix(r=Q(0)), x)
    if counterexample != Q(-57, 20):
        raise ValueError("The historical-scope regression witness changed")
    return {
        "schema": "AEGIS_FOUR_BLOCK_EXACT_COMPARISON_V2",
        "scope": "4X4_RATIONAL_COMPARISON_ONLY",
        "matrix_identity": "PASS_ALL_16_COEFFICIENTS",
        "sos_coefficients_nonnegative": True,
        "comparison_matrix": [[str(v) for v in row] for row in matrix],
        "comparison_bound": str(BOUND),
        "conditional_diagonal_target": str(DIAGONAL_TARGET),
        "conditional_coercive_margin": str(DIAGONAL_TARGET - BOUND),
        "old_9_over_8_counterexample": {"vector": [4, 5, 5, 4], "value": str(counterexample)},
        "lean_kernel": "NOT_RUN",
        "lean_axiom_audit": "NOT_RUN",
        "actual_diagonal_32_over_25": "NOT_ESTABLISHED",
        "actual_farthest_cross_13_over_50": "NOT_ESTABLISHED",
        "actual_four_packet_analytic_premises": "NOT_DISCHARGED",
        "global_weil_sign": "NOT_PROVEN",
        "riemann_hypothesis": "NOT_PROVEN",
        "authority_effect": "NONE",
    }


if __name__ == "__main__":
    print(json.dumps(receipt(), indent=2, sort_keys=True))
