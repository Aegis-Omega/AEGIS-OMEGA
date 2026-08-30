from aegis_interface.evolution import (
    VERDICT_BACKWARD,
    VERDICT_BREAKING,
    VERDICT_FORWARD,
    VERDICT_FULL,
    CompatClass,
    certificate,
    certificate_json,
    classify,
    compat_class,
    composition_proof,
    diff,
    obligations,
    recommend_version_bump,
)
from aegis_interface.ir import lower
from aegis_interface.parser import parse

BASE = """
variant Tier { bronze, silver, gold }
record Snap {
  id: string,
  tier: Tier,
  @range(0.0, 1.0)
  confidence: f64,
  note: option<string>,
}
"""


def ir(src):
    return lower(parse(src))


def verdict(old_src, new_src):
    return classify(diff(ir(old_src), ir(new_src)))


def test_add_optional_field_is_full():
    new = BASE.replace("note: option<string>,", "note: option<string>, extra: option<u32>,")
    assert verdict(BASE, new) == VERDICT_FULL
    assert recommend_version_bump(diff(ir(BASE), ir(new))) == "minor"


def test_add_required_field_is_backward_only():
    new = BASE.replace("note: option<string>,", "note: option<string>, rank: u32,")
    assert verdict(BASE, new) == VERDICT_BACKWARD


def test_remove_required_field_is_forward_only():
    new = BASE.replace("  id: string,\n", "")
    assert verdict(BASE, new) == VERDICT_FORWARD


def test_retype_is_breaking():
    new = BASE.replace("id: string,", "id: u64,")
    assert verdict(BASE, new) == VERDICT_BREAKING
    assert recommend_version_bump(diff(ir(BASE), ir(new))) == "major"


def test_add_enum_case_is_forward_only():
    new = BASE.replace("bronze, silver, gold", "bronze, silver, gold, platinum")
    assert verdict(BASE, new) == VERDICT_FORWARD


def test_remove_enum_case_is_backward_only():
    new = BASE.replace("bronze, silver, gold", "bronze, silver")
    assert verdict(BASE, new) == VERDICT_BACKWARD


def test_tighten_range_backward_widen_forward():
    tighter = BASE.replace("@range(0.0, 1.0)\n  confidence", "@range(0.0, 0.9)\n  confidence")
    wider = BASE.replace("@range(0.0, 1.0)\n  confidence", "@range(0.0, 2.0)\n  confidence")
    assert verdict(BASE, tighter) == VERDICT_BACKWARD
    assert verdict(BASE, wider) == VERDICT_FORWARD


def test_identical_schema_has_no_vectors():
    assert diff(ir(BASE), ir(BASE)) == []
    assert verdict(BASE, BASE) == VERDICT_FULL
    assert recommend_version_bump(diff(ir(BASE), ir(BASE))) == "patch"


def test_obligations_flag_violations():
    new = BASE.replace("id: string,", "id: u64,")
    obls = obligations(diff(ir(BASE), ir(new)))
    assert obls["TypeSafetyPreserved"]["holds"] is False
    assert obls["SerializationInvariant"]["holds"] is False
    assert obls["NoFieldLoss"]["holds"] is True


def test_semiring_composition_table():
    full = CompatClass(True, True)
    back = CompatClass(True, False)
    fwd = CompatClass(False, True)
    breaking = CompatClass(False, False)
    assert back.combine(fwd) == breaking          # Backward ⊗ Forward = Breaking
    assert full.combine(back) == back
    assert fwd.combine(fwd) == fwd
    assert breaking.combine(full) == breaking


def test_certificate_hashes_change_and_are_deterministic():
    new = BASE.replace("note: option<string>,", "note: option<string>, extra: option<u32>,")
    c1 = certificate(ir(BASE), ir(new))
    c2 = certificate(ir(BASE), ir(new))
    assert c1 == c2
    assert c1["source_hash"] != c1["target_hash"]
    assert certificate_json(ir(BASE), ir(new)) == certificate_json(ir(BASE), ir(new))


def test_composition_cancellation_path_stricter_than_net():
    # add a required field then remove it: net is identity (FULL), path is BREAKING.
    s1 = BASE
    s2 = BASE.replace("note: option<string>,", "note: option<string>, rank: u32,")
    s3 = BASE  # rank removed again -> back to s1
    proof = composition_proof(ir(s1), ir(s2), ir(s3))
    assert proof.direct_verdict == VERDICT_FULL
    assert proof.path_verdict == VERDICT_BREAKING
    assert proof.conservative is True       # direct ⊒ path always holds
    assert proof.equivalent is False        # cancellation occurred
