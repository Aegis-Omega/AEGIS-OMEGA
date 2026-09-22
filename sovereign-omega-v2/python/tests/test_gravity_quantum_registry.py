from __future__ import annotations
import copy
import unittest
from pathlib import Path
from gravity_quantum_registry import RegistryError, load_registry, validate_registry

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "governance" / "gravity-quantum-model-registry-v1.json"

class GravityQuantumRegistryTests(unittest.TestCase):
    def test_current_registry_passes(self):
        result=validate_registry(load_registry(REGISTRY))
        self.assertEqual(result["status"],"PASS")
        self.assertGreaterEqual(result["model_count"],5)
        self.assertEqual(result["authority_effect"],"NONE")
        self.assertIn("AZIZ_HOWL_CLASSICAL_ENTANGLEMENT_2025",result["contested_groups"])

    def test_contested_model_without_counteranalyses_denies(self):
        registry=load_registry(REGISTRY)
        bad=copy.deepcopy(registry)
        bad["models"]=[m for m in bad["models"] if m.get("evidence_class")!="PREPRINT_CRITIQUE"]
        with self.assertRaises(RegistryError):
            validate_registry(bad)

    def test_registry_cannot_self_establish_disputed_physics(self):
        registry=load_registry(REGISTRY)
        bad=copy.deepcopy(registry)
        target=next(m for m in bad["models"] if m["id"]=="AZIZ_HOWL_2025_EQ10_SMALL_DX")
        target["interpretation_status"]="ESTABLISHED_CLASSICAL_GRAVITY"
        with self.assertRaises(RegistryError):
            validate_registry(bad)

    def test_unknown_evidence_class_denies(self):
        registry=load_registry(REGISTRY)
        bad=copy.deepcopy(registry)
        bad["models"][0]["evidence_class"]="VERIFIED"
        with self.assertRaises(RegistryError):
            validate_registry(bad)

if __name__ == "__main__":
    unittest.main()
