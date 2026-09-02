#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional, Protocol, Tuple

from .acquisition_types import (
    MultilayerDAGSnapshot,
    RawGitCompare,
    RawPullRequestRecord,
    RawWorkflowReceipt,
    freeze_json,
)


class SnapshotIntegrityError(Exception):
    pass


class AcquisitionOracle(Protocol):
    def get_main_sha(self, branch: str = "main") -> str: ...
    def list_open_pulls(self) -> list[RawPullRequestRecord]: ...
    def get_exact_head_workflow_receipts(self, head_sha: str) -> list[RawWorkflowReceipt]: ...
    def compare_commits(self, base_sha: str, head_sha: str) -> RawGitCompare: ...


class DeterministicSnapshotBuilder:
    SCHEMA_VERSION = "AEDR-SNAPSHOT-V1"
    CONSISTENCY_MODEL = "OPTIMISTIC_DOUBLE_COLLECT"

    def __init__(self, oracle: AcquisitionOracle):
        self.oracle = oracle

    @staticmethod
    def parse_body_metadata(body: str) -> Tuple[Optional[int], Optional[str], Tuple[int, ...]]:
        declared_parent: Optional[int] = None
        cited_head: Optional[str] = None
        semantic_deps: List[int] = []

        parent = re.search(r"\[parent-pr:\s*#?(\d+)\]", body, re.IGNORECASE)
        if parent:
            declared_parent = int(parent.group(1))

        cited = re.search(r"\[head-sha:\s*([0-9a-fA-F]{7,40})\]", body, re.IGNORECASE)
        if cited:
            cited_head = cited.group(1).lower()

        deps = re.search(r"\[depends-on:\s*([^\]]+)\]", body, re.IGNORECASE)
        if deps:
            for part in deps.group(1).split(","):
                clean = part.strip().lstrip("#")
                if clean.isdigit():
                    semantic_deps.append(int(clean))

        return declared_parent, cited_head, tuple(sorted(set(semantic_deps)))

    @staticmethod
    def _canonical_json(value: object) -> bytes:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")

    @classmethod
    def _canonical_pr_state(cls, prs: Iterable[RawPullRequestRecord]) -> bytes:
        payload = [
            {
                "number": pr.number,
                "head_sha": pr.head_sha.lower(),
                "base_sha": pr.base_sha.lower(),
                "base_ref": pr.base_ref,
                "draft": pr.draft,
                "mergeable_state": pr.mergeable_state,
                "title": pr.title,
                "body": pr.body,
                "labels": sorted(pr.labels),
                "updated_at": pr.updated_at,
            }
            for pr in sorted(prs, key=lambda item: item.number)
        ]
        return cls._canonical_json(payload)

    @classmethod
    def _leaf_digest(cls, kind: str, value: object) -> bytes:
        return hashlib.sha256(
            f"AEDR-SNAPSHOT-LEAF-V1:{kind}\0".encode("ascii") + cls._canonical_json(value)
        ).digest()

    @staticmethod
    def _merkle_root(leaves: list[bytes]) -> str:
        if not leaves:
            return hashlib.sha256(b"AEDR-MERKLE-V1\0EMPTY").hexdigest()
        level = sorted(leaves)
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])
            level = [
                hashlib.sha256(b"AEDR-MERKLE-V1\0" + level[i] + level[i + 1]).digest()
                for i in range(0, len(level), 2)
            ]
        return level[0].hex()

    @staticmethod
    def _receipt_payload(receipt: RawWorkflowReceipt) -> dict[str, Any]:
        return {
            "run_id": receipt.run_id,
            "run_number": receipt.run_number,
            "workflow_name": receipt.workflow_name,
            "head_sha": receipt.head_sha.lower(),
            "conclusion": receipt.conclusion.value,
            "completed_at": receipt.completed_at,
            "html_url": receipt.html_url,
        }

    def _node_payload(self, pr: RawPullRequestRecord) -> dict[str, Any]:
        declared_parent, cited_head, semantic_deps = self.parse_body_metadata(pr.body)
        raw_receipts = self.oracle.get_exact_head_workflow_receipts(pr.head_sha)

        # Defense in depth: never trust the upstream head_sha filter by itself.
        exact_receipts = sorted(
            (
                receipt
                for receipt in raw_receipts
                if receipt.head_sha.lower() == pr.head_sha.lower()
            ),
            key=lambda receipt: (receipt.workflow_name, receipt.run_number, receipt.run_id),
        )
        receipt_payloads = [self._receipt_payload(receipt) for receipt in exact_receipts]

        return {
            "number": pr.number,
            "head_sha": pr.head_sha.lower(),
            "base_sha": pr.base_sha.lower(),
            "base_ref": pr.base_ref,
            "draft": pr.draft,
            "mergeable_state": pr.mergeable_state,
            "declared_parent_pr": declared_parent,
            "cited_head_sha": cited_head,
            "semantic_dependencies": list(semantic_deps),
            "labels": sorted(pr.labels),
            "exact_head_green": any(
                receipt.is_terminal_green_for(pr.head_sha) for receipt in exact_receipts
            ),
            "receipt_run_ids": [receipt.run_id for receipt in exact_receipts],
            "workflow_receipts": receipt_payloads,
        }

    @staticmethod
    def _ancestry_payload(
        relation_type: str,
        compare: RawGitCompare,
        *,
        base_pr: int | None,
        head_pr: int,
    ) -> dict[str, Any]:
        return {
            "type": relation_type,
            "base_pr": base_pr,
            "head_pr": head_pr,
            "base_sha": compare.base_sha.lower(),
            "head_sha": compare.head_sha.lower(),
            "merge_base_sha": compare.merge_base_sha.lower(),
            "ahead_by": compare.ahead_by,
            "behind_by": compare.behind_by,
            "status": compare.status,
            "files_changed": list(sorted(compare.files_changed)),
            "files_changed_count": len(compare.files_changed),
        }

    def build_snapshot(self, main_branch: str = "main") -> MultilayerDAGSnapshot:
        initial_main_sha = self.oracle.get_main_sha(main_branch).lower()
        initial_prs = self.oracle.list_open_pulls()
        initial_pr_state = self._canonical_pr_state(initial_prs)
        pr_by_number = {pr.number: pr for pr in initial_prs}

        nodes_payload = [self._node_payload(pr) for pr in initial_prs]

        ancestry_by_key: dict[tuple[str, int | None, int, str, str], dict[str, Any]] = {}

        def capture_relation(
            relation_type: str,
            base_sha: str,
            head_sha: str,
            *,
            base_pr: int | None,
            head_pr: int,
        ) -> None:
            key = (relation_type, base_pr, head_pr, base_sha.lower(), head_sha.lower())
            if key in ancestry_by_key:
                return
            compare = self.oracle.compare_commits(base_sha, head_sha)
            ancestry_by_key[key] = self._ancestry_payload(
                relation_type,
                compare,
                base_pr=base_pr,
                head_pr=head_pr,
            )

        for pr in sorted(initial_prs, key=lambda item: item.number):
            # Every PR gets a main anchor; declared/semantic edges are additional.
            capture_relation(
                "MAIN_TO_PR",
                initial_main_sha,
                pr.head_sha,
                base_pr=None,
                head_pr=pr.number,
            )

            declared_parent, _, semantic_deps = self.parse_body_metadata(pr.body)
            if declared_parent is not None:
                parent = pr_by_number.get(declared_parent)
                if parent is not None:
                    capture_relation(
                        "DECLARED_PARENT",
                        parent.head_sha,
                        pr.head_sha,
                        base_pr=declared_parent,
                        head_pr=pr.number,
                    )

            for prerequisite_num in semantic_deps:
                prerequisite = pr_by_number.get(prerequisite_num)
                if prerequisite is not None:
                    capture_relation(
                        "SEMANTIC_DEPENDENCY",
                        prerequisite.head_sha,
                        pr.head_sha,
                        base_pr=prerequisite_num,
                        head_pr=pr.number,
                    )

        # Optimistic snapshot validation: re-collect the complete observed state.
        final_prs = self.oracle.list_open_pulls()
        final_pr_state = self._canonical_pr_state(final_prs)
        final_main_sha = self.oracle.get_main_sha(main_branch).lower()

        if initial_pr_state != final_pr_state:
            raise SnapshotIntegrityError(
                "CONCURRENT_MUTATION_DETECTED: pull_requests changed during acquisition"
            )
        if initial_main_sha != final_main_sha:
            raise SnapshotIntegrityError(
                f"CONCURRENT_MUTATION_DETECTED: main shifted from {initial_main_sha} to {final_main_sha}"
            )

        nodes_payload.sort(key=lambda node: node["number"])
        ancestry_payload = sorted(
            ancestry_by_key.values(),
            key=lambda edge: (
                edge["type"],
                edge["head_pr"],
                edge["base_pr"] if edge["base_pr"] is not None else -1,
                edge["base_sha"],
                edge["head_sha"],
            ),
        )

        leaves = [self._leaf_digest("node", node) for node in nodes_payload]
        leaves.extend(self._leaf_digest("ancestry", edge) for edge in ancestry_payload)
        merkle_root = self._merkle_root(leaves)

        canonical_data = {
            "schema_version": self.SCHEMA_VERSION,
            "global_main_sha": initial_main_sha,
            "node_count": len(nodes_payload),
            "nodes": nodes_payload,
            "ancestry_matrix": ancestry_payload,
            "merkle_root": merkle_root,
            "authority_class": "NONE",
            "execution_mode": "READ_ONLY",
            "consistency_model": self.CONSISTENCY_MODEL,
        }
        snapshot_digest = hashlib.sha256(
            b"AEDR-SNAPSHOT-V1\0" + self._canonical_json(canonical_data)
        ).hexdigest()

        # captured_at_utc is observational metadata and intentionally excluded
        # from the content digest so identical repository/API observations hash identically.
        captured_at_utc = datetime.now(timezone.utc).isoformat()
        frozen_nodes = tuple(freeze_json(node) for node in nodes_payload)
        frozen_ancestry = tuple(freeze_json(edge) for edge in ancestry_payload)
        return MultilayerDAGSnapshot(
            schema_version=self.SCHEMA_VERSION,
            global_main_sha=initial_main_sha,
            captured_at_utc=captured_at_utc,
            node_count=len(nodes_payload),
            nodes=frozen_nodes,
            ancestry_matrix=frozen_ancestry,
            merkle_root=merkle_root,
            snapshot_digest=snapshot_digest,
        )
