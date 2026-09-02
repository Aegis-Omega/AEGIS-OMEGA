#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Tuple


class WorkflowRunConclusion(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"
    SKIPPED = "skipped"
    IN_PROGRESS = "in_progress"
    QUEUED = "queued"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RawWorkflowReceipt:
    run_id: int
    run_number: int
    workflow_name: str
    head_sha: str
    conclusion: WorkflowRunConclusion
    completed_at: str
    html_url: str

    @property
    def is_exact_head_green(self) -> bool:
        """Compatibility predicate; caller must still bind this receipt to a live head."""
        return self.conclusion == WorkflowRunConclusion.SUCCESS

    def is_terminal_green_for(self, expected_head_sha: str) -> bool:
        return (
            self.head_sha.lower() == expected_head_sha.lower()
            and self.conclusion == WorkflowRunConclusion.SUCCESS
        )


@dataclass(frozen=True)
class RawGitCompare:
    """GitHub comparison of base_sha...head_sha."""

    base_sha: str
    head_sha: str
    merge_base_sha: str
    ahead_by: int
    behind_by: int
    status: str
    files_changed: Tuple[str, ...]


@dataclass(frozen=True)
class RawPullRequestRecord:
    number: int
    head_sha: str
    base_sha: str
    base_ref: str
    draft: bool
    mergeable_state: str
    title: str
    body: str
    labels: Tuple[str, ...]
    updated_at: str


@dataclass(frozen=True)
class RateLimitState:
    remaining: int | None
    limit: int | None
    reset_epoch: int | None
    resource: str | None


@dataclass(frozen=True)
class MultilayerDAGSnapshot:
    schema_version: str
    global_main_sha: str
    captured_at_utc: str
    node_count: int
    nodes: Tuple[Dict[str, Any], ...]
    ancestry_matrix: Tuple[Dict[str, Any], ...]
    merkle_root: str
    snapshot_digest: str
    authority_class: str = "NONE"
    execution_mode: str = "READ_ONLY"
    consistency_model: str = "OPTIMISTIC_DOUBLE_COLLECT"
