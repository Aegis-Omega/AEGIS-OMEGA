from harness.sdk.rkhs_dominance_kernel import (
    ExactRationalV1,
    ExactSymmetricMatrixV1,
    FiniteRKHSDominanceCertificateV1,
    verify_finite_rkhs_dominance,
)


def q(n: int, d: int = 1) -> ExactRationalV1:
    return ExactRationalV1(n, d)


def matrix(rows):
    return ExactSymmetricMatrixV1(tuple(tuple(q(v) for v in row) for row in rows))


def identity_lower(n: int):
    return tuple(
        tuple(q(1 if i == j else 0) for j in range(n))
        for i in range(n)
    )


def test_finite_rkhs_dominance_is_exact_but_semantics_remain_open():
    certificate = FiniteRKHSDominanceCertificateV1(
        positive_kernel=matrix([[2, 0], [0, 1]]),
        negative_kernel=matrix([[1, 0], [0, 1]]),
        lower=identity_lower(2),
        diagonal=(q(1), q(0)),
        semantic_binding_root="a" * 64,
    )

    receipt = verify_finite_rkhs_dominance(certificate)

    assert receipt.valid is True
    assert receipt.finite_rkhs_dominance_verified is True
    assert receipt.concrete_weil_semantics_verified is False
    assert receipt.global_weil_positivity_proven is False
    assert receipt.rh_proven is False
    assert "CONCRETE_RKHS_TO_WEIL_SEMANTICS_NOT_BOUND" in receipt.open_obligations


def test_negative_dominance_is_rejected_exactly():
    certificate = FiniteRKHSDominanceCertificateV1(
        positive_kernel=matrix([[1]]),
        negative_kernel=matrix([[2]]),
        lower=identity_lower(1),
        diagonal=(q(-1),),
        semantic_binding_root="b" * 64,
    )

    receipt = verify_finite_rkhs_dominance(certificate)

    assert receipt.valid is False
    assert receipt.finite_rkhs_dominance_verified is False
    assert "NEGATIVE_DIAGONAL_ENTRY" in receipt.errors


def test_factorization_tamper_is_rejected():
    certificate = FiniteRKHSDominanceCertificateV1(
        positive_kernel=matrix([[2, 0], [0, 2]]),
        negative_kernel=matrix([[1, 0], [0, 1]]),
        lower=identity_lower(2),
        diagonal=(q(1), q(2)),
        semantic_binding_root="c" * 64,
    )

    receipt = verify_finite_rkhs_dominance(certificate)

    assert receipt.valid is False
    assert "LDLT_FACTORIZATION_MISMATCH" in receipt.errors
