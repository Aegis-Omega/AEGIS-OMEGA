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


if __name__ == "__main__":
    unittest.main()
