import pathlib
import sys
import unittest
from dataclasses import replace

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))
import cross_domain_epoch as epoch


class ProspectiveEpochTests(unittest.TestCase):
    def test_epoch_is_exactly_unicode_plus_ncbi(self):
        e = epoch.make_epoch_v1(seed=123456789, subject_count=8)
        self.assertEqual(e.registry_ids, ("unicode", "ncbi-gene"))
        self.assertEqual((e.universe_min, e.universe_max), (0, 100000))
        self.assertIsNone(e.promotion_threshold)

    def test_epoch_digest_changes_when_seed_changes(self):
        self.assertNotEqual(
            epoch.make_epoch_v1(seed=1, subject_count=8).epoch_sha256,
            epoch.make_epoch_v1(seed=2, subject_count=8).epoch_sha256,
        )

    def test_generation_replays_identically(self):
        e = epoch.make_epoch_v1(seed=1234, subject_count=16)
        a = epoch.generate_subject_receipts(e)
        b = epoch.generate_subject_receipts(e)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)
        self.assertEqual(len({r.generated_sequence_sha256 for r in a}), 1)

    def test_generation_receipt_wrong_index_fails(self):
        e = epoch.make_epoch_v1(seed=1234, subject_count=16)
        r = epoch.generate_subject_receipts(e)[0]
        with self.assertRaises(ValueError):
            epoch.verify_subject_generation_receipt(e, replace(r, draw_index=1))

    def test_generation_receipt_cross_epoch_splice_fails(self):
        a = epoch.make_epoch_v1(seed=1234, subject_count=16)
        b = epoch.make_epoch_v1(seed=1235, subject_count=16)
        with self.assertRaises(ValueError):
            epoch.verify_subject_generation_receipt(b, epoch.generate_subject_receipts(a)[0])

    def test_known_duplicate_seed_preserves_two_draw_positions(self):
        e = epoch.make_epoch_v1(seed=27, subject_count=64)
        draws = epoch.generate_subject_receipts(e)
        self.assertEqual(draws[40].value, 85237)
        self.assertEqual(draws[62].value, 85237)
        self.assertEqual(draws[40].subject_sha256, draws[62].subject_sha256)
        self.assertNotEqual(draws[40].draw_index, draws[62].draw_index)


if __name__ == "__main__":
    unittest.main()
