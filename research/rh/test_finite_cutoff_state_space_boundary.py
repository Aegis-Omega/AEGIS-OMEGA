from __future__ import annotations

from research.rh.finite_cutoff_state_space_boundary import (
    build_state_space_refutation_receipt,
    evaluate_odd_bump_witness,
)


def test_finite_cutoff_multiplier_is_refuted_only_on_the_declared_spectral_surrogate() -> None:
    receipt = build_state_space_refutation_receipt(p_cutoff=100)

    assert receipt["classification"] == "REFUTED_ON_SPECTRAL_CCINFINITY_ZERO_MOMENT_SURROGATE"
    assert receipt["symbol_at_zero_strictly_negative"] is True
    assert receipt["odd_ccinfinity_witness_exists"] is True
    assert receipt["zero_moment_by_odd_symmetry"] is True
    assert receipt["finite_cutoff_surrogate_q_negative"] is True


def test_compact_spectral_bump_is_not_silently_promoted_to_paley_wiener_test_space() -> None:
    receipt = build_state_space_refutation_receipt(p_cutoff=100)

    assert receipt["spectral_witness_compact_support"] is True
    assert receipt["spectral_witness_entire"] is False
    assert receipt["paley_wiener_image_membership"] is False
    assert receipt["classical_weil_admissible_space_refuted"] is False
    assert receipt["untruncated_renormalized_weil_form_refuted"] is False
    assert receipt["global_weil_positivity_proven"] is False
    assert receipt["rh_proven"] is False


def test_executable_odd_bump_witness_is_negative_for_a_finite_cutoff_fixture() -> None:
    witness = evaluate_odd_bump_witness(p_cutoff=100, epsilon=0.05, n_grid=8193)

    assert witness["authority"] == "T1_NUMERICAL_WITNESS"
    assert witness["support_inside_negative_symbol_region"] is True
    assert abs(witness["discrete_moment"]) < 1e-12
    assert witness["quadratic_form"] < 0.0
    assert witness["classical_weil_admissible_space_refuted"] is False
    assert witness["rh_proven"] is False
