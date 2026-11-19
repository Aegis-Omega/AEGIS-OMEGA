"""MANDATORY in the actual AEGIS repo, requires real RFC 0001 compiler files.

Fails rather than skipping if compiled outside the original project. This file
must run inside original packages/aegis-interface and is not a local fake gate.
"""
import hashlib
import json
from pathlib import Path
import unittest

from aegis_interface.compiler import compile_source
from aegis_interface.math_rh import compile_statement
from aegis_interface.mira_bridge import build_bridge, verify_bridge, verify_wit_contract

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WIT = ROOT / 'wit' / 'mira_rh_proof.wit'
FIXTURES = ROOT / 'tests' / 'fixtures'

class RealCompilerIntegration(unittest.TestCase):
    def test_full_wit_to_ir_and_readback(self):
        meta=verify_wit_contract(WIT)
        self.assertEqual(meta['equivalence'], 'PASS_ORIGINAL_COMPILER')
        result=compile_source(WIT.read_text('utf8'))
        self.assertIn('MIRAMathReceipt',result.rust)
        self.assertIn('MIRAMathReceipt',result.typescript)
        self.assertIn('MIRAMathReceipt',result.python)
        self.assertEqual(result.equivalence().findings,[])

    def test_three_exact_receipts_bridge(self):
        for f in ('v7_reflection.json','finite_gram.json','prime_cutoff.json'):
            with self.subTest(f=f):
                receipt=compile_statement(json.loads((FIXTURES / f).read_text('utf8')))
                result=build_bridge(receipt,WIT)
                self.assertTrue(verify_bridge(result,receipt,WIT))
                self.assertEqual(result['lean_source_binding'],'UNKNOWN_NOT_PRESENT')
                self.assertFalse(result['lean_kernel_checked'])
                self.assertFalse(result['riemann_hypothesis_proven'])

    def test_drift_in_field_schema_fails_closed(self):
        bad=WIT.read_text('utf8').replace('lean_kernel_checked: bool','lean_kernel_checked: string')
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as d:
            p=Path(d)/'invalid.wit';p.write_text(bad,'utf8')
            from aegis_interface.math_rh import ProofHold
            with self.assertRaises(ProofHold): verify_wit_contract(p)

    def test_modified_receipt_cannot_rebind(self):
        from aegis_interface.math_rh import ProofHold
        receipt=compile_statement(json.loads((FIXTURES/'finite_gram.json').read_text()))
        bridge=build_bridge(receipt,WIT)
        bridge['riemann_hypothesis_proven']=True
        with self.assertRaises(ProofHold): verify_bridge(bridge,receipt,WIT)

if __name__=='__main__': unittest.main()
