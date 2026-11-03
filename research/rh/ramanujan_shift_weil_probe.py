"""Weil quadratic of F_d(s) = zeta(s+d) zeta(s-d) on the moment-zero basis of
research/rh/krein_dual_beyond_log2.py (g_k = (1/4 - D^2){sin(pi x/L) sin(k pi x/L)} on [0, L]).

F_d has an Euler product (log-derivative supported on prime powers) and a symmetric
functional equation, but its zeros sit at 1/2 +/- d + i*gamma_n. The only violated
axiom is Ramanujan: Lambda_F(p) = (p^d + p^-d) log p > 2 log p.

Two independent evaluations of the same form:
  zero side    : 4 * sum_n Re ghat(gamma_n + i d) conj ghat(gamma_n - i d)   (zeta zeros)
  formula side : (1/pi) int_0^T S(t) |ghat(t)|^2 dt, arch + primes only     (d = 0 check)
Numerical diagnostic; no proof authority.
"""
import json, math, os, sys
from multiprocessing import Pool

import mpmath
import numpy as np
import scipy.linalg as la
import scipy.special as sp

HERE = os.path.dirname(os.path.abspath(__file__))
ZEROS = os.path.join(HERE, "zeta_zeros_2000.json")


def modes(L, k):
    a = math.pi / L
    return {k - 1: 0.5 * (0.25 + ((k - 1) * a) ** 2), k + 1: -0.5 * (0.25 + ((k + 1) * a) ** 2)}


def gram(L, dim):
    ms = [modes(L, k) for k in range(1, dim + 1)]
    G = np.zeros((dim, dim))
    for i in range(dim):
        for j in range(dim):
            G[i, j] = sum(ms[i][m] * ms[j][m] * (L if m == 0 else L / 2) for m in set(ms[i]) & set(ms[j]))
    return G


def ghat(tau, L, dim):
    tau = np.asarray(tau, dtype=complex)
    I = lambda c: L * np.exp(-0.5j * c * L) * np.sinc(c * L / (2 * math.pi))
    F = np.zeros((dim, tau.size), dtype=complex)
    for r, k in enumerate(range(1, dim + 1)):
        for m, co in modes(L, k).items():
            F[r] += co * 0.5 * (I(tau - m * math.pi / L) + I(tau + m * math.pi / L))
    return F


def zeta_zeros(n=2000):
    if os.path.exists(ZEROS):
        return np.array(json.load(open(ZEROS)))
    mpmath.mp.dps = 15
    with Pool(4) as p:
        z = p.map(lambda_zero, range(1, n + 1), chunksize=50)
    json.dump(z, open(ZEROS, "w"))
    return np.array(z)


def lambda_zero(n):
    return float(mpmath.zetazero(n).imag)


def zero_side(L, dim, d, gammas):
    U, V = ghat(gammas + 1j * d, L, dim), ghat(gammas - 1j * d, L, dim)
    M = 4 * (U @ V.conj().T).real
    return 0.5 * (M + M.T)


def formula_side_d0(L, dim, T=3000.0, dt=0.02):
    """zeta(s)^2: arch + prime side only (poles are killed by the moment-zero basis)."""
    lam = {}
    for p in range(2, int(math.exp(L)) + 1):
        if all(p % q for q in range(2, int(p ** 0.5) + 1)):
            q = p
            while math.log(q) < L:
                lam[q] = 2 * math.log(p)
                q *= p
    M = np.zeros((dim, dim))
    n_t = int(T / dt)
    for s0 in range(0, n_t, 4096):
        t = (np.arange(s0, min(n_t, s0 + 4096)) + 0.5) * dt
        F = ghat(t, L, dim)
        S = -2 * math.log(math.pi) + 2 * np.real(sp.digamma((0.5 + 1j * t) / 2))
        for n, v in lam.items():
            S = S - 2 * v / math.sqrt(n) * np.cos(t * math.log(n))
        M += ((F * (S * dt / math.pi)) @ F.conj().T).real
    return 0.5 * (M + M.T)


def main(L=3.5, dim=24):
    g = zeta_zeros()
    G = gram(L, dim)
    lmin = lambda M: float(la.eigh(M, G, eigvals_only=True)[0])
    Mz0, Mf0 = zero_side(L, dim, 0.0, g), formula_side_d0(L, dim)
    rng = np.random.default_rng(0)
    ratios = [float((v @ Mf0 @ v) / (v @ Mz0 @ v)) for v in rng.standard_normal((5, dim))]
    out = {"L": L, "basis_dim": dim, "zeros": int(g.size),
           "d0_zero_side_lambda_min": lmin(Mz0), "d0_formula_side_lambda_min": lmin(Mf0),
           "d0_formula_over_zero_side_ratios": ratios,
           "sweep": {f"{d:.2f}": lmin(zero_side(L, dim, d, g))
                     for d in (0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.49)},
           "truncation_check_d0.2": {n: lmin(zero_side(L, dim, 0.2, g[:n])) for n in (500, 1000, 2000)},
           "proof_authority": False, "rh_proven": False}
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
