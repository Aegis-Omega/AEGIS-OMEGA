"""Exact rational LDL^T certificate checker for AEGIS Ω proof tooling.

The kernel proves a narrow finite-dimensional statement only:

    A = L D L^T  and  D_i >= 0  =>  A is positive semidefinite.

All arithmetic is exact over :class:`fractions.Fraction`.  The checker does
not infer that ``A`` is the correct Guinand-Weil/Connes Galerkin matrix merely
because a source hash is supplied.  Matrix semantics remain a separately
verifiable proof obligation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import re

from harness.sdk.sovereign_execution import canonical_hash
from harness.sdk.weil_convergence_bridge import ExactRationalV1

CERTIFICATE_KIND = "AEGIS_EXACT_LDLT_CERTIFICATE_V1"
RECEIPT_KIND = "AEGIS_EXACT_LDLT_RECEIPT_V1"
PROOF_SEMANTICS = "FINITE_MATRIX_PSD_ONLY_NOT_GLOBAL_WEIL_PROOF"
MAX_MATRIX_DIMENSION = 256
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class LDLTError(ValueError):
    """Fail-closed structural input error with a stable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require_hash(value: str) -> None:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise LDLTError("MATRIX_SEMANTICS_ROOT_INVALID")


@dataclass(frozen=True)
class ExactSymmetricMatrixV1:
    rows: tuple[tuple[ExactRationalV1, ...], ...]

    def __post_init__(self) -> None:
        n = len(self.rows)
        if n == 0:
            raise LDLTError("MATRIX_EMPTY")
        if n > MAX_MATRIX_DIMENSION:
            raise LDLTError("MATRIX_DIMENSION_EXCEEDED")
        if any(len(row) != n for row in self.rows):
            raise LDLTError("MATRIX_NOT_SQUARE")
        for i in range(n):
            for j in range(i + 1, n):
                if self.rows[i][j].fraction != self.rows[j][i].fraction:
                    raise LDLTError("MATRIX_NOT_SYMMETRIC")

    @property
    def dimension(self) -> int:
        return len(self.rows)

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_EXACT_SYMMETRIC_MATRIX_ROOT_V1", asdict(self))


@dataclass(frozen=True)
class ExactLDLTCertificateV1:
    matrix: ExactSymmetricMatrixV1
    lower: tuple[tuple[ExactRationalV1, ...], ...]
    diagonal: tuple[ExactRationalV1, ...]
    matrix_semantics_root: str
    certificate_kind: str = CERTIFICATE_KIND
    proof_semantics: str = PROOF_SEMANTICS

    def __post_init__(self) -> None:
        if self.certificate_kind != CERTIFICATE_KIND:
            raise LDLTError("CERTIFICATE_KIND_MISMATCH")
        if self.proof_semantics != PROOF_SEMANTICS:
            raise LDLTError("PROOF_SEMANTICS_MISMATCH")
        n = self.matrix.dimension
        if len(self.lower) != n or any(len(row) != n for row in self.lower):
            raise LDLTError("LOWER_FACTOR_SHAPE_INVALID")
        if len(self.diagonal) != n:
            raise LDLTError("DIAGONAL_SHAPE_INVALID")
        _require_hash(self.matrix_semantics_root)

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_EXACT_LDLT_CERTIFICATE_ROOT_V1", asdict(self))


@dataclass(frozen=True)
class ExactLDLTVerificationV1:
    receipt_kind: str
    proof_semantics: str
    subject_root: str
    matrix_root: str
    dimension: int
    valid: bool
    status: str
    lower_factor_verified: bool
    factorization_verified: bool
    nonnegative_diagonal_verified: bool
    finite_matrix_psd_verified: bool
    galerkin_semantics_verified: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    errors: tuple[str, ...]
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_EXACT_LDLT_RECEIPT_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["receipt_root"] = self.receipt_root
        return payload


def _lower_factor_is_canonical(lower: tuple[tuple[ExactRationalV1, ...], ...]) -> bool:
    n = len(lower)
    zero = Fraction(0, 1)
    one = Fraction(1, 1)
    for i in range(n):
        if lower[i][i].fraction != one:
            return False
        for j in range(i + 1, n):
            if lower[i][j].fraction != zero:
                return False
    return True


def _reconstructed_entry(
    lower: tuple[tuple[ExactRationalV1, ...], ...],
    diagonal: tuple[ExactRationalV1, ...],
    i: int,
    j: int,
) -> Fraction:
    total = Fraction(0, 1)
    # For triangular L, terms above min(i,j) vanish. Iterating all entries is
    # intentionally simple and deterministic; dimension is bounded above.
    for k in range(len(diagonal)):
        total += lower[i][k].fraction * diagonal[k].fraction * lower[j][k].fraction
    return total


def verify_exact_ldlt(certificate: ExactLDLTCertificateV1) -> ExactLDLTVerificationV1:
    """Replay an exact LDL^T certificate and certify finite-matrix PSD."""

    errors: list[str] = []
    lower_ok = _lower_factor_is_canonical(certificate.lower)
    if not lower_ok:
        errors.append("LOWER_FACTOR_INVALID")

    diagonal_ok = all(value.fraction >= 0 for value in certificate.diagonal)
    if not diagonal_ok:
        errors.append("NEGATIVE_DIAGONAL_ENTRY")

    factorization_ok = lower_ok
    if factorization_ok:
        n = certificate.matrix.dimension
        for i in range(n):
            for j in range(n):
                if _reconstructed_entry(certificate.lower, certificate.diagonal, i, j) != certificate.matrix.rows[i][j].fraction:
                    factorization_ok = False
                    break
            if not factorization_ok:
                break
    if not factorization_ok:
        errors.append("LDLT_FACTORIZATION_MISMATCH")

    finite_psd = factorization_ok and diagonal_ok
    valid = finite_psd and not errors

    return ExactLDLTVerificationV1(
        receipt_kind=RECEIPT_KIND,
        proof_semantics=PROOF_SEMANTICS,
        subject_root=certificate.root,
        matrix_root=certificate.matrix.root,
        dimension=certificate.matrix.dimension,
        valid=valid,
        status="FINITE_MATRIX_PSD_VERIFIED" if valid else "REJECTED",
        lower_factor_verified=lower_ok,
        factorization_verified=factorization_ok,
        nonnegative_diagonal_verified=diagonal_ok,
        finite_matrix_psd_verified=finite_psd,
        galerkin_semantics_verified=False,
        global_weil_positivity_proven=False,
        rh_proven=False,
        errors=tuple(sorted(set(errors))),
        open_obligations=(
            "MATRIX_ENTRIES_REQUIRE_INDEPENDENT_GUINAND_WEIL_EVALUATOR",
            "ARCHIMEDEAN_TAIL_THEOREM_NOT_MACHINE_BOUND",
            "FINITE_MATRIX_PSD_DOES_NOT_ESTABLISH_GLOBAL_WEIL_POSITIVITY",
        ),
    )
