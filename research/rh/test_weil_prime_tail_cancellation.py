from __future__ import annotations

import numpy as np

from harness.sdk.weil_prime_support_kernel import (
    assemble_prime_galerkin_closed_form,
    assemble_prime_renormalized_components,
    support_saturation_cutoff,
)
from harness.sdk.weil_spectral_inertia_probe import SpectralProbeConfig, WeilSpectralInertiaProbe


def _probe(p_cutoff: int) -> WeilSpectralInertiaProbe:
    return WeilSpectralInertiaProbe(
        SpectralProbeConfig(
            tau=2.0,
            p_cutoff=p_cutoff,
            k_basis_dim=4,
            n_quad=512,
            t_bound=30.0,
        )
    )


def test_support_saturation_cutoff_is_finite_for_every_fixed_paley_wiener_radius() -> None:
    cutoff = support_saturation_cutoff(tau=2.0, scale_factor=1.0)

    # q = p^m is integer and visible only when log(q) < 4, hence q < e^4.
    # ceil(e^4)-1 = 54 is a sufficient integer cutoff for this support class.
    assert cutoff == 54


def test_original_prime_form_stabilizes_after_support_saturation() -> None:
    saturated = assemble_prime_galerkin_closed_form(_probe(54), scale_factor=1.0)
    huge = assemble_prime_galerkin_closed_form(_probe(20000), scale_factor=1.0)

    assert saturated["active_prime_power_count"] == huge["active_prime_power_count"]
    assert huge["discarded_prime_power_count"] > saturated["discarded_prime_power_count"]
    assert np.max(np.abs(saturated["matrix"] - huge["matrix"])) < 1e-12


def test_divergent_centered_tail_and_scalar_counterterm_cancel_on_fixed_support_class() -> None:
    receipt = assemble_prime_renormalized_components(_probe(20000), scale_factor=1.0)
    original = assemble_prime_galerkin_closed_form(_probe(20000), scale_factor=1.0)

    assert receipt["discarded_prime_power_count"] > 0
    assert receipt["discarded_prime_weight"] > 0.0
    assert receipt["tail_centered_energy_norm"] > 0.0
    assert receipt["tail_offset_norm"] > 0.0
    assert receipt["tail_cancellation_max_abs_error"] == 0.0
    assert receipt["full_decomposition_max_abs_error"] < 1e-12
    assert np.max(np.abs(receipt["original_matrix"] - original["matrix"])) < 1e-12


def test_local_renormalized_family_does_not_promote_global_levy_or_rh_authority() -> None:
    receipt = assemble_prime_renormalized_components(_probe(2000), scale_factor=1.0)

    assert receipt["authority"] == "T1_ANALYTIC_CLOSED_FORM_DIAGNOSTIC"
    assert receipt["local_prime_form_stabilizes_after_support_saturation"] is True
    assert receipt["global_standard_levy_measure_constructed"] is False
    assert receipt["globalization_across_unbounded_support_proven"] is False
    assert receipt["global_weil_positivity_proven"] is False
    assert receipt["rh_proven"] is False
