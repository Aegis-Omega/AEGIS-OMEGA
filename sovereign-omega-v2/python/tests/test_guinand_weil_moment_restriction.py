"""Falsifiers for the moment-restricted bridge M_N = S^T (K_N + eps_N G_N) S_N."""
from flint import arb, arb_mat, ctx
import pytest

from harness.sdk.guinand_weil_arb import (
    ArbGalerkinError,
    ArbGalerkinSpecV1,
    MomentRestrictionSpecV1,
    verify_cutoff_free_galerkin,
    verify_moment_restricted_galerkin,
    _certify_interval_inertia,
    _restrict_arb_matrix,
)
from harness.sdk.weil_convergence_bridge import ExactRationalV1


def identity(n):
    return tuple(
        tuple(ExactRationalV1(1 if i == j else 0) for j in range(n)) for i in range(n)
    )


def zeros(n):
    return tuple(tuple(ExactRationalV1(0) for _ in range(n)) for _ in range(n))


class _PrecisionOnlySpec:
    """Minimal stand-in so the inertia helper can run on a bare matrix."""

    prec_bits = 256
    root = "0" * 64


def test_restriction_certifies_a_form_the_psd_transfer_law_cannot():
    """The load-bearing case: A is indefinite, yet S^T A S is certified PD.

    ``A >= 0 => S^T A S >= 0`` is unusable here because its hypothesis is
    false.  The certificate comes from the product, not from transfer.
    """
    ctx.prec = 256
    entries = {
        (0, 0): 1, (0, 1): 0, (0, 2): 2,
        (1, 0): 0, (1, 1): 1, (1, 2): 0,
        (2, 0): 2, (2, 1): 0, (2, 2): 1,
    }
    matrix = arb_mat(3, 3)
    for (i, j), value in entries.items():
        matrix[i, j] = arb(value)

    witness = [arb(1), arb(0), arb(-1)]
    quadratic = sum(
        (witness[i] * matrix[i, j] * witness[j] for i in range(3) for j in range(3)),
        arb(0),
    )
    assert quadratic < 0

    restriction = [[arb(0), arb(1)], [arb(1), arb(0)], [arb(0), arb(1)]]
    restricted = _restrict_arb_matrix(matrix, restriction, 3, 2)
    assert restricted[0, 0] == 1
    assert restricted[1, 1] == 6
    assert restricted[0, 1] == 0

    n_pos, n_neg, undetermined, _ = _certify_interval_inertia(
        restricted, 2, _PrecisionOnlySpec()
    )
    assert (n_pos, n_neg, undetermined) == (2, 0, None)


def test_identity_restriction_with_zero_epsilon_reproduces_the_kernel_verifier():
    galerkin = ArbGalerkinSpecV1(c=10, N=1, prec_bits=128)
    base = verify_cutoff_free_galerkin(galerkin)
    receipt = verify_moment_restricted_galerkin(
        MomentRestrictionSpecV1(
            galerkin=galerkin,
            restriction=identity(3),
            gram=zeros(3),
            epsilon=ExactRationalV1(0),
        )
    )
    assert receipt.n_positive == base.n_positive
    assert receipt.n_negative == base.n_negative
    assert receipt.undetermined_pivot == base.undetermined_pivot
    assert receipt.kernel_matrix_root == base.matrix_root


def test_rank_deficient_restriction_fails_closed():
    galerkin = ArbGalerkinSpecV1(c=10, N=1, prec_bits=128)
    duplicated_column = (
        (ExactRationalV1(1), ExactRationalV1(1)),
        (ExactRationalV1(0), ExactRationalV1(0)),
        (ExactRationalV1(0), ExactRationalV1(0)),
    )
    receipt = verify_moment_restricted_galerkin(
        MomentRestrictionSpecV1(
            galerkin=galerkin,
            restriction=duplicated_column,
            gram=zeros(3),
            epsilon=ExactRationalV1(0),
        )
    )
    assert receipt.valid is False
    assert receipt.undetermined_pivot is not None
    assert "INTERVAL_PIVOT_UNDETERMINED" in receipt.errors
    assert receipt.restricted_form_lower_bound_verified is False


def test_epsilon_is_bound_into_the_receipt_exactly():
    galerkin = ArbGalerkinSpecV1(c=10, N=1, prec_bits=128)
    receipt = verify_moment_restricted_galerkin(
        MomentRestrictionSpecV1(
            galerkin=galerkin,
            restriction=identity(3),
            gram=identity(3),
            epsilon=ExactRationalV1(1, 100),
        )
    )
    assert (receipt.epsilon_numerator, receipt.epsilon_denominator) == (1, 100)


def test_receipt_is_deterministic_across_replay():
    galerkin = ArbGalerkinSpecV1(c=10, N=1, prec_bits=128)
    spec = MomentRestrictionSpecV1(
        galerkin=galerkin,
        restriction=identity(3),
        gram=identity(3),
        epsilon=ExactRationalV1(1, 1000),
    )
    assert (
        verify_moment_restricted_galerkin(spec).receipt_root
        == verify_moment_restricted_galerkin(spec).receipt_root
    )


@pytest.mark.parametrize(
    "code,restriction,gram,epsilon",
    [
        ("RESTRICTION_ROWS_MISMATCH", identity(2), zeros(3), ExactRationalV1(0)),
        (
            "GRAM_NOT_SYMMETRIC",
            identity(3),
            (
                (ExactRationalV1(1), ExactRationalV1(2), ExactRationalV1(0)),
                (ExactRationalV1(3), ExactRationalV1(1), ExactRationalV1(0)),
                (ExactRationalV1(0), ExactRationalV1(0), ExactRationalV1(1)),
            ),
            ExactRationalV1(0),
        ),
        ("GRAM_DIMENSION_MISMATCH", identity(3), zeros(2), ExactRationalV1(0)),
        ("EPSILON_NEGATIVE", identity(3), zeros(3), ExactRationalV1(-1, 2)),
    ],
)
def test_structural_validation_is_fail_closed(code, restriction, gram, epsilon):
    with pytest.raises(ArbGalerkinError) as excinfo:
        MomentRestrictionSpecV1(
            galerkin=ArbGalerkinSpecV1(c=10, N=1, prec_bits=128),
            restriction=restriction,
            gram=gram,
            epsilon=epsilon,
        )
    assert excinfo.value.code == code


def test_receipt_never_promotes_to_a_global_claim():
    receipt = verify_moment_restricted_galerkin(
        MomentRestrictionSpecV1(
            galerkin=ArbGalerkinSpecV1(c=10, N=1, prec_bits=128),
            restriction=identity(3),
            gram=identity(3),
            epsilon=ExactRationalV1(1, 100),
        )
    )
    assert receipt.moment_basis_identification_verified is False
    assert receipt.gram_inner_product_identification_verified is False
    assert receipt.epsilon_cofinality_verified is False
    assert receipt.galerkin_semantics_verified is False
    assert receipt.global_weil_positivity_proven is False
    assert receipt.rh_proven is False
    assert "EPSILON_COFINALITY_TO_ZERO_NOT_MACHINE_VERIFIED" in receipt.open_obligations
    assert "MOMENT_BASIS_IDENTIFICATION_NOT_MACHINE_FORMALIZED" in receipt.open_obligations
