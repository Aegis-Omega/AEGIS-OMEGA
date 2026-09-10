import numpy as np
from aegis_cstar import CStarAlgebra, StarHomomorphism, UnitaryIntertwiner

def test_cstar_identity_adjoint_and_relation():
    alg = CStarAlgebra(2)
    a = np.array([[1+1j, 2], [0, -1j]], dtype=np.complex128)
    assert np.allclose(alg.identity(), np.eye(2))
    assert np.allclose(alg.adjoint(a), a.conj().T)
    assert alg.verify_relation(a)

def test_star_homomorphism_apply_preserves_star_and_multiplication():
    src = CStarAlgebra(2)
    tgt = CStarAlgebra(3)
    e = np.array([[1,0],[0,1],[0,0]], dtype=np.complex128)
    hom = StarHomomorphism(src, tgt, e)
    a = np.array([[1,2j],[-2j,3]], dtype=np.complex128)
    b = np.array([[0,1],[1,0]], dtype=np.complex128)
    assert np.allclose(hom.apply(src.adjoint(a)), tgt.adjoint(hom.apply(a)))
    assert np.allclose(hom.apply(a @ b), hom.apply(a) @ hom.apply(b))

def test_unitary_intertwiner_identity_passes():
    alg = CStarAlgebra(2)
    hom = StarHomomorphism(alg, alg, np.eye(2, dtype=np.complex128))
    inter = UnitaryIntertwiner(hom, hom, np.eye(2, dtype=np.complex128))
    a = np.array([[1,2],[3,4]], dtype=np.complex128)
    assert inter.verify_intertwining(a)
