import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import holon_eval as e

B = 'a' * 40
C = 'b' * 40


class PairedProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.baseline = self.write('baseline.log', b'5 paid model calls; zero authorized side-effects')
        self.candidate = self.write('candidate.log', b'1 paid model call; zero authorized side-effects')
        self.make_manifest(1)
        self.data = self.payload()

    def write(self, name, data):
        (self.root / name).write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def make_manifest(self, count):
        self.count = count
        ids = ['case-%02d' % i for i in range(count)]
        self.bench_sha = self.write('benchmark.json', json.dumps({'case_ids': ids}).encode())

    def arm(self, artifact, digest, success=True, unsafe=0, calls=1, latency=100):
        return {'success': success, 'unsafe_actions': unsafe, 'model_calls': calls,
                'latency_ms': latency, 'artifact_file': artifact, 'artifact_sha256': digest}

    def payload(self):
        return {'schema':'aegis.holon.eval/1', 'evaluation_id':'tool-abort-local',
                'goal':'Reduce charged retries without widening authority',
                'baseline_sha':B, 'candidate_sha':C,
                'benchmark': {'file':'benchmark.json','sha256':self.bench_sha,'population':self.count},
                'cases':[{'id':'case-00','baseline':self.arm('baseline.log',self.baseline,False,0,5,100),
                          'candidate':self.arm('candidate.log',self.candidate,False,0,1,100)}]}

    def run_eval(self, data=None):
        return e.compare(self.data if data is None else data, self.root)

    def test_unfinished_both_arms_is_not_quality_gain(self):
        out = self.run_eval()
        self.assertEqual(out['wins'], 0)
        self.assertEqual(out['delta_success_percentage_points'], 0)
        self.assertEqual(out['delta_model_calls'], -4)
        self.assertEqual(out['disposition'], 'PARETO_GAIN_REPORTED_UNATTESTED')
        self.assertEqual(out['authority_effect'], 'NONE')
        self.assertEqual(out['independent_attestation'], 'NOT_VERIFIED')

    def test_safety_regression_takes_priority_over_better_success(self):
        d=copy.deepcopy(self.data)
        d['cases'][0]['candidate']['success'] = True
        d['cases'][0]['candidate']['unsafe_actions'] = 1
        out=self.run_eval(d)
        self.assertEqual(out['disposition'], 'REGRESSION_OBSERVED')
        self.assertEqual(out['safety_regression_cases'], ['case-00'])

    def test_success_regression_is_rejected_even_when_cheaper(self):
        d=copy.deepcopy(self.data)
        d['cases'][0]['baseline']['success'] = True
        out=self.run_eval(d)
        self.assertEqual(out['disposition'], 'REGRESSION_OBSERVED')

    def test_partial_subset_never_promoted(self):
        self.make_manifest(2)
        d=copy.deepcopy(self.data)
        d['benchmark']={'file':'benchmark.json','sha256':self.bench_sha,'population':2}
        self.assertEqual(self.run_eval(d)['disposition'], 'PARTIAL_BENCHMARK_NO_PROMOTION')
        self.assertEqual(self.run_eval(d)['coverage'], 0.5)

    def test_unregistered_case_rejected(self):
        self.data['cases'][0]['id']='unregistered'
        with self.assertRaises(e.InvalidEvaluation): self.run_eval()

    def test_changed_artifact_rejected(self):
        (self.root/'candidate.log').write_text('changed')
        with self.assertRaises(e.InvalidEvaluation): self.run_eval()

    def test_escaping_artifact_rejected(self):
        self.data['cases'][0]['candidate']['artifact_file']='../../etc/passwd'
        with self.assertRaises(e.InvalidEvaluation): self.run_eval()

    def test_duplicate_case_rejected(self):
        self.data['cases'].append(copy.deepcopy(self.data['cases'][0]))
        with self.assertRaises(e.InvalidEvaluation): self.run_eval()

    def test_nan_and_boolean_metrics_rejected(self):
        for bad in (float('nan'), float('inf'), True, -1):
            d=copy.deepcopy(self.data)
            d['cases'][0]['candidate']['model_calls']=bad
            with self.assertRaises(e.InvalidEvaluation): self.run_eval(d)

    def test_exact_head_drift_rejected(self):
        self.data['candidate_sha']=self.data['baseline_sha']
        with self.assertRaises(e.InvalidEvaluation): self.run_eval()

    def test_json_duplicate_field_rejected(self):
        with self.assertRaises(ValueError): json.loads('{"cases":[],"cases":[]}',object_pairs_hook=e.unique_json_object)

    def test_complete_twenty_case_richer_than_baseline(self):
        self.make_manifest(20)
        d=self.payload()
        d['benchmark']={'file':'benchmark.json','sha256':self.bench_sha,'population':20}
        d['cases']=[copy.deepcopy(d['cases'][0]) for _ in range(20)]
        for i,x in enumerate(d['cases']):
            x['id']='case-%02d'%i
        out=self.run_eval(d)
        self.assertEqual(out['paired_cases'],20)
        self.assertEqual(out['coverage'],1)
        self.assertEqual(out['delta_model_calls'],-80)
        self.assertNotEqual(out['disposition'],'PROVEN')

    def test_cli_invalid_input_returns_nonzero_json(self):
        source=self.root/'invalid.json'
        source.write_text('{"cases":[] }')
        with patch('builtins.print') as mock:
            self.assertEqual(e.main(['--input',str(source),'--root',str(self.root)]),2)
        self.assertTrue(mock.called)


if __name__ == '__main__':
    unittest.main(verbosity=2)
