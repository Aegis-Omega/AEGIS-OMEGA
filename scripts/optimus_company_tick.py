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
import urllib.request
import urllib.error
from pathlib import Path

SHA = re.compile(r"[a-f0-9]{40}\Z")
TOPICS = ("commerce", "engineering", "security", "research", "formal")
CHECKPOINT_MARKER = "<!-- AEGIS_OPTIMUS_CHECKPOINT_V1 -->"
CHECKPOINT_SCHEMA = "AEGIS_OPTIMUS_CHECKPOINT_V1"
CHECKPOINT_LIMIT = 512
REPO = "Aegis-Omega/AEGIS-OMEGA"

ROLES = {"commerce": "sales", "engineering": "engineering", "security": "cybersecurity",
         "research": "ai_research", "formal": "formal_verification"}


def stable_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def select_work(graph: dict, *, source_head: str, tick: str,
                prior: dict | None = None,
                completed_fingerprints: frozenset[str] = frozenset()) -> dict:
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
        if key in used or stable_hash({"key": key, "body": node.get("body_sha256", ""),
                                          "labels": sorted(labels), "title": node.get("title", "")}) in completed_fingerprints:
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
                     "selected_fingerprint": stable_hash({"key": selected["key"],
                          "body": selected.get("body_sha256", ""),
                          "labels": sorted(selected["labels"]), "title": selected.get("title", "")}),
                     "next_action": "Read exact issue and current source; complete one bounded evidence-backed artifact, test it, and post a verifiable handoff on existing work. No customer sends, deploy or paid API calls."})
    base["receipt_hash"] = stable_hash(base)
    return base



def github_json(path: str, *, token: str, method: str = "GET", body: dict | None = None):
    """Bounded authenticated GitHub API; never prints the token or response body."""
    if not token or len(token) < 12 or not path.startswith(f"/repos/{REPO}/"):
        raise ValueError("GITHUB_BINDING_MISSING")
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request("https://api.github.com" + path, data=data, method=method,
        headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "AEGIS-OPTIMUS-zero-spend"})
    try:
        with urllib.request.urlopen(request, timeout=15) as r:
            raw = r.read(1000001)
            if len(raw) > 1000000:
                raise ValueError("GITHUB_RESPONSE_TOO_LARGE")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise ValueError("GITHUB_HTTP_" + str(exc.code)) from None


def checkpoint_from_comment(comment: dict) -> dict:
    """Provider-authenticated bot comments are metadata, NEVER operational authority."""
    author = comment.get("user") or {}
    if author.get("login") != "github-actions[bot]" or author.get("type") != "Bot":
        raise ValueError("CHECKPOINT_AUTHOR_UNTRUSTED")
    body = comment.get("body", "")
    if not isinstance(body, str) or not body.startswith(CHECKPOINT_MARKER + "\n"):
        raise ValueError("CHECKPOINT_MARKER_MISSING")
    state = json.loads(body[len(CHECKPOINT_MARKER) + 1:])
    if (state.get("schema") != CHECKPOINT_SCHEMA or
        type(state.get("fingerprints")) is not list or
        len(state["fingerprints"]) > CHECKPOINT_LIMIT or
        any(not isinstance(x, str) or not re.fullmatch(r"[0-9a-f]{64}", x) for x in state["fingerprints"])):
        raise ValueError("CHECKPOINT_SCHEMA_INVALID")
    return state


def read_checkpoint(*, issue: int, token: str) -> tuple[dict, int | None]:
    """Reuse a single existing issue comment as source-linked cursor (no new DB)."""
    if issue != 734:
        raise ValueError("CHECKPOINT_ISSUE_NOT_ALLOWED")
    for page in range(1, 9):
        batch = github_json(f"/repos/{REPO}/issues/{issue}/comments?per_page=100&page={page}", token=token)
        if not isinstance(batch, list):
            raise ValueError("COMMENT_LIST_INVALID")
        for comment in reversed(batch):
            if isinstance(comment.get("body"), str) and comment["body"].startswith(CHECKPOINT_MARKER):
                return checkpoint_from_comment(comment), comment["id"]
        if len(batch) < 100:
            return {"schema": CHECKPOINT_SCHEMA, "fingerprints": []}, None
    raise ValueError("COMMENT_PAGINATION_INCOMPLETE")


def persist_checkpoint(*, issue: int, token: str, comment_id: int | None,
                       state: dict, receipt: dict) -> dict:
    """D1 metadata only; no effect on existing AEGIS authority/memory."""
    if issue != 734 or receipt.get("disposition") != "REVIEW_READY":
        return {"status": "NO_WRITE"}
    fingerprints = state["fingerprints"] + [receipt["selected_fingerprint"]]
    if len(set(fingerprints)) != len(fingerprints):
        raise ValueError("DUPLICATE_TASK_RECEIPT")
    if len(fingerprints) > CHECKPOINT_LIMIT:
        raise ValueError("CHECKPOINT_FULL_HOLD")
    body = CHECKPOINT_MARKER + "\n" + json.dumps({"schema": CHECKPOINT_SCHEMA,
        "fingerprints": fingerprints, "last_receipt": receipt["receipt_hash"],
        "authority_effect": "NONE", "execution_effect": "NONE"},
        sort_keys=True, separators=(",", ":"))
    path = f"/repos/{REPO}/issues/{issue}/comments" if comment_id is None else f"/repos/{REPO}/issues/comments/{comment_id}"
    response = github_json(path, token=token, method="POST" if comment_id is None else "PATCH", body={"body": body})
    if not isinstance(response, dict) or not isinstance(response.get("id"), int):
        raise ValueError("CHECKPOINT_WRITE_UNVERIFIED")
    return {"status": "RECORDED", "comment_id": response["id"]}

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--snapshot", type=Path, help="existing issue_evolution snapshot fixture")
    group.add_argument("--live-repo", default=None, help="allowlisted GitHub repository")
    ap.add_argument("--source-head", required=True)
    ap.add_argument("--tick", required=True)
    ap.add_argument("--prior", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--record-checkpoint", action="store_true")
    ap.add_argument("--checkpoint-issue", type=int, default=734)
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
        state = {"schema": CHECKPOINT_SCHEMA, "fingerprints": []}
        comment_id = None
        token = os.environ.get("GH_TOKEN", "")
        if args.record_checkpoint:
            if (os.environ.get("GITHUB_ACTIONS") != "true" or
                os.environ.get("GITHUB_REPOSITORY") != REPO or
                os.environ.get("GITHUB_REF") != "refs/heads/main" or
                os.environ.get("GITHUB_SHA") != args.source_head):
                raise ValueError("GITHUB_SCHEDULE_IDENTITY_UNVERIFIED")
            state, comment_id = read_checkpoint(issue=args.checkpoint_issue, token=token)
        receipt = select_work(graph, source_head=args.source_head, tick=args.tick, prior=prior,
            completed_fingerprints=frozenset(state["fingerprints"]))
        if args.record_checkpoint and receipt["disposition"] == "REVIEW_READY":
            persistence = persist_checkpoint(issue=args.checkpoint_issue, token=token,
                comment_id=comment_id, state=state, receipt=receipt)
            receipt["checkpoint_write"] = persistence
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