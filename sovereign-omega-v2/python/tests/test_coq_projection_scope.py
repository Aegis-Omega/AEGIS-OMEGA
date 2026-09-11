"""Codex H: characterize the information preserved by the live projection."""
import unittest
from coq_attestation import parse_print_assumptions, _assumption_snapshot, compare_assumption_baseline


def files(log):
    return [{'path':'Example.v','axiom_symbols':['H'],'parameter_symbols':[],
             'admitted_count':0,'theorems':[{'theorem':'target',**parse_print_assumptions(log)}]}]

class ProjectionScopeTests(unittest.TestCase):
    def test_different_types_have_same_symbol_projection(self):
        a=files('Axioms:\nH : True\n');b=files('Axioms:\nH : False\n')
        self.assertNotEqual(a[0]['theorems'][0]['raw_sha256'],b[0]['theorems'][0]['raw_sha256'])
        self.assertEqual(_assumption_snapshot(a),_assumption_snapshot(b))
        baseline={'baseline_kind':'COQ_ASSUMPTION_BASELINE_V1',**_assumption_snapshot(a)}
        comparison=compare_assumption_baseline(b,baseline,'a'*64)
        self.assertFalse(comparison['regression'])
        self.assertEqual(comparison['comparison_scope'],'SYMBOL_NAMES_AND_ADMITTED_COUNTS')
        self.assertEqual(comparison['statement_equivalence'],'NOT_EVALUATED')

    def test_new_symbol_still_reports_regression(self):
        baseline={'baseline_kind':'COQ_ASSUMPTION_BASELINE_V1',**_assumption_snapshot(files('Axioms:\nH : True\n'))}
        current=files('Axioms:\nOther : True\n')
        comparison=compare_assumption_baseline(current,baseline,'a'*64)
        self.assertTrue(comparison['regression'])
        self.assertEqual(comparison['new_theorem_assumptions'],[{'location':'Example.v::target','symbol':'Other'}])

if __name__=='__main__':unittest.main()
