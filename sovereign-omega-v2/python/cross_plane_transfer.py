"""
CrossPlaneTransferV1 — deterministic classical causal-transfer evaluator.

EPISTEMIC TIER: T2.  This module can admit evidence for a causally useful
derived representation shared across software planes.  It cannot establish
consciousness, a unified subject, or physical quantum coherence.

The evaluator is intentionally float-free and time-free.  Every decision is
bound to an exact repository head, dataset digest, policy digest, model label,
and provider-attestation state in a deterministic receipt.
"""
from __future__ import annotations

import re
import json
import sys
from dataclasses import dataclass
from enum import Enum
from math import comb
from pathlib import Path

from canonical_envelope import canon, sha256_hex


PPM = 1_000_000
ALPHA_PPM = 50_000
MINIMUM_MATCHED_TRIALS = 100
CLAIM_SCOPE = "CLASSICAL_CAUSAL_REPRESENTATION_TRANSFER"
EVIDENCE_TIER = "T2"
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40,64}$")


class ExperimentContractError(ValueError):
    """The submitted experiment does not satisfy the preregistered contract."""


class TrivialSharedStateError(ExperimentContractError):
    """The proposed mediator is only an alias of the raw shared record."""


class Arm(str, Enum):
    B_ONLY = "B_ONLY"
    RAW_SHARED_DATA = "RAW_SHARED_DATA"
    SHUFFLED_Z = "SHUFFLED_Z"
    SHARED_Z = "SHARED_Z"


ARM_ORDER = (
    Arm.B_ONLY,
    Arm.RAW_SHARED_DATA,
    Arm.SHUFFLED_Z,
    Arm.SHARED_Z,
)


@dataclass(frozen=True)
class ExperimentContext:
    experiment_id: str
    exact_head: str
    dataset_digest: str
    policy_digest: str
    model_id: str
    provider: str
    provider_attestation: str
    minimum_effect_ppm: int

    def __post_init__(self) -> None:
        if not self.experiment_id:
            raise ExperimentContractError("experiment_id is required")
        if not _GIT_SHA.fullmatch(self.exact_head):
            raise ExperimentContractError("exact_head must be a 40-64 character lowercase hex Git SHA")
        _require_digest("dataset_digest", self.dataset_digest)
        _require_digest("policy_digest", self.policy_digest)
        if not self.model_id or not self.provider:
            raise ExperimentContractError("model_id and provider are required")
        if self.provider_attestation not in {"ABSENT", "PROVIDER_SIGNED"}:
            raise ExperimentContractError("provider_attestation must be ABSENT or PROVIDER_SIGNED")
        if type(self.minimum_effect_ppm) is not int or not 0 <= self.minimum_effect_ppm <= PPM:
            raise ExperimentContractError("minimum_effect_ppm must be between 0 and 1000000")


@dataclass(frozen=True)
class TrialOutcome:
    trial_id: str
    arm: Arm
    correct: bool
    source_digest: str
    mediator_digest: str

    def __post_init__(self) -> None:
        if not self.trial_id:
            raise ExperimentContractError("trial_id is required")
        if not isinstance(self.arm, Arm):
            raise ExperimentContractError("arm must be an Arm")
        if not isinstance(self.correct, bool):
            raise ExperimentContractError("correct must be boolean")
        _require_digest("source_digest", self.source_digest)
        _require_digest("mediator_digest", self.mediator_digest)


@dataclass(frozen=True)
class ArmResult:
    arm: Arm
    correct: int
    total: int
    accuracy_ppm: int


@dataclass(frozen=True)
class TransferReceipt:
    experiment_id: str
    exact_head: str
    dataset_digest: str
    policy_digest: str
    model_id: str
    provider: str
    provider_attestation: str
    evidence_tier: str
    claim_scope: str
    minimum_effect_ppm: int
    results: tuple[ArmResult, ...]
    effect_over_b_only_ppm: int
    effect_over_raw_ppm: int
    effect_over_shuffled_ppm: int
    p_over_b_only_ppm: int
    p_over_raw_ppm: int
    p_over_shuffled_ppm: int
    admitted: bool
    promotion_eligible: bool
    failures: tuple[str, ...]
    receipt_hash: str

    def accuracy_ppm(self, arm: Arm) -> int:
        for result in self.results:
            if result.arm is arm:
                return result.accuracy_ppm
        raise KeyError(arm)

    def as_dict(self) -> dict:
        """Return a JSON-ready copy; the immutable receipt remains untouched."""
        return {
            "schema_version": "1.0.0",
            "experiment_id": self.experiment_id,
            "exact_head": self.exact_head,
            "dataset_digest": self.dataset_digest,
            "policy_digest": self.policy_digest,
            "model_id": self.model_id,
            "provider": self.provider,
            "provider_attestation": self.provider_attestation,
            "evidence_tier": self.evidence_tier,
            "claim_scope": self.claim_scope,
            "minimum_effect_ppm": self.minimum_effect_ppm,
            "alpha_ppm": ALPHA_PPM,
            "minimum_matched_trials": MINIMUM_MATCHED_TRIALS,
            "results": [
                {
                    "arm": result.arm.value,
                    "correct": result.correct,
                    "total": result.total,
                    "accuracy_ppm": result.accuracy_ppm,
                }
                for result in self.results
            ],
            "effects_ppm": {
                "over_b_only": self.effect_over_b_only_ppm,
                "over_raw": self.effect_over_raw_ppm,
                "over_shuffled": self.effect_over_shuffled_ppm,
            },
            "paired_exact_p_ppm": {
                "over_b_only": self.p_over_b_only_ppm,
                "over_raw": self.p_over_raw_ppm,
                "over_shuffled": self.p_over_shuffled_ppm,
            },
            "admitted": self.admitted,
            "promotion_eligible": self.promotion_eligible,
            "failures": list(self.failures),
            "receipt_hash": self.receipt_hash,
        }


def _require_digest(name: str, value: str) -> None:
    if not _HEX_64.fullmatch(value):
        raise ExperimentContractError(f"{name} must be 64 lowercase hexadecimal characters")


def _validate_and_group(outcomes: tuple[TrialOutcome, ...]) -> dict[Arm, tuple[TrialOutcome, ...]]:
    if not outcomes:
        raise ExperimentContractError("at least one outcome is required")

    grouped: dict[Arm, list[TrialOutcome]] = {arm: [] for arm in ARM_ORDER}
    seen: set[tuple[Arm, str]] = set()
    for outcome in outcomes:
        key = (outcome.arm, outcome.trial_id)
        if key in seen:
            raise ExperimentContractError(f"duplicate outcome for {outcome.arm.value}/{outcome.trial_id}")
        seen.add(key)
        grouped[outcome.arm].append(outcome)

    ordered = {
        arm: tuple(sorted(rows, key=lambda row: row.trial_id))
        for arm, rows in grouped.items()
    }
    reference_ids = tuple(row.trial_id for row in ordered[Arm.B_ONLY])
    if len(reference_ids) < MINIMUM_MATCHED_TRIALS:
        raise ExperimentContractError(
            f"every arm must contain at least {MINIMUM_MATCHED_TRIALS} matched trials"
        )
    for arm in ARM_ORDER[1:]:
        arm_ids = tuple(row.trial_id for row in ordered[arm])
        if arm_ids != reference_ids:
            raise ExperimentContractError("all arms must contain the same matched trial_id set")

    raw_rows = ordered[Arm.RAW_SHARED_DATA]
    if any(row.mediator_digest != row.source_digest for row in raw_rows):
        raise ExperimentContractError("RAW_SHARED_DATA must expose the raw source record")

    shared_rows = ordered[Arm.SHARED_Z]
    if any(row.mediator_digest == row.source_digest for row in shared_rows):
        raise TrivialSharedStateError("SHARED_Z aliases the raw source record")

    shuffled_rows = ordered[Arm.SHUFFLED_Z]
    shared_mediators = sorted(row.mediator_digest for row in shared_rows)
    shuffled_mediators = sorted(row.mediator_digest for row in shuffled_rows)
    if shuffled_mediators != shared_mediators:
        raise ExperimentContractError("SHUFFLED_Z must permute exactly the SHARED_Z mediator set")
    if any(
        shuffled.mediator_digest == shared.mediator_digest
        for shuffled, shared in zip(shuffled_rows, shared_rows)
    ):
        raise ExperimentContractError("SHUFFLED_Z must break every trial-to-mediator binding")

    return ordered


def _arm_result(arm: Arm, rows: tuple[TrialOutcome, ...]) -> ArmResult:
    correct = sum(1 for row in rows if row.correct)
    total = len(rows)
    return ArmResult(
        arm=arm,
        correct=correct,
        total=total,
        accuracy_ppm=(correct * PPM) // total,
    )


def _paired_one_sided_p_ppm(
    shared_rows: tuple[TrialOutcome, ...],
    comparator_rows: tuple[TrialOutcome, ...],
) -> int:
    """Exact one-sided sign test on discordant matched outcomes, encoded in ppm."""
    wins = sum(
        1
        for shared, comparator in zip(shared_rows, comparator_rows)
        if shared.correct and not comparator.correct
    )
    losses = sum(
        1
        for shared, comparator in zip(shared_rows, comparator_rows)
        if not shared.correct and comparator.correct
    )
    discordant = wins + losses
    if discordant == 0:
        return PPM
    numerator = sum(comb(discordant, k) for k in range(wins, discordant + 1))
    denominator = 2 ** discordant
    return (numerator * PPM + denominator - 1) // denominator


def _receipt_body(
    context: ExperimentContext,
    results: tuple[ArmResult, ...],
    effects: tuple[int, int, int],
    p_values: tuple[int, int, int],
    admitted: bool,
    promotion_eligible: bool,
    failures: tuple[str, ...],
) -> dict:
    return {
        "schema_version": "1.0.0",
        "experiment_id": context.experiment_id,
        "exact_head": context.exact_head,
        "dataset_digest": context.dataset_digest,
        "policy_digest": context.policy_digest,
        "model_id": context.model_id,
        "provider": context.provider,
        "provider_attestation": context.provider_attestation,
        "evidence_tier": EVIDENCE_TIER,
        "claim_scope": CLAIM_SCOPE,
        "minimum_effect_ppm": context.minimum_effect_ppm,
        "alpha_ppm": ALPHA_PPM,
        "minimum_matched_trials": MINIMUM_MATCHED_TRIALS,
        "results": [
            {
                "arm": result.arm.value,
                "correct": result.correct,
                "total": result.total,
                "accuracy_ppm": result.accuracy_ppm,
            }
            for result in results
        ],
        "effects_ppm": {
            "over_b_only": effects[0],
            "over_raw": effects[1],
            "over_shuffled": effects[2],
        },
        "paired_exact_p_ppm": {
            "over_b_only": p_values[0],
            "over_raw": p_values[1],
            "over_shuffled": p_values[2],
        },
        "admitted": admitted,
        "promotion_eligible": promotion_eligible,
        "failures": list(failures),
    }


def evaluate_transfer(
    context: ExperimentContext,
    outcomes: tuple[TrialOutcome, ...],
) -> TransferReceipt:
    """Evaluate matched-arm outcomes under the preregistered V1 contract."""
    grouped = _validate_and_group(outcomes)
    results = tuple(_arm_result(arm, grouped[arm]) for arm in ARM_ORDER)
    accuracy = {result.arm: result.accuracy_ppm for result in results}
    effects = (
        accuracy[Arm.SHARED_Z] - accuracy[Arm.B_ONLY],
        accuracy[Arm.SHARED_Z] - accuracy[Arm.RAW_SHARED_DATA],
        accuracy[Arm.SHARED_Z] - accuracy[Arm.SHUFFLED_Z],
    )
    shared_rows = grouped[Arm.SHARED_Z]
    p_values = (
        _paired_one_sided_p_ppm(shared_rows, grouped[Arm.B_ONLY]),
        _paired_one_sided_p_ppm(shared_rows, grouped[Arm.RAW_SHARED_DATA]),
        _paired_one_sided_p_ppm(shared_rows, grouped[Arm.SHUFFLED_Z]),
    )

    failures: list[str] = []
    if effects[0] < context.minimum_effect_ppm:
        failures.append("SHARED_Z_NOT_ABOVE_B_ONLY_BY_SESOI")
    if effects[1] < context.minimum_effect_ppm:
        failures.append("SHARED_Z_NOT_ABOVE_RAW_BY_SESOI")
    if effects[2] < context.minimum_effect_ppm:
        failures.append("SHARED_Z_NOT_ABOVE_SHUFFLED_BY_SESOI")
    if p_values[0] > ALPHA_PPM:
        failures.append("B_ONLY_PAIRED_TEST_ABOVE_ALPHA")
    if p_values[1] > ALPHA_PPM:
        failures.append("RAW_PAIRED_TEST_ABOVE_ALPHA")
    if p_values[2] > ALPHA_PPM:
        failures.append("SHUFFLED_PAIRED_TEST_ABOVE_ALPHA")
    failure_tuple = tuple(failures)
    admitted = not failure_tuple
    promotion_eligible = admitted and context.provider_attestation == "PROVIDER_SIGNED"
    body = _receipt_body(
        context,
        results,
        effects,
        p_values,
        admitted,
        promotion_eligible,
        failure_tuple,
    )
    receipt_hash = sha256_hex(canon(body))

    return TransferReceipt(
        experiment_id=context.experiment_id,
        exact_head=context.exact_head,
        dataset_digest=context.dataset_digest,
        policy_digest=context.policy_digest,
        model_id=context.model_id,
        provider=context.provider,
        provider_attestation=context.provider_attestation,
        evidence_tier=EVIDENCE_TIER,
        claim_scope=CLAIM_SCOPE,
        minimum_effect_ppm=context.minimum_effect_ppm,
        results=results,
        effect_over_b_only_ppm=effects[0],
        effect_over_raw_ppm=effects[1],
        effect_over_shuffled_ppm=effects[2],
        p_over_b_only_ppm=p_values[0],
        p_over_raw_ppm=p_values[1],
        p_over_shuffled_ppm=p_values[2],
        admitted=admitted,
        promotion_eligible=promotion_eligible,
        failures=failure_tuple,
        receipt_hash=receipt_hash,
    )


_SUBMISSION_FIELDS = {"consent", "context", "outcomes"}
_CONTEXT_FIELDS = {
    "experiment_id",
    "exact_head",
    "dataset_digest",
    "policy_digest",
    "model_id",
    "provider",
    "provider_attestation",
    "minimum_effect_ppm",
}
_OUTCOME_FIELDS = {
    "trial_id",
    "arm",
    "correct",
    "source_digest",
    "mediator_digest",
}


def _require_exact_fields(value: dict, expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        unexpected = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise ExperimentContractError(
            f"unexpected {label} fields: {unexpected}; missing {label} fields: {missing}"
        )


def evaluate_submission(payload: object) -> TransferReceipt:
    """Validate a privacy-minimal public submission and evaluate its receipt."""
    if not isinstance(payload, dict):
        raise ExperimentContractError("submission must be a JSON object")
    _require_exact_fields(payload, _SUBMISSION_FIELDS, "submission")
    if payload["consent"] is not True:
        raise ExperimentContractError("explicit consent is required")

    context_payload = payload["context"]
    if not isinstance(context_payload, dict):
        raise ExperimentContractError("context must be a JSON object")
    _require_exact_fields(context_payload, _CONTEXT_FIELDS, "context")
    context = ExperimentContext(**context_payload)

    outcome_payloads = payload["outcomes"]
    if not isinstance(outcome_payloads, list):
        raise ExperimentContractError("outcomes must be a JSON array")
    parsed: list[TrialOutcome] = []
    for index, row in enumerate(outcome_payloads):
        if not isinstance(row, dict):
            raise ExperimentContractError(f"outcomes[{index}] must be a JSON object")
        _require_exact_fields(row, _OUTCOME_FIELDS, f"outcomes[{index}]")
        try:
            arm = Arm(row["arm"])
        except (TypeError, ValueError) as exc:
            raise ExperimentContractError(f"outcomes[{index}].arm is invalid") from exc
        parsed.append(
            TrialOutcome(
                trial_id=row["trial_id"],
                arm=arm,
                correct=row["correct"],
                source_digest=row["source_digest"],
                mediator_digest=row["mediator_digest"],
            )
        )

    return evaluate_transfer(context, tuple(parsed))


def receipt_json(receipt: TransferReceipt) -> str:
    return json.dumps(
        receipt.as_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ) + "\n"


def run_cli(args: tuple[str, ...]) -> int:
    if len(args) != 2:
        raise ExperimentContractError(
            "usage: python cross_plane_transfer.py INPUT.json RECEIPT.json"
        )
    input_path = Path(args[0])
    output_path = Path(args[1])
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    receipt = evaluate_submission(payload)
    output_path.write_text(receipt_json(receipt), encoding="utf-8")
    print(receipt.receipt_hash)
    return 0


if __name__ == "__main__":
    sys.exit(run_cli(tuple(sys.argv[1:])))
