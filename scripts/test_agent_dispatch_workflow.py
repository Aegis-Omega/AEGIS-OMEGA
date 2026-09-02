#!/usr/bin/env python3
"""Regression contract for observable, fail-closed AEGIS agent dispatch."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "agent-dispatch.yml"
text = WORKFLOW.read_text(encoding="utf-8")


def require(fragment: str) -> None:
    if fragment not in text:
        raise AssertionError(f"required workflow contract missing: {fragment!r}")


def forbid(fragment: str) -> None:
    if fragment in text:
        raise AssertionError(f"forbidden workflow contract present: {fragment!r}")


# Job visibility: configuration absence is evidence, not a GitHub-level skip.
forbid("if: vars.PROXY_URL != ''")
require("PROXY_UNAVAILABLE")
require("decision=DEFER")

# Event classification must preserve the triggering action, not collapse every PR event
# into a misleading *_opened event.
require("EVENT_ACTION: ${{ github.event.action }}")
require("event_action")

# Only the network effect is conditional on an available proxy and a classified event.
require("steps.proxy.outputs.available == 'true'")
require("steps.classify.outputs.event_type != ''")

# Network calls must be bounded and fail loudly; never hang or silently accept HTTP errors.
require("--fail-with-body")
require("--retry 3")
require("--connect-timeout 5")
require("--max-time 30")

# Every run emits a machine-readable decision/effect receipt even when no dispatch occurs.
require("AGENT_DISPATCH_RECEIPT.json")
require("actions/upload-artifact@")

# Receipts and artifacts bind to the real candidate head, never GitHub's synthetic PR merge ref.
require("CANDIDATE_SHA: ${{ github.event.pull_request.head.sha || github.event.workflow_run.head_sha || github.sha }}")
require("agent-dispatch-receipt-${{ env.CANDIDATE_SHA }}")
forbid("agent-dispatch-receipt-${{ github.sha }}")

print("agent_dispatch_workflow_contract: PASS")
