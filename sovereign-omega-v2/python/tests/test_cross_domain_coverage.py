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


if __name__ == "__main__":
    unittest.main()
