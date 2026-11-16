"""AEGIS Q16.16 mathematical precision regressions (stdlib only).

Source-independent Decimal reference and exact integer-floor invariants.
Execute: python -m unittest discover -s python/tests -p 'test_hardware_precision_v3.py'
from the sovereign-omega-v2 directory.
"""
import math
import os
import random
import sys
import unittest
from decimal import Decimal, localcontext

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from hardware_config import INT_SCALE, fixed_sqrt, mutual_information_fixed

S = INT_SCALE


def marginals(joint, n):
    return ([sum(joint[x*n+y] for y in range(n)) for x in range(n)],
            [sum(joint[x*n+y] for x in range(n)) for y in range(n)])


def decimal_mi(joint, p, q):
    with localcontext() as ctx:
        ctx.prec = 100
        result = Decimal(0)
        ln2 = Decimal(2).ln()
        ny = len(q)
        for i, mass in enumerate(joint):
            if mass:
                ratio = Decimal(mass*S) / Decimal(p[i//ny] * q[i%ny])
                result += Decimal(mass)/S * ratio.ln()/ln2
        return float(result)


class TestFixedSqrt(unittest.TestCase):
    def test_exact_boundary_values(self):
        for x, expected in [(0, 0), (1, 256), (2, 362),
                            (S, S), (S*4, 2*S), (S*9, 3*S),
                            (2**31-1, math.isqrt((2**31-1)*S))]:
            self.assertEqual(fixed_sqrt(x), expected, x)
        self.assertEqual(fixed_sqrt(-1), 0)

    def test_integer_floor_invariant_100000_inputs(self):
        rng = random.Random(20261116)
        values = list(range(1<<16))
        values.extend(rng.randrange(0, 1<<31) for _ in range(34464))
        self.assertEqual(len(values), 100000)
        for x in values:
            y = fixed_sqrt(x)
            self.assertIs(type(y), int)
            self.assertTrue(y*y <= x*S < (y+1)*(y+1), (x, y))
            self.assertEqual(y, math.isqrt(x*S))

    def test_deterministic_3_runs(self):
        xs = [0, 1, 2, 3, 4, 10, 65535, 65536, 65537, 2**31-1]
        results = [tuple(fixed_sqrt(x) for x in xs) for _ in range(3)]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])


class TestMutualInformation(unittest.TestCase):
    def test_rare_event_product_underflow(self):
        joint = [S-1, 0, 0, 1]
        p, q = marginals(joint, 2)
        approx = mutual_information_fixed(joint, p, q)/S
        self.assertLessEqual(abs(approx-decimal_mi(joint,p,q)), 1/S)
        self.assertGreaterEqual(approx, 0)

    def test_exact_simple_channels(self):
        for joint, n, exact in [([S], 1, 0), ([S//4]*4, 2, 0),
                                ([S//2,0,0,S//2], 2, S)]:
            p, q = marginals(joint, n)
            self.assertEqual(mutual_information_fixed(joint,p,q), exact)

    def test_seeded_1024_channels_against_decimal(self):
        rng = random.Random(20261116)
        for i in range(1024):
            n = rng.choice([2,3,4,5,8])
            weights = [rng.choice([0,0,1,2,7,19,111,7777]) if i%2
                       else rng.randrange(1,10001) for _ in range(n*n)]
            if not any(weights):
                weights[0] = 1
            total = sum(weights)
            joint = [v*S//total for v in weights]
            joint[0] += S-sum(joint)
            p, q = marginals(joint, n)
            approx = mutual_information_fixed(joint,p,q)/S
            gold = decimal_mi(joint,p,q)
            self.assertLessEqual(abs(approx-gold), 1/S, (i,n,approx,gold))
            self.assertGreaterEqual(approx, 0)

    def test_deterministic_3_runs(self):
        joint = [S-1, 0, 0, 1]
        p, q = marginals(joint, 2)
        a, b, c = (mutual_information_fixed(joint,p,q) for _ in range(3))
        self.assertEqual(a,b)
        self.assertEqual(b,c)


if __name__ == '__main__':
    unittest.main(verbosity=2)
