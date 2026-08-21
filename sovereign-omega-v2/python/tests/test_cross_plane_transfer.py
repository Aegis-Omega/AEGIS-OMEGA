"""
CrossPlaneTransferV1 falsification tests.

These tests deliberately distinguish a causally useful derived mediator from
mere access to the same raw record.  They do not test consciousness or quantum
coherence; the admissible claim is limited to classical cross-plane transfer.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import replace
from hashlib import sha1, sha256
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cross_plane_transfer import (  # noqa: E402
    Arm,
    ExperimentContext,
    TrialOutcome,
    TrivialSharedStateError,
    evaluate_submission,
    evaluate_transfer,
    run_cli,
)


HEAD = "a" * 40
DATASET = "b" * 64
POLICY = "c" * 64
MATCHED_TRIALS = 100


def context(*, minimum_effect_ppm: int = 200_000) -> ExperimentContext:
    return ExperimentContext(
        experiment_id="cross-plane-transfer-v1",
        exact_head=HEAD,
        dataset_digest=DATASET,
        policy_digest=POLICY,
        model_id="gpt-daybreak-blue-latest",
        provider="openai",
        provider_attestation="ABSENT",
        minimum_effect_ppm=minimum_effect_ppm,
    )


def outcomes(
    *,
    b_only_correct: int = 50,
    raw_correct: int = 60,
    shuffled_correct: int = 50,
    shared_correct: int = 90,
    alias_shared_to_raw: bool = False,
) -> tuple[TrialOutcome, ...]:
    rows: list[TrialOutcome] = []
    correct_by_arm = {
        Arm.B_ONLY: b_only_correct,
        Arm.RAW_SHARED_DATA: raw_correct,
        Arm.SHUFFLED_Z: shuffled_correct,
        Arm.SHARED_Z: shared_correct,
    }
    for arm, correct_count in correct_by_arm.items():
        for index in range(MATCHED_TRIALS):
            source_digest = f"{index + 1:064x}"
            mediator_digest = f"{index + 101:064x}"
            if arm is Arm.RAW_SHARED_DATA:
                mediator_digest = source_digest
            elif arm is Arm.SHARED_Z:
                mediator_digest = source_digest if alias_shared_to_raw else f"{index + 201:064x}"
            elif arm is Arm.SHUFFLED_Z:
                mediator_digest = f"{((index + 1) % MATCHED_TRIALS) + 201:064x}"
            rows.append(
                TrialOutcome(
                    trial_id=f"trial-{index:02d}",
                    arm=arm,
                    correct=index < correct_count,
                    source_digest=source_digest,
                    mediator_digest=mediator_digest,
                )
            )
    return tuple(rows)


def submission_payload() -> dict:
    ctx = context()
    return {
        "consent": True,
        "context": {
            "experiment_id": ctx.experiment_id,
            "exact_head": ctx.exact_head,
            "dataset_digest": ctx.dataset_digest,
            "policy_digest": ctx.policy_digest,
            "model_id": ctx.model_id,
            "provider": ctx.provider,
            "provider_attestation": ctx.provider_attestation,
            "minimum_effect_ppm": ctx.minimum_effect_ppm,
        },
        "outcomes": [
            {
                "trial_id": row.trial_id,
                "arm": row.arm.value,
                "correct": row.correct,
                "source_digest": row.source_digest,
                "mediator_digest": row.mediator_digest,
            }
            for row in outcomes()
        ],
    }


class CrossPlaneTransferV1Tests(unittest.TestCase):
    def test_admits_only_effect_above_raw_and_shuffled_controls(self) -> None:
        receipt = evaluate_transfer(context(), outcomes())

        self.assertTrue(receipt.admitted)
        self.assertEqual(receipt.accuracy_ppm(Arm.B_ONLY), 500_000)
        self.assertEqual(receipt.accuracy_ppm(Arm.RAW_SHARED_DATA), 600_000)
        self.assertEqual(receipt.accuracy_ppm(Arm.SHUFFLED_Z), 500_000)
        self.assertEqual(receipt.accuracy_ppm(Arm.SHARED_Z), 900_000)
        self.assertEqual(receipt.effect_over_raw_ppm, 300_000)
        self.assertEqual(receipt.effect_over_shuffled_ppm, 400_000)
        self.assertEqual(receipt.p_over_raw_ppm, 1)
        self.assertEqual(receipt.p_over_shuffled_ppm, 1)
        self.assertEqual(receipt.as_dict()["minimum_matched_trials"], 100)
        self.assertEqual(receipt.provider_attestation, "ABSENT")
        self.assertEqual(receipt.claim_scope, "CLASSICAL_CAUSAL_REPRESENTATION_TRANSFER")

    def test_rejects_shared_z_that_is_only_the_raw_record_under_another_name(self) -> None:
        with self.assertRaisesRegex(TrivialSharedStateError, "aliases the raw source record"):
            evaluate_transfer(context(), outcomes(alias_shared_to_raw=True))

    def test_rejects_when_shared_z_does_not_beat_the_raw_baseline(self) -> None:
        receipt = evaluate_transfer(context(), outcomes(raw_correct=80, shared_correct=80))

        self.assertFalse(receipt.admitted)
        self.assertIn("SHARED_Z_NOT_ABOVE_RAW_BY_SESOI", receipt.failures)

    def test_rejects_when_shuffling_the_mediator_preserves_the_effect(self) -> None:
        receipt = evaluate_transfer(context(), outcomes(shuffled_correct=90, shared_correct=90))

        self.assertFalse(receipt.admitted)
        self.assertIn("SHARED_Z_NOT_ABOVE_SHUFFLED_BY_SESOI", receipt.failures)

    def test_rejects_effect_size_that_does_not_pass_the_paired_exact_test(self) -> None:
        rows = outcomes(b_only_correct=45, raw_correct=45, shuffled_correct=45, shared_correct=55)
        rows = tuple(
            replace(row, correct=int(row.trial_id.split("-")[1]) >= 45)
            if row.arm is Arm.SHARED_Z else row
            for row in rows
        )
        receipt = evaluate_transfer(context(minimum_effect_ppm=100_000), rows)

        self.assertEqual(receipt.effect_over_raw_ppm, 100_000)
        self.assertGreater(receipt.p_over_raw_ppm, 50_000)
        self.assertFalse(receipt.admitted)
        self.assertIn("RAW_PAIRED_TEST_ABOVE_ALPHA", receipt.failures)

    def test_receipt_is_deterministic_and_input_order_independent(self) -> None:
        rows = outcomes()
        first = evaluate_transfer(context(), rows)
        second = evaluate_transfer(context(), tuple(reversed(rows)))

        self.assertEqual(first, second)
        self.assertRegex(first.receipt_hash, r"^[0-9a-f]{64}$")

    def test_public_submission_requires_consent_and_rejects_identity_or_prompt_fields(self) -> None:
        denied = submission_payload()
        denied["consent"] = False
        with self.assertRaisesRegex(ValueError, "explicit consent"):
            evaluate_submission(denied)

        for forbidden_field, value in (("email", "person@example.com"), ("prompt", "secret input")):
            unsafe = submission_payload()
            unsafe[forbidden_field] = value
            with self.assertRaisesRegex(ValueError, "unexpected submission fields"):
                evaluate_submission(unsafe)

    def test_cli_exports_only_the_deterministic_receipt(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            output_path = Path(directory) / "receipt.json"
            input_path.write_text(json.dumps(submission_payload()), encoding="utf-8")

            exit_code = run_cli((str(input_path), str(output_path)))
            exported = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertTrue(exported["admitted"])
        self.assertFalse(exported["promotion_eligible"])
        self.assertNotIn("consent", exported)
        self.assertNotIn("outcomes", exported)
        self.assertNotIn("prompt", exported)
        self.assertNotIn("email", exported)

    def test_admission_workflow_executes_this_falsification_suite(self) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        workflow = (repository_root / ".github/workflows/experiment-admission.yml").read_text(
            encoding="utf-8"
        )
        command = "python python/tests/test_cross_plane_transfer.py"

        self.assertEqual(workflow.count(command), 1)

    def test_experiment_plan_is_bound_to_the_current_policy_blob(self) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        policy_path = repository_root / "docs/experiments/cross-plane-transfer-v1.md"
        plan = json.loads(
            (repository_root / ".aegis/experiments/cross-plane-transfer-v1.json").read_text(
                encoding="utf-8"
            )
        )
        policy_bytes = policy_path.read_bytes()
        git_blob = sha1(
            f"blob {len(policy_bytes)}\0".encode("ascii") + policy_bytes,
            usedforsecurity=False,
        ).hexdigest()

        self.assertEqual(plan["policy"]["blob_id"], git_blob)

    def test_experiment_parent_state_root_covers_the_current_policy_binding(self) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        plan = json.loads(
            (repository_root / ".aegis/experiments/cross-plane-transfer-v1.json").read_text(
                encoding="utf-8"
            )
        )
        payload = {
            "claims_ledger_root": plan["claims_ledger"]["root"],
            "constitution_blob_id": plan["constitution"]["blob_id"],
            "domain": "AEGIS_EXPERIMENT_PARENT_STATE_V0_1",
            "expected_parent_sha": plan["expected_parent_sha"],
            "policy_blob_id": plan["policy"]["blob_id"],
            "repository": plan["repository"],
            "sovereignty_contracts_blob_id": plan["sovereignty_contracts"]["blob_id"],
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        self.assertEqual(plan["expected_parent_state_root"], sha256(canonical).hexdigest())


if __name__ == "__main__":
    unittest.main()
