#!/usr/bin/env python3
"""Zero-inference AEGIS work selector. Existing issue_evolution owns the graph.

This is an ADVISORY adapter: it cannot grant execution authority, publish, send,
pay for model calls, change source, mark issues complete or promote policy.
It uses the existing exact-head issue graph, rather than creating an agent bus.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SHA = re.compile(r"[a-f0-9]{40}\Z")
TOPICS = ("commerce", "engineering", "security", "research", "formal")
ROLES = {"commerce": "sales", "engineering": "engineering", "security": "cybersecurity",
         "research": "ai_research", "formal": "formal_verification"}


def stable_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def select_work(graph: dict, *, source_head: str, tick: str,
                prior: dict | None = None) -> dict:
    """Deterministic bounded selection with dedup; never treats text as authority."""
    if not SHA.fullmatch(source_head):
        raise ValueError("SOURCE_HEAD_REQUIRED")
    if not isinstance(tick, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", tick):
        raise ValueError("INVALID_TICK")
    if graph.get("schema") != "AEGIS_ISSUE_EVOLUTION_GRAPH_V1" or graph.get("execution_effect") != "NONE":
        raise ValueError("UNVERIFIED_OR_EXECUTING_GRAPH")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or len(nodes) > 2048:
        raise ValueError("INVALID_ISSUE_SET")
    if not re.fullmatch(r"[a-f0-9]{64}", str(graph.get("receipt_hash", ""))):
        raise ValueError("GRAPH_RECEIPT_MISSING")
    used = set()
    if prior is not None:
        if prior.get("schema") != "AEGIS_OPTIMUS_TICK_V1" or prior.get("authority_effect") != "NONE":
            raise ValueError("PRIOR_RECEIPT_UNTRUSTED")
        if prior.get("source_head") == source_head and prior.get("graph_receipt_hash") == graph["receipt_hash"]:
            used.add(prior.get("selected_issue"))

    pool = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("INVALID_NODE")
        topic = node.get("topic")
        key = node.get("key")
        labels = node.get("labels", [])
        if not isinstance(key, str) or not re.fullmatch(r"[\w-]+/[\w-]+#[1-9][0-9]{0,6}", key):
            raise ValueError("INVALID_ISSUE_ID")
        if topic not in TOPICS or not isinstance(labels, list):
            continue
        if any(label in labels for label in ("needs-operator", "blocked", "do-not-automate")):
            continue
        if key in used:
            continue
        pool.setdefault(topic, []).append(node)

    # A fixed rotating fairness schedule avoids always choosing engineering.
    # Urgency is not inferred from unknown customer/pipeline valuations.
    offset = int(stable_hash({"tick": tick})[:8], 16) % len(TOPICS)
    rotation = TOPICS[offset:] + TOPICS[:offset]
    selected = None
    for topic in rotation:
        candidates = pool.get(topic, [])
        if candidates:
            selected = sorted(candidates, key=lambda n: (0 if "P0" in n["labels"] else 1,
                                                            n["number"]))[0]
            break

    base = {"schema": "AEGIS_OPTIMUS_TICK_V1", "tick": tick,
            "source_head": source_head, "graph_receipt_hash": graph["receipt_hash"],
            "authority_effect": "NONE", "execution_effect": "NONE", "spend_usd": 0,
            "selection_is_not_execution": True}
    if selected is None:
        base.update({"disposition": "HOLD_NO_NEW_VERIFIABLE_WORK", "selected_issue": None,
                     "proposed_role": None, "next_action": "No eligible unsuperseded source work; no agent run"})
    else:
        base.update({"disposition": "REVIEW_READY", "selected_issue": selected["key"],
                     "proposed_role": ROLES[selected["topic"]],
                     "topic": selected["topic"],
                     "next_action": "Read exact issue and current source; complete one bounded evidence-backed artifact, test it, and post a verifiable handoff on existing work. No customer sends, deploy or paid API calls."})
    base["receipt_hash"] = stable_hash(base)
    return base


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--snapshot", type=Path, help="existing issue_evolution snapshot fixture")
    group.add_argument("--live-repo", default=None, help="allowlisted GitHub repository")
    ap.add_argument("--source-head", required=True)
    ap.add_argument("--tick", required=True)
    ap.add_argument("--prior", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    # Reuse the actual pre-existing issue inventory and source-graph compiler.
    from agents.issue_evolution import fetch_open_issues, compile_graph
    try:
        if args.snapshot:
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        else:
            snapshot = fetch_open_issues(args.live_repo, token=os.environ.get("GH_TOKEN"), max_pages=10)
        graph = compile_graph(snapshot)
        prior = json.loads(args.prior.read_text(encoding="utf-8")) if args.prior else None
        receipt = select_work(graph, source_head=args.source_head, tick=args.tick, prior=prior)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": "AEGIS_OPTIMUS_TICK_V1", "disposition": "HOLD",
                          "reason": type(exc).__name__ + ":" + str(exc)[:150],
                          "authority_effect": "NONE", "execution_effect": "NONE"}))
        return 2
    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())