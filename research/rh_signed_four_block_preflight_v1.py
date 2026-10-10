#!/usr/bin/env python3
"""
AEGIS Ω — RH_SIGNED_FOUR_BLOCK_V1 preformalization gate.

NUMERIC / RATIONAL PREFLIGHT ONLY.
This file does not prove RH and is not a Lean kernel artifact.

The four translated packets have a Hermitian Toeplitz B-matrix determined by
the diagonal and three positive logarithmic gaps.  The prime centers are

  a = log(2)/sqrt(2)
  b = log(2)/2
  r = log(2)*sqrt(2)/4

and the separated Archimedean residual at each nonzero gap has certified norm
at most 1/100 * E in the existing AEGIS lane.

The exact rational checks below deliberately use only repository-proved
elementary enclosures:
  693/1000 < log 2 < 7/10
  7/5 < sqrt 2 < 10/7
"""

from fractions import Fraction
from math import log, sqrt

Q = Fraction

# Repository-certified rational enclosures.
LOG2_LO = Q(693, 1000)
LOG2_HI = Q(7, 10)
SQRT2_LO = Q(7, 5)
SQRT2_HI = Q(10, 7)
ARCH = Q(1, 100)

# Rigorous prime-center coordinate bounds.
a_lo = LOG2_LO / SQRT2_HI
a_hi = LOG2_HI / SQRT2_LO
b_lo = LOG2_LO / 2
b_hi = LOG2_HI / 2
r_lo = LOG2_LO * SQRT2_LO / 4
r_hi = LOG2_HI * SQRT2_HI / 4

assert a_lo == Q(4851, 10000)
assert a_hi == Q(1, 2)
assert b_lo == Q(693, 2000)
assert b_hi == Q(7, 20)
assert r_lo == Q(4851, 20000)
assert r_hi == Q(1, 4)

# Reversal-even sector for the real prime center:
# [[r, a+b], [a+b, a]]
# Its largest eigenvalue is
# (a+r + sqrt((a-r)^2 + 4(a+b)^2))/2.
#
# Using a<=1/2,b<=7/20,r<=1/4 gives discriminant <=1181/400.
disc_hi = (a_hi - r_hi) ** 2 + 4 * (a_hi + b_hi) ** 2
assert disc_hi == Q(1181, 400)

# sqrt(1181/400) < 43/25 = 1.72, checked by squaring rationals.
sqrt_disc_hi = Q(43, 25)
assert disc_hi < sqrt_disc_hi ** 2

prime_lambda_hi = (a_hi + r_hi + sqrt_disc_hi) / 2
assert prime_lambda_hi == Q(247, 200)  # 1.235

# A Hermitian Toeplitz residual with each of the three gap entries bounded by
# ARCH has operator norm <= max absolute row sum <= 3*ARCH.
arch_op_hi = 3 * ARCH
robust_lambda_hi = prime_lambda_hi + arch_op_hi
assert robust_lambda_hi == Q(253, 200)  # 1.265

legacy_diag = Q(103, 100)
narrow_diag = Q(32, 25)

# Existing narrow diagonal clears the robust signed preflight.
assert narrow_diag > robust_lambda_hi
narrow_margin = narrow_diag - robust_lambda_hi
assert narrow_margin == Q(3, 200)

# The 103/100 certificate is insufficient even before an eigenvalue solver:
# all-ones Rayleigh quotient of the PRIME center is
# (3a + 2b + r)/2.
prime_ones_rayleigh_lo = (3 * a_lo + 2 * b_lo + r_lo) / 2
assert prime_ones_rayleigh_lo == Q(47817, 40000)  # 1.195425

# Even allowing the Arch residual to move this direction down by the full
# operator-norm envelope 3/100, the current 103/100 diagonal certificate does
# not force negativity.
legacy_rayleigh_lower_after_arch = (
    prime_ones_rayleigh_lo - arch_op_hi - legacy_diag
)
assert legacy_rayleigh_lower_after_arch == Q(5417, 40000)
assert legacy_rayleigh_lower_after_arch > 0

# Diagnostic floating-point values (not the authority-bearing checks).
a = log(2.0) / sqrt(2.0)
bb = log(2.0) / 2.0
rr = log(2.0) * sqrt(2.0) / 4.0
disc = (a - rr) ** 2 + 4.0 * (a + bb) ** 2
lambda_even_max = (a + rr + sqrt(disc)) / 2.0

print("RH_SIGNED_FOUR_BLOCK_V1")
print("prime_centers", {"a": a, "b": bb, "r": rr})
print("prime_even_lambda_max_numeric", lambda_even_max)
print("prime_lambda_upper_rational", str(prime_lambda_hi))
print("arch_operator_upper_rational", str(arch_op_hi))
print("robust_threshold_upper_rational", str(robust_lambda_hi))
print("legacy_diag", str(legacy_diag))
print("legacy_certificate_forces_negativity", False)
print("legacy_all_ones_positive_margin_lower", str(legacy_rayleigh_lower_after_arch))
print("narrow_diag", str(narrow_diag))
print("narrow_certificate_forces_negativity", True)
print("narrow_margin_lower", str(narrow_margin))
print("AUTHORITY_EFFECT=NONE")
