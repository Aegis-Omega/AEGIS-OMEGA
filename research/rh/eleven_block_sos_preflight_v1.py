#!/usr/bin/env python3
"""Exact-rational 11x11 Hermitian/SOS preflight."""
from collections import defaultdict
from fractions import Fraction

N=11
D=Fraction(5671,3200)
weights={d:Fraction(1,100) for d in range(1,9)}
weights[9]=Fraction(57,100)
weights[10]=Fraction(837,3700)

row=[]
for i in range(N):
    row.append(sum(weights[abs(i-j)] for j in range(N) if i!=j))

assert row[0] == row[10] == Fraction(1621,1850)
assert row[1] == row[9] == Fraction(33,50)
assert all(row[i] == Fraction(1,10) for i in range(2,9))

MARGIN=D-max(row)
assert MARGIN == Fraction(106083,118400)

residual=[D-r-MARGIN for r in row]
assert residual[0] == residual[10] == 0
assert residual[1] == residual[9] == Fraction(8,37)
assert all(residual[i] == Fraction(718,925) for i in range(2,9))

lhs=defaultdict(Fraction)
rhs=defaultdict(Fraction)

# LHS: D E - C - margin E.
for i in range(N):
    lhs[(i,i)] += D-MARGIN
for i in range(N):
    for j in range(i+1,N):
        lhs[(i,j)] -= 2*weights[j-i]

# Weighted graph Laplacian.
for i in range(N):
    for j in range(i+1,N):
        w=weights[j-i]
        rhs[(i,i)] += w
        rhs[(j,j)] += w
        rhs[(i,j)] -= 2*w

# Residual diagonal squares.
for i,r in enumerate(residual):
    rhs[(i,i)] += r

assert dict(lhs)==dict(rhs)

print("ELEVEN_BLOCK_RATIONAL_SOS=PASS")
print(f"DIAGONAL={D}")
print("GAPS_1_8=1/100")
print("GAP_9=57/100")
print("GAP_10=837/3700")
print("ROW_BUDGETS="+",".join(str(x) for x in row))
print(f"CANDIDATE_MARGIN={MARGIN}")
print("RESIDUALS="+",".join(str(x) for x in residual))
print("ACTUAL_ELEVEN_PACKET_BINDING=NOT_PROVEN")
print("RH=NOT_PROVEN")
print("AUTHORITY_EFFECT=NONE")
