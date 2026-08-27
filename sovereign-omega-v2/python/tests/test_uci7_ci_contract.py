#!/usr/bin/env python3
"""Static falsifiers for the UCI-7 repo-native evidence contract."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github/workflows/uci-7-agi-evidence-protocol.yml"
FROZEN_PARENT = "156062855a91b77133d8999ce34883432435b167"
FROZEN_PARENT_BRANCH = "feat/uci-6-collective-memory-admission-v1"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_uci7_ci_binds_literal_frozen_parent_and_pr_base() -> None:
    text = _workflow_text()
    assert f"EXPECTED_PARENT_SHA: {FROZEN_PARENT}" in text
    assert "PR_BASE_SHA: ${{ github.event.pull_request.base.sha || '' }}" in text
    assert 'test "$PR_BASE_SHA" = "$EXPECTED_PARENT_SHA"' in text


def test_uci7_ci_runs_only_for_its_frozen_parent_pr() -> None:
    text = _workflow_text()
    assert "pull_request:\n    branches:\n      - " + FROZEN_PARENT_BRANCH in text


def test_uci7_ci_locks_local_protocol_cardinality() -> None:
    text = _workflow_text()
    assert "grep -Eq '13 passed'" in text
    assert 'echo "UCI7_LOCAL_PROTOCOL_13=PASS"' in text


def test_uci7_ci_executes_and_locks_inherited_proofline() -> None:
    text = _workflow_text()
    assert "test_uci6_internal_base_guard.py" in text
    assert "grep -Eq '131 passed'" in text
    assert 'echo "UCI7_INHERITED_PROOFLINE_131=PASS"' in text
    assert "test_uci5_ci_contract.py" in text
    assert "grep -Eq '3 passed'" in text
    assert 'echo "UCI7_INHERITED_UCI5_CI_GUARDS_3=PASS"' in text
