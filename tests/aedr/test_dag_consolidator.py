#!/usr/bin/env python3
from __future__ import annotations

from scripts.aedr.dag_model import (
    AncestryStatus,
    AuthorityDomain,
    EvidenceReceiptRef,
    FalsificationSurface,
    GitAncestryRelation,
    PRNode,
)
from scripts.aedr.dag_evaluator import MultilayerDAGEvaluator


def _receipt(pr: int, head: str) -> EvidenceReceiptRef:
    return EvidenceReceiptRef(
        receipt_id=f"receipt-{pr}",
        source_head_sha=head,
        terminal_green=True,
        authority_class="NONE",
    )


def test_divergent_overlap_not_superseded():
    nodes = {
        309: PRNode(
            number=309,
            head_sha="a" * 40,
            base_sha="0" * 40,
            base_ref="main",
            draft=True,
            mergeable="MERGEABLE",
            authority_domains=frozenset([AuthorityDomain.RUNTIME_EFFECT]),
            git_parents=("0" * 40,),
            semantic_dependencies=(),
            evidence_receipts=(_receipt(309, "a" * 40),),
        ),
        334: PRNode(
            number=334,
            head_sha="b" * 40,
            base_sha="0" * 40,
            base_ref="main",
            draft=True,
            mergeable="MERGEABLE",
            authority_domains=frozenset([AuthorityDomain.RUNTIME_EFFECT]),
            git_parents=("0" * 40,),
            semantic_dependencies=(),
            evidence_receipts=(_receipt(334, "b" * 40),),
        ),
    }

    def fake_ancestry(base_sha: str, head_sha: str) -> GitAncestryRelation:
        return GitAncestryRelation(
            base_sha=base_sha,
            head_sha=head_sha,
            merge_base_sha="0" * 40,
            ahead_by=71,
            behind_by=69,
            status=AncestryStatus.DIVERGED,
        )

    def fake_surfaces(pr: int):
        if pr == 309:
            return FalsificationSurface(
                source_head_sha="a" * 40,
                required_behavior_ids=frozenset(["b1", "b2"]),
                required_falsifier_ids=frozenset(["f1"]),
                unique_non_generated_paths=frozenset(["runtime/legacy_spec.ts"]),
                verified_behavior_ids=frozenset(["b1", "b2"]),
                verified_falsifier_ids=frozenset(["f1"]),
                assumption_debt_ids=frozenset(),
                security_exposure_ids=frozenset(),
                exact_head_receipt_green=True,
            )
        return FalsificationSurface(
            source_head_sha="b" * 40,
            required_behavior_ids=frozenset(["b1", "b3"]),
            required_falsifier_ids=frozenset(["f1", "f2"]),
            unique_non_generated_paths=frozenset(["runtime/effect_v2.ts"]),
            verified_behavior_ids=frozenset(["b1", "b3"]),
            verified_falsifier_ids=frozenset(["f1", "f2"]),
            assumption_debt_ids=frozenset(),
            security_exposure_ids=frozenset(),
            exact_head_receipt_green=True,
        )

    report = MultilayerDAGEvaluator(nodes, fake_ancestry, fake_surfaces).analyze_anomalies()
    assert report.supersession_candidates == []
    assert len(report.divergent_overlaps) == 1
    assert report.divergent_overlaps[0]["classification"] == "DIVERGENT_OVERLAPPING_LINEAGES"


def test_detects_semantic_dependency_without_git_integration():
    base_sha = "7" * 40
    nodes = {
        363: PRNode(
            number=363,
            head_sha="3" * 40,
            base_sha=base_sha,
            base_ref="experimental/quantum-tourbillon-mpvc-v1",
            draft=True,
            mergeable="MERGEABLE",
            authority_domains=frozenset([AuthorityDomain.T1_DIAGNOSTIC]),
            git_parents=(base_sha,),
            semantic_dependencies=(),
            evidence_receipts=(),
        ),
        364: PRNode(
            number=364,
            head_sha="4" * 40,
            base_sha="8" * 40,  # generated/bot drift must not hide missing semantic integration
            base_ref="experimental/quantum-tourbillon-mpvc-v1",
            draft=True,
            mergeable="MERGEABLE",
            authority_domains=frozenset([AuthorityDomain.GOVERNANCE_PERIMETER]),
            git_parents=("8" * 40,),
            semantic_dependencies=(363,),
            evidence_receipts=(),
        ),
    }

    def fake_ancestry(base: str, head: str) -> GitAncestryRelation:
        return GitAncestryRelation(
            base_sha=base,
            head_sha=head,
            merge_base_sha=base_sha,
            ahead_by=1,
            behind_by=1,
            status=AncestryStatus.DIVERGED,
        )

    report = MultilayerDAGEvaluator(nodes, fake_ancestry, lambda _: None).analyze_anomalies()
    assert len(report.missing_semantic_joins) == 1
    assert report.missing_semantic_joins[0]["pr_pair"] == (363, 364)


def test_stale_parent_detection_on_mhp():
    nodes = {
        354: PRNode(
            number=354,
            head_sha="f" * 40,
            base_sha="6" * 40,
            base_ref="main",
            draft=True,
            mergeable="MERGEABLE",
            authority_domains=frozenset([AuthorityDomain.SEMANTIC_LINEAGE_EVIDENCE]),
            git_parents=("6" * 40,),
            semantic_dependencies=(),
            evidence_receipts=(),
        ),
        356: PRNode(
            number=356,
            head_sha="5" * 40,
            base_sha="b" * 40,
            base_ref="main",
            draft=True,
            mergeable="MERGEABLE",
            authority_domains=frozenset([AuthorityDomain.SEMANTIC_LINEAGE_EVIDENCE]),
            git_parents=("b" * 40,),
            semantic_dependencies=(354,),
            evidence_receipts=(),
            declared_parent_pr=354,
        ),
    }

    def fake_ancestry(base: str, head: str) -> GitAncestryRelation:
        return GitAncestryRelation(
            base_sha=base,
            head_sha=head,
            merge_base_sha="b" * 40,
            ahead_by=2,
            behind_by=3,
            status=AncestryStatus.DIVERGED,
        )

    report = MultilayerDAGEvaluator(nodes, fake_ancestry, lambda _: None).analyze_anomalies()
    assert len(report.stale_parents) == 1
    assert report.stale_parents[0]["pr"] == 356
    assert report.stale_parents[0]["declared_parent_pr"] == 354


def test_parent_head_is_accepted_only_when_parent_is_ancestor_of_child():
    relation = GitAncestryRelation(
        base_sha="a" * 40,
        head_sha="b" * 40,
        merge_base_sha="a" * 40,
        ahead_by=3,
        behind_by=0,
        status=AncestryStatus.AHEAD,
    )
    assert relation.base_is_ancestor_of_head


def test_stale_green_surface_cannot_assert_supersession():
    nodes = {
        1: PRNode(1, "1" * 40, "0" * 40, "main", True, "MERGEABLE", frozenset([AuthorityDomain.T0_STRUCTURAL]), ("0" * 40,), (), (_receipt(1, "1" * 40),)),
        2: PRNode(2, "2" * 40, "0" * 40, "main", True, "MERGEABLE", frozenset([AuthorityDomain.T0_STRUCTURAL]), ("0" * 40,), (), (_receipt(2, "2" * 40),)),
    }
    stale = FalsificationSurface(
        source_head_sha="9" * 40,
        required_behavior_ids=frozenset(["b"]),
        required_falsifier_ids=frozenset(["f"]),
        unique_non_generated_paths=frozenset(["x"]),
        verified_behavior_ids=frozenset(["b"]),
        verified_falsifier_ids=frozenset(["f"]),
        assumption_debt_ids=frozenset(),
        security_exposure_ids=frozenset(),
        exact_head_receipt_green=True,
    )
    current = FalsificationSurface(
        source_head_sha="2" * 40,
        required_behavior_ids=frozenset(["b"]),
        required_falsifier_ids=frozenset(["f"]),
        unique_non_generated_paths=frozenset(["x"]),
        verified_behavior_ids=frozenset(["b"]),
        verified_falsifier_ids=frozenset(["f"]),
        assumption_debt_ids=frozenset(),
        security_exposure_ids=frozenset(),
        exact_head_receipt_green=True,
    )
    evaluator = MultilayerDAGEvaluator(nodes, lambda a, b: GitAncestryRelation(a, b, "0" * 40, 1, 1, AncestryStatus.DIVERGED), lambda pr: stale if pr == 1 else current)
    assert evaluator.evaluate_supersedes(1, 2) == (False, "ASSERTING_SURFACE_HEAD_MISMATCH")


def test_advisory_receipt_is_deterministic_content_addressed_and_non_authoritative():
    evaluator = MultilayerDAGEvaluator({}, lambda a, b: None, lambda _: None)  # ancestry oracle is never called
    report = evaluator.analyze_anomalies()
    r1 = evaluator.generate_advisory_receipt(report, global_main_sha="a" * 40)
    r2 = evaluator.generate_advisory_receipt(report, global_main_sha="a" * 40)
    assert r1 == r2
    assert r1["payload"]["authority_class"] == "NONE"
    assert r1["payload"]["execution_mode"] == "ADVISORY_PROPOSAL_ONLY"
    assert r1["signature_status"] == "UNSIGNED_CONTENT_ADDRESSED"
