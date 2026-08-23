import json
from pathlib import Path
import subprocess
import sys

import pytest

from harness.sdk.arch_tail_certificate import (
    ArchTailError,
    ArchTailSpecV1,
    verify_arch_tail_budget,
)


def test_small_tail_budget_recomputes_rigorous_positive_upper_bound():
    result = verify_arch_tail_budget(
        ArchTailSpecV1(c=5, N=1, T=32, prec_bits=192, dyadic_count=8)
    )
    assert result.valid is True
    assert result.threshold_verified is True
    assert result.scalar_budget_arithmetic_verified is True
    assert result.trace_budget_strictly_positive is True
    assert result.entry_budget_strictly_positive is True
    assert result.tail_order_theorem_verified is False
    assert result.galerkin_semantics_verified is False
    assert result.global_weil_positivity_proven is False
    assert result.rh_proven is False


def test_tail_budget_receipt_is_deterministic():
    spec = ArchTailSpecV1(c=5, N=1, T=32, prec_bits=192, dyadic_count=8)
    first = verify_arch_tail_budget(spec)
    second = verify_arch_tail_budget(spec)
    assert first.budget_root == second.budget_root
    assert first.receipt_root == second.receipt_root


def test_tail_budget_fails_closed_before_band_threshold():
    result = verify_arch_tail_budget(
        ArchTailSpecV1(c=5, N=4, T=8, prec_bits=192, dyadic_count=8)
    )
    assert result.valid is False
    assert result.threshold_verified is False
    assert "TAIL_CUTOFF_BELOW_PROVEN_BAND_THRESHOLD" in result.errors
    assert result.tail_order_theorem_verified is False


def test_tail_spec_rejects_unbounded_precision_and_dyadic_work():
    with pytest.raises(ArchTailError, match="PRECISION_TOO_LOW"):
        ArchTailSpecV1(c=5, N=1, T=32, prec_bits=64, dyadic_count=8)
    with pytest.raises(ArchTailError, match="DYADIC_COUNT_INVALID"):
        ArchTailSpecV1(c=5, N=1, T=32, prec_bits=192, dyadic_count=0)


def test_cli_verify_tail_budget_emits_non_authoritative_packet(tmp_path: Path):
    output = tmp_path / "tail.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/weil-proof.py",
            "verify-tail-budget",
            "--c", "5",
            "--N", "1",
            "--T", "32",
            "--prec", "192",
            "--dyadic-count", "8",
            "--output", str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    packet = json.loads(output.read_text(encoding="utf-8"))
    assert packet["packet_kind"] == "AEGIS_ARCH_TAIL_BUDGET_PACKET_V1"
    assert packet["verification"]["scalar_budget_arithmetic_verified"] is True
    assert packet["verification"]["tail_order_theorem_verified"] is False
    assert packet["verification"]["global_weil_positivity_proven"] is False
    assert packet["verification"]["rh_proven"] is False
