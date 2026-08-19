"""Safety checks for finite, positive batch-spending caps."""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents import batch_bridge


TASKS = [batch_bridge.AgentTask("test", "system", "prompt")]
INVALID_CAPS = (float("nan"), float("inf"), float("-inf"), 0, -0.01)
REPO_ROOT = Path(__file__).resolve().parents[2]


class BatchCapValidationTests(unittest.TestCase):
    def test_plan_accepts_finite_positive_cap(self):
        plan = batch_bridge.plan(TASKS, cap=1.00)

        self.assertFalse(plan.over_cap)

    def test_submit_accepts_finite_positive_cap(self):
        store = Mock()

        record = batch_bridge.submit(TASKS, live=False, cap=1.00, store=store)

        self.assertEqual(record["status"], "dry_run")
        store.put.assert_called_once_with("last_batch", record)

    def test_plan_rejects_non_finite_and_non_positive_caps(self):
        for cap in INVALID_CAPS:
            with self.subTest(cap=cap):
                with self.assertRaisesRegex(ValueError, "finite, strictly positive"):
                    batch_bridge.plan(TASKS, cap=cap)

    def test_submit_rejects_invalid_caps_before_anthropic_import_or_call(self):
        store = Mock()
        with patch.dict(sys.modules, {"anthropic": None}):
            for cap in INVALID_CAPS:
                with self.subTest(cap=cap):
                    with self.assertRaisesRegex(ValueError, "finite, strictly positive"):
                        batch_bridge.submit(TASKS, live=True, cap=cap, store=store)

        store.put.assert_not_called()

    def test_environment_cap_rejects_malformed_and_unsafe_values_at_import(self):
        for cap in ("not-a-number", "nan", "inf", "-inf", "0", "-1"):
            with self.subTest(cap=cap):
                env = os.environ | {"AEGIS_BATCH_MAX_USD": cap}
                result = subprocess.run(
                    [sys.executable, "-c", "import agents.batch_bridge"],
                    cwd=REPO_ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Invalid AEGIS_BATCH_MAX_USD", result.stderr)


if __name__ == "__main__":
    unittest.main()
