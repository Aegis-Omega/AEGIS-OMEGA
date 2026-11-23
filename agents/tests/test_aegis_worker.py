"""Offline tests for agents/aegis-worker/run.py (no API calls)."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_spec = importlib.util.spec_from_file_location(
    "aegis_worker_run", Path(__file__).resolve().parents[1] / "aegis-worker" / "run.py")
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)


def mcp(name):
    return SimpleNamespace(type="agent.mcp_tool_use", name=name)


def test_reads_and_delivery_writes_are_allowed():
    for name in ("get_file_contents", "list_issues", "search_code", "issue_read",
                 "create_pull_request", "add_issue_comment"):
        assert run.approve(mcp(name)), name


def test_merge_delete_and_unknown_are_denied():
    for name in ("merge_pull_request", "delete_file", "push_files", "update_repository", ""):
        assert not run.approve(mcp(name)), name


def test_undecided_builtin_calls_are_denied():
    assert not run.approve(SimpleNamespace(type="agent.tool_use", name="bash"))


def test_done_when_is_extracted_into_rubric():
    body = "Some context.\n\n**Done when:** `AGENTS.md` plus a short CLAUDE.md are the only always-read docs.\n"
    assert run.done_when(body).startswith("`AGENTS.md` plus")
    rubric = run.build_rubric(741, body)
    assert "Done when" in rubric and "Closes #741" in rubric and "agent/issue-741-" in rubric


def test_rubric_without_done_when_falls_back():
    assert "every acceptance criterion" in run.build_rubric(1, "no criteria here")
