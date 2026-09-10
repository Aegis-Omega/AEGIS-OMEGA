import cmath
import numpy as np
from aegis_cstar import CStarAlgebra, InfinityCStarSheaf, SimplicialTwoComplex, SpectralPhantomSolver, StarHomomorphism

def _hom(phase: float):
    alg = CStarAlgebra(1)
    e = np.array([[cmath.exp(1j*phase)]], dtype=np.complex128)
    return StarHomomorphism(alg, alg, e)

def test_source_compatible_phantom_detection_records_phase_twist():
    space = SimplicialTwoComplex(); space.add_simplex(0,1,2)
    sheaf = InfinityCStarSheaf(space)
    sheaf.assign_restriction(0, (0,1), _hom(0.10))
    sheaf.assign_restriction(1, (1,2), _hom(0.20))
    sheaf.assign_restriction(0, (0,2), _hom(0.00))
    solver = SpectralPhantomSolver()
    phantoms = solver.identify_phantoms(sheaf)
    assert len(phantoms) == 1
    face, phase = phantoms[0]
    assert face == (0,1,2)
    assert np.isclose(phase, 0.30)

def test_governed_phantom_receipt_denies_missing_restriction_instead_of_silent_skip():
    space = SimplicialTwoComplex(); space.add_simplex(0,1,2)
    sheaf = InfinityCStarSheaf(space)
    solver = SpectralPhantomSolver()
    assert solver.identify_phantoms(sheaf) == []
    receipt = solver.identify_phantoms_receipt(sheaf)
    assert receipt["decision"] == "DENY_INCOMPLETE_RESTRICTION_DATA"
    assert receipt["skipped_faces"] == [[0,1,2]]
    assert receipt["authority_effect"] == "NONE"
