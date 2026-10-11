"""Falsifiers for the cross-module contract spine; no network or model calls."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from agents.dendrite_mesh import digest
from agents.issue_evolution import compile_graph
from agents.evolution import AdaptiveLineage
from agents.evolution_contract_spine import (
    compose_spine, _read_bounded, TOKEN_SCHEMA, SCHEMA,
)
from harness.sdk.skill_authority import compute_registry_root

REPO = "Aegis-Omega/AEGIS-OMEGA"
OLD = "a" * 40
NEW = "b" * 40


def issue(n, title, body="", labels=None):
    return {"number": n, "title": title, "body": body,
            "labels": [{"name": x} for x in (labels or ["task"])]}


def graph_for(items=None):
    if items is None:
        items = [
            issue(734, "Firm of agents"),
            issue(757, "Evidence lab", "Parent: #734"),
            issue(758, "Evolution", "Parent: #734\nDepends on #757"),
            issue(735, "Billing key gate", labels=["task", "needs-operator"]),
        ]
    return compile_graph({"repository": REPO, "issues": items,
                          "complete_pages": True, "acquisition": "EXPLICIT_OFFLINE_FIXTURE",
                          "pages": 1})


def positive_trial():
    return {
        "schema": "AEGIS_ISSUE_EVOLUTION_TRIAL_V1", "issue": f"{REPO}#758",
        "baseline": OLD, "candidate": NEW, "pre_registered_metric": "task_success",
        "holdout_digest": "c" * 64, "rollback_ref": OLD,
        "paired_results": [
            {"task_id": f"pair-{i}", "baseline_score": 0.1,
             "candidate_score": 0.9, "safety_regression": False}
            for i in range(32)
        ],
    }


def counterexample():
    return {
        "kind": "AEGIS_REPLAYABLE_COUNTEREXAMPLE_V1",
        "outcome": "COUNTEREXAMPLE_DISCOVERED",
        "admission": "NOT_ADMITTED",
        "authority_granted": False,
        "witness": {"failure_codes": ["STATUS_MISMATCH"], "path": "/fuzz/zz"},
    }


class EvolutionContractSpineTests(unittest.TestCase):
    def test_all_issues_receive_distinct_content_bound_tokens(self):
        r = compose_spine(graph=graph_for(), trials=[], source_head=OLD)
        self.assertEqual(r["issue_count"], 4)
        self.assertEqual(len({t["token_id"] for t in r["issue_contract_tokens"]}), 4)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["improvement_admission"], "DENIED")
        self.assertEqual(r["skill_tier_effect"], "NONE")

    def test_deterministic_replay(self):
        r = graph_for()
        self.assertEqual(compose_spine(graph=r, trials=[], source_head=OLD),
                         compose_spine(graph=r, trials=[], source_head=OLD))

    def test_token_never_authorizes_execution(self):
        r = compose_spine(graph=graph_for(), trials=[positive_trial()], source_head=OLD)
        self.assertEqual(r["authority_effect"], "NONE")
        self.assertEqual(r["execution_effect"], "NONE")
        self.assertFalse(r["external_benchmark_verified"])
        for t in r["issue_contract_tokens"]:
            self.assertEqual(t["schema"], TOKEN_SCHEMA)
            self.assertFalse(t["claims_verified"])
            self.assertEqual(t["self_promotion"], "DENIED")
            self.assertEqual(t["token_id"], digest({k: v for k, v in t.items()
                                                      if k != "token_id"}))

    def test_positive_self_report_is_only_unverified_lesson(self):
        r = compose_spine(graph=graph_for(), trials=[positive_trial()], source_head=OLD)
        self.assertEqual(r["trial_count"], 1)
        self.assertEqual(r["independent_review"], "NOT_PERFORMED")
        self.assertTrue(r["cross_issue_lesson_count"] > 0)
        self.assertEqual(r["improvement_admission"], "DENIED")

    def test_operator_issues_stay_operator_required(self):
        r = compose_spine(graph=graph_for(), trials=[], source_head=OLD)
        t = next(t for t in r["issue_contract_tokens"] if t["issue"].endswith("#735"))
        self.assertTrue(t["operator_required"])
        self.assertEqual(t["authority_effect"], "NONE")

    def test_full_issue_board_batches_without_unbounded_dispatch(self):
        g = graph_for([issue(i, f"Task {i}") for i in range(1, 41)])
        r = compose_spine(graph=g, trials=[], source_head=OLD)
        self.assertEqual([b["count"] for b in r["dendrite_batches"]], [32, 8])
        self.assertEqual(r["issue_count"], 40)

    def test_wrong_source_head_denied(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_HEAD_INVALID"):
            compose_spine(graph=graph_for(), trials=[], source_head="forged")

    def test_tampered_graph_denied(self):
        g = graph_for()
        g["nodes"][0]["title"] = "altered"
        with self.assertRaises(ValueError):
            compose_spine(graph=g, trials=[], source_head=OLD)

    def test_duplicate_trial_denied(self):
        with self.assertRaisesRegex(ValueError, "EVOLUTION_DUPLICATE_CANDIDATE"):
            compose_spine(graph=graph_for(),
                          trials=[positive_trial(), positive_trial()], source_head=OLD)

    def test_forged_foundry_witness_is_never_promotion(self):
        r = compose_spine(
            graph=graph_for(), trials=[], source_head=OLD,
            counterexamples=[{"issue": f"{REPO}#758", "witness": counterexample()}])
        t = next(x for x in r["issue_contract_tokens"] if x["issue"].endswith("#758"))
        self.assertEqual(len(t["negative_knowledge"]), 1)
        self.assertEqual(t["negative_knowledge"][0]["status"],
                         "UNVERIFIED_COUNTEREXAMPLE_CANDIDATE")
        self.assertEqual(r["improvement_admission"], "DENIED")

    def test_forged_foundry_admission_denied(self):
        witness = counterexample()
        witness["authority_granted"] = True
        with self.assertRaisesRegex(ValueError, "COUNTEREXAMPLE_STATE_INVALID"):
            compose_spine(graph=graph_for(), trials=[], source_head=OLD,
                          counterexamples=[{"issue": f"{REPO}#758", "witness": witness}])

    def test_unknown_counterexample_issue_denied(self):
        with self.assertRaisesRegex(ValueError, "COUNTEREXAMPLE_ISSUE_UNRESOLVED"):
            compose_spine(graph=graph_for(), trials=[], source_head=OLD,
                          counterexamples=[{"issue": f"{REPO}#9999",
                                            "witness": counterexample()}])

    def test_duplicate_counterexample_denied(self):
        x = {"issue": f"{REPO}#758", "witness": counterexample()}
        with self.assertRaisesRegex(ValueError, "COUNTEREXAMPLE_DUPLICATE"):
            compose_spine(graph=graph_for(), trials=[], source_head=OLD,
                          counterexamples=[x, x])

    def test_registry_root_exactly_bound(self):
        registry = {"skills": [], "schema_version": "2.0.0"}
        registry["registry_root"] = compute_registry_root(registry)
        r = compose_spine(graph=graph_for(), trials=[], source_head=OLD, registry=registry)
        self.assertEqual(r["skill_registry"]["root"], registry["registry_root"])
        self.assertEqual(r["skill_registry"]["status"],
                         "LOCAL_REGISTRY_DIGEST_MATCHED_NOT_ATTESTED")

    def test_forged_registry_root_denied(self):
        registry = {"skills": [], "registry_root": "f" * 64}
        with self.assertRaisesRegex(ValueError, "SKILL_REGISTRY_ROOT_MISMATCH"):
            compose_spine(graph=graph_for(), trials=[], source_head=OLD, registry=registry)

    def test_unsealed_registry_denied(self):
        with self.assertRaisesRegex(ValueError, "SKILL_REGISTRY_UNSEALED"):
            compose_spine(graph=graph_for(), trials=[], source_head=OLD,
                          registry={"skills": []})

    def test_hash_chain_checkpoint(self):
        lineage = AdaptiveLineage()
        lineage.append("EVIDENCE_RECORDED", "research", "T2", "T2",
                       "untrusted candidate, not a promotion", timestamp_ms=100)
        r = compose_spine(graph=graph_for(), trials=[], source_head=OLD, lineage=lineage)
        self.assertEqual(r["lineage"]["root"], lineage.terminal_hash())
        self.assertEqual(r["lineage"]["status"],
                         "LOCAL_HASH_CHAIN_CONSISTENT_NOT_AUTHENTICATED")
        self.assertEqual(len(lineage.events), 1)

    def test_corrupt_chain_denied(self):
        lineage = AdaptiveLineage()
        ev = lineage.append("EVIDENCE_RECORDED", "research", "T2", "T2",
                            "candidate", timestamp_ms=100)
        ev.evidence = "forged"
        with self.assertRaisesRegex(ValueError, "LINEAGE_HASH_CHAIN_INVALID"):
            compose_spine(graph=graph_for(), trials=[], source_head=OLD, lineage=lineage)

    def test_incorrect_lineage_type_denied(self):
        with self.assertRaisesRegex(ValueError, "LINEAGE_TYPE_INVALID"):
            compose_spine(graph=graph_for(), trials=[], source_head=OLD, lineage=[])

    def test_producer_does_not_mutate_sources(self):
        g = graph_for()
        trials = [positive_trial()]
        old_graph = copy.deepcopy(g)
        old_trials = copy.deepcopy(trials)
        compose_spine(graph=g, trials=trials, source_head=OLD)
        self.assertEqual(g, old_graph)
        self.assertEqual(trials, old_trials)

    def test_authority_probe_without_identity_fails_closed(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {}, clear=True):
            r = compose_spine(graph=graph_for(), trials=[], source_head=OLD,
                              check_authority=True)
        self.assertEqual(r["authority_observation"]["decision"], "DENIED")
        self.assertEqual(r["improvement_admission"], "DENIED")

    def test_bounded_json_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "large.json"
            p.write_bytes(b"x" * 1025)
            with self.assertRaisesRegex(ValueError, "CONTRACT_INPUT_TOO_LARGE"):
                _read_bounded(p, bound=1024)


if __name__ == "__main__":
    unittest.main()
