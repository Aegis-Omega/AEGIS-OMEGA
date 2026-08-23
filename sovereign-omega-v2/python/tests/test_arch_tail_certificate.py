import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from harness.sdk.arch_tail_certificate import (
    ArchTailError,
    ArchTailSpecV1,
    FormalBridgeError,
    bind_formal_bridge_to_tail_budget,
    verify_arch_tail_budget,
    verify_weil_formal_bridge_receipt,
)


_FORMAL_THEOREMS = (
    "divided_difference_offdiag_symmetric",
    "pole_kernel_symmetric",
    "offdiag_entry_symmetric",
    "bounded_positive_tail_preserves_nonnegative",
    "bounded_positive_tail_certifies_negative",
    "gray_zone_can_change_sign",
)


def _formal_bridge_payload() -> dict[str, object]:
    source = Path("sovereign-omega-v2/formal/theories/Weil/FiniteBridge.v")
    payload: dict[str, object] = {
        "receipt_kind": "AEGIS_WEIL_FORMAL_BRIDGE_RECEIPT_V1",
        "authority": "FORMAL_MATH_EVIDENCE_ONLY",
        "source_commit": "a" * 40,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "coq_version_sha256": "1" * 64,
        "compile_log_sha256": "2" * 64,
        "theorem_assumption_log_sha256": {name: "3" * 64 for name in _FORMAL_THEOREMS},
        "theorem_count": len(_FORMAL_THEOREMS),
        "declared_assumptions": 0,
        "global_weil_positivity_proven": False,
        "rh_proven": False,
        "analytic_tail_order_theorem_proven": False,
        "formula_to_weil_operator_identity_proven": False,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


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


def test_formal_bridge_receipt_verifies_local_source_and_closed_theorem_set():
    result = verify_weil_formal_bridge_receipt(_formal_bridge_payload())
    assert result.valid is True
    assert result.source_digest_verified is True
    assert result.theorem_set_verified is True
    assert result.declared_assumptions_verified_zero is True
    assert result.finite_tail_decision_algebra_formally_verified is True
    assert result.tail_order_theorem_verified is False
    assert result.formula_to_weil_operator_identity_proven is False
    assert result.global_weil_positivity_proven is False
    assert result.rh_proven is False


def test_formal_bridge_receipt_rejects_digest_tampering():
    payload = _formal_bridge_payload()
    payload["theorem_assumption_log_sha256"][_FORMAL_THEOREMS[0]] = "4" * 64
    with pytest.raises(FormalBridgeError, match="FORMAL_RECEIPT_DIGEST_MISMATCH"):
        verify_weil_formal_bridge_receipt(payload)


def test_formal_bridge_receipt_rejects_claim_smuggling():
    payload = _formal_bridge_payload()
    payload["analytic_tail_order_theorem_proven"] = True
    canonical = json.dumps(
        {key: value for key, value in payload.items() if key != "receipt_sha256"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    payload["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    with pytest.raises(FormalBridgeError, match="FORMAL_RECEIPT_OVERCLAIM_REJECTED"):
        verify_weil_formal_bridge_receipt(payload)


def test_formal_bridge_binding_keeps_analytic_tail_obligation_open():
    budget = verify_arch_tail_budget(
        ArchTailSpecV1(c=5, N=1, T=32, prec_bits=192, dyadic_count=8)
    )
    binding = bind_formal_bridge_to_tail_budget(budget, _formal_bridge_payload())
    assert binding.valid is True
    assert binding.scalar_budget_arithmetic_verified is True
    assert binding.finite_tail_decision_algebra_formally_verified is True
    assert binding.tail_order_theorem_verified is False
    assert binding.formula_to_weil_operator_identity_proven is False
    assert binding.global_weil_positivity_proven is False
    assert binding.rh_proven is False
    assert "ARCHIMEDEAN_TAIL_OPERATOR_ORDER_THEOREM_NOT_MACHINE_FORMALIZED" in binding.open_obligations


def test_formal_bridge_binding_rejects_invalid_budget_subject():
    budget = verify_arch_tail_budget(
        ArchTailSpecV1(c=5, N=4, T=8, prec_bits=192, dyadic_count=8)
    )
    binding = bind_formal_bridge_to_tail_budget(budget, _formal_bridge_payload())
    assert binding.valid is False
    assert "SCALAR_TAIL_BUDGET_NOT_VERIFIED" in binding.errors
    assert binding.tail_order_theorem_verified is False
