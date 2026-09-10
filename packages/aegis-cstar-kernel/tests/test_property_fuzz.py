import cmath

import numpy as np
import pytest

from aegis_cstar import (
    CStarAlgebra,
    InfinityCStarSheaf,
    SimplicialTwoComplex,
    StarHomomorphism,
    UnitaryIntertwiner,
)
from aegis_cstar.receipts import canonical_sha256


SEEDS = tuple(range(24))


def _random_isometry(rng: np.random.Generator, target_dim: int, source_dim: int) -> np.ndarray:
    z = rng.normal(size=(target_dim, source_dim)) + 1j * rng.normal(
        size=(target_dim, source_dim)
    )
    q, r = np.linalg.qr(z)
    phases = np.diag(r)
    phases = np.where(np.abs(phases) > 0, phases / np.abs(phases), 1.0)
    return q @ np.diag(np.conj(phases))


def _random_unitary(rng: np.random.Generator, dim: int) -> np.ndarray:
    return _random_isometry(rng, dim, dim)


def _random_matrix(rng: np.random.Generator, dim: int) -> np.ndarray:
    return rng.normal(size=(dim, dim)) + 1j * rng.normal(size=(dim, dim))


def _scalar_intertwiner(phase: float) -> UnitaryIntertwiner:
    alg = CStarAlgebra(1)
    hom = StarHomomorphism(alg, alg, np.ones((1, 1), dtype=np.complex128))
    u = np.array([[cmath.exp(1j * phase)]], dtype=np.complex128)
    return UnitaryIntertwiner(hom, hom, u)


def _principal_phase(value: float) -> float:
    return float(cmath.phase(cmath.exp(1j * value)))


def test_isometry_gate_uses_declared_absolute_residual_boundary():
    alg = CStarAlgebra(2)

    below = np.diag([1.0 + 4.0e-11, 1.0]).astype(np.complex128)
    below_residual = np.linalg.norm(below.conj().T @ below - np.eye(2), ord=2)
    assert below_residual < 1.0e-10
    StarHomomorphism(alg, alg, below)

    above = np.diag([1.0 + 7.5e-11, 1.0]).astype(np.complex128)
    above_residual = np.linalg.norm(above.conj().T @ above - np.eye(2), ord=2)
    assert above_residual > 1.0e-10
    with pytest.raises(ValueError, match="isometry"):
        StarHomomorphism(alg, alg, above)


def test_random_isometries_preserve_star_and_multiplication():
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        source_dim = int(rng.integers(1, 4))
        target_dim = int(rng.integers(source_dim, 5))
        source = CStarAlgebra(source_dim)
        target = CStarAlgebra(target_dim)
        hom = StarHomomorphism(source, target, _random_isometry(rng, target_dim, source_dim))
        a = _random_matrix(rng, source_dim)
        b = _random_matrix(rng, source_dim)

        assert np.allclose(hom.apply(source.adjoint(a)), target.adjoint(hom.apply(a)), atol=1e-10, rtol=1e-10)
        assert np.allclose(hom.apply(a @ b), hom.apply(a) @ hom.apply(b), atol=1e-10, rtol=1e-10)


def test_random_unitary_conjugated_homomorphisms_intertwine():
    for seed in SEEDS:
        rng = np.random.default_rng(10_000 + seed)
        source_dim = int(rng.integers(1, 4))
        target_dim = int(rng.integers(source_dim, 5))
        source = CStarAlgebra(source_dim)
        target = CStarAlgebra(target_dim)
        e = _random_isometry(rng, target_dim, source_dim)
        u = _random_unitary(rng, target_dim)
        h0 = StarHomomorphism(source, target, e)
        h1 = StarHomomorphism(source, target, u @ e)
        inter = UnitaryIntertwiner(h0, h1, u)
        a = _random_matrix(rng, source_dim)
        assert inter.verify_intertwining(a)


def test_random_simplices_are_canonically_closed_under_faces():
    for seed in SEEDS:
        rng = np.random.default_rng(20_000 + seed)
        space = SimplicialTwoComplex()
        chosen = set()
        for _ in range(20):
            width = int(rng.integers(1, 4))
            nodes = tuple(int(x) for x in rng.choice(10, size=width, replace=False))
            chosen.add(tuple(sorted(nodes)))
            space.add_simplex(*nodes)

        assert space.vertices == sorted(set(space.vertices))
        assert space.edges == sorted(set(space.edges))
        assert space.faces == sorted(set(space.faces))
        for face in space.faces:
            for i in range(3):
                for j in range(i + 1, 3):
                    assert tuple(sorted((face[i], face[j]))) in space.edges
            for v in face:
                assert v in space.vertices


def test_random_scalar_postnikov_phases_match_loop_formula_and_receipt_hash_is_stable():
    for seed in SEEDS:
        rng = np.random.default_rng(30_000 + seed)
        p012, p023, p123, p013 = rng.uniform(-np.pi, np.pi, size=4)
        sheaf = InfinityCStarSheaf(SimplicialTwoComplex())
        sheaf.assign_associator(0, 1, 2, _scalar_intertwiner(float(p012)))
        sheaf.assign_associator(0, 2, 3, _scalar_intertwiner(float(p023)))
        sheaf.assign_associator(1, 2, 3, _scalar_intertwiner(float(p123)))
        sheaf.assign_associator(0, 1, 3, _scalar_intertwiner(float(p013)))

        expected = _principal_phase(float(p123 - p013 + p023 + p012))
        got = sheaf.evaluate_postnikov_k3(0, 1, 2, 3)
        receipt1 = sheaf.evaluate_postnikov_k3_receipt(0, 1, 2, 3)
        receipt2 = sheaf.evaluate_postnikov_k3_receipt(0, 1, 2, 3)

        assert np.isclose(got, expected, atol=1e-11)
        assert receipt1["decision"] == "VERIFIED_NUMERICAL_HOLONOMY"
        assert np.isclose(receipt1["k3_phase_radians"], expected, atol=1e-11)
        assert canonical_sha256(receipt1) == canonical_sha256(receipt2)


def test_random_matrix_valued_postnikov_receipts_match_direct_loop_calculation():
    for seed in SEEDS:
        rng = np.random.default_rng(40_000 + seed)
        dim = int(rng.integers(2, 5))
        alg = CStarAlgebra(dim)
        hom = StarHomomorphism(alg, alg, np.eye(dim, dtype=np.complex128))
        unitaries = [_random_unitary(rng, dim) for _ in range(4)]
        inters = [UnitaryIntertwiner(hom, hom, u) for u in unitaries]

        sheaf = InfinityCStarSheaf(SimplicialTwoComplex())
        sheaf.assign_associator(0, 1, 2, inters[0])
        sheaf.assign_associator(0, 2, 3, inters[1])
        sheaf.assign_associator(1, 2, 3, inters[2])
        sheaf.assign_associator(0, 1, 3, inters[3])

        loop = unitaries[2] @ unitaries[3].conj().T @ unitaries[1] @ unitaries[0]
        trace_val = complex(np.trace(loop) / dim)
        receipt = sheaf.evaluate_postnikov_k3_receipt(0, 1, 2, 3, trace_tol=1e-14)
        if abs(trace_val) <= 1e-14:
            assert receipt["decision"] == "DENY_PHASE_UNDEFINED_TRACE_NEAR_ZERO"
        else:
            assert receipt["decision"] == "VERIFIED_NUMERICAL_HOLONOMY"
            assert np.isclose(receipt["k3_phase_radians"], cmath.phase(trace_val), atol=1e-11)


def test_unitary_gate_uses_declared_absolute_residual_boundary():
    alg = CStarAlgebra(2)
    hom = StarHomomorphism(alg, alg, np.eye(2, dtype=np.complex128))

    below = np.diag([1.0 + 4.0e-11, 1.0]).astype(np.complex128)
    below_residual = np.linalg.norm(below.conj().T @ below - np.eye(2), ord=2)
    assert below_residual < 1.0e-10
    UnitaryIntertwiner(hom, hom, below)

    above = np.diag([1.0 + 7.5e-11, 1.0]).astype(np.complex128)
    above_residual = np.linalg.norm(above.conj().T @ above - np.eye(2), ord=2)
    assert above_residual > 1.0e-10
    with pytest.raises(ValueError, match="unitary"):
        UnitaryIntertwiner(hom, hom, above)


def test_homomorphism_embedding_is_owned_immutable_copy():
    alg = CStarAlgebra(2)
    external = np.eye(2, dtype=np.complex128)
    hom = StarHomomorphism(alg, alg, external)

    external[0, 0] = 2.0
    assert np.allclose(hom.embedding_matrix, np.eye(2))
    with pytest.raises(ValueError):
        hom.embedding_matrix[0, 0] = 2.0


def test_intertwiner_unitary_is_owned_immutable_copy():
    alg = CStarAlgebra(2)
    hom = StarHomomorphism(alg, alg, np.eye(2, dtype=np.complex128))
    external = np.eye(2, dtype=np.complex128)
    inter = UnitaryIntertwiner(hom, hom, external)

    external[0, 0] = 2.0
    assert np.allclose(inter.unitary, np.eye(2))
    with pytest.raises(ValueError):
        inter.unitary[0, 0] = 2.0


def test_homomorphism_rejects_nonfinite_embedding_as_value_error():
    alg = CStarAlgebra(2)
    bad = np.eye(2, dtype=np.complex128)
    bad[0, 0] = np.nan
    with pytest.raises(ValueError, match="embedding_matrix"):
        StarHomomorphism(alg, alg, bad)


def test_intertwiner_rejects_nonfinite_unitary_as_value_error():
    alg = CStarAlgebra(2)
    hom = StarHomomorphism(alg, alg, np.eye(2, dtype=np.complex128))
    bad = np.eye(2, dtype=np.complex128)
    bad[0, 0] = np.nan
    with pytest.raises(ValueError, match="unitary"):
        UnitaryIntertwiner(hom, hom, bad)


def test_intertwining_verifier_rejects_residual_above_declared_atol():
    alg = CStarAlgebra(2)
    h0 = StarHomomorphism(alg, alg, np.eye(2, dtype=np.complex128))
    delta = 1.5e-10
    phase = np.diag([cmath.exp(1j * delta), 1.0]).astype(np.complex128)
    h1 = StarHomomorphism(alg, alg, phase)
    inter = UnitaryIntertwiner(h0, h1, np.eye(2, dtype=np.complex128))
    a = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)

    left = h1.apply(a)
    right = h0.apply(a)
    residual = np.linalg.norm(left - right, ord=2)
    assert residual > 1e-10
    assert inter.verify_intertwining(a, atol=1e-10) is False


def test_phantom_overlap_gate_uses_declared_absolute_tolerance():
    from aegis_cstar import SpectralPhantomSolver

    a1 = CStarAlgebra(1)
    a2 = CStarAlgebra(2)
    e0 = np.array([[1.0], [0.0]], dtype=np.complex128)
    h01 = StarHomomorphism(a1, a2, e0)
    h02 = StarHomomorphism(a1, a2, e0)

    overlap = 1.0 - 1.5e-9
    s = np.sqrt(1.0 - overlap**2)
    phase = 0.1
    rotation = np.array([[overlap, -s], [s, overlap]], dtype=np.complex128)
    u = cmath.exp(1j * phase) * rotation
    h12 = StarHomomorphism(a2, a2, u)

    space = SimplicialTwoComplex()
    space.add_simplex(0, 1, 2)
    sheaf = InfinityCStarSheaf(space)
    sheaf.assign_restriction(0, (0, 1), h01)
    sheaf.assign_restriction(1, (1, 2), h12)
    sheaf.assign_restriction(0, (0, 2), h02)

    solver = SpectralPhantomSolver(overlap_tol=1e-9, phase_tol=1e-12)
    assert abs(1.0 - overlap) > solver.overlap_tol
    assert solver.identify_phantoms(sheaf) == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"overlap_tol": -1e-9},
        {"phase_tol": -1e-12},
        {"overlap_tol": np.nan},
        {"phase_tol": np.inf},
    ],
)
def test_phantom_solver_rejects_invalid_tolerances(kwargs):
    from aegis_cstar import SpectralPhantomSolver

    with pytest.raises(ValueError, match="tol"):
        SpectralPhantomSolver(**kwargs)


@pytest.mark.parametrize("trace_tol", [-1e-12, np.nan, np.inf])
def test_k3_receipt_rejects_invalid_trace_tolerance(trace_tol):
    sheaf = InfinityCStarSheaf(SimplicialTwoComplex())
    sheaf.assign_associator(0, 1, 2, _scalar_intertwiner(0.0))
    sheaf.assign_associator(0, 2, 3, _scalar_intertwiner(0.0))
    sheaf.assign_associator(1, 2, 3, _scalar_intertwiner(0.0))
    sheaf.assign_associator(0, 1, 3, _scalar_intertwiner(0.0))

    with pytest.raises(ValueError, match="trace_tol"):
        sheaf.evaluate_postnikov_k3_receipt(0, 1, 2, 3, trace_tol=trace_tol)
