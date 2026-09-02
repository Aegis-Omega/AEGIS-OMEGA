from __future__ import annotations

from pathlib import Path

from scripts.avd.frozen_reference import FrozenReferenceV1
from scripts.avd.mutation_builder import MutationFixtureBuilderV1
from scripts.avd.mutation_calibration import MutationCalibrationHarnessV1


TARGET = "sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v"
SPEC = "sovereign-omega-v2/formal/tests/Weil/CornO0MorphismBridgeSpec.v"

REFERENCE_SOURCE = """\
Definition corn_ir_to_o0_carrier_v1 (x : IR) : O0RealV1 :=
  CRmorph corn_fast_to_o0_morphism_a1c_v1 (IRasCR x).

Theorem corn_ir_to_o0_preserves_rat_v1 : forall q : Q, True.
Proof.
  intros q.
  eapply CReq_trans.
  - exact dummy_rat_left.
  - apply CRmorph_rat.
Qed.

Theorem corn_ir_to_o0_strict_v1 : forall x y : IR, x [<] y -> True.
Proof.
  intros x y Hxy.
  exact
    (map_pres_less_unfolded
       IR CRasCReals
       (iso_map_rht CRasCReals IR CRIR_iso)
       x y Hxy).
Qed.
"""


def _reference() -> FrozenReferenceV1:
    return FrozenReferenceV1.freeze(
        commit_sha="1" * 40,
        tree_sha="2" * 40,
        source_path=TARGET,
        source_bytes=REFERENCE_SOURCE.encode(),
        dedicated_run_id=101,
        dedicated_conclusion="success",
        formal_attestation_run_id=102,
        formal_attestation_conclusion="success",
        assumptions_closed=True,
    )


def _baseline(tmp_path: Path) -> Path:
    root = tmp_path / "baseline"
    spec = root / SPEC
    spec.parent.mkdir(parents=True)
    spec.write_text("(* frozen challenge spec *)\n", encoding="utf-8")
    return root


def _verifier_for(mutation_id: str):
    if mutation_id in {"MUT_00", "MUT_15"}:
        return lambda _workspace: {"status": "PASS", "reason": "ALL_THEOREMS_CLOSED"}
    if mutation_id in {"MUT_07", "MUT_08", "MUT_09"}:
        return lambda _workspace: {
            "status": "FAIL",
            "reason": "DECLARED_ASSUMPTION_OR_ADMISSION_FOUND",
        }
    return lambda _workspace: {"status": "FAIL", "reason": "SPEC_CONTRACT_FAILURE"}


def test_all_16_fixtures_must_hit_their_targeted_decision_class(tmp_path: Path) -> None:
    ref = _reference()
    fixtures = MutationFixtureBuilderV1(ref, REFERENCE_SOURCE.encode()).build_all()
    harness = MutationCalibrationHarnessV1(
        reference=ref,
        expected_h_verifier="a" * 64,
        expected_h_oracle="b" * 64,
    )
    baseline = _baseline(tmp_path)

    decisions = {}
    for mutation_id, fixture in fixtures.items():
        decisions[mutation_id] = harness.evaluate(
            baseline_root=baseline,
            fixture=fixture,
            verifier=_verifier_for(mutation_id),
        )

    assert set(decisions) == {f"MUT_{i:02d}" for i in range(16)}
    assert all(decision.calibration_passed for decision in decisions.values())


def test_harness_rebuilds_each_candidate_from_clean_baseline(tmp_path: Path) -> None:
    ref = _reference()
    fixtures = MutationFixtureBuilderV1(ref, REFERENCE_SOURCE.encode()).build_all()
    harness = MutationCalibrationHarnessV1(
        reference=ref,
        expected_h_verifier="a" * 64,
        expected_h_oracle="b" * 64,
    )
    baseline = _baseline(tmp_path)

    first = harness.evaluate(
        baseline_root=baseline,
        fixture=fixtures["MUT_10"],
        verifier=_verifier_for("MUT_10"),
    )
    second = harness.evaluate(
        baseline_root=baseline,
        fixture=fixtures["MUT_00"],
        verifier=_verifier_for("MUT_00"),
    )

    assert first.observed_reason_class == "SUBMISSION_SURFACE_REJECT"
    assert second.observed_reason_class == "VERIFIER_ACCEPT"
