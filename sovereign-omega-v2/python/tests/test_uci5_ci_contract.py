#!/usr/bin/env python3
"""Static falsifiers for the UCI-5 repo-native CI evidence contract."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github/workflows/uci-5-atomic-admission-contract.yml"
FROZEN_PARENT = "bda5c5369b15ec91f2651ddbf6d219f6b7a1d0f6"
FROZEN_PARENT_BRANCH = "feat/uci-4-effect-chain-integration-v1"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_uci5_ci_binds_literal_frozen_parent_and_pr_base() -> None:
    text = _workflow_text()
    assert f"EXPECTED_PARENT_SHA: {FROZEN_PARENT}" in text
    assert "PR_BASE_SHA: ${{ github.event.pull_request.base.sha || '' }}" in text
    assert 'test "$PR_BASE_SHA" = "$EXPECTED_PARENT_SHA"' in text


def test_uci5_ci_locks_expected_proofline_cardinality() -> None:
    text = _workflow_text()
    assert "grep -Eq '105 passed'" in text
    assert 'echo "UCI5_FULL_PROOFLINE_105=PASS"' in text


def test_uci5_ci_runs_only_for_its_frozen_parent_pr() -> None:
    text = _workflow_text()
    assert "pull_request:\n    branches:\n      - " + FROZEN_PARENT_BRANCH in text
