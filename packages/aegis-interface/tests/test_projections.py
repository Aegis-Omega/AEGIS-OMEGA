from aegis_interface.compiler import compile_source

SRC = """
variant Tier { bronze, silver, gold }
record SkillSnapshot {
  skill_id: string,
  tier: Tier,
  @range(0.0, 1.0)
  confidence: f64,
  attempts: u64,
  tags: list<string>,
  parent: option<string>,
}
"""


def test_rust_projection_shapes():
    rust = compile_source(SRC).rust
    assert "pub enum Tier {" in rust
    assert 'rename_all = "snake_case"' in rust
    assert "pub struct SkillSnapshot {" in rust
    assert "pub skill_id: String," in rust
    assert "pub tier: Tier," in rust
    assert "pub confidence: f64," in rust
    assert "pub attempts: u64," in rust
    assert "pub tags: Vec<String>," in rust
    assert "pub parent: Option<String>," in rust
    assert "/// range: 0.0..=1.0" in rust


def test_typescript_projection_shapes():
    ts = compile_source(SRC).typescript
    assert 'export type Tier = "bronze" | "silver" | "gold";' in ts
    assert "export interface SkillSnapshot {" in ts
    assert "skill_id: string;" in ts
    assert "tier: Tier;" in ts
    assert "confidence: number;" in ts
    assert "tags: string[];" in ts
    assert "parent?: string | null;" in ts
    assert "/** range: 0.0..=1.0 */" in ts


def test_python_projection_shapes():
    py = compile_source(SRC).python
    assert 'Tier = Literal["bronze", "silver", "gold"]' in py
    assert "@dataclass" in py
    assert "class SkillSnapshot:" in py
    assert "skill_id: str" in py
    assert "tier: Tier" in py
    assert "confidence: float  # range: 0.0..=1.0" in py
    assert "attempts: int" in py
    assert "tags: list[str]" in py
    assert "parent: Optional[str]" in py


def test_nested_list_of_option_is_parenthesized():
    # Regression: list<option<string>> must render as (string | null)[],
    # not string | null[] (which TS parses as string OR null[]).
    result = compile_source("record R { xs: list<option<string>> }")
    assert "xs: (string | null)[];" in result.typescript
    # and the equivalence gate must still round-trip the parenthesized form
    assert result.equivalence().ok, result.equivalence().text()


def test_generated_python_is_importable(tmp_path):
    py = compile_source(SRC).python
    mod = tmp_path / "types.py"
    mod.write_text(py)
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("gen_types", mod)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen_types"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop("gen_types", None)
    snap = module.SkillSnapshot(
        skill_id="s", tier="gold", confidence=0.9, attempts=3, tags=["a"], parent=None
    )
    assert snap.tier == "gold"
