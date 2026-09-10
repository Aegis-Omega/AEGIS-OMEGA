import numpy as np
import pytest

from aegis_cstar import CStarAlgebra, StarHomomorphism


def test_star_homomorphism_rejects_nonisometric_embedding():
    src = CStarAlgebra(2)
    tgt = CStarAlgebra(2)
    bad = np.array([[1.0, 0.0], [0.0, 2.0]], dtype=np.complex128)

    with pytest.raises(ValueError, match="isometr"):
        StarHomomorphism(src, tgt, bad)


def test_unitary_intertwiner_rejects_nonunitary_matrix():
    alg = CStarAlgebra(2)
    hom = StarHomomorphism(alg, alg, np.eye(2, dtype=np.complex128))
    bad_u = np.array([[1.0, 0.0], [0.0, 2.0]], dtype=np.complex128)

    from aegis_cstar import UnitaryIntertwiner
    with pytest.raises(ValueError, match="unitary"):
        UnitaryIntertwiner(hom, hom, bad_u)


def test_unitary_intertwiner_rejects_source_dimension_mismatch():
    from aegis_cstar import UnitaryIntertwiner

    src1 = CStarAlgebra(1)
    src2 = CStarAlgebra(2)
    tgt = CStarAlgebra(2)
    h1 = StarHomomorphism(src1, tgt, np.array([[1.0], [0.0]], dtype=np.complex128))
    h2 = StarHomomorphism(src2, tgt, np.eye(2, dtype=np.complex128))

    with pytest.raises(ValueError, match="source dimension"):
        UnitaryIntertwiner(h1, h2, np.eye(2, dtype=np.complex128))


def test_simplicial_complex_rejects_noninteger_nodes_instead_of_coercing():
    from aegis_cstar import SimplicialTwoComplex

    space = SimplicialTwoComplex()
    with pytest.raises(ValueError, match="integer"):
        space.add_simplex(0, 1.5)


def test_cstar_relation_rejects_nonfinite_matrix_without_linalg_failure():
    alg = CStarAlgebra(2)
    bad = np.array([[np.nan, 0.0], [0.0, 1.0]], dtype=np.complex128)

    assert alg.verify_relation(bad) is False


def test_phantom_receipt_denies_incompatible_restriction_path_dimensions():
    from aegis_cstar import InfinityCStarSheaf, SimplicialTwoComplex, SpectralPhantomSolver

    a1 = CStarAlgebra(1)
    a2 = CStarAlgebra(2)
    embed = np.array([[1.0], [0.0]], dtype=np.complex128)

    h01 = StarHomomorphism(a1, a2, embed)
    h12_bad = StarHomomorphism(a1, a2, embed)  # should start from h01.target (dim 2)
    h02 = StarHomomorphism(a1, a2, embed)

    space = SimplicialTwoComplex()
    space.add_simplex(0, 1, 2)
    sheaf = InfinityCStarSheaf(space)
    sheaf.assign_restriction(0, (0, 1), h01)
    sheaf.assign_restriction(1, (1, 2), h12_bad)
    sheaf.assign_restriction(0, (0, 2), h02)

    solver = SpectralPhantomSolver()
    try:
        receipt = solver.identify_phantoms_receipt(sheaf)
    except Exception as exc:  # governed path must deny, not crash
        pytest.fail(f"governed phantom receipt crashed: {exc!r}")

    assert receipt["decision"] == "DENY_INCOMPATIBLE_RESTRICTION_PATH"
    assert receipt["authority_effect"] == "NONE"


def _identity_intertwiner(dim: int):
    from aegis_cstar import UnitaryIntertwiner

    alg = CStarAlgebra(dim)
    hom = StarHomomorphism(alg, alg, np.eye(dim, dtype=np.complex128))
    return UnitaryIntertwiner(hom, hom, np.eye(dim, dtype=np.complex128))


def test_k3_receipt_denies_incompatible_associator_matrix_dimensions():
    from aegis_cstar import InfinityCStarSheaf, SimplicialTwoComplex

    sheaf = InfinityCStarSheaf(SimplicialTwoComplex())
    sheaf.assign_associator(0, 1, 2, _identity_intertwiner(2))
    sheaf.assign_associator(0, 2, 3, _identity_intertwiner(2))
    sheaf.assign_associator(0, 1, 3, _identity_intertwiner(2))
    sheaf.assign_associator(1, 2, 3, _identity_intertwiner(1))

    try:
        receipt = sheaf.evaluate_postnikov_k3_receipt(0, 1, 2, 3)
    except Exception as exc:
        pytest.fail(f"governed k3 receipt crashed: {exc!r}")

    assert receipt["decision"] == "DENY_INCOMPATIBLE_ASSOCIATOR_DIMENSIONS"
    assert receipt["authority_effect"] == "NONE"


def test_matrix_valued_postnikov_loop_preserves_nontrivial_phase():
    import cmath
    from aegis_cstar import InfinityCStarSheaf, SimplicialTwoComplex, UnitaryIntertwiner

    alg = CStarAlgebra(2)
    hom = StarHomomorphism(alg, alg, np.eye(2, dtype=np.complex128))

    def inter(phases):
        u = np.diag([cmath.exp(1j * p) for p in phases]).astype(np.complex128)
        return UnitaryIntertwiner(hom, hom, u)

    sheaf = InfinityCStarSheaf(SimplicialTwoComplex())
    sheaf.assign_associator(0, 1, 2, inter([0.0, 0.0]))
    sheaf.assign_associator(0, 2, 3, inter([0.0, 0.0]))
    sheaf.assign_associator(0, 1, 3, inter([0.0, 0.0]))
    sheaf.assign_associator(1, 2, 3, inter([0.2, 0.4]))

    # Tr(diag(e^.2i,e^.4i))/2 = e^.3i cos(.1), so the normalized-trace phase is .3.
    receipt = sheaf.evaluate_postnikov_k3_receipt(0, 1, 2, 3)
    assert receipt["decision"] == "VERIFIED_NUMERICAL_HOLONOMY"
    assert np.isclose(receipt["k3_phase_radians"], 0.3, atol=1e-12)
    assert np.isclose(sheaf.evaluate_postnikov_k3(0, 1, 2, 3), 0.3, atol=1e-12)
