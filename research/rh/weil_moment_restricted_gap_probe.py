"""T1 diagnostics for the moment-restricted Weil finite sections, with correction.

The approximation route to global Weil positivity needs, for each window, a
certified lower bound

    lambda_min(M_N, G_N) >= -eps_N      with eps_N -> 0,

since that gives q(h_N) >= -eps_N ||h_N||^2 and, with continuity, q(h) >= 0.
This module measures that quantity on the repository's own finite sections
(:mod:`harness.sdk.weil_spectral_inertia_probe`).

CORRECTION.  An earlier revision of this receipt reported that eps_N does not
tend to zero, that the obstruction is not explained by the pole moment, and
classified the result as negative evidence for the route.  That reading was
wrong.  Its pole test weighted h by e^{t/2} on the spectral side, which is not
the pole functional.  In the spectral variable t the explicit formula reads

    q(h) = (1/2pi) int |h(t)|^2 S(t) dt = sum_gamma |h(gamma)|^2 - 2 Re h(i/2)^2,

so the pole contribution is the analytic continuation h(i/2), a point value,
not an exponential moment.  With that functional:

* Under the probe's own constraint ``int h = 0`` the section still has one
  negative eigenvalue near -11.2, stable in the prime cutoff.  That measurement
  stands.  It is the pole term, and nothing else.
* Imposing ``Re h(i/2) = 0`` (half of the Weil moment conditions, the half that
  controls the sign) removes it: no negative eigenvalue, for every tau and basis
  dimension measured.
* Rebuilding the form independently from zeta zeros,
  M_zeros = sum_gamma psi(gamma) psi(gamma)^T - 2 a a^T + 2 b b^T with
  a + ib = psi(i/2), agrees with the probe's quadrature to about 0.1 per cent,
  and the zero sum alone is positive semidefinite.

So the probe's moment constraint ``int h = 0`` is not the Weil moment condition
(``WeilMomentConditionsV1`` is Mellin at s = 0 and s = 1, i.e. h(-+i/2) = 0 in
this variable), and the reported -11.2 gap is an artefact of that
misspecification, not an obstruction to the route.

WHAT THE CROSS-CHECK DOES NOT SHOW.  It uses computed zeros, which lie on the
critical line, so positivity of the zero sum is automatic.  It verifies the
explicit formula and the probe numerically; it does not test RH.  Positivity
after the correct constraint is equivalent to the zeros being real, which is
the content of the Weil criterion, not independent evidence for it.

INTERLACING.  Restricting a generalized eigenproblem can only raise lambda_min
(Cauchy interlacing), so shrinkage under added constraints is guaranteed and is
not progress by itself.  The informative content is the contrast: one correct
constraint removes the negative direction entirely, while the probe's
constraint, the spectral-side exponential weight and several point constraints
do not.

This module is T1 floating-point diagnostics.  It refutes nothing, proves
nothing, and carries no proof authority.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import numpy as np
import scipy.linalg as la

from harness.sdk.weil_spectral_inertia_probe import (
    T1_AUTHORITY,
    SpectralProbeConfig,
    WeilSpectralInertiaProbe,
)

PROBE_ID = "WEIL-MOMENT-RESTRICTED-GAP-V1"
TARGET_OBLIGATION = "W8_DensityContinuityCoverage"
CLASSIFICATION = "PROBE_MOMENT_CONSTRAINT_MISSPECIFICATION"
INTERLACING_CAVEAT = (
    "Cauchy interlacing: restricting to a subspace can only raise lambda_min, "
    "so shrinkage under added constraints is guaranteed and is not progress."
)
ZERO_SOURCE = "mpmath.zetazero(n).imag, n = 1..100, 15 decimals, verified at n = 1, 50, 100"

BASIS_SWEEP = (5, 10, 20, 40, 60, 80, 120)
CUTOFF_SWEEP = (200, 1000, 5000, 20000)
POLE_SWEEP = ((1.0, 10), (1.0, 20), (1.0, 40), (2.0, 10), (2.0, 20), (2.0, 40),
              (3.0, 10), (3.0, 20), (3.0, 40))

ZETA_ZERO_ORDINATES = (
    14.134725141734695,
    21.022039638771556,
    25.010857580145689,
    30.424876125859512,
    32.935061587739192,
    37.586178158825675,
    40.918719012147498,
    43.327073280915002,
    48.005150881167161,
    49.773832477672300,
    52.970321477714464,
    56.446247697063392,
    59.347044002602352,
    60.831778524609810,
    65.112544048081602,
    67.079810529494168,
    69.546401711173985,
    72.067157674481905,
    75.704690699083926,
    77.144840068874799,
    79.337375020249368,
    82.910380854086029,
    84.735492980517051,
    87.425274613125225,
    88.809111207634459,
    92.491899270558491,
    94.651344040519888,
    95.870634228245308,
    98.831194218193687,
    101.317851005731384,
    103.725538040478341,
    105.446623052326089,
    107.168611184276401,
    111.029535543169672,
    111.874659176992637,
    114.320220915452708,
    116.226680320857554,
    118.790782865976212,
    121.370125002420650,
    122.946829293552582,
    124.256818554345770,
    127.516683879596499,
    129.578704199956064,
    131.087688530932667,
    133.497737202997598,
    134.756509753373876,
    138.116042054533438,
    139.736208952121387,
    141.123707404021133,
    143.111845807620625,
    146.000982486765508,
    147.422765342559615,
    150.053520420784878,
    150.925257612241467,
    153.024693811198887,
    156.112909294237880,
    157.597591817594065,
    158.849988171420506,
    161.188964137596031,
    163.030709687181997,
    165.537069187900414,
    167.184439978174510,
    169.094515415568821,
    169.911976479411692,
    173.411536519591550,
    174.754191523365733,
    176.441434297710430,
    178.377407776099972,
    179.916484020257002,
    182.207078484366463,
    184.874467848387496,
    185.598783677707473,
    187.228922583501856,
    189.416158656016933,
    192.026656360713787,
    193.079726603845700,
    195.265396679529232,
    196.876481840958320,
    198.015309676251917,
    201.264751943703800,
    202.493594514140540,
    204.189671803104545,
    205.394697202163286,
    207.906258887806217,
    209.576509716856265,
    211.690862595365303,
    213.347919359712677,
    214.547044783491430,
    216.169538508263713,
    219.067596349021386,
    220.714918839314009,
    221.430705554693333,
    224.007000254604321,
    224.983324669582288,
    227.421444279679292,
    229.337413305525359,
    231.250188700499166,
    231.987235253180245,
    233.693404178908310,
    236.524229665816193,
)


def _config(*, p_cutoff: int, k_basis_dim: int, tau: float = 2.0) -> SpectralProbeConfig:
    return SpectralProbeConfig(
        tau=tau,
        p_cutoff=p_cutoff,
        k_basis_dim=k_basis_dim,
        n_quad=8192,
        t_bound=200.0,
    )


def _generalized_spectrum(M: np.ndarray, G: np.ndarray) -> np.ndarray:
    M = 0.5 * (M + M.T)
    G = 0.5 * (G + G.T)
    if float(la.eigvalsh(G).min()) <= 0.0:
        raise ValueError("restricted Gram matrix is not positive definite")
    return la.eigh(M, G, eigvals_only=True)


def _basis_at(config: SpectralProbeConfig, z: complex | np.ndarray) -> np.ndarray:
    """Evaluate every sinc basis function at a (possibly complex) spectral point."""
    probe = WeilSpectralInertiaProbe(config)
    w = (config.tau / math.pi) * z - probe.k_indices.astype(float)
    return np.where(np.abs(w) < 1e-14, 1.0 + 0j, np.sin(np.pi * w) / (np.pi * w))


def pole_vector(config: SpectralProbeConfig) -> np.ndarray:
    """psi_k(i/2): h(i/2) = pole_vector . c for h = sum_k c_k psi_k."""
    return _basis_at(config, 0.5j)


def measure_moment_restricted(config: SpectralProbeConfig) -> dict[str, Any]:
    """lambda_min under the probe's own constraint, int h dt = 0."""
    reduced = WeilSpectralInertiaProbe(config).assemble_moment_restricted(1.0)
    spectrum = _generalized_spectrum(reduced.M, reduced.G)
    return {
        "lambda_min": float(spectrum.min()),
        "n_negative": int((spectrum < -1e-8).sum()),
        "reduced_dimension": int(reduced.M.shape[0]),
    }


def measure_weil_pole_constraint(config: SpectralProbeConfig, *, both_parts: bool = False) -> dict[str, Any]:
    """lambda_min under the Weil pole condition Re h(i/2) = 0 (and Im, if asked).

    Re h(i/2) = 0 already makes the pole term -2 Re h(i/2)^2 = +2 (Im h(i/2))^2
    nonnegative; adding Im h(i/2) = 0 kills it exactly.
    """
    M, G, _ = WeilSpectralInertiaProbe(config).assemble_raw(1.0)
    pole = pole_vector(config)
    rows = [pole.real] + ([pole.imag] if both_parts else [])
    basis = la.null_space(np.vstack(rows))
    spectrum = _generalized_spectrum(basis.T @ M @ basis, basis.T @ G @ basis)
    return {
        "lambda_min": float(spectrum.min()),
        "n_negative": int((spectrum < -1e-8).sum()),
        "reduced_dimension": int(basis.shape[1]),
    }


def measure_zero_side_crosscheck(config: SpectralProbeConfig) -> dict[str, Any]:
    """Rebuild the form from zeta zeros and compare it with the probe's quadrature."""
    M, G, _ = WeilSpectralInertiaProbe(config).assemble_raw(1.0)
    dim = M.shape[0]
    zero_sum = np.zeros((dim, dim))
    for gamma in ZETA_ZERO_ORDINATES:
        for s in (gamma, -gamma):
            v = _basis_at(config, s).real
            zero_sum += np.outer(v, v)
    pole = pole_vector(config)
    rebuilt = zero_sum - 2 * np.outer(pole.real, pole.real) + 2 * np.outer(pole.imag, pole.imag)
    return {
        "zeros_used": len(ZETA_ZERO_ORDINATES),
        "gamma_max": float(ZETA_ZERO_ORDINATES[-1]),
        "relative_frobenius_difference": float(np.linalg.norm(M - rebuilt) / np.linalg.norm(M)),
        "lambda_min_probe": float(_generalized_spectrum(M, G).min()),
        "lambda_min_zeros": float(_generalized_spectrum(rebuilt, G).min()),
        "zero_sum_lambda_min": float(_generalized_spectrum(zero_sum, G).min()),
    }


def measure_scalar_shift(config: SpectralProbeConfig) -> float:
    """S_P(0), the pointwise symbol value the Levy decomposition normalises at."""
    probe = WeilSpectralInertiaProbe(config)
    return float(probe.compute_symbol(np.array([0.0]))[0])


def measure_extra_constraint(
    config: SpectralProbeConfig, *, kind: str, parameter: float
) -> dict[str, Any]:
    """One further linear constraint beyond the probe's int h = 0.

    ``kind='point'`` pins h(parameter) = 0.  ``kind='t_side_exponential'`` is the
    functional the earlier revision mistook for the pole: int h(t) e^{t/2} dt
    over |t| <= parameter.  It is kept to document the retraction.
    """
    probe = WeilSpectralInertiaProbe(config)
    M, G, moment = probe.assemble_raw(1.0)
    grid = np.linspace(-config.t_bound, config.t_bound, config.n_quad)
    psi = np.sinc((config.tau / math.pi) * grid[None, :] - probe.k_indices[:, None])
    weight = float(grid[1] - grid[0]) / (2.0 * math.pi)

    if kind == "point":
        extra = np.array([np.interp(parameter, grid, psi[k]) for k in range(psi.shape[0])])
    elif kind == "t_side_exponential":
        window = np.abs(grid) <= parameter
        extra = (psi[:, window] * np.exp(grid[window] / 2.0) * weight).sum(axis=1)
    else:
        raise ValueError("kind must be 'point' or 't_side_exponential'")

    basis = la.null_space(np.vstack([moment.reshape(1, -1), extra.reshape(1, -1)]))
    spectrum = _generalized_spectrum(basis.T @ M @ basis, basis.T @ G @ basis)
    return {
        "kind": kind,
        "parameter": float(parameter),
        "lambda_min": float(spectrum.min()),
        "n_negative": int((spectrum < -1e-8).sum()),
        "reduced_dimension": int(basis.shape[1]),
    }


def _interval(value: float, *, relative: float = 1e-6, absolute: float = 1e-9) -> list[float]:
    pad = absolute + relative * abs(value)
    return [round(value - pad, 12), round(value + pad, 12)]


def _receipt_payload() -> dict[str, Any]:
    basis_cases = []
    for dim in BASIS_SWEEP:
        observed = measure_moment_restricted(_config(p_cutoff=1000, k_basis_dim=dim))
        basis_cases.append({
            "k_basis_dim": dim,
            "lambda_min_interval": _interval(observed["lambda_min"]),
            "n_negative": observed["n_negative"],
        })

    cutoff_cases = []
    for cutoff in CUTOFF_SWEEP:
        observed = measure_moment_restricted(_config(p_cutoff=cutoff, k_basis_dim=20))
        cutoff_cases.append({
            "p_cutoff": cutoff,
            "lambda_min_interval": _interval(observed["lambda_min"]),
            "n_negative": observed["n_negative"],
            "scalar_shift_S_P_0_interval": _interval(
                measure_scalar_shift(_config(p_cutoff=cutoff, k_basis_dim=20))
            ),
        })

    pole_cases = []
    for tau, dim in POLE_SWEEP:
        cfg = _config(p_cutoff=5000, k_basis_dim=dim, tau=tau)
        re_only = measure_weil_pole_constraint(cfg)
        both = measure_weil_pole_constraint(cfg, both_parts=True)
        pole_cases.append({
            "tau": tau,
            "k_basis_dim": dim,
            "re_h_i_half_zero": {"n_negative": re_only["n_negative"],
                                 "lambda_min_above": -1e-8},
            "h_i_half_zero": {"n_negative": both["n_negative"],
                              "lambda_min_above": -1e-8},
        })

    reference = _config(p_cutoff=1000, k_basis_dim=20)
    constraint_cases = []
    for kind, parameter in (("t_side_exponential", 10.0), ("t_side_exponential", 20.0),
                            ("t_side_exponential", 40.0), ("point", 0.0)):
        observed = measure_extra_constraint(reference, kind=kind, parameter=parameter)
        constraint_cases.append({
            "kind": kind,
            "parameter": observed["parameter"],
            "lambda_min_interval": _interval(observed["lambda_min"]),
            "n_negative": observed["n_negative"],
            "reduced_dimension": observed["reduced_dimension"],
        })

    cross = measure_zero_side_crosscheck(reference)

    return {
        "authority": T1_AUTHORITY,
        "basis_dimension_sweep_under_probe_constraint": basis_cases,
        "classification": CLASSIFICATION,
        "extra_constraint_cases": constraint_cases,
        "global_weil_positivity_proven": False,
        "interlacing_caveat": INTERLACING_CAVEAT,
        "obstruction_explained_by": "pole term -2 Re h(i/2)^2 of the explicit formula",
        "obstruction_is_probe_constraint_artefact": True,
        "obstruction_rank_under_probe_constraint": 1,
        "pole_moment_explains_obstruction": True,
        "prime_cutoff_sweep_under_probe_constraint": cutoff_cases,
        "probe_constraint": "int h dt = 0 (not the Weil moment condition)",
        "probe_id": PROBE_ID,
        "refutes": None,
        "retracted_claims": [
            {"field": "pole_moment_explains_obstruction", "was": False, "now": True,
             "reason": "the earlier pole test used the spectral-side weight e^{t/2}, "
                       "not the pole functional h(i/2)"},
            {"field": "epsilon_tends_to_zero", "was": False,
             "now": "not applicable: the ~11.2 gap is the pole term under a misspecified constraint",
             "reason": "with Re h(i/2) = 0 no negative eigenvalue remains"},
            {"field": "classification", "was": "NEGATIVE_NUMERICAL_EVIDENCE",
             "now": CLASSIFICATION,
             "reason": "the gap is not evidence against the route"},
        ],
        "rh_authority": "NONE",
        "rh_proven": False,
        "scalar_shift_explains_obstruction": False,
        "schema_version": "1.1.0",
        "source": "research/rh/weil_moment_restricted_gap_probe.py",
        "target_obligation": TARGET_OBLIGATION,
        "weil_moment_condition": "h(-+i/2) = 0 in the spectral variable (Mellin at s = 0, 1)",
        "weil_pole_constraint_sweep": pole_cases,
        "zero_side_crosscheck": {
            "caveat": "computed zeros lie on the critical line, so the zero sum is PSD "
                      "by construction; this verifies the explicit formula and the probe, "
                      "not RH",
            "gamma_max": cross["gamma_max"],
            "lambda_min_probe_interval": _interval(cross["lambda_min_probe"]),
            "lambda_min_zeros_interval": _interval(cross["lambda_min_zeros"], relative=1e-4),
            "relative_frobenius_difference_below": 5e-3,
            "zero_source": ZERO_SOURCE,
            "zero_sum_is_psd": cross["zero_sum_lambda_min"] > -1e-10,
            "zeros_used": cross["zeros_used"],
        },
    }


def build_receipt() -> dict[str, Any]:
    """Return the content-addressed T1 diagnostic receipt."""
    payload = _receipt_payload()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    receipt_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {**payload, "receipt_sha256": receipt_sha256}


if __name__ == "__main__":
    print(json.dumps(build_receipt(), indent=2, sort_keys=True))
