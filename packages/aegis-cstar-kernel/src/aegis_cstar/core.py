from __future__ import annotations

from dataclasses import dataclass
import cmath
from itertools import combinations
from typing import Any

import numpy as np


ATOL = 1e-10


def _as_complex_matrix(value: np.ndarray, *, name: str) -> np.ndarray:
    arr = np.asarray(value, dtype=np.complex128)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a rank-2 matrix")
    return arr


@dataclass(frozen=True)
class CStarAlgebra:
    dim: int

    def __post_init__(self) -> None:
        if not isinstance(self.dim, int) or self.dim <= 0:
            raise ValueError("dim must be a positive integer")

    def identity(self) -> np.ndarray:
        return np.eye(self.dim, dtype=np.complex128)

    def adjoint(self, a: np.ndarray) -> np.ndarray:
        arr = _as_complex_matrix(a, name="a")
        if arr.shape != (self.dim, self.dim):
            raise ValueError(f"a must have shape {(self.dim, self.dim)}")
        return arr.conj().T

    def verify_relation(self, a: np.ndarray, *, atol: float = ATOL) -> bool:
        """Numerically verify the finite-dimensional C*-identity ||a* a|| = ||a||^2."""
        arr = _as_complex_matrix(a, name="a")
        if arr.shape != (self.dim, self.dim):
            return False
        if not np.isfinite(arr).all():
            return False
        lhs = np.linalg.norm(arr.conj().T @ arr, ord=2)
        rhs = np.linalg.norm(arr, ord=2) ** 2
        return bool(np.isclose(lhs, rhs, atol=atol, rtol=atol))


@dataclass(frozen=True)
class StarHomomorphism:
    source: CStarAlgebra
    target: CStarAlgebra
    embedding_matrix: np.ndarray

    def __post_init__(self) -> None:
        e = _as_complex_matrix(self.embedding_matrix, name="embedding_matrix").copy()
        expected = (self.target.dim, self.source.dim)
        if e.shape != expected:
            raise ValueError(f"embedding_matrix must have shape {expected}")
        if not np.isfinite(e).all():
            raise ValueError("embedding_matrix must contain only finite values")
        gram = e.conj().T @ e
        residual = np.linalg.norm(gram - np.eye(self.source.dim), ord=2)
        if not np.isfinite(residual) or residual > ATOL:
            raise ValueError("embedding_matrix must be an isometry (E*E = I)")
        e.setflags(write=False)
        object.__setattr__(self, "embedding_matrix", e)

    def apply(self, a: np.ndarray) -> np.ndarray:
        arr = _as_complex_matrix(a, name="a")
        if arr.shape != (self.source.dim, self.source.dim):
            raise ValueError(
                f"source element must have shape {(self.source.dim, self.source.dim)}"
            )
        e = self.embedding_matrix
        return e @ arr @ e.conj().T


@dataclass(frozen=True)
class UnitaryIntertwiner:
    source_hom: StarHomomorphism
    target_hom: StarHomomorphism
    unitary: np.ndarray

    def __post_init__(self) -> None:
        if self.source_hom.source.dim != self.target_hom.source.dim:
            raise ValueError("intertwined homomorphisms must share source dimension")
        if self.source_hom.target.dim != self.target_hom.target.dim:
            raise ValueError("intertwined homomorphisms must share target dimension")
        u = _as_complex_matrix(self.unitary, name="unitary").copy()
        n = self.source_hom.target.dim
        if u.shape != (n, n):
            raise ValueError(f"unitary must have shape {(n, n)}")
        if not np.isfinite(u).all():
            raise ValueError("unitary must contain only finite values")
        unitary_residual = np.linalg.norm(u.conj().T @ u - np.eye(n), ord=2)
        if not np.isfinite(unitary_residual) or unitary_residual > ATOL:
            raise ValueError("unitary must satisfy U*U = I")
        u.setflags(write=False)
        object.__setattr__(self, "unitary", u)

    def verify_intertwining(self, test_matrix: np.ndarray, *, atol: float = ATOL) -> bool:
        u = self.unitary
        unitary_residual = np.linalg.norm(u.conj().T @ u - np.eye(u.shape[0]), ord=2)
        if not np.isfinite(unitary_residual) or unitary_residual > atol:
            return False
        left = self.target_hom.apply(test_matrix)
        right = u @ self.source_hom.apply(test_matrix) @ u.conj().T
        if not np.isfinite(left).all() or not np.isfinite(right).all():
            return False
        residual = np.linalg.norm(left - right, ord=2)
        return bool(np.isfinite(residual) and residual <= atol)


class SimplicialTwoComplex:
    def __init__(self) -> None:
        self.vertices: list[int] = []
        self.edges: list[tuple[int, int]] = []
        self.faces: list[tuple[int, int, int]] = []

    def add_simplex(self, *nodes: int) -> None:
        if not 1 <= len(nodes) <= 3:
            raise ValueError("SimplicialTwoComplex accepts vertices, edges, or triangular faces")
        if any(isinstance(n, bool) or not isinstance(n, (int, np.integer)) for n in nodes):
            raise ValueError("simplex nodes must be integers")
        if len(set(nodes)) != len(nodes):
            raise ValueError("simplex nodes must be distinct")
        canonical = tuple(sorted(int(n) for n in nodes))
        for v in canonical:
            if v not in self.vertices:
                self.vertices.append(v)
        self.vertices.sort()
        if len(canonical) >= 2:
            for edge in combinations(canonical, 2):
                if edge not in self.edges:
                    self.edges.append(edge)
            self.edges.sort()
        if len(canonical) == 3 and canonical not in self.faces:
            self.faces.append(canonical)
            self.faces.sort()


class InfinityCStarSheaf:
    def __init__(self, space: SimplicialTwoComplex) -> None:
        self.space = space
        self.algebras: dict[Any, CStarAlgebra] = {}
        self.restrictions: dict[tuple[Any, Any], StarHomomorphism] = {}
        self.associators: dict[tuple[Any, Any, Any], UnitaryIntertwiner] = {}

    def assign_algebra(self, simplex: Any, algebra: CStarAlgebra) -> None:
        self.algebras[simplex] = algebra

    def assign_restriction(self, parent: Any, child: Any, hom: StarHomomorphism) -> None:
        self.restrictions[(parent, child)] = hom

    def assign_associator(
        self, s1: Any, s2: Any, s3: Any, intertwiner: UnitaryIntertwiner
    ) -> None:
        self.associators[(s1, s2, s3)] = intertwiner

    def _postnikov_associators(self, v0: Any, v1: Any, v2: Any, v3: Any):
        keys = [(v0, v1, v2), (v0, v2, v3), (v1, v2, v3), (v0, v1, v3)]
        values = [self.associators.get(k) for k in keys]
        return keys, values

    @staticmethod
    def _associator_dimensions_compatible(values: list[UnitaryIntertwiner]) -> bool:
        shapes = {v.unitary.shape for v in values}
        return len(shapes) == 1

    def _postnikov_loop(self, values: list[UnitaryIntertwiner]) -> np.ndarray:
        if not self._associator_dimensions_compatible(values):
            raise ValueError("Postnikov associator unitary dimensions must match")
        a012, a023, a123, a013 = values
        return (
            a123.unitary
            @ a013.unitary.conj().T
            @ a023.unitary
            @ a012.unitary
        )

    def evaluate_postnikov_k3(self, v0: Any, v1: Any, v2: Any, v3: Any) -> float:
        """Source-compatible evaluator: incomplete associator data returns 0.0."""
        _, values = self._postnikov_associators(v0, v1, v2, v3)
        if any(v is None for v in values):
            return 0.0
        loop = self._postnikov_loop(values)  # type: ignore[arg-type]
        trace_val = np.trace(loop) / loop.shape[0]
        return float(cmath.phase(complex(trace_val)))

    def evaluate_postnikov_k3_receipt(
        self, v0: Any, v1: Any, v2: Any, v3: Any, *, trace_tol: float = 1e-12
    ) -> dict[str, Any]:
        if not np.isfinite(trace_tol) or trace_tol < 0:
            raise ValueError("trace_tol must be finite and non-negative")
        trace_tol = float(trace_tol)
        keys, values = self._postnikov_associators(v0, v1, v2, v3)
        missing = [list(k) for k, v in zip(keys, values) if v is None]
        if missing:
            return {
                "schema": "AEGIS_CSTAR_K3_RECEIPT_V1",
                "decision": "DENY_INCOMPLETE_ASSOCIATOR_DATA",
                "missing_associators": missing,
                "authority_effect": "NONE",
            }
        typed_values = values  # all entries are non-None after the missing-data gate
        if not self._associator_dimensions_compatible(typed_values):  # type: ignore[arg-type]
            return {
                "schema": "AEGIS_CSTAR_K3_RECEIPT_V1",
                "decision": "DENY_INCOMPATIBLE_ASSOCIATOR_DIMENSIONS",
                "associator_shapes": [list(v.unitary.shape) for v in typed_values],  # type: ignore[union-attr]
                "authority_effect": "NONE",
            }
        loop = self._postnikov_loop(typed_values)  # type: ignore[arg-type]
        trace_val = complex(np.trace(loop) / loop.shape[0])
        if abs(trace_val) <= trace_tol:
            return {
                "schema": "AEGIS_CSTAR_K3_RECEIPT_V1",
                "decision": "DENY_PHASE_UNDEFINED_TRACE_NEAR_ZERO",
                "normalized_trace": [trace_val.real, trace_val.imag],
                "authority_effect": "NONE",
            }
        phase = float(cmath.phase(trace_val))
        return {
            "schema": "AEGIS_CSTAR_K3_RECEIPT_V1",
            "decision": "VERIFIED_NUMERICAL_HOLONOMY",
            "k3_phase_radians": phase,
            "normalized_trace": [trace_val.real, trace_val.imag],
            "authority_effect": "NONE",
        }


@dataclass
class SpectralSection:
    values: dict[Any, np.ndarray]


class SpectralPhantomSolver:
    def __init__(self, *, overlap_tol: float = 1e-9, phase_tol: float = 1e-12) -> None:
        if not np.isfinite(overlap_tol) or overlap_tol < 0:
            raise ValueError("overlap_tol must be finite and non-negative")
        if not np.isfinite(phase_tol) or phase_tol < 0:
            raise ValueError("phase_tol must be finite and non-negative")
        self.overlap_tol = float(overlap_tol)
        self.phase_tol = float(phase_tol)

    @staticmethod
    def _restriction_keys(face: tuple[int, int, int]):
        v0, v1, v2 = face
        return [
            (v0, (v0, v1)),
            (v1, (v1, v2)),
            (v0, (v0, v2)),
        ]

    @staticmethod
    def _restriction_path_compatible(
        hom01: StarHomomorphism, hom12: StarHomomorphism, hom02: StarHomomorphism
    ) -> bool:
        return bool(
            hom01.source.dim == hom02.source.dim
            and hom01.target.dim == hom12.source.dim
            and hom12.target.dim == hom02.target.dim
        )

    def _face_result(self, sheaf: InfinityCStarSheaf, face: tuple[int, int, int]):
        keys = self._restriction_keys(face)
        hom01, hom12, hom02 = [sheaf.restrictions.get(k) for k in keys]
        if any(h is None for h in (hom01, hom12, hom02)):
            return None
        if not self._restriction_path_compatible(hom01, hom12, hom02):  # type: ignore[arg-type]
            return {"phantom": False, "reason": "INCOMPATIBLE_RESTRICTION_PATH"}

        source_dim = hom01.source.dim  # type: ignore[union-attr]
        psi0 = np.zeros(source_dim, dtype=np.complex128)
        psi0[0] = 1.0
        direct = hom02.embedding_matrix @ psi0  # type: ignore[union-attr]
        factor = hom12.embedding_matrix @ (hom01.embedding_matrix @ psi0)  # type: ignore[union-attr]

        nd = np.linalg.norm(direct)
        nf = np.linalg.norm(factor)
        if nd <= self.phase_tol or nf <= self.phase_tol:
            return {"phantom": False, "reason": "ZERO_NORM_PATH_STATE"}
        direct = direct / nd
        factor = factor / nf
        overlap = complex(np.vdot(direct, factor))
        magnitude = abs(overlap)
        phase = float(cmath.phase(overlap))
        phantom = bool(
            abs(magnitude - 1.0) <= self.overlap_tol
            and abs(phase) > self.phase_tol
        )
        return {
            "phantom": phantom,
            "overlap_magnitude": magnitude,
            "phase_twist_radians": phase,
        }

    def identify_phantoms(self, sheaf: InfinityCStarSheaf) -> list[tuple[Any, float]]:
        """Source-compatible scan: faces with missing restrictions are silently skipped."""
        found: list[tuple[Any, float]] = []
        for face in sheaf.space.faces:
            result = self._face_result(sheaf, face)
            if result and result.get("phantom"):
                found.append((face, float(result["phase_twist_radians"])))
        return found

    def identify_phantoms_receipt(self, sheaf: InfinityCStarSheaf) -> dict[str, Any]:
        skipped: list[list[int]] = []
        incompatible: list[list[int]] = []
        phantoms: list[dict[str, Any]] = []
        for face in sheaf.space.faces:
            keys = self._restriction_keys(face)
            if any(k not in sheaf.restrictions for k in keys):
                skipped.append(list(face))
                continue
            hom01, hom12, hom02 = [sheaf.restrictions[k] for k in keys]
            if not self._restriction_path_compatible(hom01, hom12, hom02):
                incompatible.append(list(face))
                continue
            result = self._face_result(sheaf, face)
            if result and result.get("phantom"):
                phantoms.append(
                    {
                        "face": list(face),
                        "phase_twist_radians": float(result["phase_twist_radians"]),
                    }
                )

        if incompatible:
            return {
                "schema": "AEGIS_CSTAR_PHANTOM_RECEIPT_V1",
                "decision": "DENY_INCOMPATIBLE_RESTRICTION_PATH",
                "incompatible_faces": incompatible,
                "skipped_faces": skipped,
                "phantoms": phantoms,
                "authority_effect": "NONE",
            }
        if skipped:
            return {
                "schema": "AEGIS_CSTAR_PHANTOM_RECEIPT_V1",
                "decision": "DENY_INCOMPLETE_RESTRICTION_DATA",
                "skipped_faces": skipped,
                "phantoms": phantoms,
                "authority_effect": "NONE",
            }
        return {
            "schema": "AEGIS_CSTAR_PHANTOM_RECEIPT_V1",
            "decision": "VERIFIED_NUMERICAL_PHANTOM_SCAN",
            "skipped_faces": [],
            "phantoms": phantoms,
            "authority_effect": "NONE",
        }
