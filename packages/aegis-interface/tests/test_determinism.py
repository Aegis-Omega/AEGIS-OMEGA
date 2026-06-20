from pathlib import Path

from aegis_interface.compiler import compile_source

WIT = (Path(__file__).resolve().parents[1] / "wit" / "skill_snapshot.wit").read_text()


def test_repeated_compilation_is_bitwise_stable():
    a = compile_source(WIT)
    b = compile_source(WIT)
    assert a.rust == b.rust
    assert a.typescript == b.typescript
    assert a.python == b.python
    assert a.schema_json == b.schema_json


def test_declaration_order_does_not_affect_output():
    ordered = "record A { a: string } record B { b: u32 }"
    reversed_ = "record B { b: u32 } record A { a: string }"
    assert compile_source(ordered).rust == compile_source(reversed_).rust
    assert compile_source(ordered).schema_json == compile_source(reversed_).schema_json


def test_example_wit_compiles_and_is_equivalent():
    result = compile_source(WIT)
    assert result.equivalence().ok, result.equivalence().text()
