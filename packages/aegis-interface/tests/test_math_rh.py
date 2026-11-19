"""Soundness-oriented exact/algebraic, adversarial, and deterministic regression."""
from __future__ import annotations

from fractions import Fraction as F
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
MOD = ROOT / "packages" / "aegis-interface" / "aegis_interface" / "math_rh.py"
EXAMPLES = Path(__file__).resolve().parent / "fixtures"
spec = importlib.util.spec_from_file_location("aegis_mira_math_rh", MOD)
assert spec and spec.loader
math = importlib.util.module_from_spec(spec)
spec.loader.exec_module(math)

class RHLanguageTests(unittest.TestCase):
    def request(self, kind, statement):
        return {"schema": math.SCHEMA, "kind": kind, "statement": statement}

    def file_request(self, filename):
        return json.loads((EXAMPLES / filename).read_text(encoding="utf8"))

    def assertHold(self, f, *args):
        with self.assertRaises(math.ProofHold):
            f(*args)

    def test_v7_replayed_poly(self):
        receipt = math.compile_statement(self.file_request("v7_reflection.json"))
        self.assertEqual(receipt["checked"]["degree"], 7)
        self.assertEqual(len(receipt["checked"]["R_u_ascending"]), 3)
        self.assertTrue(math.verify_receipt(receipt))
        self.assertFalse(receipt["riemann_hypothesis_proven"])
        self.assertFalse(receipt["lean_kernel_checked"])

    def test_gram_decomposition(self):
        r = math.compile_statement(self.file_request("finite_gram.json"))
        self.assertEqual(r["checked"]["matrix"], [["5","1"],["1","2"]])
        self.assertTrue(math.verify_receipt(r))

    def test_prime_cutoff(self):
        r = math.compile_statement(self.file_request("prime_cutoff.json"))
        self.assertEqual(r["checked"]["exp_2delta_strict_upper_bound"], "500/499")
        self.assertIn("IF supp(g)",r["checked"]["claim"])
        self.assertTrue(math.verify_receipt(r))

    def test_symmetry_counterexample(self):
        self.assertHold(math.compile_statement, self.request("reflection_polynomial",{"coefficients_s_ascending":["0","-1","1"]}))

    def test_moment_counterexample(self):
        self.assertHold(math.compile_statement, self.request("reflection_polynomial",{"coefficients_s_ascending":["1","0","0","-1"]}))

    def test_zero_polynomial_rejected(self):
        self.assertHold(math.compile_statement, self.request("reflection_polynomial",{"coefficients_s_ascending":["0"]}))

    def test_degree_limit(self):
        self.assertHold(math.poly, ["0"]*65+["1"])

    def test_unknown_global_goal_rejected(self):
        self.assertHold(math.compile_statement, self.request("RiemannHypothesis",{"assertion":"True"}))

    def test_unknown_universal_positivity_rejected(self):
        self.assertHold(math.compile_statement, self.request("WeilUniversalPositivity",{}))

    def test_unhashable_kind_rejected(self):
        self.assertHold(math.compile_statement, self.request(["RiemannHypothesis"],{}))

    def test_rogue_field_rejected(self):
        r = self.file_request("v7_reflection.json")
        r["rh_proven"] = True
        self.assertHold(math.compile_statement, r)

    def test_float_rejected(self):
        self.assertHold(math.rational, 0.5)

    def test_nan_rejected(self):
        self.assertHold(math.rational, "NaN")

    def test_leading_zero_rejected(self):
        self.assertHold(math.rational, "01/2")

    def test_negative_zero_rejected(self):
        self.assertHold(math.rational, "-0")

    def test_nonreduced_fraction_rejected(self):
        self.assertHold(math.rational, "2/4")
        self.assertHold(math.rational, "0/4")
        self.assertHold(math.rational, "7/1")

    def test_forged_claim_rejected_even_after_rehash(self):
        r = math.compile_statement(self.file_request("v7_reflection.json"))
        r["checked"]["claim"] = "All zeta zeros lie on the critical line"
        r["receipt_sha256"] = hashlib.sha256(math.canonical({k: v for k, v in r.items() if k != "receipt_sha256"})).hexdigest()
        self.assertHold(math.verify_receipt, r)

    def test_forged_open_obligations_rejected_even_after_rehash(self):
        r = math.compile_statement(self.file_request("v7_reflection.json"))
        r["rh_obligations"] = []
        r["receipt_sha256"] = hashlib.sha256(math.canonical({k: v for k, v in r.items() if k != "receipt_sha256"})).hexdigest()
        self.assertHold(math.verify_receipt, r)


    def test_div_zero_rejected(self):
        self.assertHold(math.rational, "1/0")

    def test_oversize_token_rejected(self):
        self.assertHold(math.rational, "9"*121)

    def test_duplicate_key_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"dup.json"
            f.write_text('{"schema":"x","schema":"y"}')
            self.assertHold(math.load_json, str(f))

    def test_tampered_result_rejected(self):
        r = math.compile_statement(self.file_request("v7_reflection.json"))
        r["checked"]["R_u_ascending"][0] = "0"
        self.assertHold(math.verify_receipt, r)

    def test_tampered_hash_rejected(self):
        r = math.compile_statement(self.file_request("finite_gram.json"))
        r["receipt_sha256"] = "0"*64
        self.assertHold(math.verify_receipt, r)

    def test_forged_authority_rejected(self):
        r = math.compile_statement(self.file_request("finite_gram.json"))
        r["lean_kernel_checked"] = True
        self.assertHold(math.verify_receipt, r)

    def test_forged_rh_rejected(self):
        r = math.compile_statement(self.file_request("prime_cutoff.json"))
        r["riemann_hypothesis_proven"] = True
        self.assertHold(math.verify_receipt, r)

    def test_negative_gram_weight(self):
        st={"matrix":[["-1"]],"vectors":[["1"]],"weights":["-1"]}
        self.assertHold(math.compile_statement,self.request("finite_gram_sos",st))

    def test_incorrect_gram_matrix(self):
        st={"matrix":[["1","0"],["0","-1"]],"vectors":[["1","0"],["0","1"]],"weights":["1","1"]}
        self.assertHold(math.compile_statement,self.request("finite_gram_sos",st))

    def test_nonsymmetric_matrix(self):
        st={"matrix":[["1","2"],["0","1"]],"vectors":[["1","0"]],"weights":["1"]}
        self.assertHold(math.compile_statement,self.request("finite_gram_sos",st))

    def test_mismatched_gram_vector(self):
        st={"matrix":[["1","0"],["0","1"]],"vectors":[["1"]],"weights":["1"]}
        self.assertHold(math.compile_statement,self.request("finite_gram_sos",st))

    def test_prime_cutoff_boundary_rejected(self):
        self.assertHold(math.compile_statement,self.request("support_prime_cutoff",{"delta":"1/4"}))

    def test_nonpositive_delta_rejected(self):
        self.assertHold(math.compile_statement,self.request("support_prime_cutoff",{"delta":"0"}))

    def test_no_claim_from_empty_gram(self):
        self.assertHold(math.compile_statement,self.request("finite_gram_sos",{"matrix":[["0"]],"vectors":[],"weights":[]}))

    def test_receipt_is_deterministic(self):
        r=self.file_request("v7_reflection.json")
        self.assertEqual(math.canonical(math.compile_statement(r)), math.canonical(math.compile_statement(r)))
        dig=math.compile_statement(r)["receipt_sha256"]
        self.assertEqual(len(dig),64)

    def test_forward_inverse_randomized(self):
        rng = random.Random(20261119)
        for _ in range(250):
            degree=rng.randrange(0,12)
            R=math.trim(tuple(F(rng.randint(-100,100), rng.randrange(1,101)) for _ in range(degree+1)))
            if R==(F(0),): R=(F(1),)
            P=math.forward_normal_form(R)
            self.assertEqual(math.inverse_normal_form(P),R)
            self.assertEqual(math.add(P,math.compose(P,(F(1),F(-1)))),(F(0),))
            self.assertEqual(math.ev(P,F(0)),F(0))
            self.assertEqual(math.ev(P,F(1)),F(0))

    def test_gram_randomized(self):
        rng=random.Random(90)
        for _ in range(100):
            n=rng.randrange(1,6)
            k=rng.randrange(1,6)
            vs=[[F(rng.randrange(-5,6),rng.randrange(1,5)) for _ in range(n)] for _ in range(k)]
            weights=[F(rng.randrange(0,6),rng.randrange(1,6)) for _ in range(k)]
            A=[[sum((w*v[i]*v[j] for v,w in zip(vs,weights)),F(0)) for j in range(n)] for i in range(n)]
            st={'matrix':[[math.fmt(v) for v in row] for row in A], 'vectors':[[math.fmt(v) for v in row] for row in vs], 'weights':[math.fmt(w) for w in weights]}
            receipt=math.compile_statement(self.request('finite_gram_sos',st))
            self.assertTrue(math.verify_receipt(receipt))
            for _ in range(5):
                x=[F(rng.randrange(-4,5)) for _ in range(n)]
                lhs=sum((x[i]*A[i][j]*x[j] for i in range(n) for j in range(n)),F(0))
                rhs=sum((w*sum((v[i]*x[i] for i in range(n)),F(0))**2 for v,w in zip(vs,weights)),F(0))
                self.assertEqual(lhs,rhs)
                self.assertGreaterEqual(lhs,0)

    def test_prime_rational_bound_randomized(self):
        for n in range(5,400):
            delta=F(1,n)
            r=math.compile_statement(self.request('support_prime_cutoff',{'delta':math.fmt(delta)}))
            self.assertLess(F(r['checked']['exp_2delta_strict_upper_bound']),2)

    def test_cli_compile_verify(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"receipt.json"
            p=subprocess.run([sys.executable,str(MOD),'compile',str(EXAMPLES/'v7_reflection.json'),'--out',str(out)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run([sys.executable,str(MOD),'verify',str(out)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('RH_OPEN',p.stdout)

    def test_cli_global_rh_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"attack.json"
            f.write_text(json.dumps(self.request('RiemannHypothesis',{'claim':'universal'})))
            p=subprocess.run([sys.executable,str(MOD),'compile',str(f)],capture_output=True,text=True)
            self.assertEqual(p.returncode,2)
            self.assertIn('HOLD',p.stderr)

if __name__ == '__main__':
    unittest.main()
