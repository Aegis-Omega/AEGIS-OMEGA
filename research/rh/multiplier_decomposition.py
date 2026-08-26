"""Perron decomposition of the finite prime-power multiplier lambda_P(gamma).

EPISTEMIC_STATUS: EXACT_DERIVATION + VERIFIED_NUMERICAL
SCOPE:            P <= 2e6, first six zero ordinates, six non-zero controls
NORMALIZATION:    lambda_P(gamma) = 2 Re sum_{n<=P} Lambda(n) n^{-1/2+i gamma}
                  (identical to the finite trigonometric symbol of T_P)

DECLARED, NOT DERIVED
  zero ordinates gamma_1..gamma_6   standard tabulated constants, inputs here
  P ladder                          chosen grid; no claim of optimality
  slope tolerances                  chosen separation thresholds, not bounds
  sigma grid                        chosen Gaussian widths

NOT CLAIMED
  any statement about the Riemann Hypothesis
  a rigorous proof of the decomposition (see DERIVATION below -- the
    heuristic differentiated explicit formula is used; the rigorous route
    is Perron plus a contour shift)
  positivity of the Weil quadratic form
  that m(gamma) read off a slope is a proof of multiplicity

DERIVATION (exact, hand-derived, NOT machine-bound)
  Write w = 1/2 - i gamma so that n^{-w} = n^{-1/2+i gamma}.  Partial
  summation against psi(x) = sum_{n<=x} Lambda(n) and the explicit formula
  psi(x) = x - sum_rho x^rho / rho - ... give

      sum_{n<=P} Lambda(n) n^{-w} = P^{1-w}/(1-w) - sum_rho I_rho(P) + O(1)

  The x term contributes P^{1-w}/(1-w) = P^{1/2+i gamma}/(1/2+i gamma).
  Each zero rho contributes an exponent rho - 1 - w.  For rho = 1/2 + i g'
  that exponent is -1 + i(gamma + g'), which equals -1 exactly when
  g' = -gamma, i.e. for the CONJUGATE zero rhobar = 1/2 - i gamma.  Then
  int_1^P x^{-1} dx = ln P, real, and 2 Re gives -2 ln P.  Every other zero
  contributes P^{i(gamma+g')}/(i(gamma+g')), a bounded oscillation.  Hence

      lambda_P(gamma) = 2 Re[ P^{1/2+i gamma} / (1/2+i gamma) ]
                        - 2 m(gamma) ln P
                        + O_gamma(1)                                     (*)

  with m(gamma) the multiplicity of 1/2 + i gamma as a zero of zeta
  (m = 0 when gamma is not a zero ordinate).

WHAT THIS INSTRUMENT DOES
  (*) is asserted below, not assumed.  It separates two statements that were
  previously compressed into one reading of lambda_P at a zero:

      main term      2 Re[P^{1/2+i gamma}/(1/2+i gamma)]   truncation artifact,
                                                           present at EVERY gamma
      zero term      -2 m(gamma) ln P                      the only arithmetic
                                                           content at a zero

  Consequence measured here: the large negative values of lambda_P at zero
  ordinates are artifact-dominated, and the positive values in the gaps are
  artifact ONLY.  The residual lambda_P - main is the clean discriminant.

  It also measures the quadratic form Q_P(sigma) = <T_P psi, psi> for a
  Gaussian packet, and the closed form of the main term's share of it:

      int lambda_main(gamma) |psihat(gamma)|^2 dgamma / 2pi
          = 4 pi sigma^2 exp(sigma^2 / 4)                                (**)

  (**) is asserted against quadrature below.  The main term does NOT vanish
  under integration -- it converges to a constant.  What the packet removes
  is its P-dependence, not the term.
"""

import cmath
import json
import math
import os

P_MAX = 2_000_000
P_LADDER = [20_000, 40_000, 65_010, 100_000, 150_000,
            250_000, 400_000, 650_000, 1_000_000, 1_400_000, P_MAX]

# DECLARED: standard tabulated ordinates, inputs to this instrument.
ZEROS = [
    ("gamma_1", 14.134725141734693),
    ("gamma_2", 21.022039638771555),
    ("gamma_3", 25.010857580145688),
    ("gamma_4", 30.424876125859513),
    ("gamma_5", 32.935061587739190),
    ("gamma_6", 37.586178158825671),
]
# DECLARED: controls chosen inside gaps, no claim they are far from every zero.
CONTROLS = [("c_12.00", 12.0), ("c_17.58", 17.58), ("c_23.50", 23.5),
            ("c_28.00", 28.0), ("c_35.26", 35.26), ("c_40.00", 40.0)]

SIGMAS = [0.4, 0.8, 1.2, 1.6]


def prime_power_terms(limit):
    """Ascending (k, ln p, p^k) for every prime power p^k <= limit."""
    sieve = bytearray([1]) * (limit + 1)
    sieve[0] = sieve[1] = 0
    for i in range(2, int(limit ** 0.5) + 1):
        if sieve[i]:
            sieve[i * i::i] = bytearray(len(sieve[i * i::i]))
    out = []
    for p in range(2, limit + 1):
        if sieve[p]:
            lp, q, k = math.log(p), p, 1
            while q <= limit:
                out.append((k, lp, q))
                q *= p
                k += 1
    out.sort(key=lambda t: t[2])
    return out


def lambda_ladder(gamma, terms, ladder):
    """lambda_P(gamma) at every P in ladder, one ascending pass."""
    out, acc, i = [], 0.0, 0
    for cap in ladder:
        while i < len(terms) and terms[i][2] <= cap:
            k, lp, q = terms[i]
            acc += lp / math.sqrt(q) * math.cos(k * gamma * lp)
            i += 1
        out.append(2.0 * acc)
    return out


def main_term(gamma, P):
    """2 Re[ P^{1/2+i gamma} / (1/2+i gamma) ] -- the Perron truncation term."""
    return 2.0 * (P ** (0.5 + 1j * gamma) / (0.5 + 1j * gamma)).real


def fit_slope(xs, ys):
    """Least-squares slope and R^2."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    sst = sum((y - my) ** 2 for y in ys)
    sse = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    return b, (1.0 - sse / sst if sst > 0 else 0.0)


def quadratic_form(sigma, terms, cap):
    """<T_P psi, psi> for psi(u) = exp(-u^2/(2 sigma^2)); f = psi*psi Gaussian."""
    c, d = 2.0 * math.sqrt(math.pi) * sigma, 4.0 * sigma * sigma
    return c * sum(lp / math.sqrt(q) * math.exp(-(k * lp) ** 2 / d)
                   for (k, lp, q) in terms if q <= cap)


def main_share_quadrature(sigma, P, n=200_000):
    """int lambda_main |psihat|^2 dgamma / 2pi by Simpson-free trapezoid."""
    g_max = 60.0 / sigma
    h = 2.0 * g_max / n
    total = 0.0
    for i in range(n + 1):
        g = -g_max + i * h
        w = 0.5 if i in (0, n) else 1.0
        total += main_term(g, P) * math.exp(-sigma * sigma * g * g) * w
    return total * h * sigma * sigma


def main_share_closed_form(sigma):
    """(**) 4 pi sigma^2 exp(sigma^2 / 4)."""
    return 4.0 * math.pi * sigma * sigma * math.exp(sigma * sigma / 4.0)


def main():
    terms = prime_power_terms(P_MAX)
    logs = [math.log(p) for p in P_LADDER]
    receipt = {"p_max": P_MAX, "p_ladder": P_LADDER,
               "n_prime_powers": len(terms), "zeros": {}, "controls": {},
               "quadratic_form": {}, "main_share": {}}

    def measure(label, gamma):
        lam = lambda_ladder(gamma, terms, P_LADDER)
        mains = [main_term(gamma, p) for p in P_LADDER]
        resid = [a - b for a, b in zip(lam, mains)]
        slope, r2 = fit_slope(logs, resid)
        return {"gamma": gamma, "lambda_P": lam, "main_term": mains,
                "residual": resid, "slope": slope, "r_squared": r2,
                "implied_m": -slope / 2.0}

    for label, g in ZEROS:
        receipt["zeros"][label] = measure(label, g)
    for label, g in CONTROLS:
        receipt["controls"][label] = measure(label, g)

    # (*) asserted, not assumed: slope = -2m with m = 1 at zeros, 0 at controls.
    zs = [receipt["zeros"][l]["slope"] for l, _ in ZEROS]
    cs = [receipt["controls"][l]["slope"] for l, _ in CONTROLS]
    for l, _ in ZEROS:
        s = receipt["zeros"][l]["slope"]
        assert abs(s + 2.0) < 0.25, f"{l}: slope {s} not near -2 (predicted -2m, m=1)"
    for l, _ in CONTROLS:
        s = receipt["controls"][l]["slope"]
        assert abs(s) < 0.5, f"{l}: slope {s} not near 0 (predicted m=0)"
    sep = min(abs(s) for s in zs) - max(abs(s) for s in cs)
    assert sep > 0.0, "zero and control slope populations are not separated"
    receipt["slope_separation"] = sep

    # Q_P converges in P while lambda_P does not.
    for sigma in SIGMAS:
        vals = [quadratic_form(sigma, terms, p) for p in P_LADDER]
        receipt["quadratic_form"][f"sigma_{sigma}"] = {
            "values": vals,
            "relative_drift": abs(vals[-1] - vals[0]) / abs(vals[-1]),
        }
    drift = receipt["quadratic_form"]["sigma_0.8"]["relative_drift"]
    assert drift < 1e-12, f"Q_P not stable across the ladder: drift {drift}"

    # (**) asserted, not assumed.
    for sigma in (0.4, 0.8):
        q = main_share_quadrature(sigma, 65_010)
        cf = main_share_closed_form(sigma)
        rel = abs(q - cf) / abs(cf)
        receipt["main_share"][f"sigma_{sigma}"] = {
            "quadrature": q, "closed_form": cf, "relative_error": rel}
        assert rel < 1e-12, f"(**) violated at sigma={sigma}: rel err {rel}"

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "receipts", "multiplier_decomposition_p2e6.json")
    with open(path, "w") as fh:
        json.dump(receipt, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"prime powers <= {P_MAX}: {len(terms)}")
    print("\n  label      slope d(resid)/d(lnP)    R^2     implied m")
    for l, _ in ZEROS:
        e = receipt["zeros"][l]
        print(f"  {l:<9} {e['slope']:+9.3f}            {e['r_squared']:5.3f}   {e['implied_m']:6.3f}")
    for l, _ in CONTROLS:
        e = receipt["controls"][l]
        print(f"  {l:<9} {e['slope']:+9.3f}            {e['r_squared']:5.3f}        -")
    print(f"\n  slope separation (min|zero| - max|control|): {sep:.3f}")
    print(f"  Q_P drift over ladder (sigma=0.8):           {drift:.3e}")
    for sigma in (0.4, 0.8):
        m = receipt["main_share"][f"sigma_{sigma}"]
        print(f"  (**) sigma={sigma}: {m['quadrature']:.6f} vs {m['closed_form']:.6f}"
              f"  rel {m['relative_error']:.2e}")
    print(f"\n  receipt: {path}")


if __name__ == "__main__":
    main()
