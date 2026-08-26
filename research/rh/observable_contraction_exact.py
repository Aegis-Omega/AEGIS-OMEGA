"""Exact finite-dimensional kernel for the Observable Contraction Freeze v1.

This module is intentionally small and dependency-free. It uses
``fractions.Fraction`` throughout so the committed exact regressions exercise
algebraic identities rather than floating-point tolerances.

Scope:
    A_plus = A_minus T
    D = A_minus (I - T T^T) A_minus^T
    R_minus = Ran(A_minus^T) = row-space(A_minus)

The PSD condition on D certifies contraction only on R_minus. It does not
certify a global norm bound for a prescribed T unless R_minus is the whole
ambient space.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from typing import Iterable, Sequence

F = Fraction
Matrix = list[list[F]]
Vector = list[F]


def _f(x: object) -> F:
    if isinstance(x, Fraction):
        return x
    return F(x)  # type: ignore[arg-type]


def _matrix(a: Sequence[Sequence[object]]) -> Matrix:
    rows = [[_f(x) for x in row] for row in a]
    if not rows:
        return []
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("matrix rows must have equal length")
    return rows


def _vector(v: Sequence[object]) -> Vector:
    return [_f(x) for x in v]


def shape(a: Sequence[Sequence[object]]) -> tuple[int, int]:
    aa = _matrix(a)
    return (len(aa), len(aa[0]) if aa else 0)


def transpose(a: Sequence[Sequence[object]]) -> Matrix:
    aa = _matrix(a)
    if not aa:
        return []
    return [list(col) for col in zip(*aa)]


def identity(n: int) -> Matrix:
    if n < 0:
        raise ValueError("identity dimension must be non-negative")
    return [[F(int(i == j)) for j in range(n)] for i in range(n)]


def matmul(a: Sequence[Sequence[object]], b: Sequence[Sequence[object]]) -> Matrix:
    aa = _matrix(a)
    bb = _matrix(b)
    if not aa or not bb:
        if aa and len(aa[0]) != 0:
            raise ValueError("incompatible empty matrix product")
        return []
    if len(aa[0]) != len(bb):
        raise ValueError("incompatible matrix dimensions")
    bt = transpose(bb)
    return [[sum((x * y for x, y in zip(row, col)), F(0)) for col in bt] for row in aa]


def matvec(a: Sequence[Sequence[object]], v: Sequence[object]) -> Vector:
    aa = _matrix(a)
    vv = _vector(v)
    if not aa:
        return []
    if len(aa[0]) != len(vv):
        raise ValueError("incompatible matrix/vector dimensions")
    return [sum((x * y for x, y in zip(row, vv)), F(0)) for row in aa]


def matsub(a: Sequence[Sequence[object]], b: Sequence[Sequence[object]]) -> Matrix:
    aa = _matrix(a)
    bb = _matrix(b)
    if shape(aa) != shape(bb):
        raise ValueError("matrix dimensions differ")
    return [[x - y for x, y in zip(ra, rb)] for ra, rb in zip(aa, bb)]


def dot(a: Sequence[object], b: Sequence[object]) -> F:
    aa = _vector(a)
    bb = _vector(b)
    if len(aa) != len(bb):
        raise ValueError("vector dimensions differ")
    return sum((x * y for x, y in zip(aa, bb)), F(0))


def determinant(a: Sequence[Sequence[object]]) -> F:
    """Exact determinant by fraction-preserving Gaussian elimination."""
    m = _matrix(a)
    n, p = shape(m)
    if n != p:
        raise ValueError("determinant requires a square matrix")
    if n == 0:
        return F(1)
    work = [row[:] for row in m]
    det = F(1)
    sign = F(1)
    for col in range(n):
        pivot = next((r for r in range(col, n) if work[r][col] != 0), None)
        if pivot is None:
            return F(0)
        if pivot != col:
            work[col], work[pivot] = work[pivot], work[col]
            sign = -sign
        pv = work[col][col]
        det *= pv
        for r in range(col + 1, n):
            if work[r][col] == 0:
                continue
            factor = work[r][col] / pv
            for c in range(col, n):
                work[r][c] -= factor * work[col][c]
    return sign * det


def det_affine_2x2_coefficients(
    x: Sequence[Sequence[object]], y: Sequence[Sequence[object]]
) -> tuple[F, F, F]:
    """Return exact coefficients of det(X - lambda Y) for 2x2 matrices.

    The result ``(c0, c1, c2)`` means

        det(X - lambda Y) = c0 + c1*lambda + c2*lambda^2.

    This small symbolic certificate is sufficient to lock the canonical
    singular-Y Layer-1 cross-coupling fixture without sampling lambda values.
    """
    xx = _matrix(x)
    yy = _matrix(y)
    if shape(xx) != (2, 2) or shape(yy) != (2, 2):
        raise ValueError("affine determinant certificate requires 2x2 matrices")
    x00, x01 = xx[0]
    x10, x11 = xx[1]
    y00, y01 = yy[0]
    y10, y11 = yy[1]
    c0 = x00 * x11 - x01 * x10
    c1 = -(x00 * y11 + y00 * x11) + (x01 * y10 + y01 * x10)
    c2 = y00 * y11 - y01 * y10
    return (c0, c1, c2)


def _principal_submatrix(a: Matrix, indexes: Iterable[int]) -> Matrix:
    idx = tuple(indexes)
    return [[a[i][j] for j in idx] for i in idx]


def is_symmetric(a: Sequence[Sequence[object]]) -> bool:
    aa = _matrix(a)
    n, p = shape(aa)
    return n == p and aa == transpose(aa)


def is_psd(a: Sequence[Sequence[object]]) -> bool:
    """Exact PSD decision for a real symmetric matrix.

    A real symmetric matrix is positive semidefinite iff every principal minor
    is non-negative. The exponential enumeration is intentional: this kernel
    is for tiny exact falsification fixtures, not large numerical workloads.
    """
    aa = _matrix(a)
    n, p = shape(aa)
    if n != p or not is_symmetric(aa):
        return False
    for size in range(1, n + 1):
        for idx in combinations(range(n), size):
            if determinant(_principal_submatrix(aa, idx)) < 0:
                return False
    return True


def row_space_basis(a: Sequence[Sequence[object]]) -> Matrix:
    """Return an exact independent row basis for Ran(A^T)."""
    aa = _matrix(a)
    if not aa:
        return []
    work = [row[:] for row in aa]
    rows = len(work)
    cols = len(work[0])
    pivot_row = 0
    for col in range(cols):
        pivot = next((r for r in range(pivot_row, rows) if work[r][col] != 0), None)
        if pivot is None:
            continue
        work[pivot_row], work[pivot] = work[pivot], work[pivot_row]
        pv = work[pivot_row][col]
        work[pivot_row] = [x / pv for x in work[pivot_row]]
        for r in range(rows):
            if r == pivot_row or work[r][col] == 0:
                continue
            factor = work[r][col]
            work[r] = [x - factor * y for x, y in zip(work[r], work[pivot_row])]
        pivot_row += 1
        if pivot_row == rows:
            break
    return [row for row in work if any(x != 0 for x in row)]


def _solve(a: Sequence[Sequence[object]], b: Sequence[object]) -> Vector:
    """Solve an exact nonsingular square linear system."""
    aa = _matrix(a)
    bb = _vector(b)
    n, p = shape(aa)
    if n != p or len(bb) != n:
        raise ValueError("solve requires a square system")
    aug = [row[:] + [rhs] for row, rhs in zip(aa, bb)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if aug[r][col] != 0), None)
        if pivot is None:
            raise ValueError("singular system")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        pv = aug[col][col]
        aug[col] = [x / pv for x in aug[col]]
        for r in range(n):
            if r == col or aug[r][col] == 0:
                continue
            factor = aug[r][col]
            aug[r] = [x - factor * y for x, y in zip(aug[r], aug[col])]
    return [aug[i][-1] for i in range(n)]


def project_onto_row_space(a: Sequence[Sequence[object]], v: Sequence[object]) -> Vector:
    """Exact Euclidean orthogonal projection onto Ran(A^T)."""
    aa = _matrix(a)
    vv = _vector(v)
    if aa and len(aa[0]) != len(vv):
        raise ValueError("vector is not in A's ambient column space")
    basis = row_space_basis(aa)
    if not basis:
        return [F(0) for _ in vv]
    gram = matmul(basis, transpose(basis))
    rhs = matvec(basis, vv)
    coeff = _solve(gram, rhs)
    return matvec(transpose(basis), coeff)


def difference(a_minus: Sequence[Sequence[object]], t: Sequence[Sequence[object]]) -> Matrix:
    """Return D = A_- (I - T T^T) A_-^T exactly."""
    a = _matrix(a_minus)
    tt = _matrix(t)
    if not a:
        return []
    ambient = len(a[0])
    if shape(tt) != (ambient, ambient):
        raise ValueError("T must be square on the column space of A_-")
    defect = matsub(identity(ambient), matmul(tt, transpose(tt)))
    return matmul(matmul(a, defect), transpose(a))


def observable_defect_matrix(
    a_minus: Sequence[Sequence[object]], t: Sequence[Sequence[object]]
) -> Matrix:
    """Matrix of I - T T^T restricted to an exact row-space basis.

    If B has independent rows spanning R_- = Ran(A_-^T), this returns
    B (I - T T^T) B^T. PSD of this matrix is basis-independent and is
    equivalent to PSD of D = A_-(I-TT^T)A_-^T.
    """
    a = _matrix(a_minus)
    if not a:
        return []
    ambient = len(a[0])
    tt = _matrix(t)
    if shape(tt) != (ambient, ambient):
        raise ValueError("T must be square on the column space of A_-")
    basis = row_space_basis(a)
    if not basis:
        return []
    defect = matsub(identity(ambient), matmul(tt, transpose(tt)))
    return matmul(matmul(basis, defect), transpose(basis))


def observable_contraction_holds(
    a_minus: Sequence[Sequence[object]], t: Sequence[Sequence[object]]
) -> bool:
    """Decide the theorem's observable contraction predicate exactly."""
    return is_psd(observable_defect_matrix(a_minus, t))
