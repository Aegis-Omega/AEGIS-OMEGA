"""Closed-form prime-power Galerkin support kernel for the sinc Weil probe.

This module isolates one finite-dimensional analytic fact used by the current
research lane.  For

    psi_k(t) = sinc((tau * scale / pi) * t - k),

the product psi_k psi_l has Fourier support in

    [-2 * tau * scale, 2 * tau * scale].

Consequently a prime-power cosine mode with frequency m*log(p) outside that
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
    """Return the closed form for ``int psi_k psi_l cos(omega t) dt``.

    ``numpy.sinc(x)`` uses ``sin(pi*x)/(pi*x)``.  With
    ``a = tau*scale_factor/pi`` and ``q = omega/a``, the Fourier transform of
    the product vanishes for ``|q| >= 2*pi``.  Inside support the overlap of
    the two rectangular sinc transforms has length ``L = 2*pi-|q|``.

    The returned value is evaluated in float arithmetic, but the zero outside
    support follows from the analytic support identity rather than a numerical
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


def support_saturation_cutoff(*, tau: float, scale_factor: float = 1.0) -> int:
    """Return a sufficient integer prime-power cutoff for a fixed support class.

    Visible prime powers satisfy ``log(p^m) < 2*tau*scale``.  Since ``p^m`` is
    an integer, every visible term is included once

        P >= ceil(exp(2*tau*scale)) - 1.

    This is a sufficient support cutoff, not a claim that every integer below
    it is a prime power or that the cutoff is the minimal prime-power value.
    """

    tau, scale_factor = _validate_scale(tau, scale_factor)
    radius = 2.0 * tau * scale_factor
    try:
        bound = math.exp(radius)
    except OverflowError as exc:
        raise ValueError("support radius is too large for a finite float cutoff") from exc
    if not math.isfinite(bound):
        raise ValueError("support radius is too large for a finite float cutoff")
    return int(math.ceil(bound) - 1)


def assemble_prime_galerkin_closed_form(
    probe: WeilSpectralInertiaProbe,
    *,
    scale_factor: float = 1.0,
) -> dict[str, Any]:
    """Assemble the prime-power block using the sinc support formula.

    The prime contribution to the repository symbol is

        -2 * w_{p,m} * cos((m log p) t).

    With the repository ``dt/(2*pi)`` convention, each active term therefore
    contributes ``-(w/pi) * integral(psi_k psi_l cos(omega t) dt)``.
    Terms on or outside the Paley--Wiener support boundary are exactly zero and
    are not evaluated by quadrature.
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
        "sufficient_saturation_cutoff": support_saturation_cutoff(
            tau=tau, scale_factor=scale_factor
        ),
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


def assemble_prime_renormalized_components(
    probe: WeilSpectralInertiaProbe,
    *,
    scale_factor: float = 1.0,
) -> dict[str, Any]:
    """Expose the exact fixed-support cancellation behind the Levy split.

    For one prime-power term of weight ``w`` and cosine Galerkin block ``C``,

        original = -2 w C,
        centered =  2 w (G - C),
        offset   = -2 w G.

    Hence ``centered + offset = original``.  If the jump frequency lies on or
    outside the Paley--Wiener support radius then ``C=0`` exactly, so its
    centered energy ``2 w G`` and scalar counterterm ``-2 w G`` cancel on the
    fixed support class.  The two pieces may grow separately as P increases;
    the original localized prime form has already saturated.

    This is local renormalized-form semantics only.  It neither creates a
    standard untruncated Levy measure nor proves compatibility/global closure
    over an unbounded union of support classes.
    """

    if not isinstance(probe, WeilSpectralInertiaProbe):
        raise TypeError("probe must be WeilSpectralInertiaProbe")
    tau, scale_factor = _validate_scale(probe.config.tau, scale_factor)

    original_receipt = assemble_prime_galerkin_closed_form(
        probe, scale_factor=scale_factor
    )
    original_matrix = np.asarray(original_receipt["matrix"], dtype=float)
    gram, _ = exact_sinc_gram_and_moment(
        probe.k_indices, tau=tau, scale_factor=scale_factor
    )

    total_weight = float(sum(term.weight for term in probe.prime_power_terms))
    support_radius = 2.0 * tau * scale_factor
    discarded = tuple(
        term for term in probe.prime_power_terms if term.shift >= support_radius
    )
    discarded_weight = float(sum(term.weight for term in discarded))

    # From original = -2 sum(w C), centered = 2 W G - 2 sum(w C).
    centered_matrix = 2.0 * total_weight * gram + original_matrix
    offset_matrix = -2.0 * total_weight * gram
    reconstructed = centered_matrix + offset_matrix

    # Every discarded mode has C=0, so its split cancels identically as a
    # grouped counterterm.  Build both from the same scalar to avoid introducing
    # an artificial quadrature error into an analytic zero.
    tail_centered = 2.0 * discarded_weight * gram
    tail_offset = -tail_centered
    tail_cancellation = tail_centered + tail_offset

    return {
        "schema_version": "1.0.0",
        "authority": AUTHORITY,
        "method": "FIXED_SUPPORT_PRIME_LEVY_COUNTERTERM_CANCELLATION",
        "tau": tau,
        "scale_factor": scale_factor,
        "support_radius": support_radius,
        "sufficient_saturation_cutoff": support_saturation_cutoff(
            tau=tau, scale_factor=scale_factor
        ),
        "prime_power_count": probe.prime_power_count,
        "active_prime_power_count": original_receipt["active_prime_power_count"],
        "discarded_prime_power_count": len(discarded),
        "total_prime_weight": total_weight,
        "discarded_prime_weight": discarded_weight,
        "gram": gram,
        "original_matrix": original_matrix,
        "centered_matrix": centered_matrix,
        "offset_matrix": offset_matrix,
        "tail_centered_energy_norm": float(np.linalg.norm(tail_centered)),
        "tail_offset_norm": float(np.linalg.norm(tail_offset)),
        "tail_cancellation_max_abs_error": float(np.max(np.abs(tail_cancellation))),
        "full_decomposition_max_abs_error": float(
            np.max(np.abs(reconstructed - original_matrix))
        ),
        "local_prime_form_stabilizes_after_support_saturation": True,
        "support_localization_exact_formula": True,
        "global_standard_levy_measure_constructed": False,
        "globalization_across_unbounded_support_proven": False,
        "concrete_infinite_weil_operator_bound": False,
        "global_weil_positivity_proven": False,
        "rh_proven": False,
        "non_claims": (
            "LOCAL_COUNTERTERM_CANCELLATION_IS_NOT_A_GLOBAL_LEVY_PROCESS",
            "NO_UNIFORM_BOUND_AS_SUPPORT_RADIUS_TENDS_TO_INFINITY",
            "NO_CONCRETE_GLOBAL_WEIL_OPERATOR_IDENTIFICATION",
            "NO_WEIL_CRITERION_OR_RH_AUTHORITY",
        ),
    }
