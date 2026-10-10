#!/usr/bin/env python3
"""Exact-rational 10x10 Hermitian/SOS preflight.

This script checks coefficient equality over fractions only.
It does not evaluate floating-point eigenvalues and does not claim an
actual AEGIS ten-packet theorem.
"""
from collections import defaultdict
from fractions import Fraction

D = Fraction(5671, 3200)
MARGIN = Fraction(3591, 3200)
SMALL = Fraction(1, 100)
GAP9 = Fraction(57, 100)
EXTRA = GAP9 - SMALL

assert EXTRA == Fraction(14, 25)
assert D - MARGIN == Fraction(13, 20)

# Polynomials use monomial keys (i,j), i <= j.
lhs = defaultdict(Fraction)
rhs = defaultdict(Fraction)

# LHS = D*E10 - C10 - MARGIN*E10.
for i in range(10):
    lhs[(i, i)] += D - MARGIN

for i in range(10):
    for j in range(i + 1, 10):
        cij = GAP9 if (i, j) == (0, 9) else SMALL
        lhs[(i, j)] -= 2 * cij

# RHS = 1/100 * sum_{i<j}(xi-xj)^2
for i in range(10):
    for j in range(i + 1, 10):
        rhs[(i, i)] += SMALL
        rhs[(j, j)] += SMALL
        rhs[(i, j)] -= 2 * SMALL

# + 14/25 * ((x0-x9)^2 + sum_{i=1}^8 xi^2)
rhs[(0, 0)] += EXTRA
rhs[(9, 9)] += EXTRA
rhs[(0, 9)] -= 2 * EXTRA
for i in range(1, 9):
    rhs[(i, i)] += EXTRA

assert dict(lhs) == dict(rhs)

row_budgets = []
for i in range(10):
    budget = Fraction(0)
    for j in range(10):
        if i == j:
            continue
        pair = (min(i, j), max(i, j))
        budget += GAP9 if pair == (0, 9) else SMALL
    row_budgets.append(budget)

assert row_budgets[0] == Fraction(13, 20)
assert row_budgets[9] == Fraction(13, 20)
assert all(row_budgets[i] == Fraction(9, 100) for i in range(1, 9))
assert MARGIN > 0

print("TEN_BLOCK_RATIONAL_SOS=PASS")
print(f"DIAGONAL={D}")
print(f"SMALL_GAP_BOUND={SMALL}")
print(f"GAP9_BOUND={GAP9}")
print(f"EXTRA_GAP9_WEIGHT={EXTRA}")
print(f"CANDIDATE_MARGIN={MARGIN}")
print("ROW_BUDGETS=" + ",".join(str(x) for x in row_budgets))
print("ACTUAL_TEN_PACKET_BINDING=NOT_PROVEN")
print("RH=NOT_PROVEN")
print("AUTHORITY_EFFECT=NONE")
