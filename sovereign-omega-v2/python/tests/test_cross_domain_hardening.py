import pathlib
import sys
import unittest

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))
import cross_domain_collision as cdc
import research_invariants as ri


def criterion(**overrides):
    values = dict(
        universe_min=0,
        universe_max=100000,
        registry_set=("unicode", "ncbi-gene"),
        transform_set=("UNICODE_LOOKUP_V1", "NCBI_LOOKUP_V1"),
        independence_rule_id="UNIQUE_DOMAIN_ID_V1",
        score_function_id="UNIQUE_EXTERNAL_DOMAINS_V1",
        control_generator_id="PY_RANDOM_UNIFORM_INT_V1",
        control_seed=1234,
        control_count=4,
        promotion_threshold=0.05,
        criterion_text="hardening criterion v1",
    )
    values.update(overrides)
    return cdc.CollisionCriterionV1(**values)


def observed_collision(c):
    subject = cdc.IntegerSubjectV1(65010)
    observations = [
        cdc.DomainObservationV1(
            subject.subject_sha256,
            "unicode",
            cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING,
            "UNICODE_LOOKUP_V1",
            "a" * 64,
            "b" * 64,
            "unicode match",
        ),
        cdc.DomainObservationV1(
            subject.subject_sha256,
            "ncbi-gene",
            cdc.EvidenceClass.EXTERNAL_IDENTIFIER_MATCH,
            "NCBI_LOOKUP_V1",
            "c" * 64,
            "d" * 64,
            "ncbi match",
        ),
    ]
    return cdc.evaluate_collision(subject, cdc.SelectionProvenance.PROSPECTIVE, observations, c)


def zero_control_receipts(c):
    return tuple(
        cdc.evaluate_collision(
            cdc.IntegerSubjectV1(value),
            cdc.SelectionProvenance.PROSPECTIVE,
            [],
            c,
        )
        for value in cdc.generate_controls(c)
    )


class CrossDomainHardeningTests(unittest.TestCase):
    def test_snapshot_payload_is_deeply_immutable_after_hashing(self):
        snapshot = cdc.RegistrySnapshotV1(
            registry_id="unicode",
            registry_version_or_release="Unicode-16.0.0",
            query_key="U+FDF2",
            query_key_type="unicode-codepoint",
            result_kind="assigned-codepoint-record",
            canonical_result={"name": "A", "parts": [1, 2]},
            source_locator="fixture://immutable",
            source_observed_at="2026-08-25",
            ingestion_producer_id="test",
        )
        with self.assertRaises(TypeError):
            snapshot.canonical_result["name"] = "tampered"
        with self.assertRaises(TypeError):
            snapshot.canonical_result["parts"][0] = 9

    def test_criterion_defensively_freezes_registry_and_transform_sets(self):
        registries = ["unicode", "ncbi-gene"]
        transforms = ["UNICODE_LOOKUP_V1", "NCBI_LOOKUP_V1"]
        c = criterion(registry_set=registries, transform_set=transforms)
        registries.append("post-hoc-domain")
        transforms.append("POST_HOC_TRANSFORM")
        self.assertEqual(c.registry_set, ("unicode", "ncbi-gene"))
        self.assertEqual(c.transform_set, ("UNICODE_LOOKUP_V1", "NCBI_LOOKUP_V1"))

    def test_relation_participant_map_is_immutable_after_digesting(self):
        relation = ri.bind_relation("x-against-y-v1", {"x": "a" * 64, "y": "b" * 64})
        with self.assertRaises(TypeError):
            relation.participants["x"] = "c" * 64

    def test_raw_control_scores_cannot_mint_null_receipt(self):
        c = criterion()
        observed = observed_collision(c)
        with self.assertRaises(TypeError):
            cdc.evaluate_null_model(observed, c, [0, 0, 0, 0])

    def test_null_receipt_consumes_collision_receipts_for_exact_generated_controls(self):
        c = criterion()
        observed = observed_collision(c)
        controls = zero_control_receipts(c)
        receipt = cdc.evaluate_null_model(observed, c, controls)
        self.assertEqual(receipt.control_count, 4)
        self.assertEqual(len(receipt.control_receipt_sha256s), 4)
        self.assertTrue(receipt.promotion_eligible)


if __name__ == "__main__":
    unittest.main()
