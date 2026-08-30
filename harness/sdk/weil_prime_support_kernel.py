"""Closed-form prime-power Galerkin support kernel for the sinc Weil probe.

This module isolates one finite-dimensional analytic fact used by the current
research lane.  For

    psi_k(t) = sinc((tau * scale / pi) * t - k),

the product psi_k psi_l has Fourier support in

    [-2 * tau * scale, 2 * tau * scale].

Consequently a prime-power cosine mode with frequency k*log(p) outside that
interval contributes exactly zero to the infinite-domain Galerkin matrix.
This is a support-localization identity for the chosen Paley--Wiener section;
it does not construct the untruncated prime Levy measure, identify the full
classical Weil operator, prove global positivity, or prove RH.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np

from harness.sdk.weil_spectral_inertia_probe import WeilSpectralInertiaProbe


AUTHORITY = "T1_ANALYTIC_CLOSED_FORM_DIAGNOSTIC"
METHOD = "INFINITE_DOMAIN_SINC_PRODUCT_FOURIER_SUPPORT_CLOSED_FORM"


def _validate_scale(tau: float, scale_factor: float) -> tuple[float, float]:
    tau = float(tau)
    scale_factor = float(scale_factor)
    if not math.isfinite(tau) or tau <= 0.0:
        raise ValueError("tau must be finite and positive")
    if not math.isfinite(scale_factor) or scale_factor <= 0.0:
        raise ValueError("scale_factor must be finite and positive")
    return tau, scale_factor


def sinc_product_cosine_integral(
    k: int,
    l: int,
    omega: float,
    *,
    tau: float,
    scale_factor: float = 1.0,
) -> float:
    """Return the exact closed form for ``int psi_k psi_l cos(omega t) dt``.

    ``numpy.sinc(x)`` uses ``sin(pi*x)/(pi*x)``.  With
    ``a = tau*scale_factor/pi`` and ``q = omega/a``, the Fourier transform of
    the product vanishes for ``|q| >= 2*pi``.  Inside support the overlap of
    the two rectangular sinc transforms has length ``L = 2*pi-|q|``.

    The returned value is evaluated in float arithmetic, but the zero outside
    support follows from the closed-form support identity rather than a
    quadrature threshold.
    """

    tau, scale_factor = _validate_scale(tau, scale_factor)
    omega = float(omega)
    if not math.isfinite(omega):
        raise ValueError("omega must be finite")

    a = tau * scale_factor / math.pi
    support_radius = 2.0 * tau * scale_factor
    if abs(omega) >= support_radius:
        return 0.0

    q = omega / a
    overlap = 2.0 * math.pi - abs(q)
    d = int(k) - int(l)

    if d == 0:
        return (overlap / (2.0 * math.pi * a)) * math.cos(q * int(k))

    midpoint = 0.5 * (int(k) + int(l))
    return (
        math.sin(0.5 * d * overlap)
        / (math.pi * d * a)
        * math.cos(q * midpoint)
    )


def exact_sinc_gram_and_moment(
    k_indices: Iterable[int],
    *,
    tau: float,
    scale_factor: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return infinite-domain Gram matrix and DC moment vector.

    The repository convention includes the spectral measure factor ``1/(2*pi)``.
    Hence

        G_kl = delta_kl / (2*tau*scale),
        u_k  = 1 / (2*tau*scale).

    The moment restriction is therefore exactly ``sum_k c_k = 0`` for this
    finite sinc family.
    """

    tau, scale_factor = _validate_scale(tau, scale_factor)
    indices = np.asarray(tuple(int(k) for k in k_indices), dtype=int)
    if indices.ndim != 1 or indices.size == 0:
        raise ValueError("k_indices must be a non-empty one-dimensional iterable")

    normalization = 1.0 / (2.0 * tau * scale_factor)
    gram = normalization * np.eye(indices.size, dtype=float)
    moment = np.full(indices.size, normalization, dtype=float)
    return gram, moment


def assemble_prime_galerkin_closed_form(
    probe: WeilSpectralInertiaProbe,
    *,
    scale_factor: float = 1.0,
) -> dict[str, Any]:
    """Assemble the prime-power block using the exact sinc support formula.

    The prime contribution to the repository symbol is

        -2 * w_{p,m} * cos((m log p) t).

    With the repository ``dt/(2*pi)`` convention, each active term therefore
    contributes ``-(w/pi) * integral(psi_k psi_l cos(omega t) dt)``.
    Terms on or outside the Paley--Wiener support boundary are exactly zero and
    are not evaluated numerically.
    """

    if not isinstance(probe, WeilSpectralInertiaProbe):
        raise TypeError("probe must be WeilSpectralInertiaProbe")
    tau, scale_factor = _validate_scale(probe.config.tau, scale_factor)

    support_radius = 2.0 * tau * scale_factor
    active = tuple(term for term in probe.prime_power_terms if term.shift < support_radius)
    discarded = tuple(term for term in probe.prime_power_terms if term.shift >= support_radius)

    matrix = np.zeros((probe.dim, probe.dim), dtype=float)
    for i, k in enumerate(probe.k_indices):
        for j in range(i, probe.dim):
            l = int(probe.k_indices[j])
            entry = 0.0
            for term in active:
                integral = sinc_product_cosine_integral(
                    int(k),
                    l,
                    term.shift,
                    tau=tau,
                    scale_factor=scale_factor,
                )
                entry -= (term.weight / math.pi) * integral
            matrix[i, j] = entry
            matrix[j, i] = entry

    return {
        "schema_version": "1.0.0",
        "authority": AUTHORITY,
        "method": METHOD,
        "tau": tau,
        "scale_factor": scale_factor,
        "support_radius": support_radius,
        "prime_power_count": probe.prime_power_count,
        "active_prime_power_count": len(active),
        "discarded_prime_power_count": len(discarded),
        "active_max_shift": max((term.shift for term in active), default=None),
        "discarded_min_shift": min((term.shift for term in discarded), default=None),
        "matrix": matrix,
        "support_localization_exact_formula": True,
        "boundary_modes_contribute_zero": True,
        "infinite_prime_measure_constructed": False,
        "concrete_infinite_weil_operator_bound": False,
        "global_weil_positivity_proven": False,
        "rh_proven": False,
        "non_claims": (
            "NO_UNTRUNCATED_PRIME_LEVY_PROCESS_FROM_THIS_KERNEL",
            "NO_ARCHIMEDEAN_CONTINUOUS_OPERATOR_CLOSURE",
            "NO_DENSITY_OR_GLOBALIZATION_PROMOTION",
            "NO_WEIL_CRITERION_OR_RH_AUTHORITY",
        ),
    }
