import cmath
import numpy as np
from aegis_cstar import (
    CStarAlgebra,
    InfinityCStarSheaf,
    SimplicialTwoComplex,
    StarHomomorphism,
    UnitaryIntertwiner,
)

def _scalar_intertwiner(phase: float):
    alg = CStarAlgebra(1)
    hom = StarHomomorphism(alg, alg, np.ones((1,1), dtype=np.complex128))
    u = np.array([[cmath.exp(1j*phase)]], dtype=np.complex128)
    return UnitaryIntertwiner(hom, hom, u)

def test_source_compatible_missing_associator_returns_zero():
    sheaf = InfinityCStarSheaf(SimplicialTwoComplex())
    assert sheaf.evaluate_postnikov_k3(0,1,2,3) == 0.0

def test_governed_k3_receipt_denies_missing_associator():
    sheaf = InfinityCStarSheaf(SimplicialTwoComplex())
    receipt = sheaf.evaluate_postnikov_k3_receipt(0,1,2,3)
    assert receipt["decision"] == "DENY_INCOMPLETE_ASSOCIATOR_DATA"
    assert receipt["authority_effect"] == "NONE"
    assert len(receipt["missing_associators"]) == 4

def test_k3_phase_matches_source_loop_formula():
    sheaf = InfinityCStarSheaf(SimplicialTwoComplex())
    phases = {(0,1,2): 0.10,(0,2,3): 0.20,(1,2,3): 0.30,(0,1,3): 0.05}
    for key, phase in phases.items(): sheaf.assign_associator(*key, _scalar_intertwiner(phase))
    expected = 0.30 - 0.05 + 0.20 + 0.10
    got = sheaf.evaluate_postnikov_k3(0,1,2,3)
    assert np.isclose(got, expected)
    receipt = sheaf.evaluate_postnikov_k3_receipt(0,1,2,3)
    assert receipt["decision"] == "VERIFIED_NUMERICAL_HOLONOMY"
    assert np.isclose(receipt["k3_phase_radians"], expected)

def test_k3_receipt_denies_trace_near_zero():
    alg = CStarAlgebra(2)
    hom = StarHomomorphism(alg, alg, np.eye(2, dtype=np.complex128))
    sheaf = InfinityCStarSheaf(SimplicialTwoComplex())
    ident = UnitaryIntertwiner(hom, hom, np.eye(2, dtype=np.complex128))
    zero_trace = UnitaryIntertwiner(hom, hom, np.diag([1,-1]).astype(np.complex128))
    sheaf.assign_associator(0,1,2, ident)
    sheaf.assign_associator(0,2,3, ident)
    sheaf.assign_associator(0,1,3, ident)
    sheaf.assign_associator(1,2,3, zero_trace)
    receipt = sheaf.evaluate_postnikov_k3_receipt(0,1,2,3)
    assert receipt["decision"] == "DENY_PHASE_UNDEFINED_TRACE_NEAR_ZERO"
    assert receipt["authority_effect"] == "NONE"
