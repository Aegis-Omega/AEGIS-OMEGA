import unittest

from harness.sdk.epistemic_admission import (
    ClaimStatus,
    EpistemicClaimV1,
    FieldProvenance,
    LoadBearingFieldV1,
    RetrievalObservationV1,
    Route,
    SourceBindingV1,
    SubjectBindingV1,
    evaluate_claim,
)


def base_claim(**overrides):
    data = dict(
        claim_id="C-1",
        claim_text="candidate claim",
        status=ClaimStatus.VERIFIED,
        subject=SubjectBindingV1(subject_type="git_commit", subject_id="abc"),
        authority_scope="repo-state",
        evidence_window="run-1",
        load_bearing_fields=[],
        sources=[],
        retrieval_observations=[],
        verification_complete=True,
        historically_valid=True,
        enumeration_complete=True,
        authorship_resolved=True,
    )
    data.update(overrides)
    return EpistemicClaimV1(**data)


class EpistemicAdmissionTests(unittest.TestCase):
    def test_declared_load_bearing_field_is_quarantined(self):
        claim = base_claim(load_bearing_fields=[
            LoadBearingFieldV1("current_head", "abc", True, FieldProvenance.DECLARED)
        ])
        self.assertIs(evaluate_claim(claim, current_subject_sha="abc").route, Route.QUARANTINE)

    def test_historical_receipt_is_preserved_but_stale_head_is_quarantined(self):
        decision = evaluate_claim(base_claim(), current_subject_sha="def")
        self.assertTrue(decision.historically_valid)
        self.assertFalse(decision.current_applicability)
        self.assertIs(decision.route, Route.QUARANTINE)

    def test_search_miss_cannot_establish_nonexistence(self):
        claim = base_claim(retrieval_observations=[
            RetrievalObservationV1(query="2607.24117", found=False, asserted_outcome="NONEXISTENT")
        ])
        self.assertIs(evaluate_claim(claim, current_subject_sha="abc").route, Route.QUARANTINE)

    def test_provenance_pass_does_not_mask_entailment_fail(self):
        claim = base_claim(sources=[
            SourceBindingV1(source_id="S-1", provenance_integrity=True, entails_claim=False)
        ])
        decision = evaluate_claim(claim, current_subject_sha="abc")
        self.assertIs(decision.route, Route.QUARANTINE)
        self.assertIn("CITATION_ENTAILMENT_FAILURE", {x.value for x in decision.failure_loci})

    def test_incomplete_verification_routes_review_not_serve(self):
        decision = evaluate_claim(base_claim(verification_complete=False), current_subject_sha="abc")
        self.assertIs(decision.route, Route.REVIEW)

    def test_incomplete_enumeration_cannot_serve(self):
        decision = evaluate_claim(base_claim(enumeration_complete=False), current_subject_sha="abc")
        self.assertIs(decision.route, Route.REVIEW)
        self.assertIn("ENUMERATION_PROCEDURE", {x.value for x in decision.failure_loci})

    def test_unresolved_authorship_is_quarantined_when_load_bearing(self):
        claim = base_claim(
            authorship_resolved=False,
            load_bearing_fields=[LoadBearingFieldV1("instruction", "do-x", True, FieldProvenance.ATTESTED)],
        )
        decision = evaluate_claim(claim, current_subject_sha="abc")
        self.assertIs(decision.route, Route.QUARANTINE)
        self.assertIn("PROVENANCE_SYSTEM", {x.value for x in decision.failure_loci})

    def test_fully_bound_verified_claim_can_serve(self):
        decision = evaluate_claim(base_claim(), current_subject_sha="abc")
        self.assertIs(decision.route, Route.SERVE)
        self.assertTrue(decision.current_applicability)


if __name__ == "__main__":
    unittest.main()
