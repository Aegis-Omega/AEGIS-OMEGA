from __future__ import annotations

import unittest

from epistemic_authority_conservation import AuthorityLevel
from harness.sdk.meaning_heritage import (
    PreservationProofReceiptV1,
    PreservationRelation,
)
from no_free_epistemic_gain import EpistemicStateV1
from verified_semantic_quotient_consensus import (
    SemanticClassMembershipV1,
    SemanticProjectionReceiptV1,
    issue_projection_receipt,
    project_state,
    semantic_quotient_consensus,
)

A = "a" * 64
B = "b" * 64
C = "c" * 64
V = "1" * 64
P = "2" * 64


class Store:
    def __init__(self, *receipts):
        self.items = {item.root: item for item in receipts}

    def fetch_preservation(self, root):
        return self.items.get(root)


def semeq(source, target, source_fp, target_fp):
    return PreservationProofReceiptV1(
        source_claim_digest=source,
        derived_claim_digest=target,
        relation=PreservationRelation.SEMANTIC_EQUIVALENCE,
        source_semantic_fingerprint=source_fp,
        derived_semantic_fingerprint=target_fp,
        verifier_root=V,
        policy_root=P,
    )


class VerifiedSemanticQuotientConsensusTests(unittest.TestCase):
    def test_exact_identity_needs_no_equivalence_receipt(self):
        raw = EpistemicStateV1(
            frozenset({A}),
            AuthorityLevel.EPISTEMIC,
            100,
        )
        membership = SemanticClassMembershipV1(
            A, "meaning:A", A, "meaning:A"
        )
        receipt = issue_projection_receipt(
            raw.claims,
            (membership,),
            store=Store(),
        )
        projected = project_state(
            raw, receipt, store=Store()
        )
        self.assertEqual(
            projected.semantic_class_ids,
            frozenset({A}),
        )

    def test_different_claim_ids_can_meet_only_with_trusted_semantic_equivalence(self):
        proof = semeq(B, A, "meaning:B", "meaning:A")
        left = EpistemicStateV1(
            frozenset({A}),
            AuthorityLevel.EXECUTION,
            100,
        )
        right = EpistemicStateV1(
            frozenset({B}),
            AuthorityLevel.EPISTEMIC,
            700,
        )
        left_receipt = issue_projection_receipt(
            left.claims,
            (
                SemanticClassMembershipV1(
                    A, "meaning:A", A, "meaning:A"
                ),
            ),
            store=Store(),
        )
        right_receipt = issue_projection_receipt(
            right.claims,
            (
                SemanticClassMembershipV1(
                    B,
                    "meaning:B",
                    A,
                    "meaning:A",
                    proof.root,
                ),
            ),
            store=Store(proof),
        )
        consensus = semantic_quotient_consensus(
            left,
            right,
            left_receipt,
            right_receipt,
            store=Store(proof),
        )
        self.assertEqual(
            consensus.semantic_class_ids,
            frozenset({A}),
        )
        self.assertEqual(
            consensus.authority,
            AuthorityLevel.EPISTEMIC,
        )
        self.assertEqual(consensus.uncertainty_bps, 700)
        self.assertEqual(consensus.authority_effect, "NONE")

    def test_untrusted_equivalence_receipt_denies_projection(self):
        proof = semeq(B, A, "meaning:B", "meaning:A")
        membership = SemanticClassMembershipV1(
            B, "meaning:B", A, "meaning:A", proof.root
        )
        with self.assertRaisesRegex(
            ValueError,
            "UNVERIFIED_SEMANTIC_MEMBERSHIP",
        ):
            issue_projection_receipt(
                frozenset({B}),
                (membership,),
                store=Store(),
            )

    def test_paraphrase_abstraction_is_not_quotient_equivalence(self):
        proof = PreservationProofReceiptV1(
            source_claim_digest=B,
            derived_claim_digest=A,
            relation=PreservationRelation.PARAPHRASE_ABSTRACTION,
            source_semantic_fingerprint="meaning:B",
            derived_semantic_fingerprint="meaning:A",
            verifier_root=V,
            policy_root=P,
        )
        membership = SemanticClassMembershipV1(
            B, "meaning:B", A, "meaning:A", proof.root
        )
        with self.assertRaisesRegex(
            ValueError,
            "UNVERIFIED_SEMANTIC_MEMBERSHIP",
        ):
            issue_projection_receipt(
                frozenset({B}),
                (membership,),
                store=Store(proof),
            )

    def test_wrong_receipt_binding_denies_projection(self):
        proof = semeq(C, A, "meaning:C", "meaning:A")
        membership = SemanticClassMembershipV1(
            B, "meaning:B", A, "meaning:A", proof.root
        )
        with self.assertRaisesRegex(
            ValueError,
            "UNVERIFIED_SEMANTIC_MEMBERSHIP",
        ):
            issue_projection_receipt(
                frozenset({B}),
                (membership,),
                store=Store(proof),
            )

    def test_missing_projection_coverage_denies(self):
        membership = SemanticClassMembershipV1(
            A, "meaning:A", A, "meaning:A"
        )
        with self.assertRaisesRegex(
            ValueError,
            "PROJECTION_COVERAGE_MISMATCH",
        ):
            issue_projection_receipt(
                frozenset({A, B}),
                (membership,),
                store=Store(),
            )

    def test_directly_constructed_untrusted_projection_is_replayed_and_denied(self):
        forged = SemanticProjectionReceiptV1(
            source_claim_digests=(B,),
            memberships=(
                SemanticClassMembershipV1(
                    B,
                    "meaning:B",
                    A,
                    "meaning:A",
                    None,
                ),
            ),
            semantic_class_ids=(A,),
        )
        raw = EpistemicStateV1(
            frozenset({B}),
            AuthorityLevel.EPISTEMIC,
            0,
        )
        with self.assertRaisesRegex(
            ValueError,
            "PROJECTION_RECEIPT_UNTRUSTED",
        ):
            project_state(
                raw,
                forged,
                store=Store(),
            )

    def test_constructor_rejects_tampered_semantic_class_list(self):
        with self.assertRaisesRegex(
            ValueError,
            "SEMANTIC_CLASSES_MISMATCH",
        ):
            SemanticProjectionReceiptV1(
                source_claim_digests=(A,),
                memberships=(
                    SemanticClassMembershipV1(
                        A,
                        "meaning:A",
                        A,
                        "meaning:A",
                    ),
                ),
                semantic_class_ids=(B,),
            )

    def test_unproved_similarity_does_not_create_semantic_consensus(self):
        left = EpistemicStateV1(
            frozenset({A}),
            AuthorityLevel.EPISTEMIC,
            0,
        )
        right = EpistemicStateV1(
            frozenset({B}),
            AuthorityLevel.EPISTEMIC,
            0,
        )
        left_receipt = issue_projection_receipt(
            left.claims,
            (
                SemanticClassMembershipV1(
                    A, "same words", A, "same words"
                ),
            ),
            store=Store(),
        )
        right_receipt = issue_projection_receipt(
            right.claims,
            (
                SemanticClassMembershipV1(
                    B, "same words", B, "same words"
                ),
            ),
            store=Store(),
        )
        consensus = semantic_quotient_consensus(
            left,
            right,
            left_receipt,
            right_receipt,
            store=Store(),
        )
        self.assertEqual(
            consensus.semantic_class_ids,
            frozenset(),
        )


if __name__ == "__main__":
    unittest.main()
