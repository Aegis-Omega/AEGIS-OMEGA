from __future__ import annotations

import pytest

from harness.sdk.epistemic_quotient import (
    FINITE_SCOPE,
    OBSTRUCTION,
    PASS,
    FactorizationSampleV1,
    evaluate_factorization,
    require_factorization,
)


def test_safe_destruction_constructs_observed_quotient():
    receipt = evaluate_factorization(
        (
            FactorizationSampleV1("a", {"class": 1}, "same-target"),
            FactorizationSampleV1("b", {"class": 1}, "same-target"),
            FactorizationSampleV1("c", {"class": 2}, "other-target"),
        )
    )
    assert receipt.status == PASS
    assert receipt.scope == FINITE_SCOPE
    assert receipt.sample_count == 3
    assert receipt.fibre_count == 2
    assert receipt.quotient_root is not None
    assert receipt.collision_witnesses == ()
    assert receipt.authority_effect == "NONE"
    assert receipt.quotient_table == (
        ({"class": 1}, "same-target"),
        ({"class": 2}, "other-target"),
    )


def test_abjad_5_41_collision_obstructs_von_mangoldt_like_target():
    receipt = evaluate_factorization(
        (
            FactorizationSampleV1(
                "n=5",
                {"abjad_residue_mod_36": 5},
                {"von_mangoldt_symbolic": "log(5)"},
            ),
            FactorizationSampleV1(
                "n=41",
                {"abjad_residue_mod_36": 5},
                {"von_mangoldt_symbolic": "log(41)"},
            ),
        )
    )
    assert receipt.status == OBSTRUCTION
    assert receipt.quotient_root is None
    assert len(receipt.collision_witnesses) == 1
    witness = receipt.collision_witnesses[0]
    assert witness.projection_value == {"abjad_residue_mod_36": 5}
    assert {witness.left_sample_id, witness.right_sample_id} == {"n=5", "n=41"}


def test_ci_pre_step_fibre_rejects_run_conclusion_as_execution_semantics():
    # Same measured execution fibre: immediate start, zero steps, log unavailable.
    # Different run conclusions arise from workflow policy (continue-on-error),
    # therefore run.conclusion cannot be read as a function of that execution fibre.
    receipt = evaluate_factorization(
        (
            FactorizationSampleV1(
                "hadolint:35496413154",
                {"start_delay_ms": 0, "step_count": 0, "log_status": 404},
                {"run_conclusion": "success"},
            ),
            FactorizationSampleV1(
                "kernel-one:pre-step-control",
                {"start_delay_ms": 0, "step_count": 0, "log_status": 404},
                {"run_conclusion": "failure"},
            ),
        )
    )
    assert receipt.status == OBSTRUCTION
    assert len(receipt.collision_witnesses) == 1


def test_extended_ci_state_can_preserve_execution_class_on_observed_samples():
    receipt = require_factorization(
        (
            FactorizationSampleV1(
                "pre-step-a",
                {
                    "step_count": 0,
                    "log_status": 404,
                    "job_status": "completed",
                },
                "NOT_EXECUTED",
            ),
            FactorizationSampleV1(
                "pre-step-b",
                {
                    "step_count": 0,
                    "log_status": 404,
                    "job_status": "completed",
                },
                "NOT_EXECUTED",
            ),
            FactorizationSampleV1(
                "executed-pass",
                {
                    "step_count": 4,
                    "log_status": 200,
                    "job_status": "completed",
                },
                "EXECUTED",
            ),
        )
    )
    assert receipt.status == PASS
    assert receipt.fibre_count == 2


def test_obstruction_fails_closed_when_factorization_is_required():
    samples = (
        FactorizationSampleV1("left", "collapsed", "A"),
        FactorizationSampleV1("right", "collapsed", "B"),
    )
    with pytest.raises(ValueError, match="FACTORISATION_OBSTRUCTED"):
        require_factorization(samples)


def test_receipt_and_witnesses_are_order_invariant():
    samples = (
        FactorizationSampleV1("z", {"k": 1}, "B"),
        FactorizationSampleV1("a", {"k": 1}, "A"),
        FactorizationSampleV1("m", {"k": 2}, "C"),
    )
    forward = evaluate_factorization(samples)
    reverse = evaluate_factorization(tuple(reversed(samples)))
    assert forward == reverse
    assert forward.receipt_sha256 == reverse.receipt_sha256
    assert tuple(w.root for w in forward.collision_witnesses) == tuple(
        w.root for w in reverse.collision_witnesses
    )


def test_duplicate_sample_identity_is_rejected():
    with pytest.raises(ValueError, match="sample_id values must be unique"):
        evaluate_factorization(
            (
                FactorizationSampleV1("same", 1, "A"),
                FactorizationSampleV1("same", 2, "B"),
            )
        )
