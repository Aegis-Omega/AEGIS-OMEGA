from __future__ import annotations

from research.rh.run_phi_spectral_probe import (
    CANONICAL_CONFIG,
    build_canonical_payload,
)


def test_canonical_phi_payload_is_t1_only_and_covers_all_controls() -> None:
    payload = build_canonical_payload()

    assert payload["authority"] == "T1_NUMERICAL_DIAGNOSTIC"
    assert payload["config"] == {
        "tau": 2.0,
        "p_cutoff": 100,
        "k_basis_dim": 4,
        "n_quad": 2048,
        "t_bound": 50.0,
        "max_prime_shift": None,
        "zero_tolerance": 1e-10,
        "negative_tolerance": 1e-8,
    }
    assert set(payload["results"]) == {
        "uniform",
        "phi",
        "sqrt2",
        "sqrt3",
        "e",
        "pi",
        "liouville_trunc4",
    }
    assert payload["global_weil_positivity_proven"] is False
    assert payload["rh_proven"] is False
    assert payload["liminf_proven"] is False


def test_canonical_config_is_frozen_for_replay() -> None:
    assert CANONICAL_CONFIG.tau == 2.0
    assert CANONICAL_CONFIG.p_cutoff == 100
    assert CANONICAL_CONFIG.k_basis_dim == 4
    assert CANONICAL_CONFIG.n_quad == 2048
    assert CANONICAL_CONFIG.t_bound == 50.0
    assert CANONICAL_CONFIG.max_prime_shift is None
