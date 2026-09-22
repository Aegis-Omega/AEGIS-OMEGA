"""Exact arithmetic and source-contract tests, NOT a Lean proof checker."""
from fractions import Fraction as F
from itertools import combinations
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
LEAN = ROOT / 'sovereign-omega-v2/formal/bridges/lean'
FILES = ('RHFourBlockPrimeEightV3.lean', 'RHFineMomentPacketV3.lean',
         'RHFourBlockConcreteV3.lean')

class ExactArithmetic(unittest.TestCase):
    def test_eight_window_lower(self):
        self.assertGreater(8 * F(31,32), 7)
    def test_eight_window_upper(self):
        self.assertLess(8 * F(32,31), 9)
    def test_unique_integer_in_rational_envelope(self):
        lo, hi = 8*F(31,32), 8*F(32,31)
        self.assertEqual([n for n in range(1,12) if lo <= n <= hi], [8])
    def test_window_does_not_generalise_to_32(self):
        lo, hi = 32*F(31,32), 32*F(32,31)
        self.assertGreater(len([n for n in range(29,36) if lo <= n <= hi]), 1)
    def test_seed_has_strict_endpoint_room(self):
        self.assertLess(F(1,512), F(1,256))
        self.assertLess(F(1,256), F(1,128))
        self.assertEqual(2*F(1,128), F(1,64))
    def test_old_seed_is_not_the_new_width_certificate(self):
        self.assertGreater(2*F(1,80), F(1,64))
    def test_six_pairs_and_relative_gaps(self):
        pairs=list(combinations(range(4),2))
        self.assertEqual(pairs,[(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)])
        self.assertEqual([j-i for i,j in pairs],[1,2,3,1,2,1])
    def test_farthest_norm_budget(self):
        self.assertEqual(F(1,4)+F(1,100),F(13,50))
    def test_wrong_von_mangoldt_coefficient_is_rejected(self):
        self.assertGreater(3*F(1,4)+F(1,100),F(13,50))
    def test_margin(self):
        self.assertEqual(F(32,25)-F(158,125),F(2,125))
    def test_zero_energy(self):
        self.assertEqual(-F(2,125)*0*F(15,2),0)
    def test_translation_gap(self):
        for d in (F(-7,3),F(0),F(4,5)):
            for i,j in combinations(range(4),2):
                self.assertEqual((d+j)-(d+i),j-i)

class SourceContract(unittest.TestCase):
    def source(self, name):
        path=LEAN/name
        self.assertTrue(path.is_file(), f'missing new source: {name}')
        return path.read_text()
    def test_prime_source(self):
        t=self.source(FILES[0])
        for name in ('nat_eq_eight_of_log_window_v3','farthest_prime_sum_exact_v3',
                     'farthest_B_norm_bound_v3','B_translate_eq_of_gap_v3'):
            self.assertRegex(t, rf'theorem\s+{name}\b')
            self.assertIn('#print axioms AEGIS.RHFourBlockPrimeEightV3.'+name,t)
        self.assertIn('vonMangoldt_apply_pow',t)
    def test_fine_source(self):
        t=self.source(FILES[1])
        for name in ('gFine_moments_v3','gFine_ne_zero_v3','gFine_width_v3'):
            self.assertRegex(t,rf'theorem\s+{name}\b')
        self.assertIn('phiFine_tsupport_strict_v3',t)
        self.assertNotIn('import RHNarrowMomentPacketV1',t)
    def test_concrete_source(self):
        t=self.source(FILES[2])
        for name in ('four_diagonals_v3','six_cross_bounds_v3',
                     'four_packet_coercive_v3','canonical_four_packet_sign_v3'):
            self.assertRegex(t,rf'theorem\s+{name}\b')
        self.assertIn('actual_four_block_bound_v2',t)
        self.assertIn('farthest_B_norm_bound_v3',t)
        self.assertIn('translate_energy',t)
    def test_final_signature_has_no_analytic_bounds_as_hypotheses(self):
        t=self.source(FILES[2])
        sig=t.split('theorem four_packet_coercive_v3',1)[1].split(':= by',1)[0]
        self.assertIn('WeilMomentConditionsV1',sig)
        self.assertIn('WidthOneSixtyFourAt',sig)
        self.assertNotRegex(sig,r'\(h(?:0[123]?|1[23]?|2[3]?|3)\s*:')
    def test_no_placeholder_or_new_axiom_declarations(self):
        for f in FILES:
            t=self.source(f)
            t=re.sub(r'/\-.*?\-/','',t,flags=re.S)
            t=re.sub(r'--[^\n]*','',t)
            self.assertNotRegex(t,r'\b(sorry|admit|axiom|native_decide)\b')
            self.assertNotRegex(t,r'(?m)^\s*(opaque|constant)\s')

if __name__=='__main__': unittest.main()
