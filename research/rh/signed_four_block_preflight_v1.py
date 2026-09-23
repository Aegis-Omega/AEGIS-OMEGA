"""Exact rational preformalization gate for RH_SIGNED_FOUR_BLOCK_V1.

This script does not evaluate the full B-matrix numerically and does not prove
RH.  It uses only already-proved source bounds to test whether retaining the
signed Toeplitz structure can possibly rescue the old 103/100 diagonal
certificate.

For the dyadic four-block family, write normalized real cross entries as
b1, b2, b3 for gaps log 2, 2 log 2, 3 log 2.  Existing source theorems give
exact prime terms

  p1 = log(2)/sqrt(2)
  p2 = log(2)/2
  p3 = log(2)*sqrt(2)/4

and Archimedean error norm at most 1/100 on each gap.

Using conservative rational inequalities already present/provable in the
repository:

  log(2) > 693/1000,
  sqrt(2) < 10/7,
  sqrt(2) > 7/5,

we obtain lower bounds

  b1 > 4751/10000,
  b2 >  673/2000,
  b3 > 4651/20000.

The all-ones Rayleigh quotient of the zero-diagonal 4x4 Toeplitz cross matrix is

  (6*b1 + 4*b2 + 2*b3)/4 = 3/2*b1 + b2 + 1/2*b3.

Its rigorous rational lower bound is 46617/40000 = 1.165425, exceeding
103/100 by 5417/40000.

Therefore the current 103/100 diagonal lower certificate is insufficient even
after preserving the signed Toeplitz structure and allowing every Archimedean
cross correction to take its most favorable sign within the existing 1/100
norm budget.

This is a certificate-of-insufficiency for that proof budget, not a statement
about the exact unknown diagonal value of the concrete matrix.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction

OLD_DIAGONAL = Fraction(103, 100)
NARROW_DIAGONAL = Fraction(32, 25)
ARCH_RADIUS = Fraction(1, 100)

LOG2_LOWER = Fraction(693, 1000)
SQRT2_LOWER = Fraction(7, 5)
SQRT2_UPPER = Fraction(10, 7)


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

    def to_dict(self) -> dict[str, object]:
        def q(x: Fraction) -> dict[str, int]:
            return {"numerator": x.numerator, "denominator": x.denominator}
        return {
            k: q(v) if isinstance(v, Fraction) else v
            for k, v in asdict(self).items()
        }


def compute_preflight() -> SignedFourBlockPreflightV1:
    # 1/sqrt(2) > 7/10 follows from sqrt(2) < 10/7.
    adjacent_prime_lower = LOG2_LOWER * Fraction(7, 10)
    next_prime_lower = LOG2_LOWER / 2
    far_prime_lower = LOG2_LOWER * SQRT2_LOWER / 4

    adjacent_lower = adjacent_prime_lower - ARCH_RADIUS
    next_lower = next_prime_lower - ARCH_RADIUS
    far_lower = far_prime_lower - ARCH_RADIUS

    rayleigh = (
        Fraction(3, 2) * adjacent_lower
        + next_lower
        + Fraction(1, 2) * far_lower
    )
    old_gap = rayleigh - OLD_DIAGONAL
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
    )


if __name__ == "__main__":
    import json
    print(json.dumps(compute_preflight().to_dict(), sort_keys=True, indent=2))
