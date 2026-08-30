"""Exact finite RKHS dominance certificate kernel for the RH research lane.

This is a selective algebraic extraction of the certificate pattern used by
PR #303's exact-rational LDL^T verifier.  It verifies only the finite statement

    K_positive - K_negative = L D L^T,   D_i >= 0

and therefore certifies finite-matrix dominance on the supplied coordinates.
It deliberately does *not* identify either matrix with the prime-power or
Archimedean pieces of the classical Weil functional.  A semantic binding hash
is a commitment, not theorem authority.

Consequently:

    finite RKHS dominance != global Weil positivity != RH.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from fractions import Fraction

from harness.sdk.sovereign_execution import canonical_hash

SOURCE_PR303_HEAD = "7c94ba577f62e5a9fcd96b9b5ae4859d106db081"
SOURCE_EXACT_LDLT_GIT_BLOB = "2885b23d14f857fbcb7aa358ef0183a095482ba9"
DERIVATION = "SELECTIVE_ALGEBRAIC_EXTRACTION_FROM_PR303_EXACT_LDLT_PATTERN"
PROOF_SEMANTICS = "FINITE_RKHS_MATRIX_DOMINANCE_ONLY"
RECEIPT_KIND = "AEGIS_FINITE_RKHS_DOMINANCE_RECEIPT_V1"
MAX_MATRIX_DIMENSION = 256
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class RKHSDominanceError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ExactRationalV1:
    numerator: int
    denominator: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.numerator, bool) or not isinstance(self.numerator, int):
            raise RKHSDominanceError("NUMERATOR_INVALID")
        if isinstance(self.denominator, bool) or not isinstance(self.denominator, int) or self.denominator == 0:
            raise RKHSDominanceError("DENOMINATOR_INVALID")
        n, d = self.numerator, self.denominator
        if d < 0:
            n, d = -n, -d
        g = math.gcd(abs(n), d) or 1
        object.__setattr__(self, "numerator", n // g)
        object.__setattr__(self, "denominator", d // g)

    @property
    def fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)


@dataclass(frozen=True)
class ExactSymmetricMatrixV1:
    rows: tuple[tuple[ExactRationalV1, ...], ...]

    def __post_init__(self) -> None:
        n = len(self.rows)
        if n == 0:
            raise RKHSDominanceError("MATRIX_EMPTY")
        if n > MAX_MATRIX_DIMENSION:
            raise RKHSDominanceError("MATRIX_DIMENSION_EXCEEDED")
        if any(len(row) != n for row in self.rows):
            raise RKHSDominanceError("MATRIX_NOT_SQUARE")
        for i in range(n):
            for j in range(i + 1, n):
                if self.rows[i][j].fraction != self.rows[j][i].fraction:
                    raise RKHSDominanceError("MATRIX_NOT_SYMMETRIC")

    @property
    def dimension(self) -> int:
        return len(self.rows)

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_EXACT_RKHS_MATRIX_ROOT_V1", asdict(self))


@dataclass(frozen=True)
class FiniteRKHSDominanceCertificateV1:
    positive_kernel: ExactSymmetricMatrixV1
    negative_kernel: ExactSymmetricMatrixV1
    lower: tuple[tuple[ExactRationalV1, ...], ...]
    diagonal: tuple[ExactRationalV1, ...]
    semantic_binding_root: str
    proof_semantics: str = PROOF_SEMANTICS

    def __post_init__(self) -> None:
        if self.proof_semantics != PROOF_SEMANTICS:
            raise RKHSDominanceError("PROOF_SEMANTICS_MISMATCH")
        if self.positive_kernel.dimension != self.negative_kernel.dimension:
            raise RKHSDominanceError("KERNEL_DIMENSION_MISMATCH")
        n = self.positive_kernel.dimension
        if len(self.lower) != n or any(len(row) != n for row in self.lower):
            raise RKHSDominanceError("LOWER_FACTOR_SHAPE_INVALID")
        if len(self.diagonal) != n:
            raise RKHSDominanceError("DIAGONAL_SHAPE_INVALID")
        if not isinstance(self.semantic_binding_root, str) or SHA256_RE.fullmatch(self.semantic_binding_root) is None:
            raise RKHSDominanceError("SEMANTIC_BINDING_ROOT_INVALID")

    @property
    def root(self) -> str:
        return canonical_hash(
            "AEGIS_FINITE_RKHS_DOMINANCE_CERTIFICATE_ROOT_V1",
            {
                "positive_kernel_root": self.positive_kernel.root,
                "negative_kernel_root": self.negative_kernel.root,
                "lower": asdict(_LowerWrapper(self.lower))["rows"],
                "diagonal": [asdict(value) for value in self.diagonal],
                "semantic_binding_root": self.semantic_binding_root,
                "proof_semantics": self.proof_semantics,
                "source_pr303_head": SOURCE_PR303_HEAD,
                "source_exact_ldlt_git_blob": SOURCE_EXACT_LDLT_GIT_BLOB,
                "derivation": DERIVATION,
            },
        )


@dataclass(frozen=True)
class _LowerWrapper:
    rows: tuple[tuple[ExactRationalV1, ...], ...]


@dataclass(frozen=True)
class FiniteRKHSDominanceReceiptV1:
    receipt_kind: str
    proof_semantics: str
    certificate_root: str
    positive_kernel_root: str
    negative_kernel_root: str
    semantic_binding_root: str
    valid: bool
    status: str
    lower_factor_verified: bool
    factorization_verified: bool
    nonnegative_diagonal_verified: bool
    finite_rkhs_dominance_verified: bool
    concrete_weil_semantics_verified: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    errors: tuple[str, ...]
    open_obligations: tuple[str, ...]
    source_pr303_head: str = SOURCE_PR303_HEAD
    source_exact_ldlt_git_blob: str = SOURCE_EXACT_LDLT_GIT_BLOB
    derivation: str = DERIVATION

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_FINITE_RKHS_DOMINANCE_RECEIPT_ROOT_V1", asdict(self))


def _canonical_lower(lower: tuple[tuple[ExactRationalV1, ...], ...]) -> bool:
    zero, one = Fraction(0, 1), Fraction(1, 1)
    n = len(lower)
    for i in range(n):
        if lower[i][i].fraction != one:
            return False
        for j in range(i + 1, n):
            if lower[i][j].fraction != zero:
                return False
    return True


def _difference_entry(certificate: FiniteRKHSDominanceCertificateV1, i: int, j: int) -> Fraction:
    return (
        certificate.positive_kernel.rows[i][j].fraction
        - certificate.negative_kernel.rows[i][j].fraction
    )


def _reconstructed_entry(certificate: FiniteRKHSDominanceCertificateV1, i: int, j: int) -> Fraction:
    total = Fraction(0, 1)
    for k in range(len(certificate.diagonal)):
        total += (
            certificate.lower[i][k].fraction
            * certificate.diagonal[k].fraction
            * certificate.lower[j][k].fraction
        )
    return total


def verify_finite_rkhs_dominance(
    certificate: FiniteRKHSDominanceCertificateV1,
) -> FiniteRKHSDominanceReceiptV1:
    """Verify an exact finite dominance certificate without semantic promotion."""
    errors: list[str] = []

    lower_ok = _canonical_lower(certificate.lower)
    if not lower_ok:
        errors.append("LOWER_FACTOR_INVALID")

    diagonal_ok = all(value.fraction >= 0 for value in certificate.diagonal)
    if not diagonal_ok:
        errors.append("NEGATIVE_DIAGONAL_ENTRY")

    factorization_ok = lower_ok
    if factorization_ok:
        n = certificate.positive_kernel.dimension
        for i in range(n):
            for j in range(n):
                if _reconstructed_entry(certificate, i, j) != _difference_entry(certificate, i, j):
                    factorization_ok = False
                    break
            if not factorization_ok:
                break
    if not factorization_ok:
        errors.append("LDLT_FACTORIZATION_MISMATCH")

    finite_dominance = lower_ok and factorization_ok and diagonal_ok
    valid = finite_dominance and not errors

    return FiniteRKHSDominanceReceiptV1(
        receipt_kind=RECEIPT_KIND,
        proof_semantics=PROOF_SEMANTICS,
        certificate_root=certificate.root,
        positive_kernel_root=certificate.positive_kernel.root,
        negative_kernel_root=certificate.negative_kernel.root,
        semantic_binding_root=certificate.semantic_binding_root,
        valid=valid,
        status="FINITE_RKHS_DOMINANCE_VERIFIED" if valid else "REJECTED",
        lower_factor_verified=lower_ok,
        factorization_verified=factorization_ok,
        nonnegative_diagonal_verified=diagonal_ok,
        finite_rkhs_dominance_verified=finite_dominance,
        concrete_weil_semantics_verified=False,
        global_weil_positivity_proven=False,
        rh_proven=False,
        errors=tuple(sorted(set(errors))),
        open_obligations=(
            "CONCRETE_RKHS_TO_WEIL_SEMANTICS_NOT_BOUND",
            "FINITE_RKHS_DOMINANCE_DOES_NOT_ESTABLISH_CONTINUOUS_POSITIVITY",
            "DENSITY_CONTINUITY_COVERAGE_REMAINS_OPEN",
            "CONCRETE_WEIL_CRITERION_REMAINS_OPEN",
        ),
    )
