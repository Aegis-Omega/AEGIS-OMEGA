from dataclasses import replace
import pathlib
import sys
import unittest

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))
import cross_domain_collision as cdc
import cross_domain_coverage as cov
import research_invariants as ri


def criterion(**overrides):
    values = dict(
        universe_min=0,
        universe_max=100000,
        registry_set=("fixture-a", "fixture-b"),
        transform_set=("INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",),
        independence_rule_id="UNIQUE_DOMAIN_ID_V1",
        score_function_id="UNIQUE_EXTERNAL_DOMAINS_V1",
        control_generator_id="PY_RANDOM_UNIFORM_INT_V1",
        control_seed=1234,
        control_count=4,
        promotion_threshold=0.05,
        criterion_text="hardening criterion v2 coverage-bound",
    )
    values.update(overrides)
    return cdc.CollisionCriterionV1(**values)


def observed_collision(c, subject_value=65010):
    subject = cdc.IntegerSubjectV1(subject_value)
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


def adapter(registry_id):
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
        contract_text=f"hardening fixture adapter {registry_id} v1",
    )


def negative_snapshot(subject, registry_id):
    return cdc.RegistrySnapshotV1(
        registry_id=registry_id,
        registry_version_or_release="fixture-v1",
        query_key=str(subject.value),
        query_key_type="integer-decimal",
        result_kind="fixture-registry-result",
        canonical_result={"match": False},
        source_locator=f"fixture://hardening/{registry_id}/{subject.value}",
        source_observed_at="2026-08-25T00:00:00Z",
        ingestion_producer_id="hardening-test",
    )


def covered_controls(c):
    collisions = []
    coverages = []
    for value in cdc.generate_controls(c):
        subject = cdc.IntegerSubjectV1(value)
        probes = [
            cov.probe_registry_snapshot(subject, c, adapter("fixture-a"), negative_snapshot(subject, "fixture-a")),
            cov.probe_registry_snapshot(subject, c, adapter("fixture-b"), negative_snapshot(subject, "fixture-b")),
        ]
        collision, coverage = cov.evaluate_control_from_probes(subject, c, probes)
        collisions.append(collision)
        coverages.append(coverage)
    return tuple(collisions), tuple(coverages)


def valid_null_receipt(observed, c):
    controls, coverages = covered_controls(c)
    return cdc.evaluate_null_model(observed, c, controls, control_coverages=coverages)


def journal_at_collision(collision, c):
    journal = ri.StatusJournalV1(f"hardening:{collision.subject_sha256}")
    cdc.append_collision_status(
        journal,
        "OBSERVED",
        [collision.receipt_sha256],
        c.criterion_sha256,
        "observed",
    )
    cdc.append_collision_status(
        journal,
        "EXACT_MAPPING",
        [collision.receipt_sha256],
        c.criterion_sha256,
        "mapping",
    )
    cdc.append_collision_status(
        journal,
        "CROSS_REGISTRY_COLLISION",
        [collision.receipt_sha256],
        c.criterion_sha256,
        "collision",
    )
    return journal


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

    def test_derivation_payload_is_deeply_immutable_after_hashing(self):
        derivation = cdc.DerivationReceiptV1(
            subject_sha256="a" * 64,
            derivation_id="DERIVATION_V1",
            derivation_version="1",
            criterion_sha256="b" * 64,
            canonical_result={"factors": [2, 3, 5]},
        )
        with self.assertRaises(TypeError):
            derivation.canonical_result["factors"][0] = 7

    def test_gate_receipt_observation_is_deeply_immutable_after_hashing(self):
        relation = ri.bind_relation("x-against-y-v1", {"x": "a" * 64, "y": "b" * 64})
        receipt = ri.relation_gate_receipt(
            gate_id="hardening-relation-gate",
            relation=relation,
            verdict=ri.GateVerdict.PASS,
            observation={"nested": {"values": [1, 2]}},
        )
        with self.assertRaises(TypeError):
            receipt.observation["nested"]["values"][0] = 9

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

    def test_null_receipt_consumes_exact_generated_collisions_and_coverage(self):
        c = criterion()
        observed = observed_collision(c)
        controls, coverages = covered_controls(c)
        receipt = cdc.evaluate_null_model(observed, c, controls, control_coverages=coverages)
        self.assertEqual(receipt.control_count, 4)
        self.assertEqual(len(receipt.control_receipt_sha256s), 4)
        self.assertEqual(len(receipt.control_coverage_receipt_sha256s), 4)
        self.assertTrue(receipt.promotion_eligible)

    def test_null_receipt_rejects_p_emp_tampering(self):
        c = criterion(control_count=100)
        receipt = valid_null_receipt(observed_collision(c), c)
        tampered = replace(receipt, p_emp=0.5)
        with self.assertRaises(ValueError):
            cdc.verify_null_model_receipt(tampered)

    def test_null_status_rejects_tampered_receipt_digest(self):
        c = criterion(control_count=100)
        observed = observed_collision(c)
        null_receipt = valid_null_receipt(observed, c)
        self.assertTrue(null_receipt.null_survived)
        tampered = replace(null_receipt, receipt_sha256="f" * 64)
        journal = journal_at_collision(observed, c)
        with self.assertRaises(PermissionError):
            cdc.append_collision_status(
                journal,
                "NULL_SURVIVED",
                [tampered.receipt_sha256],
                c.criterion_sha256,
                "tampered receipt must not promote",
                null_receipt=tampered,
            )

    def test_null_status_rejects_collision_receipt_splicing(self):
        c = criterion(control_count=100)
        observed_a = observed_collision(c, 65010)
        observed_b = observed_collision(c, 65011)
        null_b = valid_null_receipt(observed_b, c)
        self.assertTrue(null_b.null_survived)
        journal = journal_at_collision(observed_a, c)
        with self.assertRaises(PermissionError):
            cdc.append_collision_status(
                journal,
                "NULL_SURVIVED",
                [null_b.receipt_sha256],
                c.criterion_sha256,
                "different collision receipt must not splice",
                null_receipt=null_b,
            )

    def test_null_status_requires_null_receipt_digest_in_transition_evidence(self):
        c = criterion(control_count=100)
        observed = observed_collision(c)
        null_receipt = valid_null_receipt(observed, c)
        self.assertTrue(null_receipt.null_survived)
        journal = journal_at_collision(observed, c)
        with self.assertRaises(PermissionError):
            cdc.append_collision_status(
                journal,
                "NULL_SURVIVED",
                [observed.receipt_sha256],
                c.criterion_sha256,
                "null receipt digest must be carried into status evidence",
                null_receipt=null_receipt,
            )

    def test_valid_null_status_requires_and_preserves_exact_lineage(self):
        c = criterion(control_count=100)
        observed = observed_collision(c)
        null_receipt = valid_null_receipt(observed, c)
        self.assertTrue(null_receipt.null_survived)
        journal = journal_at_collision(observed, c)
        transition = cdc.append_collision_status(
            journal,
            "NULL_SURVIVED",
            [null_receipt.receipt_sha256],
            c.criterion_sha256,
            "verified null receipt on exact collision and coverage lineage",
            null_receipt=null_receipt,
        )
        self.assertEqual(journal.current_status, "NULL_SURVIVED")
        self.assertEqual(
            transition.evidence_receipt_digests,
            (null_receipt.receipt_sha256,),
        )
        self.assertTrue(ri.StatusJournalV1.verify(journal.history))


if __name__ == "__main__":
    unittest.main()
