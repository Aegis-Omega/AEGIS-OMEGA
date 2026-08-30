from aegis_interface.ir import lower
from aegis_interface.parser import parse
from aegis_interface.versioned import render_rust, render_typescript

V1 = """
record Snap { id: string, tier: string, note: option<string> }
"""
V2 = """
record Snap { id: string, tier: string, note: option<string>, extra: option<u32>, rank: u64 }
"""


def ir(src):
    return lower(parse(src))


def test_rust_versioned_has_structs_enum_and_migration():
    rs = render_rust(ir(V1), ir(V2), "Snap")
    assert "pub struct SnapV1 {" in rs
    assert "pub struct SnapV2 {" in rs
    assert "pub enum EvolvedSnap {" in rs
    assert "V1(SnapV1) = 1," in rs
    assert "impl Upgrade<SnapV2> for SnapV1 {" in rs
    assert "impl Downgrade<SnapV1> for SnapV2 {" in rs
    # carried field mapped directly; added optional -> None; added required -> todo!
    assert "id: self.id," in rs
    assert "extra: None," in rs
    assert 'todo!("added required field rank")' in rs


def test_old_only_dependency_type_is_emitted():
    # Breaking migration that removes a helper type used by V1: the V1 struct
    # still references it, so the versioned artefact must define it.
    old = "variant Color { red, green } record Snap { id: string, c: Color }"
    new = "record Snap { id: string }"
    rs = render_rust(ir(old), ir(new), "Snap")
    assert "pub enum Color {" in rs          # referenced only by SnapV1
    assert "pub c: Color," in rs
    ts = render_typescript(ir(old), ir(new), "Snap")
    assert 'export type Color = "red" | "green";' in ts


def test_ts_versioned_has_interfaces_and_assertion():
    ts = render_typescript(ir(V1), ir(V2), "Snap")
    assert "export interface SnapV1 {" in ts
    assert "export interface SnapV2 {" in ts
    assert "type AssertAssignable<Sup, Sub extends Sup> = true;" in ts
    # V2 adds a required field -> backward compatible only -> backward assertion present
    assert "Verify_Snap_Backward" in ts
