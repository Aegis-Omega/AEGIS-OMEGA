"""Replay checks for the T1 moment-restricted spectral-gap receipt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness.sdk.weil_spectral_inertia_probe import T1_AUTHORITY
from research.rh.weil_moment_restricted_gap_probe import (
    PROBE_ID,
    TARGET_OBLIGATION,
    _config,
    build_receipt,
    measure_extra_constraint,
    measure_moment_restricted,
    measure_negative_direction,
    measure_scalar_shift,
)

RECEIPT_PATH = Path(__file__).resolve().parent / "receipts" / "weil_moment_restricted_gap_v1.json"


@pytest.fixture(scope="module")
def committed():
    return json.loads(RECEIPT_PATH.read_text())


def _within(interval, value):
    return interval[0] <= value <= interval[1]


def test_committed_receipt_is_content_addressed(committed):
    payload = {k: v for k, v in committed.items() if k != "receipt_sha256"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == committed["receipt_sha256"]


def test_receipt_claims_no_authority(committed):
    assert committed["authority"] == T1_AUTHORITY
    assert committed["rh_authority"] == "NONE"
    assert committed["rh_proven"] is False
    assert committed["global_weil_positivity_proven"] is False
    assert committed["refutes"] is None
    assert committed["probe_id"] == PROBE_ID
    assert committed["target_obligation"] == TARGET_OBLIGATION


def test_interlacing_caveat_is_carried(committed):
    """The shrinking tables are meaningless without it, so it must ship."""
    assert "Cauchy interlacing" in committed["interlacing_caveat"]


def test_epsilon_does_not_tend_to_zero(committed):
    assert committed["epsilon_tends_to_zero"] is False
    magnitudes = [
        abs(case["lambda_min_interval"][1]) for case in committed["basis_dimension_sweep"]
    ]
    assert min(magnitudes) > 10.0
    assert all(case["n_negative"] == 1 for case in committed["basis_dimension_sweep"])


def test_obstruction_is_rank_one_and_replays(committed):
    observed = measure_moment_restricted(_config(p_cutoff=1000, k_basis_dim=20))
    assert observed["n_negative"] == 1
    case = next(c for c in committed["basis_dimension_sweep"] if c["k_basis_dim"] == 20)
    assert _within(case["lambda_min_interval"], observed["lambda_min"])


def test_scalar_shift_diverges_while_lambda_min_stays_pinned(committed):
    shifts = [
        case["scalar_shift_S_P_0_interval"][1] for case in committed["prime_cutoff_sweep"]
    ]
    assert shifts[0] > shifts[-1] + 100.0
    lambdas = [case["lambda_min_interval"][1] for case in committed["prime_cutoff_sweep"]]
    assert max(lambdas) - min(lambdas) < 1e-3
    assert committed["scalar_shift_explains_obstruction"] is False
    observed = measure_scalar_shift(_config(p_cutoff=20000, k_basis_dim=20))
    assert _within(committed["prime_cutoff_sweep"][-1]["scalar_shift_S_P_0_interval"], observed)


def test_pole_moment_does_not_explain_the_obstruction(committed):
    assert committed["pole_moment_explains_obstruction"] is False
    poles = [c for c in committed["extra_constraint_cases"] if c["kind"] == "pole"]
    point = next(c for c in committed["extra_constraint_cases"] if c["kind"] == "point")
    assert poles, "pole constraint cases must be recorded"
    for case in poles:
        assert abs(case["lambda_min_interval"][1]) > 10.0
    assert abs(point["lambda_min_interval"][1]) < 1.0

    observed = measure_extra_constraint(_config(p_cutoff=1000, k_basis_dim=20), kind="pole", parameter=20.0)
    recorded = next(c for c in poles if c["parameter"] == 20.0)
    assert _within(recorded["lambda_min_interval"], observed["lambda_min"])


def test_negative_direction_sits_at_the_origin(committed):
    recorded = committed["negative_direction"]
    assert recorded["coincides_with_negative_archimedean_weight_at_origin"] is True
    observed = measure_negative_direction(_config(p_cutoff=1000, k_basis_dim=20))
    assert _within(recorded["peak_abscissa_interval"], observed["peak_abscissa"])
    assert _within(
        recorded["l2_mass_fraction_within_5_interval"], observed["l2_mass_fraction_within_5"]
    )
    assert observed["l2_mass_fraction_within_5"] > 0.9


def test_rebuilt_receipt_agrees_on_the_discrete_invariants(committed):
    rebuilt = build_receipt()
    assert rebuilt["obstruction_rank"] == committed["obstruction_rank"] == 1
    assert [c["n_negative"] for c in rebuilt["basis_dimension_sweep"]] == [
        c["n_negative"] for c in committed["basis_dimension_sweep"]
    ]
