import math

import numpy as np

from harness.sdk.epstein_lattice_weil_probe import (
    EpsteinWeilProbeConfig,
    arithmetic_support_certificate,
    d20_companion_coefficients,
    d20_euler_coefficients,
    d20_principal_coefficients,
    generalized_log_derivative_coefficients,
    run_d20_same_discriminant_control,
    evaluate_d20_fixed_integer_witness,
    d20_fixed_witness_arithmetic_decomposition,
    quadratic_euler_first_impulse,
)


def test_d20_principal_starts_at_four_but_log_derivative_leaks_at_six() -> None:
    a = d20_principal_coefficients(40)
    assert a[1] == 1.0
    assert a[2] == 0.0
    assert a[3] == 0.0
    assert a[4] == 1.0
    assert a[5] == 1.0
    assert a[6] == 2.0

    lam = generalized_log_derivative_coefficients(a)
    assert abs(lam[6] - 2.0 * math.log(6.0)) < 1e-12
    cert = arithmetic_support_certificate(a)
    assert cert["prime_power_only"] is False
    assert 6 in cert["non_prime_power_support"]


def test_d20_euler_classsum_log_derivative_is_prime_power_supported() -> None:
    a = d20_euler_coefficients(128)
    cert = arithmetic_support_certificate(a)
    assert cert["prime_power_only"] is True
    assert cert["non_prime_power_support"] == ()


def test_d20_principal_decomposition_matches_two_euler_components_on_prefix() -> None:
    max_n = 128
    principal = 2.0 * d20_principal_coefficients(max_n)
    classsum = d20_euler_coefficients(max_n)
    companion = d20_companion_coefficients(max_n)
    assert np.array_equal(principal[1:], (classsum + companion)[1:])


def test_same_discriminant_spectral_control_separates_at_L_3p5() -> None:
    receipt = run_d20_same_discriminant_control(
        EpsteinWeilProbeConfig(
            support_length=3.5,
            basis_dim=24,
            t_bound=600.0,
            dt=0.05,
            chunk_size=2048,
        )
    )
    assert receipt["principal_lambda_min"] < -0.25
    assert receipt["euler_classsum_lambda_min"] > 0.15
    assert receipt["principal_minimizer_on_euler_classsum"] > 1.0
    assert receipt["same_archimedean_factor"] is True
    assert receipt["same_conductor"] is True
    assert receipt["proof_authority"] is False
    assert receipt["rh_proven"] is False


def test_fixed_integer_witness_separates_same_discriminant_pair() -> None:
    receipt = evaluate_d20_fixed_integer_witness(
        EpsteinWeilProbeConfig(
            support_length=3.5,
            basis_dim=24,
            t_bound=600.0,
            dt=0.05,
            chunk_size=2048,
        )
    )
    assert receipt["modes"] == (4, 6, 8, 10, 12, 16, 18)
    assert receipt["integer_coefficients"] == (22, 10, 6, 3, 2, -2, -1)
    assert receipt["optimizer_used_for_evaluation"] is False
    assert receipt["principal_rayleigh"] < -0.05
    assert receipt["euler_classsum_rayleigh"] > 5.0
    assert receipt["proof_authority"] is False
    assert receipt["rh_proven"] is False


def test_fixed_witness_arithmetic_decomposition_exposes_composite_leakage() -> None:
    receipt = d20_fixed_witness_arithmetic_decomposition(support_length=3.5)
    by_n = {row["n"]: row for row in receipt["contributions"]}

    assert receipt["t_grid_used"] is False
    assert receipt["archimedean_difference"] == 0.0
    assert receipt["tail_bound_needed_for_pairwise_difference"] is False
    assert receipt["total_arithmetic_delta_principal_minus_euler"] < -5.4
    assert receipt["non_prime_power_leakage_delta"] < -2.5
    assert by_n[6]["prime_power"] is False
    assert by_n[6]["delta_principal_minus_euler"] < -1.0
    assert by_n[14]["prime_power"] is False
    assert by_n[21]["prime_power"] is False
    assert receipt["proof_authority"] is False
    assert receipt["rh_proven"] is False


def test_quadratic_euler_first_impulse_windows() -> None:
    square = quadratic_euler_first_impulse(-4)
    hexagonal = quadratic_euler_first_impulse(-3)
    d19 = quadratic_euler_first_impulse(-19)
    d163 = quadratic_euler_first_impulse(-163)

    assert square["first_n"] == 2
    assert square["local_type"] == "ramified"

    assert hexagonal["first_n"] == 3
    assert hexagonal["local_type"] == "ramified"

    assert d19["first_n"] == 4
    assert d19["prime"] == 2
    assert d19["exponent"] == 2
    assert d19["local_type"] == "inert"

    assert d163["first_n"] == 4
    assert d163["prime"] == 2
    assert d163["exponent"] == 2
    assert d163["local_type"] == "inert"

    assert square["log_window"] < hexagonal["log_window"] < d19["log_window"]
