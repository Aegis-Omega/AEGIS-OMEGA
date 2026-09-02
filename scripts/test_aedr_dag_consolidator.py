#!/usr/bin/env python3
"""Falsifier corpus for the AEGIS Evidence DAG Reactor."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import aedr_dag_consolidator as aedr


def node(number: int, head: str, base: str, *, domain: str = "") -> aedr.PRNode:
    return aedr.PRNode(
        number=number,
        head_sha=head,
        base_sha=base,
        base_ref="base",
        draft=True,
        mergeable="UNKNOWN",
        authority_domains=frozenset({domain}) if domain else frozenset(),
    )


class AEDRDAGFalsifierTests(unittest.TestCase):
    def test_363_364_sibling_split_is_missing_semantic_join(self) -> None:
        common = "7003e7b343fabf6a486e2fe5d5ecc393c077ebbd"
        hardened = node(363, "98e7ec038cb1e8a8722b5dcc3346a56d9da9801a", common, domain="DIAG")
        amps = node(364, "cc234e455015e104c70da6515c95e2a650dd6b46", common, domain="GOV")
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(hardened, amps),
            git_edges=(aedr.GitEdge(363, 364, aedr.AncestryRelation(
                base_sha=hardened.head_sha,
                head_sha=amps.head_sha,
                merge_base_sha=common,
                ahead_by=3,
                behind_by=7,
                status="diverged",
            )),),
            semantic_edges=(aedr.SemanticEdge(364, 363, "GOVERNS_HARDENED_MPVC", True),),
        )
        self.assertIn("MISSING_SEMANTIC_JOIN", {x.code for x in aedr.analyze_snapshot(snapshot)})

    def test_stale_parent_requires_non_ancestral_current_parent(self) -> None:
        parent = node(354, "f481f189019f5ff130331dcabc1eded504f834e2", "x" * 40, domain="MHP")
        child = aedr.PRNode(
            number=356,
            head_sha="5bf54f67d43fcbb6de2e89b0afa7945d7d4cb475",
            base_sha="b7ed712bfa54d0ffca9803344f8ffc7e7bfaeef2",
            base_ref="feat/mhp1-transitive-composition-v1",
            draft=True,
            mergeable="UNKNOWN",
            authority_domains=frozenset({"MHP"}),
        )
        bad = aedr.AncestryRelation(parent.head_sha, child.head_sha, child.base_sha, 7, 5, "diverged")
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(parent, child),
            git_edges=(aedr.GitEdge(354, 356, bad),),
            stack_edges=((356, 354),),
        )
        self.assertIn("STALE_PARENT", {x.code for x in aedr.analyze_snapshot(snapshot)})

        good = aedr.AncestryRelation(parent.head_sha, child.head_sha, parent.head_sha, 2, 0, "ahead")
        snapshot = aedr.RepositorySnapshot(
            repository=snapshot.repository,
            main_sha=snapshot.main_sha,
            nodes=snapshot.nodes,
            git_edges=(aedr.GitEdge(354, 356, good),),
            stack_edges=snapshot.stack_edges,
        )
        self.assertNotIn("STALE_PARENT", {x.code for x in aedr.analyze_snapshot(snapshot)})

    def test_309_334_divergence_never_auto_supersedes(self) -> None:
        old = node(309, "1" * 40, "a" * 40, domain="RUNTIME")
        new = node(334, "2" * 40, "a" * 40, domain="RUNTIME")
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(old, new),
            git_edges=(aedr.GitEdge(309, 334, aedr.AncestryRelation(
                old.head_sha, new.head_sha, "a" * 40, 71, 69, "diverged"
            )),),
            conflict_edges=(aedr.ConflictEdge(309, 334, "OVERLAP"),),
        )
        matching = [x for x in aedr.analyze_snapshot(snapshot) if x.code == "DIVERGENT_OVERLAP"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].proposed_action, "PROPOSE_SUPERSESSION_REVIEW")

    def _sufficient_supersession(self):
        replaced = node(1, "1" * 40, "0" * 40, domain="RUNTIME")
        candidate = node(2, "2" * 40, "0" * 40, domain="RUNTIME")
        evidence = aedr.SupersessionEvidence(
            candidate_pr=2,
            replaced_pr=1,
            required_behavior_replaced=frozenset({"effect-chain"}),
            verified_behavior_candidate=frozenset({"effect-chain", "replay"}),
            required_falsifiers_replaced=frozenset({"anti-splice"}),
            verified_falsifiers_candidate=frozenset({"anti-splice"}),
            unique_files_replaced=frozenset({"legacy_test.py", "plan.md"}),
            file_dispositions=(
                aedr.FileDisposition("legacy_test.py", "BYTE_EQUIVALENT"),
                aedr.FileDisposition("plan.md", "OPEN_OBLIGATION"),
            ),
            assumptions_candidate=frozenset(),
            assumptions_replaced=frozenset({"A"}),
            security_exposure_candidate=0,
            security_exposure_replaced=1,
            no_authority_widening=True,
            dominance_receipt=aedr.DominanceReceipt(
                "run:green", candidate.head_sha, replaced.head_sha, "SUCCESS"
            ),
        )
        return candidate, replaced, evidence

    def test_supersession_contract_is_conjunctive(self) -> None:
        candidate, replaced, sufficient = self._sufficient_supersession()
        self.assertTrue(aedr.evaluate_supersession(candidate, replaced, sufficient).established)
        regressed = aedr.SupersessionEvidence(**{
            **sufficient.__dict__,
            "assumptions_candidate": frozenset({"A", "B"}),
        })
        decision = aedr.evaluate_supersession(candidate, replaced, regressed)
        self.assertFalse(decision.established)
        self.assertIn("assumption_regression", decision.failed_conditions)

    def test_stale_dominance_receipt_cannot_establish_supersession(self) -> None:
        candidate, replaced, sufficient = self._sufficient_supersession()
        stale = aedr.SupersessionEvidence(**{
            **sufficient.__dict__,
            "dominance_receipt": aedr.DominanceReceipt(
                "run:old", "f" * 40, replaced.head_sha, "SUCCESS"
            ),
        })
        decision = aedr.evaluate_supersession(candidate, replaced, stale)
        self.assertFalse(decision.established)
        self.assertIn("dominance_receipt_candidate_head_mismatch", decision.failed_conditions)

    def test_semantic_replacement_requires_receipt(self) -> None:
        candidate, replaced, sufficient = self._sufficient_supersession()
        broken = aedr.SupersessionEvidence(**{
            **sufficient.__dict__,
            "file_dispositions": (
                aedr.FileDisposition("legacy_test.py", "SEMANTIC_REPLACEMENT"),
                aedr.FileDisposition("plan.md", "OPEN_OBLIGATION"),
            ),
        })
        decision = aedr.evaluate_supersession(candidate, replaced, broken)
        self.assertFalse(decision.established)
        self.assertIn("semantic_replacement_without_receipt:legacy_test.py", decision.failed_conditions)

    def test_generated_only_head_drift_invalidates_binding_without_semantic_claim(self) -> None:
        pr = node(365, "b" * 40, "a" * 40, domain="MODEL")
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(pr,),
            head_deltas=(aedr.HeadDelta(365, "c" * 40, pr.head_sha, (".claude.json",)),),
            generated_paths=frozenset({".claude.json"}),
        )
        self.assertIn("GENERATED_ONLY_HEAD_DRIFT", {x.code for x in aedr.analyze_snapshot(snapshot)})

    def test_stale_evidence_binding_is_not_current_green(self) -> None:
        pr = node(10, "b" * 40, "a" * 40, domain="FORMAL")
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(pr,),
            evidence_edges=(aedr.EvidenceEdge(10, "c" * 40, "run:1", "SUCCESS"),),
        )
        codes = {x.code for x in aedr.analyze_snapshot(snapshot)}
        self.assertIn("STALE_EVIDENCE_BINDING", codes)
        self.assertIn("MISSING_CURRENT_HEAD_GREEN_RECEIPT", codes)

    def test_unbound_allowed_authority_transfer_is_rejected(self) -> None:
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(node(1, "1" * 40, "0" * 40), node(2, "2" * 40, "0" * 40)),
            authority_edges=(aedr.AuthorityEdge(1, 2, "FORMAL", True, ""),),
        )
        self.assertIn("UNBOUND_AUTHORITY_TRANSFER", {x.code for x in aedr.analyze_snapshot(snapshot)})

    def test_receipt_is_deterministic_authority_none_and_propose_only(self) -> None:
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(),
            census_scope="REGRESSION_SUBGRAPH",
        )
        first = aedr.build_receipt(snapshot, ())
        second = aedr.build_receipt(snapshot, ())
        self.assertEqual(first, second)
        self.assertEqual(first["authority"], "NONE")
        self.assertEqual(first["mutation_authority"], "NONE")
        self.assertEqual(first["signature"]["state"], "NOT_ESTABLISHED")
        self.assertEqual(first["snapshot"]["census"]["scope"], "REGRESSION_SUBGRAPH")
        aedr.validate_receipt(first)

    def test_validate_receipt_rejects_non_propose_action(self) -> None:
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(),
        )
        receipt = aedr.build_receipt(snapshot, ())
        receipt["recommended_actions"] = ["CLOSE_SUPERSEDED"]
        body = dict(receipt)
        body.pop("receipt_sha256")
        receipt["receipt_sha256"] = aedr.sha256_json(body)
        with self.assertRaisesRegex(ValueError, "only PROPOSE"):
            aedr.validate_receipt(receipt)

    def test_snapshot_roundtrip_keeps_five_edge_namespaces_separate(self) -> None:
        original = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(
                aedr.PRNode(7, "b" * 40, "a" * 40, "main", False, "UNKNOWN", frozenset({"FORMAL"}), ("a" * 40,), (3,), ("run:1",)),
                node(3, "c" * 40, "a" * 40),
            ),
            git_edges=(aedr.GitEdge(3, 7, aedr.AncestryRelation("c" * 40, "b" * 40, "a" * 40, 1, 1, "diverged")),),
            semantic_edges=(aedr.SemanticEdge(7, 3),),
            authority_edges=(aedr.AuthorityEdge(3, 7, "FORMAL", False),),
            evidence_edges=(aedr.EvidenceEdge(7, "b" * 40, "run:1", "SUCCESS"),),
            conflict_edges=(aedr.ConflictEdge(3, 7, "OVERLAP"),),
            census_scope="REGRESSION_SUBGRAPH",
            open_pr_count=2,
            draft_pr_count=1,
            nondraft_pr_count=1,
        )
        rebuilt = aedr.snapshot_from_json(aedr.snapshot_payload(original))
        rebuilt_nodes = {item.number: item for item in rebuilt.nodes}
        self.assertEqual(rebuilt_nodes[7].git_parents, ("a" * 40,))
        self.assertEqual(rebuilt_nodes[7].semantic_dependencies, (3,))
        self.assertEqual(len(rebuilt.git_edges), 1)
        self.assertEqual(len(rebuilt.semantic_edges), 1)
        self.assertEqual(len(rebuilt.authority_edges), 1)
        self.assertEqual(len(rebuilt.evidence_edges), 1)
        self.assertEqual(len(rebuilt.conflict_edges), 1)
        self.assertFalse(hasattr(rebuilt_nodes[7], "lineage_tag"))

    def test_cli_fixture_writes_valid_content_addressed_receipt(self) -> None:
        payload = {
            "repository": "Aegis-Omega/AEGIS-OMEGA",
            "main_sha": "a" * 40,
            "nodes": [],
            "edges": {"E_git": [], "E_sem": [], "E_auth": [], "E_evidence": [], "E_conflict": []},
            "census": {"scope": "REGRESSION_SUBGRAPH", "open": 0, "draft": 0, "non_draft": 0},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "snapshot.json", root / "receipt.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(aedr.main(["--snapshot", str(source), "--output", str(output)]), 0)
            aedr.validate_receipt(json.loads(output.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
