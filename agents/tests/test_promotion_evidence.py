"""Synthetic cryptographic preflight fixtures, never real observed skill evidence."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from harness.sdk.skill_authority import canonical_bytes
from agents.promotion_evidence import DOMAIN, verify_promotion_evidence


def sealed_fixture():
    private = {role: Ed25519PrivateKey.generate()
               for role in ("operator", "evaluator", "reviewer")}
    trust = {
        role: {
            "key_id": f"fixture:{role}:001",
            "public_key_hex": key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw).hex(),
        } for role, key in private.items()
    }

    def sign(payload, role):
        digest = sha256(DOMAIN + canonical_bytes(payload)).digest()
        return {
            "key_id": trust[role]["key_id"],
            "signature_hex": private[role].sign(digest).hex(),
        }

    plan = {
        "schema_version": "AEGIS_PROMOTION_PLAN_V1",
        "skill_id": "synthetic/fixture",
        "candidate_commit": "a" * 40,
        "baseline_commit": "b" * 40,
        "registry_root": "c" * 64,
        "no_change_root": "d" * 64,
        "external_baseline_root": "e" * 64,
        "direction": "higher",
        "alpha": "0.05",
        "minimum_mean_gain": "0.03",
        "maximum_regressions": 3,
        "tasks": [
            {"id": f"pair-{i:03d}", "task_sha256": sha256(f"task:{i}".encode()).hexdigest()}
            for i in range(30)
        ],
    }
    root = sha256(canonical_bytes(plan)).hexdigest()
    evaluation = {
        "schema_version": "AEGIS_PROMOTION_EVALUATION_V1",
        "plan_sha256": root,
        "candidate_commit": plan["candidate_commit"],
        "baseline_commit": plan["baseline_commit"],
        "registry_root": plan["registry_root"],
        "no_change_root": plan["no_change_root"],
        "external_baseline_root": plan["external_baseline_root"],
        "run_id": "synthetic-fixture-001",
        "trials": [
            {
                "id": task["id"],
                "task_sha256": task["task_sha256"],
                **{f"{name}_score": value for name, value in (
                    ("candidate", "0.70"), ("baseline", "0.51"),
                    ("no_change", "0.50"), ("external", "0.49")
                )},
                **{f"{name}_output_sha256": sha256(
                    f"{task['id']}:{name}".encode()).hexdigest()
                   for name in ("candidate", "baseline", "no_change", "external")},
            } for task in plan["tasks"]
        ],
    }
    signatures = {
        "evaluator": sign(evaluation, "evaluator"),
        "reviewer": sign(evaluation, "reviewer"),
    }
    return {
        "plan": plan,
        "plan_signature": sign(plan, "operator"),
        "evaluation": evaluation,
        "signatures": signatures,
        "trust": trust,
        "expected_plan_sha256": root,
        "expected_candidate": plan["candidate_commit"],
        "expected_registry_root": plan["registry_root"],
    }, sign


class PromotionEvidencePreflightTests(unittest.TestCase):
    def setUp(self):
        self.fixture, self.sign = sealed_fixture()

    def deny(self, reason):
        verdict = verify_promotion_evidence(**self.fixture)
        self.assertEqual(verdict.outcome, "DENIED", verdict)
        self.assertEqual(verdict.reason, reason)

    def resign(self):
        self.fixture["signatures"] = {
            role: self.sign(self.fixture["evaluation"], role)
            for role in ("evaluator", "reviewer")
        }

    def test_valid_synthetic_evidence_only_eligible_for_review(self):
        verdict = verify_promotion_evidence(**self.fixture)
        self.assertEqual(verdict.outcome, "ELIGIBLE_FOR_REVIEW")
        self.assertEqual(verdict.trial_count, 30)
        self.assertEqual(len(verdict.comparisons), 3)
        self.assertEqual(verdict.comparisons[0][2], "1/1073741824")

    def test_self_submitted_public_key_is_not_trust_anchor(self):
        outsider = Ed25519PrivateKey.generate()
        payload = self.fixture["evaluation"]
        self.fixture["signatures"]["evaluator"]["signature_hex"] = outsider.sign(
            sha256(DOMAIN + canonical_bytes(payload)).digest()).hex()
        payload["untrusted_public_key"] = outsider.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw).hex()
        self.deny("EVALUATOR_SIGNATURE_INVALID")

    def test_evaluator_signature_tampering(self):
        self.fixture["signatures"]["evaluator"]["signature_hex"] = "00" * 64
        self.deny("EVALUATOR_SIGNATURE_INVALID")

    def test_reviewer_signature_tampering(self):
        self.fixture["signatures"]["reviewer"]["signature_hex"] = "00" * 64
        self.deny("REVIEWER_SIGNATURE_INVALID")

    def test_operator_plan_signature_tampering(self):
        self.fixture["plan_signature"]["signature_hex"] = "00" * 64
        self.deny("OPERATOR_SIGNATURE_INVALID")

    def test_evaluator_reviewer_role_keys_not_distinct(self):
        self.fixture["trust"]["reviewer"] = deepcopy(self.fixture["trust"]["evaluator"])
        self.deny("SIGNER_ROLES_NOT_INDEPENDENT")

    def test_wrong_head(self):
        self.fixture["expected_candidate"] = "f" * 40
        self.deny("CANDIDATE_HEAD_MISMATCH")

    def test_wrong_registry(self):
        self.fixture["expected_registry_root"] = "f" * 64
        self.deny("REGISTRY_ROOT_MISMATCH")

    def test_modified_or_unpreregistered_plan(self):
        self.fixture["expected_plan_sha256"] = "0" * 64
        self.deny("PLAN_NOT_PREREGISTERED_OR_MODIFIED")

    def test_unplanned_trial(self):
        self.fixture["evaluation"]["trials"].append(
            deepcopy(self.fixture["evaluation"]["trials"][0]))
        self.resign()
        self.deny("TRIAL_SET_NOT_PREREGISTERED")

    def test_duplicate_trial(self):
        trials = self.fixture["evaluation"]["trials"]
        trials[-1] = deepcopy(trials[0])
        self.resign()
        self.deny("DUPLICATE_TRIAL")

    def test_duplicate_task_digests_even_with_distinct_ids(self):
        tasks = self.fixture["plan"]["tasks"]
        tasks[1]["task_sha256"] = tasks[0]["task_sha256"]
        self.fixture["expected_plan_sha256"] = sha256(
            canonical_bytes(self.fixture["plan"])).hexdigest()
        self.fixture["plan_signature"] = self.sign(self.fixture["plan"], "operator")
        self.deny("DUPLICATE_PREREGISTERED_TASK_DIGEST")

    def test_fewer_than_thirty_planned(self):
        self.fixture["plan"]["tasks"] = self.fixture["plan"]["tasks"][:29]
        self.fixture["expected_plan_sha256"] = sha256(
            canonical_bytes(self.fixture["plan"])).hexdigest()
        self.fixture["plan_signature"] = self.sign(self.fixture["plan"], "operator")
        self.deny("FEWER_THAN_30_PREREGISTERED_TASKS")

    def test_trial_task_digest_tampering_even_if_signed(self):
        self.fixture["evaluation"]["trials"][0]["task_sha256"] = "f" * 64
        self.resign()
        self.deny("TASK_DIGEST_MISMATCH")

    def test_external_baseline_regression(self):
        for trial in self.fixture["evaluation"]["trials"]:
            trial["external_score"] = "0.90"
        self.resign()
        self.deny("EXTERNAL_NOT_SIGNIFICANT")

    def test_mean_improvement_below_threshold(self):
        for trial in self.fixture["evaluation"]["trials"]:
            trial["candidate_score"] = "0.515"
            trial["external_score"] = "0.50"
        self.resign()
        self.deny("BASELINE_EFFECT_TOO_SMALL")

    def test_all_ties_fail_significance(self):
        for trial in self.fixture["evaluation"]["trials"]:
            trial["candidate_score"] = "0.51"
        self.resign()
        self.deny("BASELINE_ALL_TIES")

    def test_nan_is_not_a_score(self):
        self.fixture["evaluation"]["trials"][0]["candidate_score"] = "NaN"
        self.resign()
        self.deny("SCORE_FORMAT_INVALID")

    def test_missing_output_binding(self):
        del self.fixture["evaluation"]["trials"][0]["candidate_output_sha256"]
        self.resign()
        self.deny("OUTPUT_DIGEST_MISSING")

    def test_trial_order_invariant_with_new_valid_signatures(self):
        before = verify_promotion_evidence(**self.fixture)
        self.fixture["evaluation"]["trials"].reverse()
        self.resign()
        after = verify_promotion_evidence(**self.fixture)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
