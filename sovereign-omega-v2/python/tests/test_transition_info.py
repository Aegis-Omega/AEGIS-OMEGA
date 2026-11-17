"""AEGIS V14 streaming Markov statistics: independent regressions.

Run from sovereign-omega-v2:
    python -m unittest discover -s python/tests -p test_transition_info.py -v
"""
import itertools
import random
import subprocess
import sys
import unittest
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transition_info import (
    InvalidStats, TransitionStats, SCALE, analyze,
    adjacent_mi_q16, entropy_rate_q16, log2_ratio_bounds,
)


def decimal_oracle(seq):
    if len(seq) < 2:
        return (0, 0)
    stats = TransitionStats.from_iterable(seq, max(seq) + 1)
    prev, nxt = stats.margins()
    t = len(seq) - 1
    with localcontext() as ctx:
        ctx.prec = 100
        ln2 = Decimal(2).ln()
        rate = mi = Decimal(0)
        for a, b, count in stats.edges:
            q = Decimal(count) / t
            rate += q * (Decimal(prev[a]) / count).ln() / ln2
            mi += q * (Decimal(count * t) / Decimal(prev[a] * nxt[b])).ln() / ln2
        quant = lambda value: int((value * SCALE).to_integral_value(rounding=ROUND_HALF_EVEN))
        return quant(rate), quant(mi)


class TransitionTests(unittest.TestCase):
    def test_short_binary_and_all_two_way_splits(self):
        for n in range(8):
            for seq in itertools.product(range(2), repeat=n):
                stats = TransitionStats.from_iterable(seq, 2)
                self.assertEqual(stats, TransitionStats.parse(stats.canonical_bytes()))
                self.assertEqual((entropy_rate_q16(stats), adjacent_mi_q16(stats)), decimal_oracle(seq))
                for split in range(n + 1):
                    a = TransitionStats.from_iterable(seq[:split], 2)
                    b = TransitionStats.from_iterable(seq[split:], 2)
                    joined = a.concat(b)
                    self.assertEqual(joined, stats)
                    self.assertEqual(joined.digest(), stats.digest())

    def test_associativity_exhaustive(self):
        short = [seq for n in range(4) for seq in itertools.product(range(2), repeat=n)]
        for a, b, c in itertools.product(short, repeat=3):
            sa, sb, sc = (TransitionStats.from_iterable(seq, 2) for seq in (a, b, c))
            merged = sa.concat(sb).concat(sc)
            self.assertEqual(merged, sa.concat(sb.concat(sc)))
            self.assertEqual(merged, TransitionStats.from_iterable(a + b + c, 2))

    def test_100_digit_decimal_random(self):
        rng = random.Random(20261116)
        for _ in range(160):
            alphabet = rng.randrange(2, 12)
            seq = [rng.randrange(alphabet) for _ in range(rng.randrange(2, 300))]
            stats = TransitionStats.from_iterable(seq, alphabet)
            self.assertEqual((entropy_rate_q16(stats), adjacent_mi_q16(stats)), decimal_oracle(seq))

    def test_log_enclosures(self):
        rng = random.Random(56)
        examples = [(1, 1), (2, 1), (1, 2), (3, 2), (7, 3)]
        examples += [(rng.randrange(1, 100000), rng.randrange(1, 100000)) for _ in range(120)]
        with localcontext() as ctx:
            ctx.prec = 85
            for a, b in examples:
                low, high = log2_ratio_bounds(a, b)
                value = Decimal(a).ln() / Decimal(2).ln() - Decimal(b).ln() / Decimal(2).ln()
                decimal_low = Decimal(low.numerator) / Decimal(low.denominator)
                decimal_high = Decimal(high.numerator) / Decimal(high.denominator)
                self.assertLessEqual(decimal_low - Decimal('1e-70'), value)
                self.assertLessEqual(value, decimal_high + Decimal('1e-70'))

    def test_analytic_summary_is_not_forensic_identity(self):
        a = analyze([0, 0, 1, 0], 2, source_id="same")
        b = analyze([0, 1, 0, 0], 2, source_id="same")
        c = analyze([0, 0, 1, 0], 2, source_id="other")
        self.assertEqual(a["statistics_sha256"], b["statistics_sha256"])
        self.assertNotEqual(a["source_order_sha256"], b["source_order_sha256"])
        self.assertNotEqual(a["source_order_sha256"], c["source_order_sha256"])

    def test_malformed_data_fail_closed(self):
        bad = [
            (2, 3, 0, 0, ((0, 1, 1), (1, 1, 1))),
            (2, 3, 0, 0, ((0, 1, 1), (1, 0, 1), (1, 0, 1))),
            (2, 2, 0, 1, ((0, 0, 1),)),
            (2, 2, 0, 1, ((0, 1, 2),)),
            (2, 1, 0, 1, ()),
            (2, 0, 0, None, ()),
        ]
        for value in bad:
            with self.assertRaises(InvalidStats):
                TransitionStats(*value)
        for seq, alphabet in [([0, True], 2), ([-1], 2), ([0], 0)]:
            with self.assertRaises(InvalidStats):
                TransitionStats.from_iterable(seq, alphabet)
        valid = TransitionStats.from_iterable([0, 1, 0], 2)
        for data in [valid.canonical_bytes() + b" ", b'{"schema":1,"schema":2}']:
            with self.assertRaises(InvalidStats):
                TransitionStats.parse(data)
        with self.assertRaises(InvalidStats):
            valid.concat(TransitionStats.from_iterable([0], 3))
        with self.assertRaises(InvalidStats):
            analyze([0], 2, source_id="bad\n")

    def test_large_one_shot_stream(self):
        stats = TransitionStats.from_iterable((i % 7 for i in range(100000)), 7)
        self.assertEqual(stats.length, 100000)
        self.assertEqual(sum(count for _, _, count in stats.edges), 99999)
        self.assertEqual(entropy_rate_q16(stats), 0)

    def test_command_line_entrypoint(self):
        path = ROOT / "transition_info.py"
        valid = subprocess.run(
            [sys.executable, str(path), "--alphabet", "2", "--source-id", "test"],
            input="0\n1\n0\n1\n", text=True, capture_output=True,
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertIn('"entropy_rate_q16": 0', valid.stdout)
        invalid = subprocess.run(
            [sys.executable, str(path), "--alphabet", "2", "--source-id", "test"],
            input="0\nnot-number\n", text=True, capture_output=True,
        )
        self.assertEqual(invalid.returncode, 2)


if __name__ == "__main__":
    unittest.main()
