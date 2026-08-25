import pathlib
import sys
import unittest
from dataclasses import replace

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

import cross_domain_collision as cdc
import cross_domain_coverage as cov
import research_invariants as ri


def make_criterion(control_count=4, threshold=0.05):
    return cdc.CollisionCriterionV1(
        universe_min=0,
        universe_max=100000,
        registry_set=("fixture-a", "fixture-b"),
        transform_set=("INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",),
        independence_rule_id="UNIQUE_DOMAIN_ID_V1",
        score_function_id="UNIQUE_EXTERNAL_DOMAINS_V1",
        control_generator_id="PY_RANDOM_UNIFORM_INT_V1",
        control_seed=1234,
        control_count=control_count,
        promotion_threshold=threshold,
        criterion_text=f"coverage-v1-test-criterion:{control_count}:{threshold}",
    )


def make_adapter(registry_id):
    return cov.RegistryAdapterContractV1(
        registry_id=registry_id,
        adapter_version="1",
        query_key_type="integer-decimal",
        transform_id="INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",
        transform_criterion_sha256=ri.literal_sha256("integer identity external lookup key v1"),
        positive_result_rule_id="MATCH_BOOL_TRUE_V1",
        negative_result_rule_id="MATCH_BOOL_FALSE_V1",
        ambiguous_result_rule_id="STATUS_NOT_ESTABLISHED_V1",
        canonicalization_rule_id="CANONICAL_JSON_V1",
        contract_text=f"fixture adapter {registry_id} v1",
    )


def make_snapshot(subject, registry_id, matched):
    return cdc.RegistrySnapshotV1(
        registry_id=registry_id,
        registry_version_or_release="fixture-v1",
        query_key=str(subject.value),
        query_key_type="integer-decimal",
        result_kind="fixture-registry-result",
        canonical_result={"match": matched},
        source_locator=f"fixture://{registry_id}/{subject.value}",
        source_observed_at="2026-08-25T00:00:00Z",
        ingestion_producer_id="coverage-test",
    )


def rehash_receipt(receipt):
    provisional = replace(receipt, receipt_sha256="0" * 64)
    return replace(provisional, receipt_sha256=ri.sha256_hex(cov._probe_receipt_material(provisional)))


def complete_negative_probes(subject, c):
    return [
        cov.probe_registry_snapshot(subject, c, make_adapter("fixture-a"), make_snapshot(subject, "fixture-a", False)),
        cov.probe_registry_snapshot(subject, c, make_adapter("fixture-b"), make_snapshot(subject, "fixture-b", False)),
    ]


def observed_collision(c):
    subject = cdc.IntegerSubjectV1(65010)
    observations = [
        cdc.DomainObservationV1(
            subject.subject_sha256,
            "fixture-a",
            cdc.EvidenceClass.EXTERNAL_IDENTIFIER_MATCH,
            "INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",
            "a" * 64,
            "b" * 64,
            "fixture-a match",
        ),
        cdc.DomainObservationV1(
            subject.subject_sha256,
            "fixture-b",
            cdc.EvidenceClass.EXTERNAL_IDENTIFIER_MATCH,
            "INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",
            "c" * 64,
            "d" * 64,
            "fixture-b match",
        ),
    ]
    return cdc.evaluate_collision(subject, cdc.SelectionProvenance.PROSPECTIVE, observations, c)


def generated_complete_controls(c):
    collisions = []
    coverages = []
    for value in cdc.generate_controls(c):
        subject = cdc.IntegerSubjectV1(value)
        collision, coverage = cov.evaluate_control_from_probes(subject, c, complete_negative_probes(subject, c))
        collisions.append(collision)
        coverages.append(coverage)
    return tuple(collisions), tuple(coverages)


class CoverageProbeTests(unittest.TestCase):
    def test_match_and_no_match_are_source_replayable_and_distinct(self):
        subject = cdc.IntegerSubjectV1(42)
        c = make_criterion()
        adapter = make_adapter("fixture-a")
        match = cov.probe_registry_snapshot(subject, c, adapter, make_snapshot(subject, "fixture-a", True))
        no_match = cov.probe_registry_snapshot(subject, c, adapter, make_snapshot(subject, "fixture-a", False))
        self.assertEqual(match.receipt.outcome, cov.RegistryProbeOutcomeV1.MATCH)
        self.assertEqual(no_match.receipt.outcome, cov.RegistryProbeOutcomeV1.NO_MATCH)
        self.assertNotEqual(match.receipt.receipt_sha256, no_match.receipt.receipt_sha256)
        cov.verify_verified_probe(match)
        cov.verify_verified_probe(no_match)

    def test_unsupported_adapter_rule_fails_closed(self):
        subject = cdc.IntegerSubjectV1(42)
        c = make_criterion()
        bad = replace(make_adapter("fixture-a"), positive_result_rule_id="UNKNOWN_RULE")
        with self.assertRaises(ValueError):
            cov.probe_registry_snapshot(subject, c, bad, make_snapshot(subject, "fixture-a", True))

    def test_probe_receipt_digest_tampering_is_detected(self):
        subject = cdc.IntegerSubjectV1(42)
        probe = cov.probe_registry_snapshot(subject, make_criterion(), make_adapter("fixture-a"), make_snapshot(subject, "fixture-a", True))
        tampered_receipt = replace(probe.receipt, receipt_sha256="f" * 64)
        with self.assertRaises(ValueError):
            cov.verify_verified_probe(replace(probe, receipt=tampered_receipt))

    def test_source_payload_tampering_breaks_replay(self):
        subject = cdc.IntegerSubjectV1(42)
        probe = cov.probe_registry_snapshot(subject, make_criterion(), make_adapter("fixture-a"), make_snapshot(subject, "fixture-a", False))
        wrong_source = make_snapshot(subject, "fixture-a", True)
        with self.assertRaises(ValueError):
            cov.verify_verified_probe(replace(probe, source_snapshot=wrong_source))

    def test_hash_valid_subject_query_splicing_fails(self):
        subject_42 = cdc.IntegerSubjectV1(42)
        subject_43 = cdc.IntegerSubjectV1(43)
        probe = cov.probe_registry_snapshot(subject_42, make_criterion(), make_adapter("fixture-a"), make_snapshot(subject_42, "fixture-a", False))
        spliced = rehash_receipt(replace(probe.receipt, subject_sha256=subject_43.subject_sha256))
        cov.verify_registry_probe_receipt(spliced)
        with self.assertRaises(ValueError):
            cov.verify_verified_probe(replace(probe, receipt=spliced))

    def test_hash_valid_criterion_splicing_fails(self):
        subject = cdc.IntegerSubjectV1(42)
        original = make_criterion(control_count=4)
        other = make_criterion(control_count=5)
        probe = cov.probe_registry_snapshot(subject, original, make_adapter("fixture-a"), make_snapshot(subject, "fixture-a", False))
        spliced = rehash_receipt(replace(probe.receipt, criterion_sha256=other.criterion_sha256))
        cov.verify_registry_probe_receipt(spliced)
        with self.assertRaises(ValueError):
            cov.verify_verified_probe(replace(probe, receipt=spliced))

    def test_missing_registry_cannot_establish_complete_coverage(self):
        subject = cdc.IntegerSubjectV1(42)
        c = make_criterion()
        coverage = cov.aggregate_control_coverage(subject, c, complete_negative_probes(subject, c)[:1])
        self.assertFalse(coverage.coverage_complete)
        self.assertEqual(coverage.missing_registry_ids, ("fixture-b",))

    def test_not_established_registry_blocks_complete_coverage(self):
        subject = cdc.IntegerSubjectV1(42)
        c = make_criterion()
        failure = cov.ProbeFailureEvidenceV1(
            "TimeoutError", "offline fixture timeout", "fixture://failure",
            "2026-08-25T00:00:00Z", "coverage-test"
        )
        probes = [
            cov.probe_registry_snapshot(subject, c, make_adapter("fixture-a"), make_snapshot(subject, "fixture-a", False)),
            cov.probe_not_established(subject, c, make_adapter("fixture-b"), "fixture-v1", failure),
        ]
        coverage = cov.aggregate_control_coverage(subject, c, probes)
        self.assertFalse(coverage.coverage_complete)
        self.assertEqual(coverage.unestablished_registry_ids, ("fixture-b",))

    def test_duplicate_registry_probe_fails_closed(self):
        subject = cdc.IntegerSubjectV1(42)
        c = make_criterion()
        probe = complete_negative_probes(subject, c)[0]
        with self.assertRaises(ValueError):
            cov.aggregate_control_coverage(subject, c, [probe, probe])

    def test_complete_negative_coverage_mints_zero_score_control(self):
        subject = cdc.IntegerSubjectV1(42)
        c = make_criterion()
        collision, coverage = cov.evaluate_control_from_probes(subject, c, complete_negative_probes(subject, c))
        self.assertTrue(coverage.coverage_complete)
        self.assertEqual(collision.score, 0)
        self.assertEqual(collision.provenance, cdc.SelectionProvenance.PROSPECTIVE)

    def test_caller_probe_order_does_not_change_coverage_digest(self):
        subject = cdc.IntegerSubjectV1(42)
        c = make_criterion()
        probes = complete_negative_probes(subject, c)
        a = cov.aggregate_control_coverage(subject, c, probes)
        b = cov.aggregate_control_coverage(subject, c, list(reversed(probes)))
        self.assertEqual(a.receipt_sha256, b.receipt_sha256)

    def test_prospective_null_model_rejects_missing_coverage(self):
        c = make_criterion(control_count=4)
        collisions, _ = generated_complete_controls(c)
        with self.assertRaises(PermissionError):
            cdc.evaluate_null_model(observed_collision(c), c, collisions)

    def test_prospective_null_model_rejects_reordered_coverage(self):
        c = make_criterion(control_count=4)
        collisions, coverages = generated_complete_controls(c)
        with self.assertRaises(ValueError):
            cdc.evaluate_null_model(
                observed_collision(c), c, collisions,
                control_coverages=tuple(reversed(coverages)),
            )

    def test_prospective_null_model_rejects_collision_coverage_splicing(self):
        c = make_criterion(control_count=4)
        collisions, coverages = generated_complete_controls(c)
        subject = coverages[0].subject
        spliced_collision, spliced_coverage = cov.evaluate_control_from_probes(
            subject,
            c,
            [
                cov.probe_registry_snapshot(subject, c, make_adapter("fixture-a"), make_snapshot(subject, "fixture-a", True)),
                cov.probe_registry_snapshot(subject, c, make_adapter("fixture-b"), make_snapshot(subject, "fixture-b", False)),
            ],
        )
        self.assertTrue(spliced_coverage.coverage_complete)
        self.assertEqual(spliced_collision.score, 1)
        self.assertEqual(collisions[0].score, 0)
        with self.assertRaises(ValueError):
            cdc.evaluate_null_model(
                observed_collision(c),
                c,
                (spliced_collision,) + collisions[1:],
                control_coverages=coverages,
            )

    def test_complete_coverage_is_bound_into_null_receipt(self):
        c = make_criterion(control_count=100)
        collisions, coverages = generated_complete_controls(c)
        receipt = cdc.evaluate_null_model(
            observed_collision(c), c, collisions,
            control_coverages=coverages,
        )
        self.assertEqual(
            receipt.control_coverage_receipt_sha256s,
            tuple(x.receipt_sha256 for x in coverages),
        )
        self.assertTrue(receipt.promotion_eligible)
        self.assertTrue(receipt.null_survived)


if __name__ == "__main__":
    unittest.main()
