import json
from pathlib import Path
import subprocess
import sys

import pytest

from harness.sdk.guinand_weil_arb import (
    ArbGalerkinError,
    ArbGalerkinSpecV1,
    prime_powers_up_to,
    verify_cutoff_free_galerkin,
)


def test_prime_power_enumeration_is_exact_and_complete_for_small_cutoff():
    assert prime_powers_up_to(5) == ((2, 2), (3, 3), (4, 2), (5, 5))


def test_small_cutoff_free_galerkin_matrix_has_rigorous_entry_enclosures():
    receipt = verify_cutoff_free_galerkin(ArbGalerkinSpecV1(c=5, N=1, prec_bits=192))
    assert receipt.valid is True
    assert receipt.dimension == 3
    assert receipt.cutoff_free_entry_enclosures_verified is True
    assert receipt.interval_inertia_verified is True
    assert receipt.n_positive + receipt.n_negative == receipt.dimension
    assert receipt.undetermined_pivot is None
    assert receipt.galerkin_semantics_verified is False
    assert receipt.global_weil_positivity_proven is False
    assert receipt.rh_proven is False


def test_receipt_is_deterministic_for_identical_spec():
    spec = ArbGalerkinSpecV1(c=5, N=1, prec_bits=192)
    first = verify_cutoff_free_galerkin(spec)
    second = verify_cutoff_free_galerkin(spec)
    assert first.matrix_root == second.matrix_root
    assert first.pivot_root == second.pivot_root
    assert first.receipt_root == second.receipt_root


def test_spec_rejects_unsafe_or_unbounded_inputs():
    with pytest.raises(ArbGalerkinError, match="CUTOFF_INVALID"):
        ArbGalerkinSpecV1(c=1, N=1, prec_bits=192)
    with pytest.raises(ArbGalerkinError, match="BAND_INVALID"):
        ArbGalerkinSpecV1(c=5, N=-1, prec_bits=192)
    with pytest.raises(ArbGalerkinError, match="PRECISION_TOO_LOW"):
        ArbGalerkinSpecV1(c=5, N=1, prec_bits=64)


def test_cli_verify_galerkin_emits_fail_closed_packet(tmp_path: Path):
    output_path = tmp_path / "galerkin-receipt.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/weil-proof.py",
            "verify-galerkin",
            "--c",
            "5",
            "--N",
            "1",
            "--prec",
            "192",
            "--output",
            str(output_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    packet = json.loads(output_path.read_text(encoding="utf-8"))
    assert packet["packet_kind"] == "AEGIS_ARB_GALERKIN_PACKET_V1"
    assert packet["verification"]["cutoff_free_entry_enclosures_verified"] is True
    assert packet["verification"]["interval_inertia_verified"] is True
    assert packet["verification"]["galerkin_semantics_verified"] is False
    assert packet["verification"]["global_weil_positivity_proven"] is False
    assert packet["verification"]["rh_proven"] is False
