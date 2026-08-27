from __future__ import annotations

import math

import pytest

from harness.sdk.qform_error_bound import build_analytic_error_budget
from harness.sdk.qform_galerkin_crossprobe import (
    QFormGalerkinCrossSpecV1,
    build_qform_galerkin_cross_receipt,
)
from harness.sdk.qform_operator import (
    QFormOperatorSpecV1,
    build_operator_receipt,
    build_preflight_receipt,
    exact_prime_power_indices,
    verify_preflight_receipt,
)
from harness.sdk.qform_receipt import (
    CERTIFIED_INTERVAL,
    EMPIRICAL_FIXTURE,
    EXACT,
    NUMERICALLY_VERIFIED,
    QFormReceiptError,
    QFormSpecV1,
    build_qform_receipt,
    exact_prime_power_census,
    gaussian_cutoff_certificate,
    weakest_authority,
)


COMMIT = "a" * 40
TREE = "b" * 40


def test_exact_prime_power_counts_lock_reported_census() -> None:
    rows_100 = exact_prime_power_census(100)
    rows_5000 = exact_prime_power_census(5000)
    rows_65010 = exact_prime_power_census(65010)
    assert len(rows_100) == 35
    assert len(rows_5000) == 711
    assert len({p for _q, p, _k in rows_5000}) == 669
    assert len(rows_65010) == 6586
    assert len({p for _q, p, _k in rows_65010}) == 6494
    assert rows_100[:6] == (
        (2, 2, 1),
        (3, 3, 1),
        (4, 2, 2),
        (5, 5, 1),
        (7, 7, 1),
        (8, 2, 3),
    )


def test_authority_lattice_is_fail_closed() -> None:
    assert weakest_authority(EXACT, CERTIFIED_INTERVAL) == CERTIFIED_INTERVAL
    assert weakest_authority(EXACT, NUMERICALLY_VERIFIED) == NUMERICALLY_VERIFIED
    assert weakest_authority(EXACT, CERTIFIED_INTERVAL, EMPIRICAL_FIXTURE) == EMPIRICAL_FIXTURE
    with pytest.raises(QFormReceiptError, match="AUTHORITY_UNKNOWN"):
        weakest_authority(EXACT, "PROVED_BY_CONFIDENCE")


def test_gaussian_cutoff_constant_matches_analytic_law() -> None:
    cert = gaussian_cutoff_certificate(
        sigma="0.8",
        epsilon="1e-11",
        P_cutoff=65010,
        prec_bits=192,
    )
    c_mid = float(cert["C_epsilon_ball"]["mid"])
    expected = 2.0 * math.sqrt(math.log(1e11))
    assert abs(c_mid - expected) < 1e-12
    assert 10.06 < c_mid < 10.08
    assert cert["cutoff_relation_verified"] is True
    assert cert["envelope_below_epsilon_verified"] is True
    assert cert["scope"] == "SCALAR_GAUSSIAN_ENVELOPE_ONLY"


def test_receipt_promotes_only_finite_formula_arithmetic() -> None:
    receipt = build_qform_receipt(
        QFormSpecV1(P_cutoff=100, sigma="0.8", du="0.01", U_max="6", prec_bits=192),
        source_commit=COMMIT,
        source_tree=TREE,
    ).to_dict()

    assert receipt["receipt_version"] == "QFormReceiptV1"
    assert receipt["exact_census"]["status"] == EXACT
    assert receipt["exact_census"]["integer_crosscheck_verified"] is True
    assert receipt["exact_census"]["prime_powers_count"] == 35
    assert receipt["evaluations"]["main_term"]["status"] == CERTIFIED_INTERVAL
    assert receipt["evaluations"]["prime_trace_functional"]["status"] == CERTIFIED_INTERVAL
    assert receipt["evaluations"]["spectral_symbol_gamma_fixture"]["status"] == EMPIRICAL_FIXTURE
    assert receipt["finite_formula_authority"] == CERTIFIED_INTERVAL
    assert receipt["overall_authority"] == EMPIRICAL_FIXTURE
    assert receipt["formula_to_weil_operator_identity_proven"] is False
    assert receipt["tail_order_theorem_verified"] is False
    assert receipt["global_weil_positivity_proven"] is False
    assert receipt["rh_proven"] is False
    assert len(receipt["receipt_root"]) == 64


def test_reported_gamma1_fixture_is_rigorously_negative_at_finite_cutoff() -> None:
    receipt = build_qform_receipt(
        QFormSpecV1(P_cutoff=65010, sigma="0.8", du="0.005", U_max="8", prec_bits=192),
        gamma_fixture="14.134725",
        source_commit=COMMIT,
        source_tree=TREE,
    ).to_dict()
    symbol = receipt["evaluations"]["spectral_symbol_gamma_fixture"]
    assert symbol["status"] == EMPIRICAL_FIXTURE
    assert float(symbol["undamped_arb_ball"]["mid"]) < -30.0


def test_crossprobe_binds_scale_but_refuses_semantic_promotion() -> None:
    receipt = build_qform_galerkin_cross_receipt(
        QFormGalerkinCrossSpecV1(
            c=10,
            sigma="0.1",
            epsilon="1e-6",
            N=0,
            prec_bits=128,
        ),
        source_commit=COMMIT,
        source_tree=TREE,
    ).to_dict()

    assert receipt["finite_scale_binding_authority"] == CERTIFIED_INTERVAL
    assert receipt["scale_binding"]["c_equals_P_cutoff_by_construction"] is True
    assert receipt["scale_binding"]["L_ge_C_sigma_verified"] is True
    assert receipt["scale_binding"]["gaussian_envelope_below_epsilon_verified"] is True
    assert receipt["galerkin_replay"]["c"] == 10
    assert receipt["galerkin_replay"]["N"] == 0
    assert receipt["galerkin_replay"]["galerkin_semantics_verified"] is False
    assert receipt["overall_authority"] == EMPIRICAL_FIXTURE
    assert receipt["gaussian_to_galerkin_semantics_verified"] is False
    assert receipt["compact_support_bridge_verified"] is False
    assert receipt["formula_to_weil_operator_identity_proven"] is False
    assert receipt["global_weil_positivity_proven"] is False
    assert receipt["rh_proven"] is False
    assert len(receipt["receipt_root"]) == 64


def test_spec_rejects_precision_below_certification_floor() -> None:
    with pytest.raises(QFormReceiptError, match="PRECISION_OUT_OF_RANGE"):
        QFormSpecV1(P_cutoff=100, sigma="0.8", du="0.01", U_max="6", prec_bits=64)


def _operator_spec(**overrides: object) -> QFormOperatorSpecV1:
    values: dict[str, object] = {
        "P_cutoff": 100,
        "sigma": "0.8",
        "du": "0.04",
        "U_max": "4.1",
        "N_F": 8,
        "h": "1.0",
        "gamma_max": "14.2",
        "prec_bits": 192,
    }
    values.update(overrides)
    return QFormOperatorSpecV1(**values)  # type: ignore[arg-type]


def test_operator_prime_power_indices_preserve_exact_structure() -> None:
    terms = exact_prime_power_indices(100)
    assert len(terms) == 35
    assert (terms[0].q, terms[0].p, terms[0].k) == (2, 2, 1)
    assert terms[2].tau_formula == "2*log(2)"
    assert terms[2].weight_formula == "log(2)/sqrt(4)"


def test_zero_discretion_preflight_blocks_insufficient_fourier_coverage() -> None:
    receipt = build_preflight_receipt(_operator_spec(N_F=1, h="1", gamma_max="4")).to_dict()
    assert receipt["blocked"] is True
    assert receipt["status"] == "BLOCKED"
    assert receipt["reason"] == "FOURIER_COVERAGE_INSUFFICIENT"
    with pytest.raises(QFormReceiptError, match="PREFLIGHT_BLOCKED"):
        verify_preflight_receipt(receipt, _operator_spec(N_F=1, h="1", gamma_max="4"))


def test_preflight_receipt_is_invalidated_by_parameter_change() -> None:
    original = _operator_spec()
    receipt = build_preflight_receipt(original).to_dict()
    verify_preflight_receipt(receipt, original)
    mutated = _operator_spec(gamma_max="14.3")
    with pytest.raises(QFormReceiptError, match="PREFLIGHT_PARAMETER_ROOT_MISMATCH"):
        verify_preflight_receipt(receipt, mutated)


def test_translation_operator_probe_matches_finite_gaussian_formula_without_promotion() -> None:
    receipt = build_operator_receipt(_operator_spec()).to_dict()
    assert receipt["preflight_status"] == "PASS"
    assert receipt["prime_power_count"] == 35
    assert receipt["discretization_status"] == NUMERICALLY_VERIFIED
    assert receipt["observed_relative_error_to_closed_form"] < 2.0e-6
    ratio = receipt["observed_refinement_ratio"]
    assert ratio is not None
    assert 3.8 < ratio < 4.2
    assert receipt["discretization_order_theorem_verified"] is False
    assert receipt["finite_domain_error_theorem_verified"] is False
    assert receipt["formula_to_weil_operator_identity_proven"] is False
    assert receipt["global_weil_positivity_proven"] is False
    assert receipt["rh_proven"] is False


def test_operator_probe_rejects_stale_preflight_before_numerics() -> None:
    original = _operator_spec()
    stale = build_preflight_receipt(original).to_dict()
    with pytest.raises(QFormReceiptError, match="PREFLIGHT_PARAMETER_ROOT_MISMATCH"):
        build_operator_receipt(_operator_spec(du="0.02"), preflight_payload=stale)


def test_analytic_error_budget_computes_constants_but_refuses_theorem_promotion() -> None:
    operator = build_operator_receipt(_operator_spec()).to_dict()
    receipt = build_analytic_error_budget(_operator_spec()).to_dict()

    observed_abs_error = abs(
        operator["discrete_prime_trace_numeric"] - operator["closed_form_prime_trace_numeric"]
    )
    assert receipt["receipt_kind"] == "AEGIS_QFORM_ANALYTIC_ERROR_BUDGET_V1"
    assert receipt["constant_arithmetic_status"] == CERTIFIED_INTERVAL
    assert float(receipt["K_disc_ball"]["mid"]) > 0.0
    assert float(receipt["finite_domain_tail_bound_ball"]["mid"]) > 0.0
    assert receipt["conditional_absolute_error_bound_upper"] > observed_abs_error
    assert receipt["gaussian_tail_inequality_machine_bound"] is False
    assert receipt["composite_trapezoid_theorem_machine_bound"] is False
    assert receipt["quotient_stability_machine_bound"] is False
    assert receipt["analytic_error_bound_machine_bound"] is False
    assert receipt["formula_to_weil_operator_identity_proven"] is False
    assert receipt["global_weil_positivity_proven"] is False
    assert receipt["rh_proven"] is False


def test_analytic_error_budget_fails_closed_without_positive_shift_margin() -> None:
    with pytest.raises(QFormReceiptError, match="DOMAIN_SHIFT_MARGIN_NONPOSITIVE"):
        build_analytic_error_budget(_operator_spec(U_max="2.0"))
