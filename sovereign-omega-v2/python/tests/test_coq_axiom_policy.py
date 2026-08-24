"""Per-theorem axiom policy: an allowlist that fails closed independently of the baseline.

compare_assumption_baseline() is a ratchet -- it reports what changed since the
last snapshot. It cannot distinguish

  (a) FunctionalExtensionality appearing because a theorem legitimately crossed
      from Q_scope into R, which is the accepted foundation for real analysis in
      Coq and costs exactly two standard axioms, from

  (b) an arbitrary Axiom introduced to discharge a hard lemma,

because both read as regression: true. The only way past (a) is to bump the
baseline, which silently re-baselines any (b) that landed in the same commit.

The policy layer closes that. Permitted symbols are declared with a reason and
a category; everything else is a violation whether or not the baseline knows
about it.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE = (
    Path(__file__).resolve().parents[1] / "coq_attestation.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("_coq_att", MODULE)
    m = importlib.util.module_from_spec(spec)
    sys.modules["_coq_att"] = m
    spec.loader.exec_module(m)
    return m


def _theorem(name: str, symbols: list[str]) -> dict:
    return {"theorem": name, "assumption_symbols": symbols}


def _file(path: str, theorems: list[dict]) -> dict:
    return {
        "path": path,
        "axiom_symbols": [],
        "parameter_symbols": [],
        "admitted_count": 0,
        "theorems": theorems,
    }


def test_axiom_free_theorem_is_clean() -> None:
    m = _load()
    files = [_file("Weil/FiniteBridge.v", [_theorem("pole_kernel_symmetric", [])])]
    policy = m.evaluate_axiom_policy(files)
    assert policy["policy_violation"] is False
    assert policy["unpermitted_assumptions"] == []
    assert policy["permitted_assumptions"] == []


def test_classical_reals_axioms_are_permitted_with_a_reason() -> None:
    """Crossing into R must not read as a fall from grace."""
    m = _load()
    files = [
        _file(
            "Weil/AnalyticTail.v",
            [
                _theorem(
                    "tail_order_bound",
                    [
                        "ClassicalDedekindReals.sig_forall_dec",
                        "FunctionalExtensionality.functional_extensionality_dep",
                    ],
                )
            ],
        )
    ]
    policy = m.evaluate_axiom_policy(files)
    assert policy["policy_violation"] is False, policy["unpermitted_assumptions"]
    assert len(policy["permitted_assumptions"]) == 2
    for entry in policy["permitted_assumptions"]:
        assert entry["category"] == "CLASSICAL_REAL_ANALYSIS_FOUNDATION"
        assert entry["reason"]
        assert entry["location"] == "Weil/AnalyticTail.v::tail_order_bound"


def test_unlisted_axiom_is_a_violation() -> None:
    m = _load()
    files = [
        _file(
            "Weil/AnalyticTail.v",
            [_theorem("global_positivity", ["MyProject.assume_global_weil"])],
        )
    ]
    policy = m.evaluate_axiom_policy(files)
    assert policy["policy_violation"] is True
    assert policy["unpermitted_assumptions"] == [
        {
            "location": "Weil/AnalyticTail.v::global_positivity",
            "symbol": "MyProject.assume_global_weil",
        }
    ]


def test_declared_axiom_in_source_is_a_violation() -> None:
    """An Axiom in the .v file is not laundered by never being reached."""
    m = _load()
    files = [
        {
            "path": "Weil/Shortcut.v",
            "axiom_symbols": ["riemann_hypothesis"],
            "parameter_symbols": [],
            "admitted_count": 0,
            "theorems": [],
        }
    ]
    policy = m.evaluate_axiom_policy(files)
    assert policy["policy_violation"] is True
    assert policy["unpermitted_assumptions"][0]["symbol"] == "riemann_hypothesis"


def test_policy_is_independent_of_the_baseline() -> None:
    """The escape hatch this exists to close.

    A bad axiom present in the baseline produces no ratchet regression, because
    nothing changed. The policy must still reject it.
    """
    m = _load()
    files = [
        _file(
            "Weil/AnalyticTail.v",
            [_theorem("global_positivity", ["MyProject.assume_global_weil"])],
        )
    ]
    baseline = {
        "baseline_kind": "test",
        "declared_assumptions": {},
        "theorem_assumptions": {
            "Weil/AnalyticTail.v::global_positivity": ["MyProject.assume_global_weil"]
        },
        "admitted_sources": {},
    }
    diff = m.compare_assumption_baseline(files, baseline, "0" * 64)
    assert diff["regression"] is False, "ratchet is quiet -- nothing changed"

    policy = m.evaluate_axiom_policy(files)
    assert policy["policy_violation"] is True, (
        "policy must reject an unlisted axiom the baseline has already accepted"
    )


def test_admitted_is_never_permitted() -> None:
    m = _load()
    files = [
        {
            "path": "Weil/WorkInProgress.v",
            "axiom_symbols": [],
            "parameter_symbols": [],
            "admitted_count": 1,
            "theorems": [],
        }
    ]
    policy = m.evaluate_axiom_policy(files)
    assert policy["policy_violation"] is True
    assert policy["admitted_sources"] == ["Weil/WorkInProgress.v"]


def test_the_live_tree_has_exactly_one_unpermitted_axiom() -> None:
    """Pins the finding so it cannot vanish silently.

    Bisimulation/ThreeWay.v:5 asserts

        Axiom cross_runtime_bisimulation :
          forall s e, encode_JS (step_JS s e) = encode_WASM (step_WASM s e) /\\ ...

    which is the three-way bisimulation claim, not a premise of it -- the same
    shape the Python kernel refuses under ASSUME_TARGET_CLAIM. The seven
    Parameters in the same tree abstract over implementations and assert
    nothing, so they are permitted.

    If this test starts failing because the count dropped to zero, the axiom was
    discharged and this test should be tightened, not deleted.
    """
    m = _load()
    root = MODULE.parents[1] / "formal" / "theories"
    files = [
        {"path": str(f.relative_to(root)), **m.inspect_coq_source(f), "theorems": []}
        for f in sorted(root.rglob("*.v"))
    ]
    assert len(files) >= 6, (
        f"found {len(files)} .v files under {root} -- a path bug must not pass "
        "as a clean tree"
    )
    policy = m.evaluate_axiom_policy(files)

    assert policy["policy_violation"] is True
    assert [u["symbol"] for u in policy["unpermitted_assumptions"]] == [
        "cross_runtime_bisimulation"
    ]
    assert len(policy["permitted_assumptions"]) == 7
    assert all(
        e["category"] == m.ABSTRACTION_PARAMETER for e in policy["permitted_assumptions"]
    )
