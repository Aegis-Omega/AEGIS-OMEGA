"""Safety regressions for the opt-in Anthropic batch dispatcher."""

import math
import tempfile
import unittest
from pathlib import Path

from agents.batch_bridge import AgentTask, FileStore, _tok, plan, submit


class BatchBridgeSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks = [AgentTask("engineering", "system", "prompt", max_tokens=1)]

    def test_non_finite_or_negative_cap_is_rejected(self) -> None:
        for cap in (math.nan, math.inf, -math.inf, -0.01):
            with self.subTest(cap=cap):
                with self.assertRaises(ValueError):
                    plan(self.tasks, cap=cap)

    def test_dry_run_persists_without_submitting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            record = submit(self.tasks, live=False, cap=1.0,
                            store=FileStore(Path(directory)))

            self.assertEqual(record["status"], "dry_run")
            self.assertFalse(record["live"])
            self.assertIsNone(record["batch_id"])
            self.assertEqual(FileStore(Path(directory)).get("last_batch"), record)

    def test_prompt_estimate_is_conservative_for_utf8(self) -> None:
        self.assertEqual(_tok("你好"), len("你好".encode("utf-8")))


if __name__ == "__main__":
    unittest.main()
