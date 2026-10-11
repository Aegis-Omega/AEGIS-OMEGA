"""Synthetic benchmark reproducibility and negative-case regressions."""
import unittest
from research_benchmark import (ALL_CLASSES, POSITIVE_CLASSES, NEGATIVE_CLASSES,
                               corpus, naive_two_urls, scout_ready, wilson, report, pinned_legacy_module)


class ResearchBenchmarkTests(unittest.TestCase):
    def test_fixed_corpus_size_and_balance(self):
        x = corpus()
        self.assertEqual(len(x),100)
        self.assertEqual(len(POSITIVE_CLASSES),5)
        self.assertEqual(len(NEGATIVE_CLASSES),15)
        self.assertEqual(len(ALL_CLASSES),20)
        self.assertEqual(len({case[0] for case in x}),100)
        self.assertEqual(sum(p[2] for p in x),25)

    def test_labels_are_stated_before_scorers(self):
        for _id,cls,label,_pkt in corpus():
            self.assertEqual(label,cls in POSITIVE_CLASSES)

    def test_naive_baseline_fails_manually_typed_website_evidence(self):
        xs=[p for _id,k,label,p in corpus() if k=='two_manual_notes']
        self.assertEqual(len(xs),5)
        self.assertTrue(all(naive_two_urls(p) for p in xs))
        self.assertTrue(all(not scout_ready(p)[0] for p in xs))

    def test_all_structural_positive_fixtures_test_ready_only(self):
        positives=[p for _id,k,label,p in corpus() if label]
        self.assertTrue(all(scout_ready(p)[0] for p in positives))

    def test_all_structural_negative_fixtures_abstain_or_reject(self):
        negatives=[p for _id,k,label,p in corpus() if not label]
        self.assertTrue(all(not scout_ready(p)[0] for p in negatives))

    def test_wilson_bounds(self):
        self.assertEqual(wilson(0,75)[0],0)
        self.assertEqual(wilson(75,75)[1],1)
        self.assertTrue(0 < wilson(20,75)[0] < wilson(20,75)[1] < 1)

    def test_receipt_deterministic(self):
        self.assertEqual(report()['receipt_sha256'],report()['receipt_sha256'])
        self.assertEqual(report()['scout'],report()['scout'])

    def test_wrong_prior_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'LEGACY_BLOB_MISMATCH'):
            pinned_legacy_module(__file__)

    def test_no_benchmark_superiority_claim(self):
        r=report()
        self.assertEqual(r['dataset']['held_out'],'NO')
        self.assertEqual(r['dataset']['model_or_agent_competitor'],'NO')
        self.assertEqual(r['benchmark_superiority'],'NOT_ESTABLISHED_OUTSIDE_THIS_SYNTHETIC_CORPUS')
        self.assertEqual(r['authority_effect'],'NONE')

if __name__=='__main__':unittest.main()
