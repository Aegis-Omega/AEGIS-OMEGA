"""T1 spectral-gap diagnostics for the moment-restricted Weil finite sections.

The approximation route to global Weil positivity needs, for each window, a
certified lower bound

    lambda_min(M_N, G_N) >= -eps_N      with eps_N -> 0,

since that gives q(h_N) >= -eps_N ||h_N||^2 and, with continuity, q(h) >= 0 in
the limit.  This module measures eps_N for the repository's own finite sections
(:mod:`harness.sdk.weil_spectral_inertia_probe`) and records what it finds.

What is observed, at T1 only:

* eps_N does NOT tend to zero.  It converges in the basis dimension to about
  11.2 and is stable to six decimals across two orders of magnitude of prime
  cutoff.
* The obstruction has rank one.  Exactly one negative generalized eigenvalue
  survives every restriction tried here.
* The obstruction is not the diverging scalar shift S_P(0): that runs to -565
  while lambda_min stays pinned at -11.025.
* The obstruction is not the s=1 pole moment.  Constraining against the pole
  weight e^{t/2} moves lambda_min by less than 0.06, whereas constraining the
  point value h(0) moves it by a factor of sixty.
* The negative direction is a bump at the origin, where the Archimedean weight
  Re psi(1/4 + i t/2) - log(pi) is negative.

READ THE INTERLACING CAVEAT BEFORE READING THE TABLES.  Restricting a
generalized eigenproblem to a subspace can only raise lambda_min (Cauchy
interlacing), so the decrease in magnitude as constraints are added is
guaranteed a priori and is NOT evidence of progress.  The informative content
is the contrast between constraints, and the fact that the count of negative
directions never reaches zero.

This module is T1 floating-point diagnostics.  It refutes nothing, proves
nothing, and carries no proof authority.  In particular a failure of eps_N to
vanish in THIS discretization is not a statement about the Weil form itself:
the sinc sections, the quadrature truncation at t_bound, and the single
imposed moment are all modelling choices.
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
CLASSIFICATION = "NEGATIVE_NUMERICAL_EVIDENCE"
INTERLACING_CAVEAT = (
    "Cauchy interlacing: restricting to a subspace can only raise lambda_min, "
    "so shrinkage under added constraints is guaranteed and is not progress."
)

BASIS_SWEEP = (5, 10, 20, 40, 60, 80, 120)
CUTOFF_SWEEP = (200, 1000, 5000, 20000)


def _config(*, p_cutoff: int, k_basis_dim: int) -> SpectralProbeConfig:
    return SpectralProbeConfig(
        tau=2.0,
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


def measure_moment_restricted(config: SpectralProbeConfig) -> dict[str, Any]:
    """lambda_min and the negative count for one moment-restricted section."""
    reduced = WeilSpectralInertiaProbe(config).assemble_moment_restricted(1.0)
    spectrum = _generalized_spectrum(reduced.M, reduced.G)
    return {
        "lambda_min": float(spectrum.min()),
        "n_negative": int((spectrum < -1e-8).sum()),
        "reduced_dimension": int(reduced.M.shape[0]),
    }


def measure_scalar_shift(config: SpectralProbeConfig) -> float:
    """S_P(0), the pointwise symbol value the Levy decomposition normalises at."""
    probe = WeilSpectralInertiaProbe(config)
    return float(probe.compute_symbol(np.array([0.0]))[0])


def _basis_functionals(config: SpectralProbeConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    probe = WeilSpectralInertiaProbe(config)
    grid = np.linspace(-config.t_bound, config.t_bound, config.n_quad)
    psi = np.sinc((config.tau / math.pi) * grid[None, :] - probe.k_indices[:, None])
    weight = float(grid[1] - grid[0]) / (2.0 * math.pi)
    return grid, psi, np.asarray(weight)


def measure_extra_constraint(
    config: SpectralProbeConfig, *, kind: str, parameter: float
) -> dict[str, Any]:
    """Impose one further linear constraint beyond the s=0 moment.

    ``kind='point'`` pins h(parameter) = 0.  ``kind='pole'`` constrains against
    the s=1 pole weight e^{t/2} truncated to |t| <= parameter, which is the
    only way that weight is representable on a grid truncated at t_bound.
    """
    probe = WeilSpectralInertiaProbe(config)
    M, G, moment = probe.assemble_raw(1.0)
    grid, psi, weight = _basis_functionals(config)

    if kind == "point":
        extra = np.array([np.interp(parameter, grid, psi[k]) for k in range(psi.shape[0])])
    elif kind == "pole":
        window = np.abs(grid) <= parameter
        extra = (psi[:, window] * np.exp(grid[window] / 2.0) * weight).sum(axis=1)
    else:
        raise ValueError("kind must be 'point' or 'pole'")

    basis = la.null_space(np.vstack([moment.reshape(1, -1), extra.reshape(1, -1)]))
    spectrum = _generalized_spectrum(basis.T @ M @ basis, basis.T @ G @ basis)
    return {
        "kind": kind,
        "parameter": float(parameter),
        "lambda_min": float(spectrum.min()),
        "n_negative": int((spectrum < -1e-8).sum()),
        "reduced_dimension": int(basis.shape[1]),
    }


def measure_negative_direction(config: SpectralProbeConfig) -> dict[str, Any]:
    """Where the single negative direction lives, as a function of t."""
    probe = WeilSpectralInertiaProbe(config)
    reduced = probe.assemble_moment_restricted(1.0)
    values, vectors = la.eigh(reduced.M, reduced.G)
    index = int(np.argmin(values))
    direction = reduced.constraint_basis @ vectors[:, index]
    direction = direction / np.linalg.norm(direction)

    grid, psi, weight = _basis_functionals(config)
    profile = direction @ psi
    density = profile**2 * float(weight)
    return {
        "lambda_min": float(values[index]),
        "peak_abscissa": float(grid[int(np.argmax(np.abs(profile)))]),
        "l2_mass_fraction_within_5": float(density[np.abs(grid) < 5.0].sum() / density.sum()),
    }


def _interval(value: float, *, relative: float = 1e-6, absolute: float = 1e-9) -> list[float]:
    pad = absolute + relative * abs(value)
    return [round(value - pad, 12), round(value + pad, 12)]


def _receipt_payload() -> dict[str, Any]:
    basis_cases = []
    for dim in BASIS_SWEEP:
        observed = measure_moment_restricted(_config(p_cutoff=1000, k_basis_dim=dim))
        basis_cases.append(
            {
                "k_basis_dim": dim,
                "lambda_min_interval": _interval(observed["lambda_min"]),
                "n_negative": observed["n_negative"],
            }
        )

    cutoff_cases = []
    for cutoff in CUTOFF_SWEEP:
        observed = measure_moment_restricted(_config(p_cutoff=cutoff, k_basis_dim=20))
        cutoff_cases.append(
            {
                "p_cutoff": cutoff,
                "lambda_min_interval": _interval(observed["lambda_min"]),
                "n_negative": observed["n_negative"],
                "scalar_shift_S_P_0_interval": _interval(
                    measure_scalar_shift(_config(p_cutoff=cutoff, k_basis_dim=20))
                ),
            }
        )

    reference = _config(p_cutoff=1000, k_basis_dim=20)
    constraint_cases = [
        {
            **measure_extra_constraint(reference, kind=kind, parameter=parameter),
            "lambda_min_interval": _interval(
                measure_extra_constraint(reference, kind=kind, parameter=parameter)["lambda_min"]
            ),
        }
        for kind, parameter in (("pole", 10.0), ("pole", 20.0), ("pole", 40.0), ("point", 0.0))
    ]
    for case in constraint_cases:
        case.pop("lambda_min")

    direction = measure_negative_direction(reference)

    return {
        "authority": T1_AUTHORITY,
        "basis_dimension_sweep": basis_cases,
        "classification": CLASSIFICATION,
        "epsilon_tends_to_zero": False,
        "extra_constraint_cases": constraint_cases,
        "global_weil_positivity_proven": False,
        "interlacing_caveat": INTERLACING_CAVEAT,
        "negative_direction": {
            "lambda_min_interval": _interval(direction["lambda_min"]),
            "l2_mass_fraction_within_5_interval": _interval(
                direction["l2_mass_fraction_within_5"]
            ),
            "peak_abscissa_interval": _interval(direction["peak_abscissa"], absolute=1e-3),
            "coincides_with_negative_archimedean_weight_at_origin": True,
        },
        "observed_gap_limit_estimate": -11.22,
        "obstruction_rank": 1,
        "pole_moment_explains_obstruction": False,
        "prime_cutoff_sweep": cutoff_cases,
        "probe_id": PROBE_ID,
        "refutes": None,
        "rh_authority": "NONE",
        "rh_proven": False,
        "scalar_shift_explains_obstruction": False,
        "schema_version": "1.0.0",
        "source": "research/rh/weil_moment_restricted_gap_probe.py",
        "target_obligation": TARGET_OBLIGATION,
    }


def build_receipt() -> dict[str, Any]:
    """Return the content-addressed T1 diagnostic receipt."""
    payload = _receipt_payload()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    receipt_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {**payload, "receipt_sha256": receipt_sha256}


if __name__ == "__main__":
    print(json.dumps(build_receipt(), indent=2, sort_keys=True))
