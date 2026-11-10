"""Keep live telemetry useful without promoting it to verified knowledge.

Preserve the static bans on fixed counts and unconditional status claims.
Exercise only the extracted context function with controlled telemetry; importing
bridge.py would start unrelated server dependencies. These are formatter checks,
not verification of the telemetry source or the complete runtime.
"""
import ast
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

BRIDGE = Path(__file__).resolve().parents[1] / "bridge.py"
FUNC = "_build_live_state_context"

# 3+ digits, or a comma-grouped thousand — the shape of a count or a gate total.
NUMERIC_CLAIM = re.compile(r"\d{1,3},\d{3}|\d{3,}")

# Asserted unconditionally in the original: no code path computes them.
UNCONDITIONAL_STATUS = ("INTACT", "SOVEREIGN")


def _literal_segments() -> list[str]:
    """Every string literal inside the function, f-string parts included.

    FormattedValue nodes (the {var} holes) are deliberately skipped: those are
    the measured parts. Only the literal text between them is under test.
    """
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    fn = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.FunctionDef) and n.name == FUNC),
        None,
    )
    assert fn is not None, f"{FUNC} not found in {BRIDGE} — test is stale, fix the test"
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
    assert out, "no string literals found — the function shape changed"
    return out


def test_no_hardcoded_counts_in_the_live_state_block() -> None:
    offenders = [
        (seg, NUMERIC_CLAIM.findall(seg))
        for seg in _literal_segments()
        if NUMERIC_CLAIM.search(seg)
    ]
    assert not offenders, (
        "hardcoded numbers in a block the model is told to cite as T1 evidence: "
        + "; ".join(f"{nums} in {seg!r}" for seg, nums in offenders)
    )


def test_no_unconditionally_asserted_status_words() -> None:
    offenders = [
        (word, seg)
        for seg in _literal_segments()
        for word in UNCONDITIONAL_STATUS
        if word in seg
    ]
    assert not offenders, (
        "status asserted with no code path computing it: "
        + "; ".join(f"{w!r} in {s!r}" for w, s in offenders)
    )


def _render_context(telemetry=None, error=None) -> str:
    """Run the actual function body without importing the bridge server."""
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    matches = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == FUNC
    ]
    assert len(matches) == 1, f"expected one top-level {FUNC}"
    calls = 0

    def emit_vcg_telemetry():
        nonlocal calls
        calls += 1
        if error is not None:
            raise error
        return telemetry

    namespace = {"matrix": SimpleNamespace(emit_vcg_telemetry=emit_vcg_telemetry)}
    module = ast.Module(body=matches, type_ignores=[])
    exec(compile(module, str(BRIDGE), "exec"), namespace)
    result = namespace[FUNC]()
    assert calls == 1, "context must read the supplied telemetry once"
    assert isinstance(result, str) and result.strip(), "context must not be empty"
    return result


def _assert_candidate_boundary(context: str) -> None:
    for required in (
        "candidate observation", "not admitted knowledge",
        "binds seq/epoch/corruption only",
        "does not prove semantic truth", "Independent verification",
        "admission receipt",
    ):
        assert required in context, f"missing evidence boundary: {required}"
    for forbidden in (
        "verified at this conversation start", "You can reference it as T1 evidence",
        "operating within constitutional bounds right now", "certifies",
    ):
        assert forbidden not in context, f"unsupported promotion: {forbidden}"


def test_observed_telemetry_requires_independent_admission() -> None:
    context = _render_context({
        "sequence": 17, "epoch": 2, "corruption_count": 0,
        "drift_index": 1.0, "pgcs_passes": True,
    })
    _assert_candidate_boundary(context)
    assert "Sequence: 17 | Epoch: 2" in context
    assert "corruption=0" in context
    assert "Assessment: WITHIN_REPORTED_LIMITS" in context
    assert "PGCS flag: reported-passing" in context


def test_changed_telemetry_remains_a_candidate_observation() -> None:
    context = _render_context({
        "sequence": 18, "epoch": 3, "corruption_count": 1,
        "drift_index": 8.0, "pgcs_passes": False,
    })
    _assert_candidate_boundary(context)
    assert "Sequence: 18 | Epoch: 3" in context
    assert "corruption=1" in context
    assert "Assessment: OUTSIDE_REPORTED_LIMITS" in context
    assert "PGCS flag: reported-failing" in context


def test_unavailable_telemetry_does_not_report_verified_state() -> None:
    context = _render_context(error=RuntimeError("telemetry unavailable"))
    assert "unavailable (substrate offline)" in context
    assert "constitutional machinery not confirmed active" in context
    assert "verified at this conversation start" not in context
    assert "T1 evidence" not in context


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(
        unittest.FunctionTestCase(test)
        for name, test in sorted(globals().items())
        if name.startswith("test_") and callable(test)
    )


if __name__ == "__main__":
    unittest.main()
