from __future__ import annotations

import cmath
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aegis_cstar import (  # noqa: E402
    CStarAlgebra,
    InfinityCStarSheaf,
    SimplicialTwoComplex,
    SpectralPhantomSolver,
    StarHomomorphism,
    UnitaryIntertwiner,
)
from aegis_cstar.receipts import canonical_sha256  # noqa: E402
from aegis_cstar.core import ATOL  # noqa: E402


MASTER_SEED = 20260910


def random_isometry(rng: np.random.Generator, target_dim: int, source_dim: int) -> np.ndarray:
    z = rng.normal(size=(target_dim, source_dim)) + 1j * rng.normal(size=(target_dim, source_dim))
    q, r = np.linalg.qr(z)
    diag = np.diag(r)
    phases = np.where(np.abs(diag) > 0, diag / np.abs(diag), 1.0)
    return q @ np.diag(np.conj(phases))


def random_unitary(rng: np.random.Generator, dim: int) -> np.ndarray:
    return random_isometry(rng, dim, dim)


def random_matrix(rng: np.random.Generator, dim: int) -> np.ndarray:
    return rng.normal(size=(dim, dim)) + 1j * rng.normal(size=(dim, dim))


def scalar_intertwiner(phase: float) -> UnitaryIntertwiner:
    alg = CStarAlgebra(1)
    hom = StarHomomorphism(alg, alg, np.ones((1, 1), dtype=np.complex128))
    return UnitaryIntertwiner(
        hom,
        hom,
        np.array([[cmath.exp(1j * phase)]], dtype=np.complex128),
    )


def principal_phase(x: float) -> float:
    return float(cmath.phase(cmath.exp(1j * x)))


def run() -> dict[str, Any]:
    rng = np.random.default_rng(MASTER_SEED)
    maxima = {
        "isometry_gram_residual": 0.0,
        "star_preservation_residual": 0.0,
        "multiplication_residual": 0.0,
        "intertwining_residual": 0.0,
        "scalar_k3_phase_residual": 0.0,
        "matrix_k3_phase_residual": 0.0,
    }
    counts = {
        "random_isometry_cases": 0,
        "random_intertwiner_cases": 0,
        "random_scalar_k3_cases": 0,
        "random_matrix_k3_cases": 0,
        "random_simplicial_cases": 0,
        "receipt_determinism_checks": 0,
        "tolerance_boundary_checks": 0,
        "phantom_phase_cases": 0,
    }

    # Random finite-dimensional *-homomorphism properties.
    for _ in range(768):
        src_dim = int(rng.integers(1, 5))
        tgt_dim = int(rng.integers(src_dim, 7))
        src = CStarAlgebra(src_dim)
        tgt = CStarAlgebra(tgt_dim)
        e = random_isometry(rng, tgt_dim, src_dim)
        hom = StarHomomorphism(src, tgt, e)
        a = random_matrix(rng, src_dim)
        b = random_matrix(rng, src_dim)
        gram_res = float(np.linalg.norm(e.conj().T @ e - np.eye(src_dim), ord=2))
        star_res = float(
            np.linalg.norm(hom.apply(src.adjoint(a)) - tgt.adjoint(hom.apply(a)), ord=2)
        )
        mult_res = float(np.linalg.norm(hom.apply(a @ b) - hom.apply(a) @ hom.apply(b), ord=2))
        maxima["isometry_gram_residual"] = max(maxima["isometry_gram_residual"], gram_res)
        maxima["star_preservation_residual"] = max(maxima["star_preservation_residual"], star_res)
        maxima["multiplication_residual"] = max(maxima["multiplication_residual"], mult_res)
        if star_res > 5e-12 or mult_res > 5e-11:
            raise AssertionError(("homomorphism_property_failure", star_res, mult_res))
        counts["random_isometry_cases"] += 1

    # Random conjugacy intertwiners.
    for _ in range(768):
        src_dim = int(rng.integers(1, 5))
        tgt_dim = int(rng.integers(src_dim, 7))
        src = CStarAlgebra(src_dim)
        tgt = CStarAlgebra(tgt_dim)
        e = random_isometry(rng, tgt_dim, src_dim)
        u = random_unitary(rng, tgt_dim)
        h0 = StarHomomorphism(src, tgt, e)
        h1 = StarHomomorphism(src, tgt, u @ e)
        inter = UnitaryIntertwiner(h0, h1, u)
        a = random_matrix(rng, src_dim)
        left = h1.apply(a)
        right = u @ h0.apply(a) @ u.conj().T
        residual = float(np.linalg.norm(left - right, ord=2))
        maxima["intertwining_residual"] = max(maxima["intertwining_residual"], residual)
        if not inter.verify_intertwining(a, atol=1e-10):
            raise AssertionError(("intertwining_false_negative", residual))
        counts["random_intertwiner_cases"] += 1

    # Scalar Postnikov loop phase and receipt determinism.
    for _ in range(768):
        phases = rng.uniform(-np.pi, np.pi, size=4)
        p012, p023, p123, p013 = [float(x) for x in phases]
        sheaf = InfinityCStarSheaf(SimplicialTwoComplex())
        sheaf.assign_associator(0, 1, 2, scalar_intertwiner(p012))
        sheaf.assign_associator(0, 2, 3, scalar_intertwiner(p023))
        sheaf.assign_associator(1, 2, 3, scalar_intertwiner(p123))
        sheaf.assign_associator(0, 1, 3, scalar_intertwiner(p013))
        expected = principal_phase(p123 - p013 + p023 + p012)
        got = sheaf.evaluate_postnikov_k3(0, 1, 2, 3)
        residual = abs(principal_phase(got - expected))
        maxima["scalar_k3_phase_residual"] = max(maxima["scalar_k3_phase_residual"], residual)
        if residual > 5e-12:
            raise AssertionError(("scalar_k3_phase_failure", expected, got))
        r1 = sheaf.evaluate_postnikov_k3_receipt(0, 1, 2, 3)
        r2 = sheaf.evaluate_postnikov_k3_receipt(0, 1, 2, 3)
        if canonical_sha256(r1) != canonical_sha256(r2):
            raise AssertionError("receipt nondeterminism")
        counts["receipt_determinism_checks"] += 1
        counts["random_scalar_k3_cases"] += 1

    # Matrix-valued Postnikov loops.
    for _ in range(384):
        dim = int(rng.integers(2, 6))
        alg = CStarAlgebra(dim)
        hom = StarHomomorphism(alg, alg, np.eye(dim, dtype=np.complex128))
        us = [random_unitary(rng, dim) for _ in range(4)]
        ints = [UnitaryIntertwiner(hom, hom, u) for u in us]
        sheaf = InfinityCStarSheaf(SimplicialTwoComplex())
        sheaf.assign_associator(0, 1, 2, ints[0])
        sheaf.assign_associator(0, 2, 3, ints[1])
        sheaf.assign_associator(1, 2, 3, ints[2])
        sheaf.assign_associator(0, 1, 3, ints[3])
        loop = us[2] @ us[3].conj().T @ us[1] @ us[0]
        trace_val = complex(np.trace(loop) / dim)
        receipt = sheaf.evaluate_postnikov_k3_receipt(0, 1, 2, 3, trace_tol=1e-14)
        if abs(trace_val) <= 1e-14:
            if receipt["decision"] != "DENY_PHASE_UNDEFINED_TRACE_NEAR_ZERO":
                raise AssertionError("matrix k3 zero-trace gate failure")
        else:
            expected = float(cmath.phase(trace_val))
            got = float(receipt["k3_phase_radians"])
            residual = abs(principal_phase(got - expected))
            maxima["matrix_k3_phase_residual"] = max(maxima["matrix_k3_phase_residual"], residual)
            if receipt["decision"] != "VERIFIED_NUMERICAL_HOLONOMY" or residual > 5e-12:
                raise AssertionError(("matrix_k3_failure", expected, got))
        counts["random_matrix_k3_cases"] += 1

    # Simplicial canonical closure under faces/edges.
    for _ in range(384):
        space = SimplicialTwoComplex()
        for _ in range(30):
            width = int(rng.integers(1, 4))
            nodes = tuple(int(x) for x in rng.choice(16, size=width, replace=False))
            space.add_simplex(*nodes)
        if space.vertices != sorted(set(space.vertices)):
            raise AssertionError("vertex canonicalization failure")
        if space.edges != sorted(set(space.edges)):
            raise AssertionError("edge canonicalization failure")
        if space.faces != sorted(set(space.faces)):
            raise AssertionError("face canonicalization failure")
        for face in space.faces:
            a, b, c = face
            for edge in [(a, b), (a, c), (b, c)]:
                if tuple(sorted(edge)) not in space.edges:
                    raise AssertionError("simplicial closure failure")
        counts["random_simplicial_cases"] += 1

    # Tolerance edge corpus: just-below accepted, just-above denied.
    alg = CStarAlgebra(2)
    for residual_target, should_pass in [
        (0.50 * ATOL, True),
        (0.95 * ATOL, True),
        (1.05 * ATOL, False),
        (1.50 * ATOL, False),
        (4.00 * ATOL, False),
    ]:
        # For diagonal e=diag(1+eps,1), Gram residual = (1+eps)^2 - 1.
        eps = math.sqrt(1.0 + residual_target) - 1.0
        e = np.diag([1.0 + eps, 1.0]).astype(np.complex128)
        accepted = True
        try:
            StarHomomorphism(alg, alg, e)
        except ValueError:
            accepted = False
        if accepted != should_pass:
            actual = float(np.linalg.norm(e.conj().T @ e - np.eye(2), ord=2))
            raise AssertionError(("isometry_tolerance_boundary_failure", residual_target, actual))
        counts["tolerance_boundary_checks"] += 1

    # Random scalar phantom phases: path overlap exactly one, phase should be reported.
    for _ in range(384):
        p01, p12, p02 = [float(x) for x in rng.uniform(-np.pi, np.pi, size=3)]
        a1 = CStarAlgebra(1)
        h01 = StarHomomorphism(a1, a1, np.array([[cmath.exp(1j*p01)]], dtype=np.complex128))
        h12 = StarHomomorphism(a1, a1, np.array([[cmath.exp(1j*p12)]], dtype=np.complex128))
        h02 = StarHomomorphism(a1, a1, np.array([[cmath.exp(1j*p02)]], dtype=np.complex128))
        space = SimplicialTwoComplex(); space.add_simplex(0, 1, 2)
        sheaf = InfinityCStarSheaf(space)
        sheaf.assign_restriction(0, (0, 1), h01)
        sheaf.assign_restriction(1, (1, 2), h12)
        sheaf.assign_restriction(0, (0, 2), h02)
        expected = principal_phase(p12 + p01 - p02)
        solver = SpectralPhantomSolver(overlap_tol=1e-10, phase_tol=1e-12)
        found = solver.identify_phantoms(sheaf)
        if abs(expected) <= 1e-12:
            if found:
                raise AssertionError(("phantom_false_positive", expected, found))
        else:
            if len(found) != 1 or abs(principal_phase(found[0][1] - expected)) > 5e-12:
                raise AssertionError(("phantom_phase_failure", expected, found))
        counts["phantom_phase_cases"] += 1

    total = int(sum(counts.values()))
    return {
        "schema": "AEGIS_CSTAR_PROPERTY_FUZZ_STRESS_RECEIPT_V1",
        "master_seed": MASTER_SEED,
        "counts": counts,
        "total_property_checks": total,
        "maxima": maxima,
        "result": "PASS",
        "scope": {
            "establishes": [
                "Deterministic randomized finite-dimensional stress coverage for the declared C*-kernel APIs.",
                "Random isometry multiplication/star preservation, conjugacy intertwining, Postnikov phase calculation, simplicial closure, receipt determinism, tolerance-boundary behavior, and scalar phantom phase behavior on the executed corpus."
            ],
            "does_not_establish": [
                "Exhaustive correctness over all finite-dimensional matrices.",
                "Infinite-dimensional C*-algebra correctness.",
                "Formal theorem proof.",
                "Repository or production authority."
            ]
        },
        "authority_effect": "NONE",
    }


def main() -> None:
    receipt = run()
    out = ROOT / "property_fuzz_stress_receipt_v1.json"
    payload = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    receipt["receipt_sha256"] = hashlib.sha256(payload).hexdigest()
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
