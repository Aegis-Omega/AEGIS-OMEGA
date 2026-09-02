#!/usr/bin/env python3
"""Falsifier corpus for the AEGIS Evidence DAG Reactor."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import aedr_dag_consolidator as aedr


def node(
    number: int,
    head: str,
    base: str,
    *,
    domain: str = "",
    receipts: tuple[str, ...] = ("receipt",),
) -> aedr.PRNode:
    return aedr.PRNode(
        number=number,
        head_sha=head,
        base_sha=base,
        base_ref="base",
        draft=True,
        mergeable="UNKNOWN",
        authority_domains=frozenset({domain}) if domain else frozenset(),
        evidence_receipts=receipts if domain else (),
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
            ancestry=(aedr.PairAncestry(
                363,
                364,
                aedr.AncestryRelation(
                    base_sha=hardened.head_sha,
                    head_sha=amps.head_sha,
                    merge_base_sha=common,
                    ahead_by=3,
                    behind_by=7,
                    status="diverged",
                ),
            ),),
            semantic_edges=((364, 363),),
        )
        anomalies = aedr.analyze_snapshot(snapshot)
        self.assertIn("MISSING_SEMANTIC_JOIN", {item.code for item in anomalies})

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
            evidence_receipts=("red-first",),
        )
        relation = aedr.AncestryRelation(
            base_sha=parent.head_sha,
            head_sha=child.head_sha,
            merge_base_sha=child.base_sha,
            ahead_by=7,
            behind_by=5,
            status="diverged",
        )
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(parent, child),
            ancestry=(aedr.PairAncestry(354, 356, relation),),
            stack_edges=((356, 354),),
        )
        anomalies = aedr.analyze_snapshot(snapshot)
        self.assertIn("STALE_PARENT", {item.code for item in anomalies})

        # A base SHA mismatch alone is insufficient if current parent is already
        # an ancestor of the child.
        good_relation = aedr.AncestryRelation(
            base_sha=parent.head_sha,
            head_sha=child.head_sha,
            merge_base_sha=parent.head_sha,
            ahead_by=2,
            behind_by=0,
            status="ahead",
        )
        good_snapshot = aedr.RepositorySnapshot(
            repository=snapshot.repository,
            main_sha=snapshot.main_sha,
            nodes=snapshot.nodes,
            ancestry=(aedr.PairAncestry(354, 356, good_relation),),
            stack_edges=snapshot.stack_edges,
        )
        self.assertNotIn(
            "STALE_PARENT",
            {item.code for item in aedr.analyze_snapshot(good_snapshot)},
        )

    def test_309_334_divergence_never_auto_supersedes(self) -> None:
        old = node(309, "1406aacca95fef02a942621a7060e0b6b14a5809", "a" * 40, domain="RUNTIME")
        new = node(334, "65f97558615c848c46239706a019c3478bea5a87", "a" * 40, domain="RUNTIME")
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(old, new),
            ancestry=(aedr.PairAncestry(
                309, 334,
                aedr.AncestryRelation(
                    base_sha=old.head_sha,
                    head_sha=new.head_sha,
                    merge_base_sha="a" * 40,
                    ahead_by=71,
                    behind_by=69,
                    status="diverged",
                ),
            ),),
            overlap_pairs=((309, 334),),
        )
        anomalies = aedr.analyze_snapshot(snapshot)
        matching = [item for item in anomalies if item.code == "DIVERGENT_OVERLAP"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].proposed_action, "PROPOSE_SUPERSESSION_REVIEW")

    def test_supersession_contract_is_conjunctive(self) -> None:
        replaced = node(1, "1" * 40, "0" * 40, domain="RUNTIME")
        candidate = node(2, "2" * 40, "0" * 40, domain="RUNTIME")
        insufficient = aedr.SupersessionEvidence(
            candidate_pr=2,
            replaced_pr=1,
            required_behavior_replaced=frozenset({"effect-chain"}),
            verified_behavior_candidate=frozenset({"effect-chain"}),
            required_falsifiers_replaced=frozenset({"anti-splice"}),
            verified_falsifiers_candidate=frozenset({"anti-splice"}),
            unique_files_disposition_complete=True,
            assumptions_candidate=frozenset({"A"}),
            assumptions_replaced=frozenset(),
            security_exposure_candidate=0,
            security_exposure_replaced=0,
            no_authority_widening=True,
            exact_head_green_dominance_receipt="run:green",
        )
        decision = aedr.evaluate_supersession(candidate, replaced, insufficient)
        self.assertFalse(decision.established)
        self.assertIn("assumption_regression", decision.failed_conditions)

        sufficient = aedr.SupersessionEvidence(
            **{
                **insufficient.__dict__,
                "assumptions_candidate": frozenset(),
            }
        )
        self.assertTrue(
            aedr.evaluate_supersession(candidate, replaced, sufficient).established
        )

    def test_generated_only_head_drift_invalidates_binding_without_semantic_claim(self) -> None:
        pr = node(365, "b" * 40, "a" * 40, domain="MODEL")
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(pr,),
            head_deltas=(aedr.HeadDelta(365, "c" * 40, pr.head_sha, (".claude.json",)),),
            generated_paths=frozenset({".claude.json"}),
        )
        anomalies = aedr.analyze_snapshot(snapshot)
        codes = {item.code for item in anomalies}
        self.assertIn("GENERATED_ONLY_HEAD_DRIFT", codes)

    def test_receipt_is_deterministic_authority_none_and_propose_only(self) -> None:
        snapshot = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(),
            open_pr_count=0,
            draft_pr_count=0,
            nondraft_pr_count=0,
        )
        first = aedr.build_receipt(snapshot, ())
        second = aedr.build_receipt(snapshot, ())
        self.assertEqual(first, second)
        self.assertEqual(first["authority"], "NONE")
        self.assertEqual(first["mutation_authority"], "NONE")
        self.assertEqual(first["signature"]["state"], "NOT_ESTABLISHED")
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

    def test_snapshot_roundtrip_keeps_relation_types_separate(self) -> None:
        original = aedr.RepositorySnapshot(
            repository="Aegis-Omega/AEGIS-OMEGA",
            main_sha="a" * 40,
            nodes=(aedr.PRNode(
                number=7,
                head_sha="b" * 40,
                base_sha="a" * 40,
                base_ref="main",
                draft=False,
                mergeable="UNKNOWN",
                authority_domains=frozenset({"FORMAL"}),
                git_parents=("a" * 40,),
                semantic_dependencies=(3,),
                evidence_receipts=("run:1",),
            ),),
            semantic_edges=((7, 3),),
            open_pr_count=1,
            nondraft_pr_count=1,
        )
        payload = aedr.snapshot_payload(original)
        rebuilt = aedr.snapshot_from_json(payload)
        self.assertEqual(rebuilt.nodes[0].git_parents, ("a" * 40,))
        self.assertEqual(rebuilt.nodes[0].semantic_dependencies, (3,))
        self.assertFalse(hasattr(rebuilt.nodes[0], "lineage_tag"))

    def test_cli_fixture_writes_valid_content_addressed_receipt(self) -> None:
        payload = {
            "repository": "Aegis-Omega/AEGIS-OMEGA",
            "main_sha": "a" * 40,
            "nodes": [],
            "ancestry": [],
            "census": {"open": 0, "draft": 0, "non_draft": 0},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "snapshot.json"
            output = root / "receipt.json"
            source.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(
                aedr.main(["--snapshot", str(source), "--output", str(output)]),
                0,
            )
            receipt = json.loads(output.read_text(encoding="utf-8"))
            aedr.validate_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
