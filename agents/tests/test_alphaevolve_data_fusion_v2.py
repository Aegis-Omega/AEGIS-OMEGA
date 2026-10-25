"""Negative controls and deterministic replay for #758 AlphaEvolve data search.
All GitHub CI fixtures synthetic, no dependency on user-owned data.
"""
import copy
import csv
import hashlib
import math
import tempfile
import unittest
from pathlib import Path
from agents.alphaevolve_data_fusion_v2 import (
    PINNED, BENCHMARK, BATH, SCENARIOS, METHODS,
    read_csv_strict, real, load_benchmark, load_bath, benchmark_score,
    bench_search, bath_search, bath_decision, digest,
)


class FusionTests(unittest.TestCase):
    def fixture_benchmark(self):
        return {(scenario, z, method):{
            'success':(0.65 if method=='C0_verified_static' else 0.66 if method=='C_adaptive_window' else 0.35),
            'false':(0.10 if method in ('C0_verified_static','C_adaptive_window') else 0.4),
            'cost':(2 if method in ('C0_verified_static','C_adaptive_window') else 1)}
            for scenario in SCENARIOS for z in range(40) for method in METHODS}

    def bath_fixture(self):
        out=[]
        for model in ('intermediate','near_degenerate'):
            for beta in (0.5,1):
                for lam in (0.01,0.03,0.06):
                    key=(model,'1.0','0.2' if model=='intermediate' else '0.08',str(beta),str(lam))
                    for probe in range(4):
                        for t in range(5):
                            out.append({'group':key,'feature':{'t':float(t),'lambda':lam,'beta':float(beta),'tau_c':50.0},
                                        'cg':0.01,'davies':0.02,'key':key+(str(probe),str(t))})
        return out

    def test_dataset_pins_complete(self):
        self.assertEqual(set(PINNED),{BENCHMARK,BATH})
        self.assertTrue(all(len(h)==64 for h in PINNED.values()))

    def test_canonical_determinism_and_no_nan(self):
        self.assertEqual(digest({'a':1,'b':2}),digest({'b':2,'a':1}))
        with self.assertRaises(ValueError): digest({'nan':math.nan})

    def test_reject_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'x.csv';p.write_text('a,b\n1,2\n')
            with self.assertRaisesRegex(ValueError,'DATASET_SHA256_MISMATCH'):
                read_csv_strict(p,'0'*64,('a',))

    def test_reject_malformed_csv(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'x.csv';p.write_text('a,b\n1,2,3\n')
            sha=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'DATASET_ROWS_INVALID'):
                read_csv_strict(p,sha,('a','b'))

    def test_reject_duplicate_headers(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'x.csv';p.write_text('a,a\n1,2\n')
            sha=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'DATASET_SCHEMA_MISMATCH'):
                read_csv_strict(p,sha,('a',))

    def test_reject_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'x.csv';p.write_text('a\n1\n')
            q=Path(root)/'link.csv';q.symlink_to(p)
            with self.assertRaisesRegex(ValueError,'SOURCE_NOT_REGULAR_FILE'):
                read_csv_strict(q,hashlib.sha256(p.read_bytes()).hexdigest(),('a',))

    def test_reject_nan_and_bounds(self):
        for bad in ('NaN','inf','-inf','2'):
            with self.subTest(v=bad),self.assertRaises(ValueError):
                real({'x':bad},'x',0,1)

    def test_incomplete_benchmark_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'bench.csv'
            with p.open('w',newline='') as f:
                w=csv.writer(f);w.writerow(['scenario','seed','method','verified_success','false_admission','mean_cost'])
                w.writerow(['blindspot','0','C_adaptive_window','0.8','0.1','2'])
            with self.assertRaisesRegex(ValueError,'BENCHMARK_FACTORIAL_INCOMPLETE'):
                load_benchmark(p,hashlib.sha256(p.read_bytes()).hexdigest())

    def test_duplicate_benchmark_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'bench.csv'
            with p.open('w',newline='') as f:
                w=csv.writer(f);w.writerow(['scenario','seed','method','verified_success','false_admission','mean_cost'])
                for _ in range(2):w.writerow(['blindspot','0','C_adaptive_window','0.8','0.1','2'])
            with self.assertRaisesRegex(ValueError,'DUPLICATE_BENCHMARK_PAIR'):
                load_benchmark(p,hashlib.sha256(p.read_bytes()).hexdigest())

    def test_deterministic_search(self):
        d=self.fixture_benchmark()
        self.assertEqual(bench_search(d,generations=8),bench_search(d,generations=8))

    def test_budget_failclosed(self):
        for n in (0,129,True,1.0,-1):
            with self.subTest(budget=n),self.assertRaisesRegex(ValueError,'INVALID_EVOLUTION_BUDGET'):
                bench_search(self.fixture_benchmark(),generations=n)

    def test_holdout_does_not_affect_candidate_selection(self):
        d=self.fixture_benchmark();a=bench_search(d,generations=8)
        e=copy.deepcopy(d)
        # Deliberately rewrite ONLY held-out scores; policy search must not observe them.
        for scenario in SCENARIOS:
            for z in range(16,40):
                for method in METHODS:
                    e[(scenario,z,method)]['success']=0.01 if method=='C0_verified_static' else 0.9
        b=bench_search(e,generations=8)
        self.assertEqual(a['selected_policy'],b['selected_policy'])
        self.assertEqual(a['training_trace'],b['training_trace'])

    def test_no_self_promotion(self):
        x=bench_search(self.fixture_benchmark(),generations=8)
        self.assertEqual(x['candidate_promotion'],'DENIED')
        self.assertEqual(x['independent_reproduction'],'NOT_PERFORMED')
        self.assertEqual(len(x['paired_holdout']),96)
        self.assertEqual(x['holdout_baseline']['unique_seeds'],24)

    def test_cost_and_false_admission_penalty(self):
        a={'success':0.80,'false':0.1,'cost':2}
        b={'success':0.80,'false':0.2,'cost':2}
        c={'success':0.80,'false':0.1,'cost':3}
        self.assertGreater(benchmark_score(a),benchmark_score(b))
        self.assertGreater(benchmark_score(a),benchmark_score(c))

    def test_bath_baseline_no_fabricated_improvement(self):
        x=bath_search(self.bath_fixture(),generations=8)
        self.assertEqual(x['selected_policy'],('constant','CG'))
        self.assertEqual(x['holdout_delta_error'],0)
        self.assertEqual(x['candidate_promotion'],'DENIED')

    def test_bath_determinism(self):
        q=self.bath_fixture()
        self.assertEqual(bath_search(q,generations=8),bath_search(q,generations=8))

    def test_bath_holdout_split_nonoverlap(self):
        q=bath_search(self.bath_fixture(),generations=8)
        gs=[{tuple(x) for x in q[k]} for k in ('train_physics_groups','validation_physics_groups','holdout_physics_groups')]
        self.assertEqual([len(x) for x in gs],[6,3,3])
        self.assertFalse(gs[0]&gs[1] or gs[1]&gs[2] or gs[0]&gs[2])

    def test_bath_holdout_may_not_change_selection(self):
        data=self.bath_fixture()
        a=bath_search(data,generations=8)
        q=copy.deepcopy(data)
        held={tuple(x) for x in a['holdout_physics_groups']}
        for row in q:
            if row['group'] in held:
                row['cg'],row['davies']=1.0,0.00001
        b=bath_search(q,generations=8)
        self.assertEqual(a['selected_policy'],b['selected_policy'])

    def test_reject_arbitrary_policy_code(self):
        q=self.bath_fixture()[0]
        with self.assertRaisesRegex(ValueError,'INVALID_BATH_POLICY'):
            bath_decision(('__import__','<=',1.0,'DAVIES'),q)

    def test_bath_duplicate_rows_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'bath.csv'
            with p.open('w',newline='') as f:
                w=csv.writer(f);w.writerow([*('model','J','h','beta','lambda','tau_c','probe','t'),
                    'exact_vs_CG_trace_distance','exact_vs_Davies_trace_distance','winner'])
                for _ in range(2):w.writerow(['intermediate','1','0.2','0.5','0.01','749','a','0','0.1','0.2','CG'])
            with self.assertRaisesRegex(ValueError,'BATH_DUPLICATE_EXPERIMENT'):
                load_bath(p,hashlib.sha256(p.read_bytes()).hexdigest())

    def test_24_clusters_can_never_pass_issue758_gate(self):
        x=bench_search(self.fixture_benchmark(),generations=8)
        self.assertEqual(x["holdout_independent_cluster_count"],24)
        self.assertFalse(x["issue758_minimum_pairs_met"])
        self.assertEqual(x["issue758_minimum_independent_pairs"],30)
        self.assertEqual(x["screen"],"NOT_ADMITTED")

    def test_global_oracle_proves_bounded_256_policy_space(self):
        x=bench_search(self.fixture_benchmark(),generations=8)
        self.assertEqual(x["oracle_train_validation_only"]["policies_enumerated"],256)
        self.assertGreaterEqual(x["oracle_train_validation_only"]["validation_gap"],-1e-12)

    def test_cluster_bootstrap_finite_and_deterministic(self):
        x=bench_search(self.fixture_benchmark(),generations=8)
        y=bench_search(self.fixture_benchmark(),generations=8)
        self.assertEqual(x["cluster_bootstrap"],y["cluster_bootstrap"])
        self.assertTrue(math.isfinite(x["cluster_bootstrap"]["lower_95"]))
        self.assertLessEqual(x["cluster_bootstrap"]["lower_95"],
                             x["cluster_bootstrap"]["upper_95"])

    def test_scenario_risk_included_and_never_self_promotes(self):
        x=bench_search(self.fixture_benchmark(),generations=8)
        self.assertEqual(set(v["scenario"] for v in x["scenario_safety"]),set(SCENARIOS))
        self.assertEqual(x["candidate_promotion"],"DENIED")
        self.assertEqual(x["independent_reproduction"],"NOT_PERFORMED")


if __name__=='__main__':unittest.main()