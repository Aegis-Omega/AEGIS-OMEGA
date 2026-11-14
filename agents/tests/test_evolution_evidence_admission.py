"""Evidence-only evolution regression ring for SEC-01, UWP-09 / UWP-10.

All records and evaluator callbacks in this file are SYNTHETIC TEST DOUBLES.
They do not authenticate a human, a real model, or any production evaluation.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from agents.evolution import AdaptiveLineage, EvolutionEngine  # noqa: E402
from harness.sdk.skill_authority import compute_registry_root, evaluate_registry  # noqa: E402


def synthetic_skill() -> dict:
    receipts = [
        {
            "schema_version": "1.0.0",
            "receipt_kind": "AEGIS_SKILL_OBSERVATION_RECEIPT_V1",
            "receipt_id": f"receipt-{index}",
            "run_id": f"run-{index}",
            "skill_id": "swarm_research_v2",
            "outcome": "SUCCEEDED",
            "source_commit": "1" * 40,
            "task_sha256": "2" * 64,
            "result_sha256": "3" * 64,
            "evaluator_receipt_sha256": "4" * 64,
            "agent_id": "synthetic-agent",
            "reviewer_id": "independent-test-double",
            "reviewer_signature_ref": f"synthetic-signature-{index}",
            "review_status": "PASSED",
            "adjudicated_confidence": 0.95,
            "observed_at": f"2026-11-14T00:00:0{index}Z",
        }
        for index in range(3)
    ]
    return {
        "skill_id": "swarm_research_v2",
        "tier": "T2",
        "observation_state": "OBSERVED",
        "validated_runs": 3,
        "confidence": 0.95,
        "recency_score": 0.9,
        "failure_rate": 0.0,
        "failure_rate_observed": 0.0,
        "last_validated": receipts[-1]["observed_at"],
        "observation_receipts": receipts,
        "evidence_refs": ["evidence/fixture.txt"],
        "promotion_admission": {
            "kind": "AEGIS_SKILL_PROMOTION_ADMISSION_V1",
            "skill_id": "swarm_research_v2",
            "admission_sha256": "a" * 64,
            "candidate_sha256": "b" * 64,
            "baseline_sha256": "c" * 64,
            "heldout_evaluation_receipt_sha256": "d" * 64,
            "rollback_sha256": "e" * 64,
            "approval_scope": "T2_TO_T1_ONLY",
            "heldout_pair_count": 30,
            "improvement_status": "IMPROVED",
            "safety_regressions": 0,
            "reviewer_id": "independent-test-double",
            "agent_id": "synthetic-agent",
            "review_status": "PASSED",
            "status": "ADMITTED",
        },
    }


def synthetic_only_verifier(receipt: dict) -> str:
    """Controlled unit test stub. NEVER inject into production."""
    return receipt.get("admission_sha256") or receipt.get("evaluator_receipt_sha256")


def engine(verifier=None) -> EvolutionEngine:
    obj = EvolutionEngine.__new__(EvolutionEngine)
    obj.evidence_verifier = verifier
    return obj


class TemporaryLineage(AdaptiveLineage):
    def __init__(self, path: Path):
        super().__init__()
        self._test_path = path

    def save(self, path: Path | None = None) -> None:
        super().save(path=self._test_path if path is None else path)


class EvidenceEvolutionTests(TestCase):
    def test_30_unverified_numbers_do_not_promote(self):
        skill = synthetic_skill()
        skill["validated_runs"] = 30
        skill["confidence"] = 0.99
        skill["observation_receipts"] = []
        result = engine().evaluate_skill(skill)
        self.assertFalse(result.promoted)
        self.assertIsNone(result.eligible_tier)
        self.assertIn("HOLD_UNVERIFIED_EVIDENCE", result.reason)

    def test_unverified_high_failure_cannot_demote(self):
        skill = synthetic_skill()
        skill["tier"] = "T1"
        skill["failure_rate"] = 0.9
        result = engine().evaluate_skill(skill)
        self.assertIsNone(result.eligible_tier)
        self.assertIn("HOLD_UNVERIFIED_EVIDENCE", result.reason)

    def test_authenticated_observations_without_heldout_admission_hold(self):
        skill = synthetic_skill()
        skill.pop("promotion_admission")
        result = engine(synthetic_only_verifier).evaluate_skill(skill)
        self.assertFalse(result.promoted)
        self.assertEqual(result.reason, "HOLD_PROMOTION_ADMISSION_MISSING")

    def test_29_pairs_are_insufficient(self):
        skill = synthetic_skill()
        skill["promotion_admission"]["heldout_pair_count"] = 29
        result = engine(synthetic_only_verifier).evaluate_skill(skill)
        self.assertEqual(result.reason, "HOLD_INSUFFICIENT_PAIRED_HOLDOUT_EVIDENCE")

    def test_mutation_authority_is_not_self_review(self):
        skill = synthetic_skill()
        skill["promotion_admission"]["reviewer_id"] = "synthetic-agent"
        result = engine(synthetic_only_verifier).evaluate_skill(skill)
        self.assertEqual(result.reason, "HOLD_PROMOTION_REVIEWER_NOT_INDEPENDENT")

    def test_digest_mismatch_and_unavailable_host_hold(self):
        skill = synthetic_skill()
        result = engine().evaluate_skill(skill)
        self.assertFalse(result.promoted)
        result = engine(lambda _: "0" * 64).evaluate_skill(skill)
        self.assertIn("HOLD_UNVERIFIED_EVIDENCE", result.reason)

    def test_safety_regression_and_missing_improvement_hold(self):
        skill = synthetic_skill()
        skill["promotion_admission"]["safety_regressions"] = 1
        self.assertEqual(
            engine(synthetic_only_verifier).evaluate_skill(skill).reason,
            "HOLD_SAFETY_REGRESSION_NOT_CLEARED",
        )
        skill = synthetic_skill()
        skill["promotion_admission"]["improvement_status"] = "UNKNOWN"
        self.assertEqual(
            engine(synthetic_only_verifier).evaluate_skill(skill).reason,
            "HOLD_MEASURED_IMPROVEMENT_NOT_ESTABLISHED",
        )

    def test_t2_t1_positive_is_synthetic_contract_only(self):
        result = engine(synthetic_only_verifier).evaluate_skill(synthetic_skill())
        self.assertTrue(result.promoted)
        self.assertEqual(result.eligible_tier, "T1")

    def test_invalid_registry_denies_tick_without_mutating_files(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            tree = {"schema_version": "2.0.0", "skills": [synthetic_skill()]}
            token = compute_registry_root(tree)
            tree["registry_root"] = token
            tree["genesis_seal"] = token
            tree_path = root / "skill_tree.json"
            tree_path.write_text(json.dumps(tree) + "\n", encoding="utf-8")
            before = tree_path.read_bytes()
            worker = EvolutionEngine(
                tree_path=str(tree_path),
                lineage=TemporaryLineage(root / "lineage.json"),
            )
            with self.assertRaisesRegex(ValueError, "registry evidence invalid"):
                worker.tick(apply_changes=True)
            self.assertEqual(tree_path.read_bytes(), before)
            self.assertFalse((root / "lineage.json").exists())

    def test_promoted_synthetic_temp_registry_rebinds_root(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = root / "evidence" / "fixture.txt"
            evidence.parent.mkdir()
            evidence.write_text("synthetic only\n", encoding="utf-8")
            tree = {"schema_version": "2.0.0", "skills": [synthetic_skill()]}
            previous_root = compute_registry_root(tree)
            tree["registry_root"] = previous_root
            tree["genesis_seal"] = previous_root
            tree_path = root / "skill_tree.json"
            tree_path.write_text(json.dumps(tree) + "\n", encoding="utf-8")
            lineage = TemporaryLineage(root / "lineage.json")
            worker = EvolutionEngine(
                tree_path=str(tree_path),
                lineage=lineage,
                evidence_verifier=synthetic_only_verifier,
            )
            verdicts = worker.tick(apply_changes=True)
            self.assertEqual(len(verdicts), 1)
            self.assertTrue(verdicts[0].promoted)
            saved = json.loads(tree_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["skills"][0]["tier"], "T1")
            self.assertEqual(saved["registry_root"], compute_registry_root(saved))
            self.assertEqual(saved["genesis_seal"], saved["registry_root"])
            self.assertNotEqual(saved["registry_root"], previous_root)
            self.assertEqual(
                evaluate_registry(saved, evidence_verifier=synthetic_only_verifier).outcome,
                "ADMITTED",
            )
            self.assertTrue(lineage.verify_chain()[0])
            self.assertTrue((root / "lineage.json").exists())

    def test_boolean_metrics_and_malformed_admission_do_not_promote(self):
        skill = synthetic_skill()
        skill["validated_runs"] = True
        self.assertIn("HOLD_MALFORMED_METRICS", engine().evaluate_skill(skill).reason)
        skill = synthetic_skill()
        skill["promotion_admission"]["admission_sha256"] = "not-a-sha"
        self.assertEqual(
            engine(synthetic_only_verifier).evaluate_skill(skill).reason,
            "HOLD_PROMOTION_ADMISSION_DIGEST_INVALID",
        )


if __name__ == "__main__":
    main()
