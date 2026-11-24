# Euler product + functional equation is not enough: the Ramanujan shift probe (V1)

Status: numerical diagnostic, no proof authority. Script: `ramanujan_shift_weil_probe.py`.

## Object

F_d(s) = zeta(s+d) zeta(s-d), 0 < d < 1/2.

- Euler product: Lambda_F(p^k) = (p^{kd} + p^{-kd}) log p, supported on prime powers
  (so it passes `EulerProductSupport.multiplicative_iff_support`).
- Symmetric functional equation: Lambda(s+d)Lambda(s-d) is invariant under s -> 1-s.
- Zeros at 1/2 +/- d + i gamma_n: off the critical line for every d > 0.
- Only violated Selberg-class axiom: Ramanujan, Lambda_F(p) > 2 log p.

So prime-power support (the filter that rejects the D = -20 Epstein zeta) is necessary
but not sufficient. A size bound on Lambda_F is also needed, and even with it the
statement is GRH, open.

## Result on the repo's moment-zero basis (L = 3.5, basis_dim = 24, 2000 zeta zeros)

| d | lambda_min |
|---|---|
| 0 (zeta^2) | ~1e-15 (zero side and formula side both) |
| 0.01 | -4.79e-4 |
| 0.05 | -1.65e-2 |
| 0.10 | -7.39e-2 |
| 0.20 | -0.310 |
| 0.49 | -2.18 |

Checks: at d = 0 the explicit-formula side (Archimedean + primes, no zeros) and the zero
side agree to ratio 1.00000-1.00001 on random vectors; zero truncation 500/1000/2000 moves
lambda_min(d=0.2) only in the sixth digit.

## What was learned

1. The negativity is O(d^2) (about -4.8 d^2 for small d): any off-line shift is seen at once.
2. The reason is not detection power but a zero margin at d = 0: on this basis zeta^2 has
   lambda_min ~ 0. The minimiser has ghat ~ 0 above t ~ 25, and below 25 zeta has only two
   zeros (14.13, 21.02), which 24 basis functions can annihilate.
3. Consequence for the Epstein note: a positive finite-section margin (e.g. +0.15 for
   zeta(s)L(s,chi_{-20})) reflects how many zeros lie inside the basis bandwidth, not
   "how Euler" the function is. Margins of different L-functions are not comparable
   without accounting for their low-lying zero density.
