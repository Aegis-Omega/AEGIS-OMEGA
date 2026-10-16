"""Cross-module lineage recording must fail closed on bad evidence/state."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agents.evolution import AdaptiveLineage
from agents.revenue_engine import _record_revenue_cycle


def revenue():
    return SimpleNamespace(
        objective="Synthetic contract candidate",
        projection=None,
        artifacts=[SimpleNamespace(role="strategy", sequence=0),
                   SimpleNamespace(role="finance", sequence=1)],
    )


class RevenueLineageSafetyTests(unittest.TestCase):
    def test_valid_chain_has_digest_when_save_succeeds(self):
        chain = AdaptiveLineage()
        with patch.object(AdaptiveLineage, "load", return_value=chain), \
                patch.object(AdaptiveLineage, "save") as save, \
                patch("agents.evolution.EvolutionEngine.tick") as tick:
            root, valid = _record_revenue_cycle(revenue())
        self.assertTrue(valid)
        self.assertEqual(root, chain.terminal_hash())
        self.assertEqual(len(root), 64)
        self.assertEqual(len(chain.events), 2)
        save.assert_called_once()
        tick.assert_called_once_with(apply_changes=False)

    def test_corrupted_old_chain_never_written(self):
        chain = AdaptiveLineage()
        event = chain.append("EVIDENCE_RECORDED", "strategy", "T2", "T2",
                             "candidate", timestamp_ms=100)
        event.evidence = "tampered"
        with patch.object(AdaptiveLineage, "load", return_value=chain), \
                patch.object(AdaptiveLineage, "save") as save:
            root, valid = _record_revenue_cycle(revenue())
        self.assertEqual((root, valid), ("", False))
        save.assert_not_called()

    def test_corrupted_result_never_written(self):
        chain = AdaptiveLineage()
        with patch.object(AdaptiveLineage, "load", return_value=chain), \
                patch.object(chain, "verify_chain", side_effect=[(True, None), (False, 1)]), \
                patch.object(AdaptiveLineage, "save") as save:
            root, valid = _record_revenue_cycle(revenue())
        self.assertEqual((root, valid), ("", False))
        save.assert_not_called()

    def test_save_failure_is_not_reported_as_valid(self):
        chain = AdaptiveLineage()
        with patch.object(AdaptiveLineage, "load", return_value=chain), \
                patch.object(AdaptiveLineage, "save", side_effect=OSError("disk unavailable")):
            root, valid = _record_revenue_cycle(revenue())
        self.assertEqual((root, valid), ("", False))

    def test_lineage_load_failure_is_not_reported_as_valid(self):
        with patch.object(AdaptiveLineage, "load", side_effect=ValueError("corrupt JSON")):
            self.assertEqual(_record_revenue_cycle(revenue()), ("", False))

    def test_evolution_exception_is_not_reported_as_valid(self):
        chain = AdaptiveLineage()
        with patch.object(AdaptiveLineage, "load", return_value=chain), \
                patch("agents.evolution.EvolutionEngine.tick",
                      side_effect=RuntimeError("unsafe evolution")):
            self.assertEqual(_record_revenue_cycle(revenue()), ("", False))


if __name__ == "__main__":
    unittest.main()
