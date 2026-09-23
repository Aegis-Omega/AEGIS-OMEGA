"""Exact rational preformalization gate for RH_SIGNED_FOUR_BLOCK_V1.

Two objects are kept separate:

1. ACTUAL-B interval information derived from exact prime terms plus the existing
   1/100 Archimedean error budget.
2. A rational COMPARISON-ENVELOPE Toeplitz matrix using the proven absolute
   cross bounds 51/100, 9/25, 13/50.

The comparison matrix is not asserted to be the actual B-matrix. Its LDL^T
pivots certify exactly what the current bound package can and cannot prove.

No RH conclusion is asserted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Iterable

OLD_DIAGONAL = Fraction(103, 100)
NARROW_DIAGONAL = Fraction(32, 25)
ARCH_RADIUS = Fraction(1, 100)

ADJACENT_UPPER = Fraction(51, 100)
NEXT_UPPER = Fraction(9, 25)
FAR_UPPER = Fraction(13, 50)

LOG2_LOWER = Fraction(693, 1000)
SQRT2_LOWER = Fraction(7, 5)
SQRT2_UPPER = Fraction(10, 7)


def comparison_matrix(diagonal: Fraction) -> tuple[tuple[Fraction, ...], ...]:
    d = -diagonal
    a, b, c = ADJACENT_UPPER, NEXT_UPPER, FAR_UPPER
    return (
        (d, a, b, c),
        (a, d, a, b),
        (b, a, d, a),
        (c, b, a, d),
    )


def ldlt_pivots(
    matrix: tuple[tuple[Fraction, ...], ...],
) -> tuple[Fraction, ...]:
    n = len(matrix)
    if any(len(row) != n for row in matrix):
        raise ValueError("matrix must be square")
    if any(matrix[i][j] != matrix[j][i] for i in range(n) for j in range(n)):
        raise ValueError("matrix must be symmetric")

    L = [[Fraction(int(i == j), 1) for j in range(n)] for i in range(n)]
    D = [Fraction(0, 1) for _ in range(n)]

    for i in range(n):
        D[i] = matrix[i][i] - sum(
            L[i][k] * L[i][k] * D[k] for k in range(i)
        )
        if D[i] == 0 and i != n - 1:
            raise ZeroDivisionError("zero LDL pivot")
        for j in range(i + 1, n):
            L[j][i] = (
                matrix[j][i]
                - sum(L[j][k] * L[i][k] * D[k] for k in range(i))
            ) / D[i]
    return tuple(D)


def inertia_from_pivots(
    pivots: Iterable[Fraction],
) -> tuple[int, int, int]:
    p = n = z = 0
    for x in pivots:
        if x > 0:
            p += 1
        elif x < 0:
            n += 1
        else:
            z += 1
    return p, n, z


@dataclass(frozen=True)
class SignedFourBlockPreflightV1:
    adjacent_lower: Fraction
    next_lower: Fraction
    far_lower: Fraction
    all_ones_rayleigh_lower: Fraction
    old_diagonal: Fraction
    old_certificate_gap: Fraction
    narrow_diagonal: Fraction
    narrow_minus_rayleigh_lower: Fraction
    old_certificate_sufficient: bool
    old_comparison_ldlt_pivots: tuple[Fraction, ...]
    old_comparison_inertia: tuple[int, int, int]
    narrow_comparison_ldlt_pivots: tuple[Fraction, ...]
    narrow_comparison_inertia: tuple[int, int, int]

    def to_dict(self) -> dict[str, object]:
        def encode(v):
            if isinstance(v, Fraction):
                return {"numerator": v.numerator, "denominator": v.denominator}
            if isinstance(v, tuple):
                return [encode(x) for x in v]
            return v

        return {k: encode(v) for k, v in asdict(self).items()}


def compute_preflight() -> SignedFourBlockPreflightV1:
    # 1/sqrt(2) > 7/10 follows from sqrt(2) < 10/7.
    adjacent_prime_lower = LOG2_LOWER * Fraction(7, 10)
    next_prime_lower = LOG2_LOWER / 2
    far_prime_lower = LOG2_LOWER * SQRT2_LOWER / 4

    # Existing |arch| <= 1/100 * E permits the most favorable signed
    # cancellation of exactly ARCH_RADIUS in a lower-bound preflight.
    adjacent_lower = adjacent_prime_lower - ARCH_RADIUS
    next_lower = next_prime_lower - ARCH_RADIUS
    far_lower = far_prime_lower - ARCH_RADIUS

    rayleigh = (
        Fraction(3, 2) * adjacent_lower
        + next_lower
        + Fraction(1, 2) * far_lower
    )
    old_gap = rayleigh - OLD_DIAGONAL

    old_pivots = ldlt_pivots(comparison_matrix(OLD_DIAGONAL))
    narrow_pivots = ldlt_pivots(comparison_matrix(NARROW_DIAGONAL))

    return SignedFourBlockPreflightV1(
        adjacent_lower=adjacent_lower,
        next_lower=next_lower,
        far_lower=far_lower,
        all_ones_rayleigh_lower=rayleigh,
        old_diagonal=OLD_DIAGONAL,
        old_certificate_gap=old_gap,
        narrow_diagonal=NARROW_DIAGONAL,
        narrow_minus_rayleigh_lower=NARROW_DIAGONAL - rayleigh,
        old_certificate_sufficient=rayleigh <= OLD_DIAGONAL,
        old_comparison_ldlt_pivots=old_pivots,
        old_comparison_inertia=inertia_from_pivots(old_pivots),
        narrow_comparison_ldlt_pivots=narrow_pivots,
        narrow_comparison_inertia=inertia_from_pivots(narrow_pivots),
    )


if __name__ == "__main__":
    import json
    print(json.dumps(compute_preflight().to_dict(), sort_keys=True, indent=2))
