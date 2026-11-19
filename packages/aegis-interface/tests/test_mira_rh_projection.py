"""Local exact projection controls; original compiler tested separately."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
MOD = ROOT / 'packages/aegis-interface/aegis_interface/math_rh.py'
EXAMPLES = ROOT / 'examples'
spec = importlib.util.spec_from_file_location('mira_math_rh', MOD)
math = importlib.util.module_from_spec(spec)
spec.loader.exec_module(math)


class ProjectionTests(unittest.TestCase):
    def request(self, name):
        return json.loads((EXAMPLES / name).read_text('utf-8'))

    def test_three_receipts_typed(self):
        for fixture in ('v7_reflection.json','finite_gram.json','prime_cutoff.json'):
            with self.subTest(fixture=fixture):
                r = math.compile_statement(self.request(fixture))
                t = math.project_wit_receipt(r)
                self.assertEqual(set(t), {'kind','state','statement_sha256','receipt_sha256','scope',
                                          'authority_class','lean_kernel_checked','riemann_hypothesis_proven'})
                self.assertEqual(t['statement_sha256'], hashlib.sha256(math.canonical(self.request(fixture))).hexdigest())
                self.assertEqual(t['receipt_sha256'], r['receipt_sha256'])
                self.assertEqual(t['state'], ('conditional_support' if fixture=='prime_cutoff.json' else 'local_exact'))
                self.assertEqual(t['authority_class'], 'NONE')
                self.assertFalse(t['riemann_hypothesis_proven'])
                self.assertFalse(t['lean_kernel_checked'])

    def test_tampering_prevents_projection_even_if_rehashed(self):
        r = math.compile_statement(self.request('finite_gram.json'))
        r['lean_kernel_checked'] = True
        r['receipt_sha256'] = hashlib.sha256(math.canonical({k:v for k,v in r.items() if k!='receipt_sha256'})).hexdigest()
        with self.assertRaises(math.ProofHold):
            math.project_wit_receipt(r)

    def test_forged_positive_gram_rejected(self):
        r = math.compile_statement(self.request('finite_gram.json'))
        r['checked']['matrix'][0][0] = '9000'
        r['receipt_sha256'] = hashlib.sha256(math.canonical({k:v for k,v in r.items() if k!='receipt_sha256'})).hexdigest()
        with self.assertRaises(math.ProofHold):
            math.project_wit_receipt(r)

    def test_project_cli_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            req=Path(tmp)/'q.json'; rec=Path(tmp)/'r.json'
            req.write_text(json.dumps(self.request('v7_reflection.json')),encoding='utf8')
            subprocess.run([sys.executable,str(MOD),'compile',str(req),'--out',str(rec)],check=True,capture_output=True)
            result=subprocess.run([sys.executable,str(MOD),'project',str(rec)],check=True,capture_output=True,text=True)
            self.assertEqual(json.loads(result.stdout)['state'],'local_exact')

    def test_project_cli_forged_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'fake.json'
            r=math.compile_statement(self.request('prime_cutoff.json'))
            r['riemann_hypothesis_proven']=True
            p.write_text(json.dumps(r),encoding='utf8')
            done=subprocess.run([sys.executable,str(MOD),'project',str(p)],capture_output=True,text=True)
            self.assertEqual(done.returncode,2)
            self.assertIn('HOLD',done.stderr)

if __name__=='__main__': unittest.main()
