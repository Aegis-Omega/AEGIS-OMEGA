# E1' feasibility at w = 1/32: which prime powers each dyadic gap sees, and the Perron margin
# of norm ceilings c_k = log2 * 2^{-k/2} + a for 5-7 blocks against the proved diagonal.
# For a nonnegative symmetric C, min over positive weights of the max weighted row sum equals
# rho(C) (Collatz-Wielandt), so no weighted-row certificate with these ceilings beats D - rho(C).
import math
from fractions import Fraction
import numpy as np

W = 1 / 32
D = 103 / 100 + math.exp(-W) * math.log(2)            # WeilDiagonalLogGainV1, class (a)

def is_prime_power(n):
    for p in range(2, n + 1):
        if n % p == 0:
            while n % p == 0:
                n //= p
            return n == 1
    return False

print("gap k: prime powers q with |log q - k log 2| <= 1/32")
for k in range(1, 8):
    lo, hi = 2 ** k * math.exp(-W), 2 ** k * math.exp(W)
    qs = [q for q in range(math.ceil(lo), math.floor(hi) + 1) if is_prime_power(q)]
    print(f"  k={k}  window [{lo:.3f}, {hi:.3f}]  {qs}")

def rho(n, a):
    C = np.array([[0.0 if i == j else math.log(2) * 2 ** (-abs(i - j) / 2) + a
                   for j in range(n)] for i in range(n)])
    return max(np.linalg.eigvalsh(C))

print(f"diagonal D = {D:.5f}")
for n in (5, 6, 7):
    for a in (Fraction(1, 100), Fraction(0)):
        r = rho(n, float(a))
        print(f"  blocks={n}  arch a={str(a):>5}  rho={r:.4f}  D - rho = {D - r:+.4f}")
