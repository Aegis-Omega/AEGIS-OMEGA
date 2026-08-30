import pytest

from aegis_interface.ir import IRError, canonical_schema, lower
from aegis_interface.parser import parse


def _ir(src):
    return lower(parse(src))


def test_primitive_aliases_normalised():
    ir = _ir("record R { a: float64, b: int, c: boolean, d: str }")
    types = {f.name: f.type.name for f in ir.records[0].fields}
    assert types == {"a": "f64", "b": "s64", "c": "bool", "d": "string"}


def test_unknown_type_rejected():
    with pytest.raises(IRError):
        _ir("record R { a: widget }")


def test_reference_to_defined_type_resolves():
    ir = _ir("variant V { x, y } record R { v: V }")
    field = ir.records[0].fields[0]
    assert field.type.kind == "ref"
    assert field.type.name == "V"
    assert ir.type_kind("V") == "variant"


def test_range_on_non_numeric_rejected():
    with pytest.raises(IRError):
        _ir("record R { @range(0.0, 1.0) name: string }")


def test_range_on_numeric_ok():
    ir = _ir("record R { @range(0.0, 1.0) c: f64 }")
    assert ir.records[0].fields[0].range is not None


def test_duplicate_type_name_rejected():
    with pytest.raises(IRError):
        _ir("record R { a: string } variant R { x }")


def test_empty_record_rejected():
    with pytest.raises(IRError):
        _ir("record R { }")


def test_canonical_schema_sorted_top_level():
    ir = _ir("record B { a: string } record A { b: u32 }")
    schema = canonical_schema(ir)
    assert list(schema["records"].keys()) == ["A", "B"]


def test_canonical_schema_preserves_field_order():
    ir = _ir("record R { z: string, a: u32, m: bool }")
    names = [f["name"] for f in canonical_schema(ir)["records"]["R"]]
    assert names == ["z", "a", "m"]
