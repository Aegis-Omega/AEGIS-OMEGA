from pathlib import Path
import copy
from scripts.validate_obligations import load_registry, validate_registry

ROOT = Path(__file__).resolve().parents[1]

def registry():
    return load_registry(ROOT / "PROOF_OBLIGATIONS.yaml")

def test_canonical_registry_validates():
    assert validate_registry(registry(), ROOT / "schemas/proof-obligations.schema.json") == []

def test_duplicate_node_id_fails_closed():
    data = registry(); data["nodes"].append(copy.deepcopy(data["nodes"][0]))
    assert any("duplicate node id" in e.lower() for e in validate_registry(data, ROOT / "schemas/proof-obligations.schema.json"))

def test_unknown_dependency_fails_closed():
    data = registry(); data["nodes"][-1]["dependencies"] = ["DOES_NOT_EXIST"]
    assert any("unknown dependency" in e.lower() for e in validate_registry(data, ROOT / "schemas/proof-obligations.schema.json"))

def test_cycle_fails_closed():
    data = registry(); {n["id"]: n for n in data["nodes"]}["CRITICAL_STRIP_LOCALIZATION"]["dependencies"] = ["RH"]
    assert any("cycle" in e.lower() for e in validate_registry(data, ROOT / "schemas/proof-obligations.schema.json"))

def test_rh_cannot_be_promoted_with_open_ancestors():
    data = registry(); data["rh_status"] = "PROVEN"; {n["id"]: n for n in data["nodes"]}["RH"]["status"] = "PROVED_MACHINE_CHECKED"
    assert any("rh promotion" in e.lower() for e in validate_registry(data, ROOT / "schemas/proof-obligations.schema.json"))

def test_authority_effect_is_constitutionally_none():
    data = registry(); data["authority_effect"] = "ELEVATED"
    assert any("authority_effect" in e.lower() for e in validate_registry(data, ROOT / "schemas/proof-obligations.schema.json"))

def test_machine_checked_requires_exact_binding():
    data = registry(); node = next(n for n in data["nodes"] if n["status"] == "PROVED_MACHINE_CHECKED"); node["proof_binding"]["exact_head"] = None
    assert any("exact_head" in e.lower() for e in validate_registry(data, ROOT / "schemas/proof-obligations.schema.json"))
