#!/usr/bin/env python3
"""Offline attack fixtures for the independent-review reducer."""
import unittest

from independent_review import (
    SCHEMA,
    assess,
    canonical_digest,
    select_challenges,
    select_reviewer,
)

HEAD = "a" * 40
SEED = "f" * 64


def identity_snapshot():
    body = {
        "source": "trusted_identity_snapshot",
        "snapshot_id": "directory-snapshot-1",
        "identities": [
            {"principal_id": "agent:submitter", "github_ids": [11]},
            {"principal_id": "agent:reviewer", "github_ids": [20, 21]},
            {"principal_id": "agent:challenge-author", "github_ids": [30]},
        ],
    }
    return {**body, "sha256": canonical_digest(body)}


def good_receipt():
    roster = identity_snapshot()
    source_files = [{
        "path": "src/change.py",
        "blob_sha256": "1" * 64,
    }]
    source = {
        "head_sha": HEAD,
        "files": source_files,
    }
    source["sha256"] = canonical_digest(source)
    reviewer = select_reviewer(HEAD, "agent:submitter", roster, SEED)
    challenge_pool = [
        {
            "id": f"falsifier-{index}",
            "class": "counterexample" if index == 1 else "provenance",
            "source_snapshot_sha256": source["sha256"],
            "prompt_sha256": str(index) * 64,
            "expected_answer_visible": False,
            "generator_principal_id": "agent:challenge-author",
        }
        for index in (2, 3)
    ]
    challenges = select_challenges(
        source["sha256"], challenge_pool, SEED, 1,
        "agent:submitter", reviewer["principal_id"],
    )
    return {
        "schema": SCHEMA,
        "selection_seed": SEED,
        "candidate": {"head_sha": HEAD, "source_snapshot": source},
        "submitter": {"principal_id": "agent:submitter", "github_id": 11},
        "review": {
            "approval_id": "review-100",
            "decision": "APPROVED",
            "approved_head_sha": HEAD,
            "source_snapshot_sha256": source["sha256"],
            "reviewer": reviewer,
            "source_isolation": {
                "source_snapshot_sha256": source["sha256"],
                "submitter_identity_visible": False,
                "expected_answer_visible": False,
            },
            "challenge_generator_principal_id": "agent:challenge-author",
            "challenge_pool": challenge_pool,
            "challenge_count": 1,
            "challenge_set": challenges,
            "challenge_set_sha256": canonical_digest(challenges),
            "evidence": [
                {
                    "class": "independent_reproduction",
                    "quality": "strong",
                    "result": "supports",
                    "provenance_group": "reproduction-a",
                },
                {
                    "class": "domain_observation",
                    "quality": "strong",
                    "result": "supports",
                    "provenance_group": "observation-b",
                },
                {
                    "class": "compiler",
                    "quality": "strong",
                    "result": "supports",
                    "provenance_group": "compiler-c",
                },
            ],
            "unresolved_conflicts": [],
            "falsifier_results": [{"id": "falsifier-1", "result": "survived"}],
            "residual_uncertainty": "One supported task class has not been tested.",
        },
    }


class IndependentReviewTests(unittest.TestCase):
    def reject(self, receipt, roster, reason):
        result = assess(receipt, roster)
        self.assertEqual(result["disposition"], "NOT_ADMITTED", result)
        self.assertEqual(result["authority_effect"], "NONE")
        self.assertEqual(result["reason"], reason)

    def test_valid_fixture_is_simulation_only_and_records_review_receipt(self):
        result = assess(good_receipt(), identity_snapshot())
        self.assertEqual(result["disposition"], "OFFLINE_SIMULATION_ONLY")
        self.assertEqual(result["authority_effect"], "NONE")
        self.assertEqual(result["record"]["reviewer_identity"]["github_id"],
                         select_reviewer(HEAD, "agent:submitter",
                                         identity_snapshot(), SEED)["github_id"])
        self.assertEqual(result["record"]["source_snapshot_sha256"],
                         good_receipt()["candidate"]["source_snapshot"]["sha256"])
        self.assertEqual(result["record"]["failed_falsifiers"], [])
        self.assertTrue(result["record"]["residual_uncertainty"])

    def test_selection_collapses_sybil_accounts_to_one_principal(self):
        receipt = good_receipt()
        reviewer = receipt["review"]["reviewer"]
        reviewer["github_id"] = 21 if reviewer["github_id"] == 20 else 20
        self.reject(receipt, identity_snapshot(), "REVIEWER_IDENTITY_MISMATCH")

    def test_forged_reviewer_account_is_rejected(self):
        receipt = good_receipt()
        receipt["review"]["reviewer"]["github_id"] = 999
        self.reject(receipt, identity_snapshot(), "REVIEWER_IDENTITY_MISMATCH")

    def test_reviewer_alias_of_submitter_is_not_independent(self):
        receipt = good_receipt()
        receipt["review"]["reviewer"]["principal_id"] = "agent:submitter"
        receipt["review"]["reviewer"]["github_id"] = 11
        self.reject(receipt, identity_snapshot(), "REVIEWER_IDENTITY_MISMATCH")

    def test_stale_approval_is_rejected(self):
        receipt = good_receipt()
        receipt["review"]["approved_head_sha"] = "b" * 40
        self.reject(receipt, identity_snapshot(), "STALE_APPROVAL")

    def test_leaked_expected_answer_is_rejected(self):
        receipt = good_receipt()
        receipt["review"]["source_isolation"]["expected_answer_visible"] = True
        self.reject(receipt, identity_snapshot(), "EXPECTED_ANSWER_LEAKED")

    def test_challenge_answer_leak_is_rejected(self):
        receipt = good_receipt()
        receipt["review"]["challenge_pool"][0]["expected_answer_visible"] = True
        self.reject(receipt, identity_snapshot(), "CHALLENGE_ANSWER_LEAKED")

    def test_expected_answer_material_is_never_part_of_challenge_pool(self):
        receipt = good_receipt()
        receipt["review"]["challenge_pool"][0]["expected_answer"] = "private answer"
        self.reject(receipt, identity_snapshot(), "CHALLENGE_ANSWER_LEAKED")

    def test_challenge_pool_is_drawn_independently_and_deterministically(self):
        receipt = good_receipt()
        review = receipt["review"]
        expected = select_challenges(
            review["source_snapshot_sha256"], review["challenge_pool"],
            SEED, 1, "agent:submitter", review["reviewer"]["principal_id"],
        )
        self.assertEqual(review["challenge_set"], expected)
        self.assertEqual(expected, select_challenges(
            review["source_snapshot_sha256"], review["challenge_pool"],
            SEED, 1, "agent:submitter", review["reviewer"]["principal_id"],
        ))

    def test_challenge_generator_cannot_share_submitter_or_reviewer_identity(self):
        receipt = good_receipt()
        receipt["review"]["challenge_generator_principal_id"] = (
            receipt["review"]["reviewer"]["principal_id"]
        )
        for item in receipt["review"]["challenge_pool"]:
            item["generator_principal_id"] = receipt["review"]["reviewer"]["principal_id"]
        self.reject(receipt, identity_snapshot(), "CHALLENGE_GENERATOR_NOT_INDEPENDENT")

    def test_weak_evidence_is_rejected(self):
        receipt = good_receipt()
        for item in receipt["review"]["evidence"]:
            item["quality"] = "weak"
        self.reject(receipt, identity_snapshot(), "INSUFFICIENT_INDEPENDENT_EVIDENCE")

    def test_conflicting_evidence_is_rejected(self):
        receipt = good_receipt()
        receipt["review"]["evidence"].append({
            "class": "domain_observation",
            "quality": "strong",
            "result": "contradicts",
            "provenance_group": "observation-c",
        })
        self.reject(receipt, identity_snapshot(), "CONFLICTING_EVIDENCE")

    def test_compiler_only_success_is_rejected(self):
        receipt = good_receipt()
        receipt["review"]["evidence"] = [{
            "class": "compiler",
            "quality": "strong",
            "result": "supports",
            "provenance_group": "compiler-a",
        }]
        self.reject(receipt, identity_snapshot(), "INSUFFICIENT_INDEPENDENT_EVIDENCE")

    def test_triggered_falsifier_is_recorded_and_rejected(self):
        receipt = good_receipt()
        receipt["review"]["falsifier_results"] = [{
            "id": "counterexample-1", "result": "triggered",
        }]
        result = assess(receipt, identity_snapshot())
        self.assertEqual(result["disposition"], "NOT_ADMITTED")
        self.assertEqual(result["reason"], "FALSIFIER_TRIGGERED")
        self.assertEqual(result["record"]["failed_falsifiers"], ["counterexample-1"])

    def test_missing_residual_uncertainty_is_rejected(self):
        receipt = good_receipt()
        receipt["review"]["residual_uncertainty"] = "  "
        self.reject(receipt, identity_snapshot(), "RESIDUAL_UNCERTAINTY_MISSING")

    def test_stale_source_snapshot_is_rejected(self):
        receipt = good_receipt()
        receipt["candidate"]["source_snapshot"]["head_sha"] = "b" * 40
        self.reject(receipt, identity_snapshot(), "SOURCE_SNAPSHOT_STALE")

    def test_untrusted_identity_snapshot_fails_closed(self):
        receipt = good_receipt()
        roster = identity_snapshot()
        roster["source"] = "caller_claim"
        self.reject(receipt, roster, "IDENTITY_SOURCE_UNVERIFIED")

    def test_seeded_selection_is_stable_for_same_exact_head(self):
        roster = identity_snapshot()
        selected = select_reviewer(HEAD, "agent:submitter", roster, SEED)
        self.assertEqual(selected, select_reviewer(HEAD, "agent:submitter", roster, SEED))
        self.assertNotEqual(selected["principal_id"], "agent:submitter")


if __name__ == "__main__":
    unittest.main(verbosity=2)
