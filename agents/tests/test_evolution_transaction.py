"""Native AEGIS demotion journal tests. All files confined to temporary fixtures.

No real registry or production state is mutated.
"""
from __future__ import annotations

import copy
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agents.evolution import (
    AdaptiveLineage, EvolutionEngine, _demotion_evidence_fingerprint,
)
from agents.evolution_transaction import (
    EvolutionTransactionError, commit_demotions, inspect_pending, journal_path,
)
from harness.sdk.skill_authority import compute_registry_root, evaluate_registry


class EvolutionTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name in ("harness", "agents", "evidence"):
            (self.root / name).mkdir()
        (self.root / "evidence" / "run.json").write_text("{}\n", encoding="utf-8")
        self.tree = self.root / "harness" / "skill_tree.json"
        self.lineage = self.root / "agents" / "adaptive_lineage.json"
        self.old_tree = {
            "schema_version": "2.0.0", "version": "2.0.0",
            "authority_state": "NON_AUTHORITATIVE_UNTIL_OBSERVED",
            "source_commit": "a" * 40,
            "skills": [{
                "skill_id": "candidate",
                "tier": "T1",
                "observation_state": "OBSERVED",
                "validated_runs": 4,
                "confidence": 0.80,
                "recency_score": 1.0,
                "failure_rate": 0.60,
                "failure_rate_observed": 0.60,
                "last_validated": "2026-11-16T00:00:00Z",
                "evidence_refs": ["evidence/run.json"],
            }],
        }
        self.old_tree["registry_root"] = self.old_tree["genesis_seal"] = compute_registry_root(self.old_tree)
        self.tree.write_text(json.dumps(self.old_tree, indent=2) + "\n", encoding="utf-8")
        self.next_tree = copy.deepcopy(self.old_tree)
        self.next_tree["skills"][0]["tier"] = "T2"
        self.next_tree["registry_root"] = self.next_tree["genesis_seal"] = compute_registry_root(self.next_tree)
        self.next_lineage = AdaptiveLineage()
        self.next_lineage.append(
            "TIER_DEMOTION", "candidate", "T1", "T2",
            "failure_rate high; obs=" + _demotion_evidence_fingerprint(self.old_tree["skills"][0]),
            timestamp_ms=12345,
        )

    def commit(self, **kwargs):
        return commit_demotions(
            tree_path=self.tree,
            lineage_path=self.lineage,
            next_tree=self.next_tree,
            next_lineage=self.next_lineage,
            repo_root=self.root,
            **kwargs,
        )

    def test_normal_demotion_commit_preserves_both_verified_files(self):
        receipt = self.commit()
        self.assertEqual(len(receipt), 64)
        self.assertEqual(inspect_pending(self.tree, self.lineage)["status"], "CLEAN")
        result = json.loads(self.tree.read_text(encoding="utf-8"))
        self.assertEqual(result["skills"][0]["tier"], "T2")
        self.assertEqual(result["registry_root"], compute_registry_root(result))
        self.assertEqual(evaluate_registry(result, repo_root=self.root).outcome, "ADMITTED")
        self.assertEqual(AdaptiveLineage.load(self.lineage).terminal_hash(),
                         self.next_lineage.terminal_hash())

    def test_engine_actual_tick_uses_journal_and_remains_idempotent(self):
        engine = EvolutionEngine(tree_path=str(self.tree),
                                 lineage_path=self.lineage, repo_root=self.root)
        v = engine.tick(apply_changes=True)
        self.assertEqual(v[0].eligible_tier, "T2")
        self.assertEqual(inspect_pending(self.tree, self.lineage)["status"], "CLEAN")
        tree_before = self.tree.read_bytes()
        lineage_before = self.lineage.read_bytes()
        engine2 = EvolutionEngine(tree_path=str(self.tree),
                                  lineage_path=self.lineage, repo_root=self.root)
        engine2.tick(apply_changes=True)
        self.assertEqual(tree_before, self.tree.read_bytes())
        self.assertEqual(lineage_before, self.lineage.read_bytes())

    def test_crash_after_journal_is_prepared_and_blocks_next_writer(self):
        with self.assertRaisesRegex(EvolutionTransactionError, "INJECTED_CRASH_AFTER_JOURNAL"):
            self.commit(fault_after="journal")
        self.assertEqual(inspect_pending(self.tree, self.lineage)["status"], "PREPARED_NOT_APPLIED")
        with self.assertRaisesRegex(EvolutionTransactionError, "UNRESOLVED_EVOLUTION_TRANSACTION"):
            self.commit()
        with self.assertRaisesRegex(ValueError, "UNRESOLVED_EVOLUTION_TRANSACTION"):
            EvolutionEngine(tree_path=str(self.tree),
                            lineage_path=self.lineage, repo_root=self.root).tick(apply_changes=False)

    def test_crash_after_lineage_is_partial_and_blocks_readers(self):
        with self.assertRaisesRegex(EvolutionTransactionError, "INJECTED_CRASH_AFTER_LINEAGE"):
            self.commit(fault_after="lineage")
        state = inspect_pending(self.tree, self.lineage)
        self.assertEqual(state["status"], "PARTIAL_COMMIT")
        self.assertEqual(state["files"], {"registry": "OLD", "lineage": "NEW"})
        with self.assertRaisesRegex(ValueError, "UNRESOLVED_EVOLUTION_TRANSACTION"):
            EvolutionEngine(tree_path=str(self.tree),
                            lineage_path=self.lineage, repo_root=self.root).tick(apply_changes=False)

    def test_crash_after_registry_requires_explicit_recovery(self):
        with self.assertRaisesRegex(EvolutionTransactionError, "INJECTED_CRASH_AFTER_REGISTRY"):
            self.commit(fault_after="registry")
        self.assertEqual(inspect_pending(self.tree, self.lineage)["status"],
                         "READY_FOR_EXPLICIT_FINALIZATION")
        with self.assertRaisesRegex(ValueError, "UNRESOLVED_EVOLUTION_TRANSACTION"):
            EvolutionEngine(tree_path=str(self.tree),
                            lineage_path=self.lineage, repo_root=self.root).tick(apply_changes=False)

    def test_tampered_journal_never_becomes_clean(self):
        with self.assertRaises(EvolutionTransactionError):
            self.commit(fault_after="journal")
        path = journal_path(self.tree)
        entry = json.loads(path.read_text(encoding="utf-8"))
        entry["new_registry_root"] = "f" * 64
        path.write_text(json.dumps(entry), encoding="utf-8")
        self.assertEqual(inspect_pending(self.tree, self.lineage)["status"],
                         "INVALID_PENDING_JOURNAL")

    def test_unjournaled_registry_save_is_denied(self):
        engine = EvolutionEngine(tree_path=str(self.tree),
                                 lineage_path=self.lineage, repo_root=self.root)
        with self.assertRaisesRegex(ValueError, "UNJOURNALED_REGISTRY_SAVE_DENIED"):
            engine._save_tree()

    def test_promotions_are_never_allowed_by_transaction_helper(self):
        self.next_tree["skills"][0]["tier"] = "T0"
        self.next_tree["registry_root"] = self.next_tree["genesis_seal"] = compute_registry_root(self.next_tree)
        with self.assertRaisesRegex(EvolutionTransactionError, "PROMOTION_NOT_SUPPORTED"):
            self.commit()
        self.assertFalse(journal_path(self.tree).exists())

    def test_changed_observation_is_not_same_evidence(self):
        self.next_tree["skills"][0]["confidence"] = 0.99
        self.next_tree["registry_root"] = self.next_tree["genesis_seal"] = compute_registry_root(self.next_tree)
        with self.assertRaisesRegex(EvolutionTransactionError, "OBSERVATION_CHANGED_DURING_COMMIT"):
            self.commit()

    def test_invalid_event_kind_denied_before_commit(self):
        self.next_lineage = AdaptiveLineage()
        self.next_lineage.append("TIER_PROMOTION", "candidate", "T1", "T2", "fake",
                                 timestamp_ms=1)
        with self.assertRaisesRegex(EvolutionTransactionError, "NON_DEMOTION_EVENT"):
            self.commit()

    def test_invalid_fingerprint_denied_before_commit(self):
        self.next_lineage = AdaptiveLineage()
        self.next_lineage.append("TIER_DEMOTION", "candidate", "T1", "T2",
                                 "high failures; obs=" + "0" * 64, timestamp_ms=1)
        with self.assertRaisesRegex(EvolutionTransactionError, "DEMOTION_EVIDENCE_FINGERPRINT_INVALID"):
            self.commit()

    def test_missing_evidence_denied_before_journal(self):
        (self.root / "evidence" / "run.json").unlink()
        with self.assertRaisesRegex(EvolutionTransactionError, "BASE_REGISTRY_NOT_ADMITTED"):
            self.commit()
        self.assertFalse(journal_path(self.tree).exists())

    def test_concurrent_writer_lock_denied(self):
        lock_path = self.tree.with_name(self.tree.name + ".evolution.lock")
        with open(lock_path, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.assertRaisesRegex(EvolutionTransactionError, "CONCURRENT_WRITER"):
                self.commit()

    def test_symlink_registry_denied(self):
        linked = self.root / "harness" / "linked.json"
        linked.symlink_to(self.tree)
        with self.assertRaisesRegex(EvolutionTransactionError, "SYMLINK_TARGET_OR_PARENT"):
            commit_demotions(tree_path=linked, lineage_path=self.lineage,
                             next_tree=self.next_tree, next_lineage=self.next_lineage,
                             repo_root=self.root)

    def test_replayed_prior_event_requires_exact_chain(self):
        earlier = AdaptiveLineage()
        earlier.append("EVIDENCE_RECORDED", "candidate", "T1", "T1",
                       "old evidence", timestamp_ms=1)
        earlier.save(self.lineage)
        new_lineage = AdaptiveLineage()
        new_lineage.append("EVIDENCE_RECORDED", "candidate", "T1", "T1",
                           "not the same prior event", timestamp_ms=1)
        new_lineage.append("TIER_DEMOTION", "candidate", "T1", "T2",
                           "bad; obs=" + _demotion_evidence_fingerprint(self.old_tree["skills"][0]),
                           timestamp_ms=2)
        self.next_lineage = new_lineage
        with self.assertRaisesRegex(EvolutionTransactionError, "LINEAGE_PRIOR_EVENTS_CHANGED"):
            self.commit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
