"""
_build_live_state_context() injects a block into every model conversation that
says, verbatim: "This state is not a claim. It is a measurement taken by your
own substrate ... You can reference it as T1 evidence."

That sentence is only true if every fact in the block comes from live telemetry.
A hardcoded constant there is a claim wearing a measurement's label, and the
model is instructed to cite it as T1.

Static test on the AST rather than a runtime one: importing bridge.py pulls in
the whole server. The invariant is about the source, so check the source.
"""
import ast
import re
from pathlib import Path

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


def test_the_measurement_sentence_is_still_there() -> None:
    """Guard against 'fixing' this by deleting the claim instead of the falsehood.

    If the sentence goes away the two tests above pass vacuously, so pin it.
    """
    joined = " ".join(_literal_segments())
    assert "It is a measurement" in joined, (
        "the T1 measurement sentence was removed; if that was deliberate, "
        "delete this test with it"
    )
