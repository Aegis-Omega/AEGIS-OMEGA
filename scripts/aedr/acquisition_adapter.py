#!/usr/bin/env python3
from __future__ import annotations

from typing import Dict, Optional, Tuple

from .acquisition_types import MultilayerDAGSnapshot
from .dag_evaluator import MultilayerDAGEvaluator
from .dag_model import (
    AncestryStatus,
    AuthorityDomain,
    EvidenceReceiptRef,
    FalsificationSurface,
    GitAncestryRelation,
    PRNode,
)


def label_to_authority_domains(labels: list[str]) -> frozenset[AuthorityDomain]:
    mapping = {
        "domain:formal": AuthorityDomain.T0_FORMAL,
        "domain:structural": AuthorityDomain.T0_STRUCTURAL,
        "domain:mhp": AuthorityDomain.SEMANTIC_LINEAGE_EVIDENCE,
        "domain:runtime": AuthorityDomain.RUNTIME_EFFECT,
        "domain:governance": AuthorityDomain.GOVERNANCE_PERIMETER,
        "domain:diagnostic": AuthorityDomain.T1_DIAGNOSTIC,
        "domain:hardware-evidence": AuthorityDomain.T1_HARDWARE_EVIDENCE,
    }
    domains = {mapping[label] for label in labels if label in mapping}
    return frozenset(domains) if domains else frozenset([AuthorityDomain.RAW_PROVIDER_NONE])


def _body_head_reference(cited: str | None, actual_head: str) -> str | None:
    if cited is None:
        return None
    normalized = cited.lower()
    actual = actual_head.lower()
    # A short Git SHA citation that unambiguously prefixes the live head is not stale.
    return actual if len(normalized) >= 7 and actual.startswith(normalized) else normalized


def snapshot_to_evaluator(snapshot: MultilayerDAGSnapshot) -> MultilayerDAGEvaluator:
    nodes: Dict[int, PRNode] = {}
    ancestry_lookup: Dict[Tuple[str, str], GitAncestryRelation] = {}

    for raw in snapshot.nodes:
        exact_head = str(raw["head_sha"]).lower()
        receipts = []
        for receipt in raw.get("workflow_receipts", []):
            receipt_head = str(receipt["head_sha"]).lower()
            if receipt_head != exact_head:
                continue
            receipts.append(
                EvidenceReceiptRef(
                    receipt_id=f"github-actions-run:{int(receipt['run_id'])}",
                    source_head_sha=receipt_head,
                    terminal_green=str(receipt["conclusion"]) == "success",
                    authority_class="NONE",
                )
            )

        labels = [str(label) for label in raw.get("labels", [])]
        cited = raw.get("cited_head_sha")
        nodes[int(raw["number"])] = PRNode(
            number=int(raw["number"]),
            head_sha=exact_head,
            base_sha=str(raw["base_sha"]).lower(),
            base_ref=str(raw["base_ref"]),
            draft=bool(raw["draft"]),
            mergeable=str(raw["mergeable_state"]),
            authority_domains=label_to_authority_domains(labels),
            # Acquisition has not fetched the commit object's immediate parents;
            # base_sha is not silently re-labeled as a git parent.
            git_parents=(),
            semantic_dependencies=tuple(int(value) for value in raw.get("semantic_dependencies", [])),
            evidence_receipts=tuple(receipts),
            declared_parent_pr=(
                int(raw["declared_parent_pr"])
                if raw.get("declared_parent_pr") is not None
                else None
            ),
            body_references_head_sha=_body_head_reference(
                str(cited) if cited is not None else None,
                exact_head,
            ),
        )

    for edge in snapshot.ancestry_matrix:
        try:
            status = AncestryStatus(str(edge["status"]))
        except ValueError:
            status = AncestryStatus.UNKNOWN
        relation = GitAncestryRelation(
            base_sha=str(edge["base_sha"]).lower(),
            head_sha=str(edge["head_sha"]).lower(),
            merge_base_sha=str(edge["merge_base_sha"]).lower(),
            ahead_by=int(edge["ahead_by"]),
            behind_by=int(edge["behind_by"]),
            status=status,
        )
        ancestry_lookup[(relation.base_sha, relation.head_sha)] = relation

    def snapshot_ancestry_oracle(base_sha: str, head_sha: str) -> GitAncestryRelation:
        relation = ancestry_lookup.get((base_sha.lower(), head_sha.lower()))
        if relation is not None:
            return relation
        # Missing relation is UNKNOWN, never inferred from base refs or mergeability.
        return GitAncestryRelation(
            base_sha=base_sha.lower(),
            head_sha=head_sha.lower(),
            merge_base_sha="",
            ahead_by=-1,
            behind_by=-1,
            status=AncestryStatus.UNKNOWN,
        )

    def snapshot_surface_oracle(pr: int) -> Optional[FalsificationSurface]:
        # A workflow SUCCESS bit is evidence about a run, not a complete
        # falsification surface. Surface admission requires a separate
        # authenticated acquisition slice.
        return None

    return MultilayerDAGEvaluator(nodes, snapshot_ancestry_oracle, snapshot_surface_oracle)
