from aegis_interface.compiler import compile_source
from aegis_interface.equivalence import validate

SRC = """
variant Tier { bronze, silver, gold }
record SkillSnapshot {
  skill_id: string,
  tier: Tier,
  @range(0.0, 1.0)
  confidence: f64,
  tags: list<string>,
}
"""


def test_clean_projections_are_equivalent():
    result = compile_source(SRC)
    report = result.equivalence()
    assert report.ok, report.text()


def test_dropped_field_detected():
    result = compile_source(SRC)
    broken_rust = result.rust.replace("    pub tags: Vec<String>,\n", "")
    report = validate(result.ir, broken_rust, result.typescript, result.python)
    assert not report.ok
    assert any("missing field 'tags'" in f for f in report.findings)


def test_wrong_type_detected():
    result = compile_source(SRC)
    broken_ts = result.typescript.replace("confidence: number;", "confidence: string;")
    report = validate(result.ir, result.rust, broken_ts, result.python)
    assert not report.ok
    assert any("confidence" in f and "type" in f for f in report.findings)


def test_extra_field_detected():
    result = compile_source(SRC)
    broken_py = result.python.replace(
        "    tags: list[str]", "    tags: list[str]\n    sneaky: int"
    )
    report = validate(result.ir, result.rust, result.typescript, broken_py)
    assert not report.ok
    assert any("unexpected field 'sneaky'" in f for f in report.findings)


def test_altered_enum_case_detected():
    result = compile_source(SRC)
    broken_ts = result.typescript.replace('"gold"', '"platinum"')
    report = validate(result.ir, result.rust, broken_ts, result.python)
    assert not report.ok
    assert any("variant Tier" in f for f in report.findings)


def test_missing_range_detected():
    result = compile_source(SRC)
    broken_rust = result.rust.replace("    /// range: 0.0..=1.0\n", "")
    report = validate(result.ir, broken_rust, result.typescript, result.python)
    assert not report.ok
    assert any("confidence" in f and "range" in f for f in report.findings)
