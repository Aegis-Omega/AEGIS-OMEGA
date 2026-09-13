"""Offline regression checks for genomics input and interpretation provenance."""
import copy
import unittest

from interpret import fold_interpretation, interpret_variants
from replay_pipeline import (
    CLINVAR_TOY, LineageChain, SAMPLE_READS, SAMPLE_REFERENCE, canon, run_pipeline,
)


class SemanticIntegrityTests(unittest.TestCase):
    def sample(self):
        chain = run_pipeline(SAMPLE_REFERENCE, SAMPLE_READS)
        return chain, chain.records[-1].output["annotated_variants"]

    def test_offline_interpretation_uses_actual_alleles_and_annotation(self):
        chain, variants = self.sample()
        result = interpret_variants(variants)
        self.assertIn("C>T", result["text"])
        self.assertIn("annotation=uncertain_significance", result["text"])
        self.assertNotIn("A>T", result["text"])
        self.assertNotIn("annotation=pathogenic", result["text"])
        fold_interpretation(chain, variants, result)
        self.assertTrue(chain.certify()["is_valid"])

    def test_empty_variants_do_not_invent_a_call(self):
        result = interpret_variants([])
        self.assertIn("No variants", result["text"])
        self.assertNotIn("pos 5", result["text"])

    def test_all_variants_keep_their_own_semantics(self):
        variants = [[0, "A", "G", 3, "benign"], [8, "T", "C", 4, "uncertain_significance"]]
        text = interpret_variants(variants)["text"]
        self.assertIn("pos 0: A>G, read_support=3, annotation=benign", text)
        self.assertIn("pos 8: T>C, read_support=4, annotation=uncertain_significance", text)

    def test_interpretation_for_other_variants_is_rejected(self):
        chain, variants = self.sample()
        other = [[5, "C", "G", 2, "benign"]]
        before = chain.terminal_hash()
        with self.assertRaises(ValueError):
            fold_interpretation(chain, variants, interpret_variants(other))
        self.assertEqual(before, chain.terminal_hash())

    def test_variants_must_match_annotate_stage(self):
        chain, _ = self.sample()
        other = [[5, "C", "G", 2, "benign"]]
        with self.assertRaises(ValueError):
            fold_interpretation(chain, other, interpret_variants(other))

    def test_unbound_interpretation_is_rejected(self):
        chain, variants = self.sample()
        with self.assertRaises(ValueError):
            fold_interpretation(chain, variants, {"model": "fixture", "text": "unbound", "live": False})

    def test_fold_rejects_corrupt_chain(self):
        chain, variants = self.sample()
        chain.records[0].output["length"] += 1
        with self.assertRaises(ValueError):
            fold_interpretation(chain, variants, interpret_variants(variants))

    def test_live_marker_is_bound_to_chain(self):
        chain, variants = self.sample()
        fold_interpretation(chain, variants, interpret_variants(variants))
        chain.records[-1].output["live"] = True
        self.assertFalse(chain.certify()["is_valid"])

    def test_fixture_cannot_be_relabelled_as_live(self):
        for forged_text in [False, True]:
            with self.subTest(forged_text=forged_text):
                chain, variants = self.sample()
                result = interpret_variants(variants)
                result["live"] = True
                if forged_text:
                    result["text"] = "A>T, annotation=pathogenic"
                before = chain.terminal_hash()
                with self.assertRaisesRegex(ValueError, "mode and model"):
                    fold_interpretation(chain, variants, result)
                self.assertEqual(before, chain.terminal_hash())

    def test_offline_result_requires_fixture_model(self):
        chain, variants = self.sample()
        result = interpret_variants(variants)
        result["model"] = "a-live-model"
        with self.assertRaisesRegex(ValueError, "mode and model"):
            fold_interpretation(chain, variants, result)

    def test_annotation_database_changes_are_bound_even_for_unused_entries(self):
        before, _ = self.sample()
        original = copy.deepcopy(CLINVAR_TOY)
        try:
            CLINVAR_TOY["11|C|G"] = "uncertain_significance"
            after, _ = self.sample()
            self.assertNotEqual(before.terminal_hash(), after.terminal_hash())
        finally:
            CLINVAR_TOY.clear()
            CLINVAR_TOY.update(original)

    def test_unknown_annotation_class_is_rejected(self):
        with self.assertRaises(ValueError):
            interpret_variants([[5, "C", "T", 2, "unknown_class"]])

    def test_invalid_variant_shapes_and_values_are_rejected(self):
        cases = [None, "not variants", [[-1, "C", "T", 2, "benign"]],
                 [[True, "C", "T", 2, "benign"]], [[5, "C", "T", True, "benign"]],
                 [[5, "C", "C", 2, "benign"]], [[5, "C", "X", 2, "benign"]],
                 [[5, "C", "T", 0, "benign"]], [[5, "C", "T"]]]
        for variants in cases:
            with self.subTest(variants=variants), self.assertRaises((TypeError, ValueError)):
                interpret_variants(variants)

    def test_invalid_reads_fail_instead_of_wrapping_or_truncating(self):
        cases = [{"pos": -1, "bases": "T"}, {"pos": True, "bases": "T"},
                 {"pos": 15, "bases": "AA"}, {"pos": 0, "bases": "AX"},
                 {"pos": 0, "bases": ""}, {"pos": 0}]
        for read in cases:
            with self.subTest(read=read), self.assertRaises((TypeError, ValueError)):
                run_pipeline(SAMPLE_REFERENCE, [read])

    def test_invalid_reference_is_rejected(self):
        for reference in ["", "acgt", "ACGN", None]:
            with self.subTest(reference=reference), self.assertRaises((TypeError, ValueError)):
                run_pipeline(reference, [])

    def test_append_takes_snapshot_of_output(self):
        output = {"nested": ["original"]}
        chain = LineageChain()
        chain.append("EXAMPLE", output)
        output["nested"][0] = "changed by caller"
        self.assertTrue(chain.certify()["is_valid"])
        self.assertEqual(chain.records[0].output["nested"], ["original"])

    def test_sequence_number_cannot_be_rebased(self):
        chain = LineageChain()
        chain.append("EXAMPLE", {})
        chain.records[0].sequence = 4
        chain.records[0].compute()
        self.assertFalse(chain.certify()["is_valid"])

    def test_malformed_hashed_state_fails_closed(self):
        chain, _ = self.sample()
        chain.records[-1].output["invalid"] = float("nan")
        self.assertFalse(chain.certify()["is_valid"])

    def test_exact_text_is_not_unicode_normalized_before_hashing(self):
        self.assertNotEqual(canon({"text": "\u00e9"}), canon({"text": "e\u0301"}))

    def test_non_string_object_keys_are_rejected(self):
        with self.assertRaises(TypeError):
            canon({1: "a"})


if __name__ == "__main__":
    unittest.main()
