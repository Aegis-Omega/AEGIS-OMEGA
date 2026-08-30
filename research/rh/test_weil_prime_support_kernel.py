from __future__ import annotations

import math

import numpy as np

from harness.sdk.weil_prime_support_kernel import (
    assemble_prime_galerkin_closed_form,
    exact_sinc_gram_and_moment,
    run_support_growth_probe,
    sinc_product_cosine_integral,
)
from harness.sdk.weil_spectral_inertia_probe import SpectralProbeConfig, WeilSpectralInertiaProbe


def test_sinc_product_cosine_integral_has_exact_paley_wiener_support_cutoff() -> None:
    tau = 2.0
    scale = 1.0

    inside = sinc_product_cosine_integral(0, 0, 3.9, tau=tau, scale_factor=scale)
    boundary = sinc_product_cosine_integral(0, 0, 4.0, tau=tau, scale_factor=scale)
    outside = sinc_product_cosine_integral(0, 0, 4.1, tau=tau, scale_factor=scale)

    assert inside > 0.0
    assert boundary == 0.0
    assert outside == 0.0


def test_exact_infinite_domain_gram_and_moment_are_closed_form() -> None:
    k_indices = np.arange(-3, 4, dtype=int)
    gram, moment = exact_sinc_gram_and_moment(k_indices, tau=2.0, scale_factor=1.0)

    expected = 1.0 / 4.0
    assert np.max(np.abs(gram - expected * np.eye(len(k_indices)))) < 1e-15
    assert np.max(np.abs(moment - expected)) < 1e-15


def test_prime_galerkin_matrix_is_independent_of_cutoff_after_support_saturation() -> None:
    common = dict(tau=2.0, k_basis_dim=4, n_quad=512, t_bound=30.0)
    p100 = WeilSpectralInertiaProbe(SpectralProbeConfig(p_cutoff=100, **common))
    p20000 = WeilSpectralInertiaProbe(SpectralProbeConfig(p_cutoff=20000, **common))

    m100 = assemble_prime_galerkin_closed_form(p100, scale_factor=1.0)
    m20000 = assemble_prime_galerkin_closed_form(p20000, scale_factor=1.0)

    # For tau=2 and scale=1, products of sinc basis functions have Fourier
    # support in [-4, 4]. Every prime-power shift above 4 is exactly invisible.
    assert m100["support_radius"] == 4.0
    assert m20000["support_radius"] == 4.0
    assert m20000["discarded_prime_power_count"] > 0
    assert m100["active_prime_power_count"] == m20000["active_prime_power_count"]
    assert np.max(np.abs(m100["matrix"] - m20000["matrix"])) < 1e-12


def test_support_growth_probe_binds_finite_radius_norms_to_conservative_bounds() -> None:
    radii = (4.0, 6.0, 8.0)
    receipt = run_support_growth_probe(
        support_radii=radii,
        tau=2.0,
        k_basis_dim=4,
    )

    assert receipt["authority"] == "T1_ANALYTIC_CLOSED_FORM_DIAGNOSTIC"
    assert tuple(receipt["support_radii"]) == radii
    assert set(receipt["cases"]) == {"R=4", "R=6", "R=8"}

    observed_norms = []
    for radius in radii:
        case = receipt["cases"][f"R={radius:g}"]
        assert case["support_radius"] == radius
        assert case["sufficient_saturation_cutoff"] == math.ceil(math.exp(radius)) - 1
        assert case["zero_moment_constraint"] == "SUM_COEFFICIENTS_EQUALS_ZERO"
        assert case["operator_norm"] >= 0.0
        assert case["operator_norm"] <= case["compression_weight_bound"] + 1e-10
        assert case["compression_weight_bound"] <= case["elementary_growth_bound"] + 1e-10
        observed_norms.append(case["operator_norm"])

    # This monotonicity assertion is a preregistered finite diagnostic on these
    # three radii only. It is not promoted to an R -> infinity theorem.
    assert observed_norms[0] < observed_norms[1] < observed_norms[2]
    assert receipt["finite_grid_growth_observed"] is True
    assert receipt["uniform_support_bound_proven"] is False
    assert receipt["operator_norm_unbounded_proven"] is False
    assert receipt["globalization_across_unbounded_support_proven"] is False
    assert receipt["global_weil_positivity_proven"] is False
    assert receipt["rh_proven"] is False


def test_prime_support_kernel_is_diagnostic_only_and_cannot_promote_rh() -> None:
    probe = WeilSpectralInertiaProbe(
        SpectralProbeConfig(
            tau=2.0,
            p_cutoff=2000,
            k_basis_dim=3,
            n_quad=512,
            t_bound=30.0,
        )
    )
    receipt = assemble_prime_galerkin_closed_form(probe, scale_factor=1.0)

    assert receipt["authority"] == "T1_ANALYTIC_CLOSED_FORM_DIAGNOSTIC"
    assert receipt["support_localization_exact_formula"] is True
    assert receipt["infinite_prime_measure_constructed"] is False
    assert receipt["global_weil_positivity_proven"] is False
    assert receipt["rh_proven"] is False
