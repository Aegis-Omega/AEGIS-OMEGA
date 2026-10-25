import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

path = Path(__file__).with_name('experience_eval.py')
spec = importlib.util.spec_from_file_location('experience_eval', path)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def sample():
    h = 'a' * 64
    return {'schema': engine.SCHEMA, 'task_id': '#760 experience pilot',
            'candidate_sha256': h, 'baseline_sha256': 'b'*64, 'source_head':'1'*40,
            'comparison_scope': 'synthetic unit fixture only',
            'reviewer': {'identity':'test reviewer', 'relation':'SELF', 'evidence':None},
            'authority_effect':'NONE', 'axes': [
                {'id':key, 'state':'UNMEASURED', 'rationale':'No matched user test yet',
                 'metric':None, 'unit':None, 'direction':None, 'baseline':None,
                 'candidate':None, 'tolerance':None, 'evidence_sha256':None,
                 'standard_ref':'pending source scoping'} for key in engine.AXES]}


def measure(doc, key, b=10., c=12., direction='HIGHER', tol=0):
    a = next(x for x in doc['axes'] if x['id'] == key)
    a.update(state='MEASURED', rationale='Synthetic matched controlled test',
             metric='test fixture metric', unit='fixture_points', direction=direction,
             baseline=b, candidate=c, tolerance=tol, evidence_sha256='c'*64)
    return doc


class Tests(unittest.TestCase):
    def test_good_unknown_manifest(self):
        r = engine.evaluate(sample())
        self.assertEqual(r['status'], 'STRUCTURAL_VALIDATION_ONLY')
        self.assertEqual(len(r['unresolved_or_regressed_axes']), len(engine.AXES))
        self.assertFalse(r['independent_measurements_authenticated'])
        self.assertFalse(r['all_applicable_improved_on_declared_values'])
        self.assertEqual(r['world_best'], 'NOT_ESTABLISHED')

    def test_all_reported_improved_not_proof(self):
        s = sample()
        for x in engine.AXES: measure(s, x)
        r = engine.evaluate(s)
        self.assertTrue(r['all_applicable_improved_on_declared_values'])
        self.assertFalse(r['standards_conformance_verified'])
        self.assertEqual(r['world_best'], 'NOT_ESTABLISHED')

    def test_regression_blocked(self):
        s = measure(sample(), 'sonic', 10, 8)
        r = engine.evaluate(s)
        self.assertIn('sonic', r['unresolved_or_regressed_axes'])
        self.assertEqual(next(x for x in r['axes'] if x['id']=='sonic')['finding'], 'REGRESSED')

    def test_not_applicable_is_disclosed(self):
        s = sample()
        s['axes'][2]['state'] = 'NOT_APPLICABLE'
        self.assertIn(s['axes'][2]['id'], engine.evaluate(s)['unresolved_or_regressed_axes'])

    def test_lower_direction(self):
        s = measure(sample(), 'performance', 14, 8, 'LOWER')
        r = engine.evaluate(s)
        self.assertEqual(next(x for x in r['axes'] if x['id']=='performance')['finding'], 'IMPROVED')

    def test_tolerance(self):
        s = measure(sample(), 'usability', 10, 10.1, 'HIGHER', .2)
        self.assertEqual(next(x for x in engine.evaluate(s)['axes'] if x['id']=='usability')['finding'], 'NO_DEMONSTRATED_GAIN')

    def test_deterministic_digest_irrespective_of_dict_key_order(self):
        s = sample()
        t = {k:s[k] for k in reversed(list(s.keys()))}
        self.assertEqual(engine.evaluate(s)['manifest_sha256'], engine.evaluate(t)['manifest_sha256'])

    def test_duplicate_axis(self):
        s = sample(); s['axes'][0]['id'] = s['axes'][1]['id']
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_missing_axis(self):
        s = sample(); s['axes'].pop()
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_additional_undocumented_axis(self):
        s = sample(); s['axes'][0]['id'] = 'magical_mood'
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_namespaced_additional_domain_axis(self):
        s = sample()
        extra = dict(s['axes'][0]); extra['id'] = 'ext.haptics'
        s['axes'].append(extra)
        r = engine.evaluate(s)
        self.assertIn('ext.haptics', r['unresolved_or_regressed_axes'])

    def test_source_revision_sha(self):
        s = sample(); s['candidate_sha256'] = 'not-a-hash'
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_source_head_required(self):
        s = sample(); s['source_head'] = 'not-a-head'
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_all_not_applicable_not_global_success(self):
        s = sample()
        for x in s['axes']: x['state'] = 'NOT_APPLICABLE'
        self.assertFalse(engine.evaluate(s)['all_applicable_improved_on_declared_values'])

    def test_candidate_equals_baseline(self):
        s = sample(); s['candidate_sha256'] = s['baseline_sha256']
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_authority_expansion(self):
        s = sample(); s['authority_effect'] = 'PROD_WRITE'
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_unauthenticated_reviewer_never_certifies(self):
        s = sample(); s['reviewer'] = {'identity':'different', 'relation':'INDEPENDENT_CLAIMED', 'evidence':'c'*64}
        self.assertFalse(engine.evaluate(s)['independent_measurements_authenticated'])

    def test_false_boolean_reject(self):
        s = measure(sample(), 'visual'); s['axes'][0]['candidate'] = True
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_nonfinite_reject(self):
        s = measure(sample(), 'visual'); s['axes'][0]['candidate'] = float('nan')
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_negative_tolerance(self):
        s = measure(sample(), 'visual'); s['axes'][0]['tolerance'] = -1
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_missing_evidence(self):
        s = measure(sample(), 'visual'); s['axes'][0]['evidence_sha256'] = None
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_unmeasured_cannot_smuggle_measurement(self):
        s = sample(); s['axes'][0]['candidate'] = 100
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_missing_rationale(self):
        s = sample(); s['axes'][0]['rationale'] = ''
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_missing_standard_source(self):
        s = sample(); s['axes'][0]['standard_ref'] = ''
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_extra_untrusted_instruction_field(self):
        s = sample(); s['execute_shell'] = 'rm -rf /'
        with self.assertRaises(ValueError): engine.evaluate(s)

    def test_cli_reject_machine_readable(self):
        p = subprocess.run([sys.executable, str(path), '-'],input='{}',text=True,capture_output=True)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(json.loads(p.stdout)['status'], 'REJECTED')

    def test_cli_accept_offline(self):
        p = subprocess.run([sys.executable, str(path), '-'], input=json.dumps(sample()), text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)['world_best'], 'NOT_ESTABLISHED')

if __name__ == '__main__': unittest.main()
