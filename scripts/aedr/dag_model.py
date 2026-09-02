#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, FrozenSet, Optional, Tuple


class AuthorityDomain(str, Enum):
    T0_FORMAL = "T0_FORMAL"
    T0_STRUCTURAL = "T0_STRUCTURAL"
    T1_HARDWARE_EVIDENCE = "T1_HARDWARE_EVIDENCE"
    SEMANTIC_LINEAGE_EVIDENCE = "SEMANTIC_LINEAGE_EVIDENCE"
    RUNTIME_EFFECT = "RUNTIME_EFFECT"
    GOVERNANCE_PERIMETER = "GOVERNANCE_PERIMETER"
    T1_DIAGNOSTIC = "T1_DIAGNOSTIC"
    RAW_PROVIDER_NONE = "RAW_PROVIDER_NONE"


class AncestryStatus(str, Enum):
    IDENTICAL = "identical"
    AHEAD = "ahead"
    BEHIND = "behind"
    DIVERGED = "diverged"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class GitAncestryRelation:
    """GitHub-style comparison of base_sha...head_sha."""

    base_sha: str
    head_sha: str
    merge_base_sha: str
    ahead_by: int
    behind_by: int
    status: AncestryStatus

    @property
    def is_diverged(self) -> bool:
        return self.status == AncestryStatus.DIVERGED or (
            self.ahead_by > 0 and self.behind_by > 0
        )

    @property
    def base_is_ancestor_of_head(self) -> bool:
        return self.status == AncestryStatus.IDENTICAL or (
            self.status == AncestryStatus.AHEAD
            and self.behind_by == 0
        )


@dataclass(frozen=True)
class EvidenceReceiptRef:
    receipt_id: str
    source_head_sha: str
    terminal_green: bool
    authority_class: str = "NONE"


@dataclass(frozen=True)
class PRNode:
    number: int
    head_sha: str
    base_sha: str
    base_ref: str
    draft: bool
    mergeable: str
    authority_domains: FrozenSet[AuthorityDomain]
    git_parents: Tuple[str, ...]
    semantic_dependencies: Tuple[int, ...]
    evidence_receipts: Tuple[EvidenceReceiptRef, ...]
    declared_parent_pr: Optional[int] = None
    body_references_head_sha: Optional[str] = None
    generated_only_drift: bool = False
    last_semantic_head_sha: Optional[str] = None


@dataclass(frozen=True)
class FalsificationSurface:
    source_head_sha: str
    required_behavior_ids: FrozenSet[str]
    required_falsifier_ids: FrozenSet[str]
    unique_non_generated_paths: FrozenSet[str]
    verified_behavior_ids: FrozenSet[str]
    verified_falsifier_ids: FrozenSet[str]
    assumption_debt_ids: FrozenSet[str]
    security_exposure_ids: FrozenSet[str]
    exact_head_receipt_green: bool
    semantic_surface_ids: FrozenSet[str] = frozenset()

    @property
    def internally_complete(self) -> bool:
        return (
            self.required_behavior_ids.issubset(self.verified_behavior_ids)
            and self.required_falsifier_ids.issubset(self.verified_falsifier_ids)
        )


@dataclass(frozen=True)
class GitLayerEdge:
    parent_sha: str
    child_sha: str


@dataclass(frozen=True)
class SemanticLayerEdge:
    prerequisite_pr: int
    dependent_pr: int
    relation: str


@dataclass(frozen=True)
class AuthorityLayerEdge:
    pr: int
    domain: AuthorityDomain


@dataclass(frozen=True)
class EvidenceLayerEdge:
    pr: int
    receipt: EvidenceReceiptRef


@dataclass(frozen=True)
class ConflictLayerEdge:
    pr_a: int
    pr_b: int
    classification: str


@dataclass(frozen=True)
class MultilayerDAGSnapshot:
    """Five orthogonal edge layers over one exact-head PR snapshot."""

    nodes: Tuple[PRNode, ...]
    git_edges: Tuple[GitLayerEdge, ...] = ()
    semantic_edges: Tuple[SemanticLayerEdge, ...] = ()
    authority_edges: Tuple[AuthorityLayerEdge, ...] = ()
    evidence_edges: Tuple[EvidenceLayerEdge, ...] = ()
    conflict_edges: Tuple[ConflictLayerEdge, ...] = ()


@dataclass
class MultilayerAnomalyReport:
    stale_parents: list[dict[str, Any]] = field(default_factory=list)
    divergent_overlaps: list[dict[str, Any]] = field(default_factory=list)
    missing_semantic_joins: list[dict[str, Any]] = field(default_factory=list)
    stale_body_provenance: list[dict[str, Any]] = field(default_factory=list)
    generated_head_drifts: list[dict[str, Any]] = field(default_factory=list)
    supersession_candidates: list[dict[str, Any]] = field(default_factory=list)
