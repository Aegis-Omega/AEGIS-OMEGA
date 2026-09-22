"""Replay checks for the corrected T1 moment-restricted spectral-gap receipt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness.sdk.weil_spectral_inertia_probe import T1_AUTHORITY
from research.rh.weil_moment_restricted_gap_probe import (
    CLASSIFICATION,
    PROBE_ID,
    TARGET_OBLIGATION,
    ZETA_ZERO_ORDINATES,
    _config,
    measure_extra_constraint,
    measure_moment_restricted,
    measure_scalar_shift,
    measure_weil_pole_constraint,
    measure_zero_side_crosscheck,
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
    assert committed["classification"] == CLASSIFICATION


def test_retraction_of_the_earlier_reading_is_recorded(committed):
    """The v1.0 receipt claimed the pole did not explain the gap; it did."""
    retracted = {r["field"]: r for r in committed["retracted_claims"]}
    assert retracted["pole_moment_explains_obstruction"]["was"] is False
    assert retracted["pole_moment_explains_obstruction"]["now"] is True
    assert retracted["classification"]["was"] == "NEGATIVE_NUMERICAL_EVIDENCE"
    assert committed["pole_moment_explains_obstruction"] is True
    assert committed["obstruction_is_probe_constraint_artefact"] is True


def test_gap_under_the_probe_constraint_still_replays(committed):
    """The measurement itself was right; only its interpretation was not."""
    observed = measure_moment_restricted(_config(p_cutoff=1000, k_basis_dim=20))
    assert observed["n_negative"] == 1
    case = next(c for c in committed["basis_dimension_sweep_under_probe_constraint"]
                if c["k_basis_dim"] == 20)
    assert _within(case["lambda_min_interval"], observed["lambda_min"])


def test_weil_pole_constraint_removes_the_negative_direction():
    """Re h(i/2) = 0 leaves no negative eigenvalue; the probe constraint leaves one."""
    cfg = _config(p_cutoff=5000, k_basis_dim=20)
    assert measure_moment_restricted(cfg)["n_negative"] == 1
    assert measure_weil_pole_constraint(cfg)["n_negative"] == 0
    assert measure_weil_pole_constraint(cfg, both_parts=True)["n_negative"] == 0


def test_pole_constraint_sweep_is_uniform(committed):
    for case in committed["weil_pole_constraint_sweep"]:
        assert case["re_h_i_half_zero"]["n_negative"] == 0
        assert case["h_i_half_zero"]["n_negative"] == 0


def test_spectral_side_exponential_weight_is_not_the_pole():
    """The retracted functional leaves the gap intact, which is why it misled."""
    observed = measure_extra_constraint(
        _config(p_cutoff=1000, k_basis_dim=20), kind="t_side_exponential", parameter=20.0
    )
    assert observed["n_negative"] == 1
    assert observed["lambda_min"] < -10.0


def test_zero_side_rebuild_matches_the_probe(committed):
    """Independent reconstruction from zeta zeros agrees with the quadrature."""
    assert len(ZETA_ZERO_ORDINATES) == 100
    assert abs(ZETA_ZERO_ORDINATES[0] - 14.134725141734695) < 1e-12
    cross = measure_zero_side_crosscheck(_config(p_cutoff=1000, k_basis_dim=20))
    recorded = committed["zero_side_crosscheck"]
    assert cross["relative_frobenius_difference"] < recorded["relative_frobenius_difference_below"]
    assert _within(recorded["lambda_min_zeros_interval"], cross["lambda_min_zeros"])
    assert cross["zero_sum_lambda_min"] > -1e-10
    assert "not RH" in recorded["caveat"]


def test_scalar_shift_diverges_while_the_gap_stays_pinned(committed):
    cases = committed["prime_cutoff_sweep_under_probe_constraint"]
    shifts = [c["scalar_shift_S_P_0_interval"][1] for c in cases]
    lambdas = [c["lambda_min_interval"][1] for c in cases]
    assert shifts[0] > shifts[-1] + 100.0
    assert max(lambdas) - min(lambdas) < 1e-3
    assert committed["scalar_shift_explains_obstruction"] is False
    observed = measure_scalar_shift(_config(p_cutoff=20000, k_basis_dim=20))
    assert _within(cases[-1]["scalar_shift_S_P_0_interval"], observed)


def test_interlacing_caveat_is_carried(committed):
    assert "Cauchy interlacing" in committed["interlacing_caveat"]
