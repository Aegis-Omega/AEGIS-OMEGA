from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


class MutationDecisionError(RuntimeError):
    pass


_EXPECTED: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
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
)


def expected_reason_class(mutation_id: str) -> tuple[str, str]:
    expected = _EXPECTED.get(mutation_id)
    if expected is None:
        raise MutationDecisionError(f"UNKNOWN_MUTATION_ID:{mutation_id}")
    return expected


@dataclass(frozen=True)
class MutationDecisionV1:
    mutation_id: str
    observed_decision: str
    observed_reason_class: str
    observed_reason: str
    expected_decision: str
    expected_reason_class: str
    calibration_passed: bool

    @classmethod
    def validate(
        cls,
        *,
        mutation_id: str,
        observed_decision: str,
        observed_reason_class: str,
        observed_reason: str,
    ) -> "MutationDecisionV1":
        expected_decision, required_class = expected_reason_class(mutation_id)

        if observed_decision not in {"ACCEPT", "REJECT"}:
            raise MutationDecisionError(
                f"INVALID_OBSERVED_DECISION:{mutation_id}:{observed_decision}"
            )
        if not isinstance(observed_reason, str) or not observed_reason:
            raise MutationDecisionError(f"MISSING_OBSERVED_REASON:{mutation_id}")
        if observed_decision != expected_decision:
            raise MutationDecisionError(
                f"WRONG_DECISION:{mutation_id}:expected={expected_decision}:observed={observed_decision}"
            )
        if observed_reason_class != required_class:
            if expected_decision == "ACCEPT":
                label = "WRONG_ACCEPTANCE_CLASS"
            else:
                label = "WRONG_REJECTION_CLASS"
            raise MutationDecisionError(
                f"{label}:{mutation_id}:expected={required_class}:observed={observed_reason_class}"
            )

        return cls(
            mutation_id=mutation_id,
            observed_decision=observed_decision,
            observed_reason_class=observed_reason_class,
            observed_reason=observed_reason,
            expected_decision=expected_decision,
            expected_reason_class=required_class,
            calibration_passed=True,
        )
