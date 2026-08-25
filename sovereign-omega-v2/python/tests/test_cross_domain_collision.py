import pathlib
import sys
import unittest

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))
import cross_domain_collision as cdc


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
            "INTEGER_TO_HEX_V1",
            "1",
            "IntegerSubjectV1",
            "HexString",
            "uppercase hexadecimal",
        )
        b = cdc.TransformSpecV1(
            "INTEGER_TO_HEX_V1",
            "1",
            "IntegerSubjectV1",
            "HexString",
            "uppercase  hexadecimal",
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
        a = cdc.RegistrySnapshotV1(
            canonical_result={"codepoint": "U+FDF2", "name": "A"},
            **common,
        )
        b = cdc.RegistrySnapshotV1(
            canonical_result={"codepoint": "U+FDF2", "name": "B"},
            **common,
        )
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


if __name__ == "__main__":
    unittest.main()
