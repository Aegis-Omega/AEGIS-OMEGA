"""
Regression for _build_live_state_context().

The function explicitly tells the model that its live-state block is a measurement
and may be referenced as T1 evidence. Literal claims inside that block therefore
must not contain unmeasured counts or unconditional runtime-status assertions.

This is a static AST test: importing bridge.py starts pulling in the server graph,
while the invariant under test is the source-level distinction between measured
formatted values and hard-coded assertions.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

BRIDGE = Path(__file__).resolve().parents[1] / "bridge.py"
FUNC = "_build_live_state_context"

# Three-or-more digits, or a comma-grouped thousand: the shape of the historical
# hard-coded gate/test counts that were incorrectly presented as live evidence.
NUMERIC_CLAIM = re.compile(r"\d{1,3},\d{3}|\d{3,}")
UNCONDITIONAL_STATUS = ("INTACT", "SOVEREIGN")


def _literal_segments() -> list[str]:
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    fn = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == FUNC
        ),
        None,
    )
    assert fn is not None, f"{FUNC} not found in {BRIDGE}; test must be reconciled"

    segments: list[str] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            segments.append(node.value)

    assert segments, "no string literals found; function shape changed"
    return segments


def test_no_hardcoded_counts_in_live_measurement_block() -> None:
    offenders = [
        (segment, NUMERIC_CLAIM.findall(segment))
        for segment in _literal_segments()
        if NUMERIC_CLAIM.search(segment)
    ]
    assert not offenders, (
        "hard-coded counts appear inside a block represented as live T1 evidence: "
        + "; ".join(f"{numbers} in {segment!r}" for segment, numbers in offenders)
    )


def test_no_unconditionally_asserted_runtime_status() -> None:
    offenders = [
        (word, segment)
        for segment in _literal_segments()
        for word in UNCONDITIONAL_STATUS
        if word in segment
    ]
    assert not offenders, (
        "runtime status asserted without a measured code path: "
        + "; ".join(f"{word!r} in {segment!r}" for word, segment in offenders)
    )


def test_measurement_claim_remains_explicit() -> None:
    joined = " ".join(_literal_segments())
    assert "It is a measurement" in joined, (
        "measurement contract disappeared; if semantics changed, reconcile this test"
    )
