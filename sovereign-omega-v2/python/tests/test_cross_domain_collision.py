import pathlib
import sys
import unittest

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))
import cross_domain_collision as cdc


def fixture_criterion(**overrides):
    values = dict(
        universe_min=0,
        universe_max=100000,
        registry_set=("unicode", "ncbi-gene"),
        transform_set=("UNICODE_LOOKUP_V1", "NCBI_LOOKUP_V1", "INTEGER_FACTORISATION_V1"),
        independence_rule_id="UNIQUE_DOMAIN_ID_V1",
        score_function_id="UNIQUE_EXTERNAL_DOMAINS_V1",
        control_generator_id="PY_RANDOM_UNIFORM_INT_V1",
        control_seed=1234,
        control_count=16,
        promotion_threshold=0.05,
        criterion_text="fixture collision criterion v1",
    )
    values.update(overrides)
    return cdc.CollisionCriterionV1(**values)


def fixture_observation(subject, domain_id, evidence_class, transform_id, suffix):
    return cdc.DomainObservationV1(
        subject_sha256=subject.subject_sha256,
        domain_id=domain_id,
        evidence_class=evidence_class,
        transform_id=transform_id,
        transform_criterion_sha256="c" * 64,
        evidence_artifact_sha256=(suffix * 64)[:64],
        normalized_claim=f"claim-{domain_id}-{suffix}",
    )


def two_domain_collision(provenance, criterion):
    subject = cdc.IntegerSubjectV1(65010)
    unicode_obs = fixture_observation(
        subject,
        "unicode",
        cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING,
        "UNICODE_LOOKUP_V1",
        "a",
    )
    ncbi_obs = fixture_observation(
        subject,
        "ncbi-gene",
        cdc.EvidenceClass.EXTERNAL_IDENTIFIER_MATCH,
        "NCBI_LOOKUP_V1",
        "b",
    )
    return cdc.evaluate_collision(subject, provenance, [unicode_obs, ncbi_obs], criterion)


def zero_control_receipts(criterion):
    return tuple(
        cdc.evaluate_collision(
            cdc.IntegerSubjectV1(value),
            cdc.SelectionProvenance.PROSPECTIVE,
            [],
            criterion,
        )
        for value in cdc.generate_controls(criterion)
    )


class CrossDomainCollisionTests(unittest.TestCase):
    def test_integer_subject_is_representation_independent(self):
        a = cdc.IntegerSubjectV1(65010)
        b = cdc.IntegerSubjectV1(int("FDF2", 16))
        self.assertEqual(a.value, b.value)
        self.assertEqual(a.subject_sha256, b.subject_sha256)
        self.assertEqual(a.hex_upper, "FDF2")
        self.assertEqual(a.unicode_codepoint_label, "U+FDF2")

    def test_unicode_label_rejects_out_of_range_integer(self):
        subject = cdc.IntegerSubjectV1(0x110000)
        with self.assertRaises(ValueError):
            _ = subject.unicode_codepoint_label

    def test_transform_epoch_changes_on_literal_edit(self):
        a = cdc.TransformSpecV1(
            "INTEGER_TO_HEX_V1", "1", "IntegerSubjectV1", "HexString", "uppercase hexadecimal"
        )
        b = cdc.TransformSpecV1(
            "INTEGER_TO_HEX_V1", "1", "IntegerSubjectV1", "HexString", "uppercase  hexadecimal"
        )
        self.assertNotEqual(a.criterion_sha256, b.criterion_sha256)

    def test_snapshot_digest_changes_with_semantic_result(self):
        common = dict(
            registry_id="unicode",
            registry_version_or_release="observed-2026-08-25",
            query_key="U+FDF2",
            query_key_type="unicode-codepoint",
            result_kind="assigned-codepoint-record",
            source_locator="unicode://U+FDF2",
            source_observed_at="2026-08-25T00:00:00Z",
            ingestion_producer_id="fixture-test-v1",
        )
        a = cdc.RegistrySnapshotV1(canonical_result={"codepoint": "U+FDF2", "name": "A"}, **common)
        b = cdc.RegistrySnapshotV1(canonical_result={"codepoint": "U+FDF2", "name": "B"}, **common)
        self.assertNotEqual(a.content_sha256, b.content_sha256)

    def test_local_derivation_is_not_external_registry_evidence(self):
        subject = cdc.IntegerSubjectV1(65010)
        transform = cdc.TransformSpecV1(
            "INTEGER_TO_NUMBER_THEORY_PROPERTIES_V1",
            "1",
            "IntegerSubjectV1",
            "NumberTheoryProperties",
            "exact integer factorisation",
        )
        receipt = cdc.DerivationReceiptV1(
            subject_sha256=subject.subject_sha256,
            derivation_id="INTEGER_FACTORISATION_V1",
            derivation_version="1",
            criterion_sha256=transform.criterion_sha256,
            canonical_result={"prime_factors": [2, 3, 5, 11, 197]},
        )
        self.assertEqual(receipt.evidence_class, cdc.EvidenceClass.DERIVED_PROPERTY)

    def test_same_domain_cannot_inflate_independent_domain_count(self):
        subject = cdc.IntegerSubjectV1(65010)
        a = fixture_observation(subject, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "UNICODE_LOOKUP_V1", "a")
        b = fixture_observation(subject, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "UNICODE_LOOKUP_V1", "b")
        receipt = cdc.evaluate_collision(subject, cdc.SelectionProvenance.RETROSPECTIVE, [a, b], fixture_criterion())
        self.assertEqual(receipt.independent_external_domain_count, 1)
        self.assertFalse(receipt.cross_registry_collision)

    def test_local_derived_property_does_not_satisfy_external_threshold(self):
        subject = cdc.IntegerSubjectV1(65010)
        unicode_obs = fixture_observation(subject, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "UNICODE_LOOKUP_V1", "a")
        arithmetic_obs = fixture_observation(subject, "number-theory", cdc.EvidenceClass.DERIVED_PROPERTY, "INTEGER_FACTORISATION_V1", "b")
        receipt = cdc.evaluate_collision(subject, cdc.SelectionProvenance.RETROSPECTIVE, [unicode_obs, arithmetic_obs], fixture_criterion())
        self.assertEqual(receipt.independent_external_domain_count, 1)
        self.assertFalse(receipt.cross_registry_collision)

    def test_two_unique_external_domains_form_collision(self):
        receipt = two_domain_collision(cdc.SelectionProvenance.RETROSPECTIVE, fixture_criterion())
        self.assertEqual(receipt.independent_external_domain_count, 2)
        self.assertTrue(receipt.cross_registry_collision)
        self.assertEqual(receipt.score, 2)

    def test_subject_splicing_fails_closed(self):
        a = cdc.IntegerSubjectV1(65010)
        b = cdc.IntegerSubjectV1(65011)
        observation = fixture_observation(a, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "UNICODE_LOOKUP_V1", "a")
        with self.assertRaises(ValueError):
            cdc.evaluate_collision(b, cdc.SelectionProvenance.RETROSPECTIVE, [observation], fixture_criterion())

    def test_unknown_transform_fails_closed(self):
        subject = cdc.IntegerSubjectV1(65010)
        observation = fixture_observation(subject, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "UNREGISTERED_TRANSFORM_V1", "a")
        with self.assertRaises(ValueError):
            cdc.evaluate_collision(subject, cdc.SelectionProvenance.RETROSPECTIVE, [observation], fixture_criterion())

    def test_control_generation_is_exactly_replayable(self):
        criterion = fixture_criterion(control_seed=1234, control_count=16)
        self.assertEqual(cdc.generate_controls(criterion), cdc.generate_controls(criterion))

    def test_different_seed_changes_control_sequence(self):
        a = fixture_criterion(control_seed=1234, control_count=16)
        b = fixture_criterion(control_seed=1235, control_count=16)
        self.assertNotEqual(cdc.generate_controls(a), cdc.generate_controls(b))

    def test_retrospective_fixture_cannot_be_promoted_by_null_model(self):
        criterion = fixture_criterion(control_count=100)
        collision = two_domain_collision(cdc.SelectionProvenance.RETROSPECTIVE, criterion)
        with self.assertRaises(PermissionError):
            cdc.evaluate_null_model(collision, criterion, zero_control_receipts(criterion))

    def test_retrospective_descriptive_null_receipt_is_not_promotion_eligible(self):
        criterion = fixture_criterion(control_count=100)
        collision = two_domain_collision(cdc.SelectionProvenance.RETROSPECTIVE, criterion)
        receipt = cdc.evaluate_null_model(
            collision,
            criterion,
            zero_control_receipts(criterion),
            allow_retrospective_descriptive=True,
        )
        self.assertFalse(receipt.promotion_eligible)
        self.assertIsNone(receipt.null_survived)
        self.assertEqual(receipt.control_coverage_receipt_sha256s, ())

    def test_prospective_null_cannot_use_uncovered_synthetic_controls(self):
        criterion = fixture_criterion(control_count=100, promotion_threshold=0.05)
        collision = two_domain_collision(cdc.SelectionProvenance.PROSPECTIVE, criterion)
        with self.assertRaises(PermissionError):
            cdc.evaluate_null_model(collision, criterion, zero_control_receipts(criterion))

    def test_threshold_free_prospective_null_still_requires_coverage(self):
        criterion = fixture_criterion(control_count=10, promotion_threshold=None)
        collision = two_domain_collision(cdc.SelectionProvenance.PROSPECTIVE, criterion)
        with self.assertRaises(PermissionError):
            cdc.evaluate_null_model(collision, criterion, zero_control_receipts(criterion))


if __name__ == "__main__":
    unittest.main()
