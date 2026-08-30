from __future__ import annotations

import math

import numpy as np

from harness.sdk.weil_spectral_inertia_probe import (
    SpectralProbeConfig,
    WeilSpectralInertiaProbe,
    generalized_inertia,
    truncated_liouville_control,
)


def test_prime_cutoff_is_not_silently_replaced_by_tau_support_cutoff() -> None:
    unrestricted = WeilSpectralInertiaProbe(
        SpectralProbeConfig(
            tau=2.0,
            p_cutoff=2000,
            k_basis_dim=3,
            n_quad=512,
            t_bound=30.0,
            max_prime_shift=None,
        )
    )
    support_limited = WeilSpectralInertiaProbe(
        SpectralProbeConfig(
            tau=2.0,
            p_cutoff=2000,
            k_basis_dim=3,
            n_quad=512,
            t_bound=30.0,
            max_prime_shift=4.0,
        )
    )

    assert unrestricted.prime_power_count > support_limited.prime_power_count
    assert max(term.shift for term in unrestricted.prime_power_terms) > 4.0
    assert max(term.shift for term in support_limited.prime_power_terms) < 4.0


def test_moment_constraint_is_exact_nullspace_reduction_not_regularization() -> None:
    probe = WeilSpectralInertiaProbe(
        SpectralProbeConfig(
            tau=2.0,
            p_cutoff=100,
            k_basis_dim=4,
            n_quad=1024,
            t_bound=40.0,
        )
    )

    reduced = probe.assemble_moment_restricted(scale_factor=1.0)

    assert reduced.M.shape == (probe.dim - 1, probe.dim - 1)
    assert reduced.G.shape == (probe.dim - 1, probe.dim - 1)
    assert reduced.constraint_basis.shape == (probe.dim, probe.dim - 1)
    assert np.linalg.norm(reduced.moment_vector @ reduced.constraint_basis) < 1e-10
    assert float(np.min(np.linalg.eigvalsh(reduced.G))) > 0.0


def test_generalized_inertia_is_congruence_invariant_on_same_span() -> None:
    M = np.diag([-2.0, -0.5, 1.0, 3.0])
    G = np.diag([1.0, 2.0, 3.0, 4.0])
    S = np.array(
        [
            [1.0, 0.2, 0.0, 0.0],
            [0.0, 1.0, 0.1, 0.0],
            [0.0, 0.0, 1.0, 0.3],
            [0.1, 0.0, 0.0, 1.0],
        ]
    )

    original = generalized_inertia(M, G)
    transformed = generalized_inertia(S.T @ M @ S, S.T @ G @ S)

    assert original.nu_minus == transformed.nu_minus == 2
    assert original.nu_plus == transformed.nu_plus == 2
    assert original.nu_zero == transformed.nu_zero == 0


def test_phi_probe_is_t1_diagnostic_and_cannot_promote_weil_or_rh() -> None:
    probe = WeilSpectralInertiaProbe(
        SpectralProbeConfig(
            tau=2.0,
            p_cutoff=100,
            k_basis_dim=3,
            n_quad=1024,
            t_bound=40.0,
        )
    )

    phi = (1.0 + math.sqrt(5.0)) / 2.0
    receipt = probe.run_scale_probe({"uniform": 1.0, "phi": phi})

    assert receipt["authority"] == "T1_NUMERICAL_DIAGNOSTIC"
    assert receipt["phi_nonresonant_positivity_hypothesis"] in {
        "NOT_SUPPORTED",
        "REFUTED_AS_CLOSURE_MECHANISM_ON_TESTED_FINITE_SECTIONS",
    }
    assert receipt["global_weil_positivity_proven"] is False
    assert receipt["rh_proven"] is False
    assert set(receipt["results"]) == {"uniform", "phi"}


def test_liouville_control_is_explicitly_truncated_not_claimed_exact() -> None:
    control = truncated_liouville_control(terms=4)

    assert control["label"] == "TRUNCATED_LIOUVILLE_APPROXIMATION"
    assert control["is_exact_liouville_number"] is False
    assert 0.0 < control["value"] < 1.0
