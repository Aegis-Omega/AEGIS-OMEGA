import importlib

import pytest


fixed_point = importlib.import_module("agents.quantummanifold.fixed_point")


def test_fixed_point_component_exists_before_behavior_contracts():
    assert fixed_point is not None


@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_qm_red_011_rejects_invalid_canonical_numeric_domain(value):
    with pytest.raises(ValueError, match="^FIXED_POINT_DOMAIN_ERROR$"):
        fixed_point.require_canonical_metric(value)


def test_qm_red_011_rejects_serialized_metric_overflow():
    with pytest.raises(ValueError, match="^SCORE_RANGE_EXCEEDED$"):
        fixed_point.require_canonical_metric(9_007_199_254_740_992)


def test_qm_red_012_rejects_nonpositive_epsilon():
    for epsilon_ppm in (0, -1):
        with pytest.raises(ValueError, match="^INVALID_STABILIZER$"):
            fixed_point.require_positive_stabilizer(epsilon_ppm)


def test_mul_ppm_uses_exact_floor_integer_arithmetic():
    assert fixed_point.mul_ppm(333_333, 333_333) == 111_110


def test_ranking_score_matches_normative_fixed_point_formula():
    score = fixed_point.ranking_score_ppm(
        alpha_ppm=1_000_000,
        information_gain_ppm=1_000_000,
        beta_ppm=1_000_000,
        closure_leverage_ppm=500_000,
        gamma_ppm=1_000_000,
        falsification_value_ppm=500_000,
        epsilon_ppm=1,
        cost_ppm=1_000_001,
    )
    assert score == 1_999_996
