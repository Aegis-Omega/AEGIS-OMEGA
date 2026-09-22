from __future__ import annotations
import copy
import unittest
from pathlib import Path
from rh_spectral_operator_registry import RegistryError, load_registry, validate_registry

ROOT=Path(__file__).resolve().parents[3]
REG=ROOT/"governance"/"rh-spectral-operator-registry-v1.json"

class RHSpectralOperatorRegistryTests(unittest.TestCase):
    def test_current_registry_passes(self):
        result=validate_registry(load_registry(REG))
        self.assertEqual(result["status"],"PASS")
        self.assertGreaterEqual(result["claim_count"],15)
        self.assertEqual(result["authority_effect"],"NONE")

    def test_fk_xi_cannot_be_promoted_without_new_evidence(self):
        bad=copy.deepcopy(load_registry(REG))
        target=next(c for c in bad["claims"] if c["id"]=="SPECTRAL_IDENTITY_FK_EQ_XI")
        target["status"]="ESTABLISHED"
        with self.assertRaises(RegistryError):
            validate_registry(bad)

    def test_hilbert_polya_operator_cannot_be_marked_verified(self):
        bad=copy.deepcopy(load_registry(REG))
        target=next(c for c in bad["claims"] if c["id"]=="HILBERT_POLYA_OPERATOR_K")
        target["status"]="VERIFIED"
        with self.assertRaises(RegistryError):
            validate_registry(bad)

    def test_8907_build_does_not_bind_candidate(self):
        bad=copy.deepcopy(load_registry(REG))
        target=next(c for c in bad["claims"] if c["id"]=="FORMALCONJECTURES_UPSTREAM_BUILD")
        target["candidate_binding"]="ESTABLISHED"
        with self.assertRaises(RegistryError):
            validate_registry(bad)

    def test_conditional_s2_cannot_lose_open_premises(self):
        bad=copy.deepcopy(load_registry(REG))
        target=next(c for c in bad["claims"] if c["id"]=="S2_CONDITIONAL_SPECTRAL_RH")
        target["required_open_premises"]=[]
        with self.assertRaises(RegistryError):
            validate_registry(bad)

if __name__=="__main__":
    unittest.main()
