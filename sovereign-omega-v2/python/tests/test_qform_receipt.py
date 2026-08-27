from __future__ import annotations

import math

import pytest

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
    rows_65010 = exact_prime_power_census(65010)
    assert len(rows_100) == 35
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


def test_spec_rejects_precision_below_certification_floor() -> None:
    with pytest.raises(QFormReceiptError, match="PRECISION_OUT_OF_RANGE"):
        QFormSpecV1(P_cutoff=100, sigma="0.8", du="0.01", U_max="6", prec_bits=64)
