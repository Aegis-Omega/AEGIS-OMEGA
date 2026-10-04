import json
from pathlib import Path
import subprocess
import sys

import pytest

from harness.sdk.sovereign_execution import canonical_hash
from harness.sdk.weil_convergence_bridge import (
    ASSUME_RH,
    ExactIntervalV1,
    ExactRationalV1,
    WeilBridgeError,
    WeilContributionV1,
    WeilFiniteCertificateV1,
    verify_weil_finite_certificate,
)


def h(label: str) -> str:
    return canonical_hash("TEST_WEIL_FINITE_CERT_V1", {"label": label})


def r(n: int, d: int = 1) -> ExactRationalV1:
    return ExactRationalV1(n, d)


def interval(lo: tuple[int, int], hi: tuple[int, int]) -> ExactIntervalV1:
    return ExactIntervalV1(lower=r(*lo), upper=r(*hi))


def contribution(label: str, lo=(1, 1), hi=(1, 1), kind="PRIME_TERM") -> WeilContributionV1:
    return WeilContributionV1(
        contribution_id=label,
        contribution_kind=kind,
        value_interval=interval(lo, hi),
        source_root=h(f"source:{label}"),
    )


def certificate(*, assumptions=(), contributions=None) -> WeilFiniteCertificateV1:
    items = contributions or (
        contribution("p2", (3, 4), (4, 5)),
        contribution("arch", (1, 2), (3, 5), "ARCHIMEDEAN_TERM"),
        contribution("corr", (-1, 10), (-1, 20), "CORRECTION_TERM"),
    )
    return WeilFiniteCertificateV1(
        test_function_digest=h("f"),
        cutoff=13,
        contributions=tuple(items),
        norm_sq=r(2),
        epsilon_r=r(1, 4),
        approximation_delta=r(1, 2),
        approximation_bound_root=h("approx"),
        assumption_tags=tuple(assumptions),
    )


def test_interval_rejects_reversed_bounds():
    with pytest.raises(WeilBridgeError, match="INTERVAL_BOUNDS_REVERSED"):
        ExactIntervalV1(lower=r(2), upper=r(1))


def test_certificate_recomputes_aggregate_interval_from_contributions():
    result = verify_weil_finite_certificate(certificate())
    # lower = 3/4 + 1/2 - 1/10 = 23/20
    # upper = 4/5 + 3/5 - 1/20 = 27/20
    assert (result.aggregate_interval.lower.numerator, result.aggregate_interval.lower.denominator) == (23, 20)
    assert (result.aggregate_interval.upper.numerator, result.aggregate_interval.upper.denominator) == (27, 20)
    assert result.arithmetic_certificate_verified is True
    assert result.finite_lower_bound_verified is True
    assert result.conditional_target_nonnegative is True
    assert result.contribution_semantics_verified is False
    assert result.rh_proven is False


def test_certificate_identity_is_order_independent():
    items = certificate().contributions
    a = verify_weil_finite_certificate(certificate(contributions=items))
    b = verify_weil_finite_certificate(certificate(contributions=tuple(reversed(items))))
    assert a.subject_root == b.subject_root
    assert a.receipt_root == b.receipt_root


def test_duplicate_contribution_identity_fails_closed():
    item = contribution("dup")
    with pytest.raises(WeilBridgeError, match="CONTRIBUTION_DUPLICATE"):
        certificate(contributions=(item, item))


def test_certificate_rejects_target_circularity():
    result = verify_weil_finite_certificate(certificate(assumptions=(ASSUME_RH,)))
    assert result.valid is False
    assert result.circular is True
    assert result.rh_proven is False


def test_negative_aggregate_that_breaks_lower_bound_is_rejected():
    items = (contribution("bad", (-3, 1), (-2, 1)),)
    result = verify_weil_finite_certificate(certificate(contributions=items))
    assert result.valid is False
    assert result.finite_lower_bound_verified is False
    assert "FINITE_CERTIFICATE_LOWER_BOUND_VIOLATED" in result.errors


def test_certificate_tamper_changes_receipt_root():
    original = verify_weil_finite_certificate(certificate())
    changed = list(certificate().contributions)
    changed[0] = contribution("p2", (7, 10), (4, 5))
    tampered = verify_weil_finite_certificate(certificate(contributions=tuple(changed)))
    assert original.receipt_root != tampered.receipt_root


def _rat_json(value: ExactRationalV1) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _interval_json(value: ExactIntervalV1) -> dict[str, object]:
    return {"lower": _rat_json(value.lower), "upper": _rat_json(value.upper)}


def cli_certificate_payload() -> dict[str, object]:
    cert = certificate()
    return {
        "test_function_digest": cert.test_function_digest,
        "cutoff": cert.cutoff,
        "contributions": [
            {
                "contribution_id": item.contribution_id,
                "contribution_kind": item.contribution_kind,
                "value_interval": _interval_json(item.value_interval),
                "source_root": item.source_root,
            }
            for item in cert.contributions
        ],
        "norm_sq": _rat_json(cert.norm_sq),
        "epsilon_r": _rat_json(cert.epsilon_r),
        "approximation_delta": _rat_json(cert.approximation_delta),
        "approximation_bound_root": cert.approximation_bound_root,
        "assumption_tags": [],
    }


def test_cli_verify_certificate_emits_recomputed_packet(tmp_path: Path):
    input_path = tmp_path / "certificate.json"
    output_path = tmp_path / "packet.json"
    input_path.write_text(json.dumps(cli_certificate_payload()), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "scripts/weil-proof.py", "verify-certificate", "--input", str(input_path), "--output", str(output_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    packet = json.loads(output_path.read_text(encoding="utf-8"))
    assert packet["packet_kind"] == "AEGIS_WEIL_FINITE_CERTIFICATE_PACKET_V1"
    assert packet["verification"]["arithmetic_certificate_verified"] is True
    assert packet["verification"]["contribution_semantics_verified"] is False
    assert packet["verification"]["rh_proven"] is False
