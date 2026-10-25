"""Adversarial tests for #758 real experiment into existing AEGIS evolution."""
import copy
import unittest
from agents.alphaevolve_issue758_v1 import (
    seeds, exact, compress, mutate, experiment, hash_object,
    attach_to_existing_spine,
)
from agents.issue_evolution import compile_graph

REPO = "Aegis-Omega/AEGIS-OMEGA"

def graph():
    return compile_graph({
        "repository":REPO,"complete_pages":True,
        "acquisition":"EXPLICIT_OFFLINE_FIXTURE","pages":1,
        "issues":[
            {"number":734,"title":"Agent firm","body":"","labels":[{"name":"task"}]},
            {"number":757,"title":"Evaluation lab","body":"Parent #734","labels":[{"name":"task"}]},
            {"number":758,"title":"Evidence-gated evolution",
             "body":"Parent #734. Depends on #757","labels":[{"name":"task"}]},
        ],
    })

class AlphaEvolveIssue758Tests(unittest.TestCase):
    def test_schoolbook_rank8_exact(self):
        self.assertEqual(exact(seeds()[0]),8)

    def test_published_strassen_rank7_exact(self):
        self.assertEqual(exact(seeds()[1]),7)

    def test_corrupt_coefficient_fail_closed(self):
        bad=copy.deepcopy(seeds()[1])
        bad[0][0][0] += 1
        with self.assertRaisesRegex(ValueError,"EXACT_TENSOR_MISMATCH"):
            exact(bad)

    def test_malformed_factor_fail_closed(self):
        bad=copy.deepcopy(seeds()[1])
        bad[0][0].pop()
        with self.assertRaisesRegex(ValueError,"NONRECTANGULAR_FACTORS"):
            exact(bad)

    def test_float_coefficient_rejected(self):
        bad=copy.deepcopy(seeds()[1])
        bad[0][0][0] = 1.0
        with self.assertRaisesRegex(ValueError,"INVALID_COEFFICIENTS"):
            exact(bad)

    def test_compress_exact_duplicates(self):
        src=copy.deepcopy(seeds()[1])
        for idx,f in enumerate(src):
            for row in f:
                row.append(row[0])
                if idx==2:
                    row[0] *= 2
                    row[-1] *= -1
        self.assertEqual(exact(src),8)
        self.assertEqual(exact(compress(src)),7)

    def test_actual_generate_evaluate_select(self):
        r=experiment(generations=48)
        self.assertEqual((r["baseline_rank"],r["champion_rank"]),(8,7))
        self.assertGreater(r["new_exact_candidates"],0)
        self.assertEqual(len(r["paired_results"]),32)
        self.assertEqual({x["baseline_score"] for x in r["paired_results"]},{0})
        self.assertEqual({x["candidate_score"] for x in r["paired_results"]},{1})

    def test_deterministic_replay(self):
        self.assertEqual(experiment(generations=48),experiment(generations=48))

    def test_invalid_budget_rejected(self):
        for n in (-1,257,True,1.2):
            with self.subTest(n=n),self.assertRaisesRegex(ValueError,"INVALID_BUDGET"):
                experiment(generations=n)

    def test_no_fabricated_novelty_or_promotion(self):
        r=experiment(generations=4)
        self.assertFalse(r["novel_discovery"])
        self.assertEqual(r["promotion"],"DENIED")
        self.assertEqual(r["admission"],"DENIED")
        self.assertEqual(r["independent_review"],"NOT_PERFORMED")

    def test_existing_issue_reducer_and_spine_receive_real_pairs(self):
        output=attach_to_existing_spine(
            graph(), baseline_head="a"*40,source_head="b"*40,generations=8)
        self.assertEqual(output["trial"]["schema"],"AEGIS_ISSUE_EVOLUTION_TRIAL_V1")
        self.assertEqual(len(output["trial"]["paired_results"]),32)
        self.assertEqual(output["admission"],"DENIED")
        self.assertEqual(output["skill_promotion"],"DENIED")

    def test_same_source_head_rejected(self):
        with self.assertRaisesRegex(ValueError,"INVALID_HEADS"):
            attach_to_existing_spine(
                graph(),baseline_head="a"*40,source_head="a"*40)

if __name__=="__main__":
    unittest.main()
