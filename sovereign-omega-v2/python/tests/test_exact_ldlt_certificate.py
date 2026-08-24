import json
from pathlib import Path
import subprocess
import sys

import pytest

from harness.sdk.exact_ldlt import (
    ExactLDLTCertificateV1,
    ExactSymmetricMatrixV1,
    LDLTError,
    verify_exact_ldlt,
)
from harness.sdk.sovereign_execution import canonical_hash
from harness.sdk.weil_convergence_bridge import ExactRationalV1


def r(n: int, d: int = 1) -> ExactRationalV1:
    return ExactRationalV1(n, d)


def h(label: str) -> str:
    return canonical_hash("TEST_EXACT_LDLT_V1", {"label": label})


def matrix(rows):
    return ExactSymmetricMatrixV1(rows=tuple(tuple(r(*x) if isinstance(x, tuple) else r(x) for x in row) for row in rows))


def certificate() -> ExactLDLTCertificateV1:
    # A = [[2, 1], [1, 2]] = L diag(2, 3/2) L^T
    return ExactLDLTCertificateV1(
        matrix=matrix(((2, 1), (1, 2))),
        lower=tuple(
            tuple(r(*x) if isinstance(x, tuple) else r(x) for x in row)
            for row in ((1, 0), ((1, 2), 1))
        ),
        diagonal=(r(2), r(3, 2)),
        matrix_semantics_root=h("galerkin-matrix"),
    )


def test_exact_ldlt_recomputes_factorization_and_certifies_psd():
    result = verify_exact_ldlt(certificate())
    assert result.valid is True
    assert result.factorization_verified is True
    assert result.nonnegative_diagonal_verified is True
    assert result.finite_matrix_psd_verified is True
    assert result.galerkin_semantics_verified is False
    assert result.global_weil_positivity_proven is False
    assert result.rh_proven is False


def test_nonsymmetric_matrix_is_rejected_at_construction():
    with pytest.raises(LDLTError, match="MATRIX_NOT_SYMMETRIC"):
        matrix(((1, 2), (3, 4)))


def test_non_unit_or_non_lower_triangular_factor_is_rejected():
    cert = certificate()
    bad = ExactLDLTCertificateV1(
        matrix=cert.matrix,
        lower=((r(1), r(1)), (r(1, 2), r(1))),
        diagonal=cert.diagonal,
        matrix_semantics_root=cert.matrix_semantics_root,
    )
    result = verify_exact_ldlt(bad)
    assert result.valid is False
    assert "LOWER_FACTOR_INVALID" in result.errors


def test_negative_diagonal_does_not_certify_psd():
    cert = certificate()
    bad = ExactLDLTCertificateV1(
        matrix=cert.matrix,
        lower=cert.lower,
        diagonal=(r(2), r(-3, 2)),
        matrix_semantics_root=cert.matrix_semantics_root,
    )
    result = verify_exact_ldlt(bad)
    assert result.valid is False
    assert result.nonnegative_diagonal_verified is False
    assert result.finite_matrix_psd_verified is False


def test_factorization_tamper_fails_closed():
    cert = certificate()
    bad = ExactLDLTCertificateV1(
        matrix=cert.matrix,
        lower=cert.lower,
        diagonal=(r(2), r(5, 2)),
        matrix_semantics_root=cert.matrix_semantics_root,
    )
    result = verify_exact_ldlt(bad)
    assert result.valid is False
    assert result.factorization_verified is False
    assert "LDLT_FACTORIZATION_MISMATCH" in result.errors


def test_receipt_root_changes_when_matrix_semantics_commitment_changes():
    cert = certificate()
    first = verify_exact_ldlt(cert)
    changed = ExactLDLTCertificateV1(
        matrix=cert.matrix,
        lower=cert.lower,
        diagonal=cert.diagonal,
        matrix_semantics_root=h("different-galerkin-matrix"),
    )
    second = verify_exact_ldlt(changed)
    assert first.receipt_root != second.receipt_root


def _rat(value: ExactRationalV1) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def test_cli_verify_ldlt_emits_finite_psd_packet(tmp_path: Path):
    cert = certificate()
    payload = {
        "matrix": [[_rat(value) for value in row] for row in cert.matrix.rows],
        "lower": [[_rat(value) for value in row] for row in cert.lower],
        "diagonal": [_rat(value) for value in cert.diagonal],
        "matrix_semantics_root": cert.matrix_semantics_root,
    }
    input_path = tmp_path / "ldlt.json"
    output_path = tmp_path / "ldlt-receipt.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "scripts/weil-proof.py", "verify-ldlt", "--input", str(input_path), "--output", str(output_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    packet = json.loads(output_path.read_text(encoding="utf-8"))
    assert packet["packet_kind"] == "AEGIS_EXACT_LDLT_PACKET_V1"
    assert packet["verification"]["finite_matrix_psd_verified"] is True
    assert packet["verification"]["galerkin_semantics_verified"] is False
    assert packet["verification"]["global_weil_positivity_proven"] is False
    assert packet["verification"]["rh_proven"] is False
