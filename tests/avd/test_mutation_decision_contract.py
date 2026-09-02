from __future__ import annotations

import pytest

from scripts.avd.mutation_decision import (
    MutationDecisionError,
    MutationDecisionV1,
    expected_reason_class,
)


EXPECTED = {
    "MUT_00": ("ACCEPT", "VERIFIER_ACCEPT"),
    "MUT_01": ("REJECT", "CANDIDATE_SEMANTIC_REJECT"),
    "MUT_02": ("REJECT", "CANDIDATE_SEMANTIC_REJECT"),
    "MUT_03": ("REJECT", "CANDIDATE_SEMANTIC_REJECT"),
    "MUT_04": ("REJECT", "CANDIDATE_SEMANTIC_REJECT"),
    "MUT_05": ("REJECT", "CANDIDATE_SEMANTIC_REJECT"),
    "MUT_06": ("REJECT", "CANDIDATE_SEMANTIC_REJECT"),
    "MUT_07": ("REJECT", "PROOF_INTEGRITY_REJECT"),
    "MUT_08": ("REJECT", "PROOF_INTEGRITY_REJECT"),
    "MUT_09": ("REJECT", "PROOF_INTEGRITY_REJECT"),
    "MUT_10": ("REJECT", "SUBMISSION_SURFACE_REJECT"),
    "MUT_11": ("REJECT", "SUBMISSION_SURFACE_REJECT"),
    "MUT_12": ("REJECT", "ANCHOR_BINDING_REJECT"),
    "MUT_13": ("REJECT", "AUTHORITY_REJECT"),
    "MUT_14": ("REJECT", "COMMITMENT_REJECT"),
    "MUT_15": ("ACCEPT", "VERIFIER_ACCEPT"),
}


def test_every_mutation_has_one_frozen_decision_and_reason_class() -> None:
    assert {f"MUT_{i:02d}" for i in range(16)} == set(EXPECTED)
    for mutation_id, (decision, reason_class) in EXPECTED.items():
        assert expected_reason_class(mutation_id) == (decision, reason_class)


def test_result_must_match_both_decision_and_targeted_reason_class() -> None:
    good = MutationDecisionV1.validate(
        mutation_id="MUT_07",
        observed_decision="REJECT",
        observed_reason_class="PROOF_INTEGRITY_REJECT",
        observed_reason="DECLARED_ASSUMPTION_OR_ADMISSION_FOUND",
    )
    assert good.calibration_passed is True

    with pytest.raises(MutationDecisionError, match="WRONG_REJECTION_CLASS"):
        MutationDecisionV1.validate(
            mutation_id="MUT_07",
            observed_decision="REJECT",
            observed_reason_class="HARNESS_FAILURE",
            observed_reason="COQ_NOT_INSTALLED",
        )


def test_accept_mutants_cannot_pass_on_non_verifier_acceptance() -> None:
    with pytest.raises(MutationDecisionError, match="WRONG_ACCEPTANCE_CLASS"):
        MutationDecisionV1.validate(
            mutation_id="MUT_00",
            observed_decision="ACCEPT",
            observed_reason_class="BYPASS_ACCEPT",
            observed_reason="commitments_valid=True",
        )


def test_unknown_mutation_fails_closed() -> None:
    with pytest.raises(MutationDecisionError, match="UNKNOWN_MUTATION_ID"):
        expected_reason_class("MUT_99")
