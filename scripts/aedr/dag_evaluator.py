#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from typing import Callable, Dict, Optional, Tuple

from .dag_model import FalsificationSurface, GitAncestryRelation, MultilayerAnomalyReport, PRNode


class MultilayerDAGEvaluator:
    POLICY_VERSION = "AEDR-DAG-POLICY-V1"
    RECEIPT_VERSION = "AEDR-DAG-RECEIPT-V1"

    def __init__(
        self,
        nodes: Dict[int, PRNode],
        ancestry_oracle: Callable[[str, str], GitAncestryRelation],
        surface_oracle: Callable[[int], Optional[FalsificationSurface]],
    ):
        self.nodes = dict(nodes)
        self.ancestry_oracle = ancestry_oracle
        self.surface_oracle = surface_oracle
        self._ancestry_cache: dict[tuple[str, str], GitAncestryRelation] = {}
        self._surface_cache: dict[int, Optional[FalsificationSurface]] = {}

    def _ancestry(self, base_sha: str, head_sha: str) -> GitAncestryRelation:
        key = (base_sha, head_sha)
        if key not in self._ancestry_cache:
            self._ancestry_cache[key] = self.ancestry_oracle(base_sha, head_sha)
        return self._ancestry_cache[key]

    def _surface(self, pr: int) -> Optional[FalsificationSurface]:
        if pr not in self._surface_cache:
            self._surface_cache[pr] = self.surface_oracle(pr)
        return self._surface_cache[pr]

    def evaluate_supersedes(self, pr_a: int, pr_b: int) -> Tuple[bool, str]:
        node_a = self.nodes.get(pr_a)
        node_b = self.nodes.get(pr_b)
        if not node_a or not node_b:
            return False, "NODE_NOT_FOUND"

        # V1 stays conservative: a domain-superset rule would require a
        # separately verified authority-refinement proof.
        if node_a.authority_domains != node_b.authority_domains:
            return False, "AUTHORITY_DOMAIN_MISMATCH"

        surf_a = self._surface(pr_a)
        surf_b = self._surface(pr_b)
        if not surf_a or not surf_b:
            return False, "MISSING_FALSIFICATION_SURFACE"

        if surf_a.source_head_sha != node_a.head_sha:
            return False, "ASSERTING_SURFACE_HEAD_MISMATCH"
        if surf_b.source_head_sha != node_b.head_sha:
            return False, "SUPERSEDED_SURFACE_HEAD_MISMATCH"

        bound_green_receipt = any(
            receipt.terminal_green and receipt.source_head_sha == node_a.head_sha
            for receipt in node_a.evidence_receipts
        )
        if not surf_a.exact_head_receipt_green or not bound_green_receipt:
            return False, "ASSERTING_NODE_LACKS_GREEN_HEAD_RECEIPT"

        if not surf_a.internally_complete:
            return False, "ASSERTING_SURFACE_INCOMPLETE"

        if not surf_b.required_behavior_ids.issubset(surf_a.verified_behavior_ids):
            return False, "BEHAVIOR_COVERAGE_DEFICIT"
        if not surf_b.required_falsifier_ids.issubset(surf_a.verified_falsifier_ids):
            return False, "FALSIFIER_COVERAGE_DEFICIT"
        if not surf_b.unique_non_generated_paths.issubset(surf_a.unique_non_generated_paths):
            return False, "SURFACE_DROPPED_WITHOUT_RECEIPT"

        # Debt is identity-aware, not count-only: replacing one assumption or
        # security finding with another at the same count is still regression.
        if not surf_a.assumption_debt_ids.issubset(surf_b.assumption_debt_ids):
            return False, "ASSUMPTION_DEBT_REGRESSION"
        if not surf_a.security_exposure_ids.issubset(surf_b.security_exposure_ids):
            return False, "SECURITY_EXPOSURE_REGRESSION"

        return True, "DOMINANCE_VERIFIED"

    def analyze_anomalies(self) -> MultilayerAnomalyReport:
        report = MultilayerAnomalyReport()

        for pr_num, node in sorted(self.nodes.items()):
            if node.body_references_head_sha and node.body_references_head_sha != node.head_sha:
                report.stale_body_provenance.append(
                    {"pr": pr_num, "body_sha": node.body_references_head_sha, "actual_head_sha": node.head_sha}
                )

            if node.generated_only_drift:
                report.generated_head_drifts.append(
                    {
                        "pr": pr_num,
                        "actual_head_sha": node.head_sha,
                        "last_semantic_head_sha": node.last_semantic_head_sha,
                        "classification": "GENERATED_ONLY_HEAD_DRIFT",
                    }
                )

            if node.declared_parent_pr:
                parent_node = self.nodes.get(node.declared_parent_pr)
                if parent_node:
                    # Oracle semantics are GitHub compare parent...child.
                    ancestry = self._ancestry(parent_node.head_sha, node.head_sha)
                    if not ancestry.base_is_ancestor_of_head:
                        report.stale_parents.append(
                            {
                                "pr": pr_num,
                                "declared_parent_pr": node.declared_parent_pr,
                                "expected_parent_head": parent_node.head_sha,
                                "merge_base": ancestry.merge_base_sha,
                                "ahead_by": ancestry.ahead_by,
                                "behind_by": ancestry.behind_by,
                                "status": ancestry.status.value,
                            }
                        )

        # E_sem is independent of exact base identity. Generated/bot commits can
        # move a base without satisfying a semantic dependency.
        seen_semantic_pairs: set[tuple[int, int]] = set()
        for dependent_num, dependent in sorted(self.nodes.items()):
            for prerequisite_num in sorted(set(dependent.semantic_dependencies)):
                prerequisite = self.nodes.get(prerequisite_num)
                if prerequisite is None:
                    continue
                ancestry = self._ancestry(prerequisite.head_sha, dependent.head_sha)
                if not ancestry.base_is_ancestor_of_head:
                    pair = tuple(sorted((prerequisite_num, dependent_num)))
                    if pair not in seen_semantic_pairs:
                        seen_semantic_pairs.add(pair)
                        report.missing_semantic_joins.append(
                            {
                                "pr_pair": pair,
                                "prerequisite_pr": prerequisite_num,
                                "dependent_pr": dependent_num,
                                "prerequisite_head": prerequisite.head_sha,
                                "dependent_head": dependent.head_sha,
                                "ancestry_status": ancestry.status.value,
                                "reason": "Semantic dependency declared without topological git integration.",
                            }
                        )

        numbers = sorted(self.nodes)
        for index, num_a in enumerate(numbers):
            node_a = self.nodes[num_a]
            for num_b in numbers[index + 1 :]:
                node_b = self.nodes[num_b]
                if not node_a.authority_domains.intersection(node_b.authority_domains):
                    continue
                ancestry = self._ancestry(node_a.head_sha, node_b.head_sha)
                if not ancestry.is_diverged:
                    continue

                dom_a_b, _ = self.evaluate_supersedes(num_a, num_b)
                dom_b_a, _ = self.evaluate_supersedes(num_b, num_a)
                if not dom_a_b and not dom_b_a:
                    report.divergent_overlaps.append(
                        {
                            "pr_a": num_a,
                            "pr_b": num_b,
                            "ahead_by": ancestry.ahead_by,
                            "behind_by": ancestry.behind_by,
                            "status": ancestry.status.value,
                            "classification": "DIVERGENT_OVERLAPPING_LINEAGES",
                        }
                    )
                elif dom_a_b:
                    report.supersession_candidates.append({"dominant_pr": num_a, "superseded_pr": num_b})
                else:
                    report.supersession_candidates.append({"dominant_pr": num_b, "superseded_pr": num_a})

        return report

    def _proposal_strings(self, report: MultilayerAnomalyReport) -> list[str]:
        proposals: list[str] = []
        for item in report.stale_parents:
            proposals.append(
                f"PROPOSE_RESTACK: PR #{item['pr']} onto current head of PR #{item['declared_parent_pr']}"
            )
        for item in report.missing_semantic_joins:
            proposals.append(
                f"PROPOSE_SEMANTIC_JOIN: Integrate prerequisite PR #{item['prerequisite_pr']} into dependent PR #{item['dependent_pr']}"
            )
        for item in report.divergent_overlaps:
            proposals.append(
                f"PROPOSE_DIVERGENT_REVIEW: Formal reconciliation between PR #{item['pr_a']} and PR #{item['pr_b']}"
            )
        for item in report.stale_body_provenance:
            proposals.append(
                f"PROPOSE_PROVENANCE_BODY_ALIGN: Refresh PR #{item['pr']} body to match live head {item['actual_head_sha']}"
            )
        for item in report.supersession_candidates:
            proposals.append(
                f"PROPOSE_SUPERSESSION_REVIEW: Verify dominance of PR #{item['dominant_pr']} over PR #{item['superseded_pr']}"
            )
        return sorted(set(proposals))

    @staticmethod
    def _canonical_json(value: object) -> bytes:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")

    def generate_advisory_receipt(
        self,
        report: MultilayerAnomalyReport,
        global_main_sha: str,
    ) -> dict[str, object]:
        node_snapshot = [
            {
                "pr": node.number,
                "head_sha": node.head_sha,
                "base_sha": node.base_sha,
                "authority_domains": sorted(domain.value for domain in node.authority_domains),
            }
            for _, node in sorted(self.nodes.items())
        ]
        source_snapshot_digest = hashlib.sha256(
            b"AEDR-DAG-SNAPSHOT-V1\0" + self._canonical_json(node_snapshot)
        ).hexdigest()

        payload = {
            "protocol_version": self.RECEIPT_VERSION,
            "policy_version": self.POLICY_VERSION,
            "global_main_sha": global_main_sha,
            "source_snapshot_digest": source_snapshot_digest,
            "authority_class": "NONE",
            "execution_mode": "ADVISORY_PROPOSAL_ONLY",
            "anomalies": {
                "stale_parents": report.stale_parents,
                "divergent_overlaps": report.divergent_overlaps,
                "missing_semantic_joins": report.missing_semantic_joins,
                "stale_body_provenance": report.stale_body_provenance,
                "generated_head_drifts": report.generated_head_drifts,
                "supersession_candidates": report.supersession_candidates,
            },
            "proposals": self._proposal_strings(report),
        }
        digest = hashlib.sha256(
            b"AEDR-DAG-RECEIPT-V1\0" + self._canonical_json(payload)
        ).hexdigest()
        return {
            "receipt_digest": digest,
            "digest_algorithm": "sha256",
            "signature_status": "UNSIGNED_CONTENT_ADDRESSED",
            "payload": payload,
        }
