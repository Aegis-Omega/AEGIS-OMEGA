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
import time
import urllib.request
import urllib.error
from pathlib import Path

SHA = re.compile(r"[a-f0-9]{40}\Z")
TOPICS = ("commerce", "engineering", "security", "research", "formal")
CHECKPOINT_MARKER = "<!-- AEGIS_OPTIMUS_CHECKPOINT_V2 -->"
CHECKPOINT_SCHEMA = "AEGIS_OPTIMUS_CHECKPOINT_V2"
LEASE_SECONDS = 24 * 60 * 60
MAX_ATTEMPTS_PER_REVISION = 3
CHECKPOINT_LIMIT = 128
REPO = "Aegis-Omega/AEGIS-OMEGA"

ROLES = {"commerce": "sales", "engineering": "engineering", "security": "cybersecurity",
         "research": "ai_research", "formal": "ai_research"}  # coordinator.AgentRole has no formal_verification value


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
    if (graph.get("schema") != "AEGIS_ISSUE_EVOLUTION_GRAPH_V1" or
            graph.get("execution_effect") != "NONE" or graph.get("authority_effect") not in (None, "NONE")):
        raise ValueError("UNVERIFIED_OR_EXECUTING_GRAPH")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or len(nodes) > 2048:
        raise ValueError("INVALID_ISSUE_SET")
    if graph.get("repository") not in (None, REPO):
        raise ValueError("GRAPH_REPOSITORY_MISMATCH")
    if not re.fullmatch(r"[a-f0-9]{64}", str(graph.get("receipt_hash", ""))):
        raise ValueError("GRAPH_RECEIPT_MISSING")
    # An open dependency or an unresolved dependency cannot be assumed done.
    # Related/parent links carry context; only explicit depends_on blocks work.
    edges, unresolved = graph.get("edges"), graph.get("unresolved_references")
    if (not isinstance(edges, list) or not isinstance(unresolved, list) or
            len(edges) + len(unresolved) > 8192):
        raise ValueError("GRAPH_DEPENDENCY_COVERAGE_UNKNOWN")
    waiting_on = set()
    for relation in edges + unresolved:
        if (not isinstance(relation, dict) or
                set(relation) != {"from", "to", "kind"} or
                relation["kind"] not in ("depends_on", "parent", "related") or
                not isinstance(relation["from"], str) or
                not isinstance(relation["to"], str) or
                not re.fullmatch(r"Aegis-Omega/AEGIS-OMEGA#[1-9][0-9]{0,6}", relation["from"]) or
                not re.fullmatch(r"Aegis-Omega/AEGIS-OMEGA#[1-9][0-9]{0,6}", relation["to"])):
            raise ValueError("GRAPH_EDGE_UNTRUSTED")
        if relation["kind"] == "depends_on":
            waiting_on.add(relation["from"])
    # Legacy --prior receipts report only that an issue was SELECTED.
    # They must never remove an unfinished issue from the eligible pool:
    # queue cooldown and bounded escalation live exclusively in V2 leases.
    if prior is not None:
        if (not isinstance(prior, dict) or
                prior.get("schema") != "AEGIS_OPTIMUS_TICK_V1" or
                prior.get("authority_effect") != "NONE" or
                prior.get("execution_effect") != "NONE"):
            raise ValueError("PRIOR_RECEIPT_UNTRUSTED")

    pool = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("INVALID_NODE")
        topic = node.get("topic")
        key = node.get("key")
        labels = node.get("labels", [])
        title = node.get("title")
        if not isinstance(title, str) or not 0 < len(title) <= 800:
            raise ValueError("ISSUE_TITLE_REQUIRED")
        if not isinstance(key, str) or not re.fullmatch(r"[\w-]+/[\w-]+#[1-9][0-9]{0,6}", key):
            raise ValueError("INVALID_ISSUE_ID")
        if (topic not in TOPICS or not isinstance(labels, list) or
                any(not isinstance(x, str) or len(x) > 100 for x in labels)):
            continue
        if not re.fullmatch(r"[a-f0-9]{64}", str(node.get("body_sha256", ""))):
            continue  # no revision identity, so no durable lease; cannot silently seal work
        if node.get("number") != int(key.rsplit("#", 1)[1]):
            raise ValueError("ISSUE_ID_NUMBER_MISMATCH")
        if any(label.lower() in ("needs-operator", "blocked", "do-not-automate") for label in labels):
            continue
        # A human-only administrative issue can lack GitHub labels.
        # Never route an explicit operator decision to autonomous engineering.
        if re.match(r"^\s*(?:operator(?:[- ]only|[- ]action|[- ]decision)?|"
                    r"requires[- ]operator|manual[- ]approval|approval[- ]required|"
                    r"human[- ]approval|admin[- ]action|billing[- ]action)\s*[:—-]", title, re.I):
            continue
        if key in waiting_on:
            continue  # unmet open/unknown prerequisite; never dispatch prematurely
        if stable_hash({"key": key, "body": node.get("body_sha256", ""),
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
    """Read a bot-authored lease cursor; it never attests execution/completion.

    V1 fingerprints are intentionally NOT migrated: V1 incorrectly interpreted
    work *selection* as completion. Failing open from that state would lose work.
    """
    author = comment.get("user") or {}
    if author.get("login") != "github-actions[bot]" or author.get("type") != "Bot":
        raise ValueError("CHECKPOINT_AUTHOR_UNTRUSTED")
    body = comment.get("body", "")
    if not isinstance(body, str) or not body.startswith(CHECKPOINT_MARKER + "\n"):
        raise ValueError("CHECKPOINT_MARKER_MISSING")
    state = json.loads(body[len(CHECKPOINT_MARKER) + 1:])
    if (not isinstance(state, dict) or state.get("schema") != CHECKPOINT_SCHEMA or
            type(state.get("leases")) is not list or len(state["leases"]) > CHECKPOINT_LIMIT or
            state.get("authority_effect") != "NONE" or state.get("execution_effect") != "NONE"):
        raise ValueError("CHECKPOINT_SCHEMA_INVALID")
    fingerprints = set()
    for lease in state["leases"]:
        if (not isinstance(lease, dict) or
                set(lease) != {"issue", "fingerprint", "state", "attempt", "expires_epoch", "receipt_hash"} or
                not isinstance(lease["fingerprint"], str) or
                not re.fullmatch(r"[a-f0-9]{64}", lease["fingerprint"]) or
                not isinstance(lease["receipt_hash"], str) or
                not re.fullmatch(r"[a-f0-9]{64}", lease["receipt_hash"]) or
                not isinstance(lease["issue"], str) or
                not re.fullmatch(r"Aegis-Omega/AEGIS-OMEGA#[1-9][0-9]{0,6}", lease["issue"]) or
                lease["state"] not in ("QUEUED_UNEXECUTED", "EXHAUSTED_UNEXECUTED") or
                type(lease["attempt"]) is not int or not 1 <= lease["attempt"] <= MAX_ATTEMPTS_PER_REVISION or
                type(lease["expires_epoch"]) is not int or not 0 <= lease["expires_epoch"] <= 99999999999 or
                lease["fingerprint"] in fingerprints):
            raise ValueError("CHECKPOINT_LEASE_INVALID")
        fingerprints.add(lease["fingerprint"])
    return state


def checkpoint_exclusions(state: dict, *, now_epoch: int) -> frozenset[str]:
    """Cooldown a QUEUED lease; stop after bounded attempts, NEVER label it DONE."""
    if type(now_epoch) is not int or now_epoch < 0 or state.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError("CHECKPOINT_CLOCK_OR_SCHEMA_INVALID")
    excluded = set()
    for lease in state.get("leases", []):
        if (lease["state"] == "EXHAUSTED_UNEXECUTED" or
                lease["expires_epoch"] > now_epoch):
            excluded.add(lease["fingerprint"])
    return frozenset(excluded)


def read_checkpoint(*, issue: int, token: str) -> tuple[dict, int | None]:
    """Scan all bounded comment pages to choose the newest V2 checkpoint.

    GitHub returns issue comments oldest-first, 100/page. Returning the first
    matching page silently resurrects an old cursor after >100 comments.
    Treat a missing final page or a malformed newest checkpoint as HOLD.
    """
    if issue != 734:
        raise ValueError("CHECKPOINT_ISSUE_NOT_ALLOWED")
    newest = None
    for page in range(1, 9):
        batch = github_json(f"/repos/{REPO}/issues/{issue}/comments?per_page=100&page={page}", token=token)
        if not isinstance(batch, list) or len(batch) > 100:
            raise ValueError("COMMENT_LIST_INVALID")
        for comment in batch:
            if not isinstance(comment, dict):
                raise ValueError("COMMENT_ENTRY_INVALID")
            if isinstance(comment.get("body"), str) and comment["body"].startswith(CHECKPOINT_MARKER):
                newest = comment
        if len(batch) < 100:
            if newest is None:
                return {"schema": CHECKPOINT_SCHEMA, "leases": [],
                        "authority_effect": "NONE", "execution_effect": "NONE"}, None
            comment_id = newest.get("id")
            if type(comment_id) is not int or comment_id <= 0:
                raise ValueError("CHECKPOINT_COMMENT_ID_INVALID")
            return checkpoint_from_comment(newest), comment_id
    raise ValueError("COMMENT_PAGINATION_INCOMPLETE")

def next_lease(state: dict, receipt: dict, *, now_epoch: int) -> dict:
    """Stage an idempotent advisory claim; real completion requires separate proof."""
    if receipt.get("disposition") != "REVIEW_READY":
        raise ValueError("NO_ELIGIBLE_WORK_TO_CLAIM")
    if state.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError("CHECKPOINT_SCHEMA_INVALID")
    fingerprint = receipt["selected_fingerprint"]
    if fingerprint in checkpoint_exclusions(state, now_epoch=now_epoch):
        raise ValueError("LEASE_STILL_ACTIVE_OR_EXHAUSTED")
    leases = list(state["leases"])
    prior = next((x for x in leases if x["fingerprint"] == fingerprint), None)
    attempts = (prior["attempt"] if prior else 0) + 1
    if attempts > MAX_ATTEMPTS_PER_REVISION:
        raise ValueError("RETRY_BUDGET_EXHAUSTED")
    leases = [x for x in leases if x["fingerprint"] != fingerprint]
    leases.append({"issue": receipt["selected_issue"],
                   "fingerprint": fingerprint,
                   "state": "EXHAUSTED_UNEXECUTED" if attempts == MAX_ATTEMPTS_PER_REVISION else "QUEUED_UNEXECUTED",
                   "attempt": attempts,
                   "expires_epoch": now_epoch + LEASE_SECONDS,
                   "receipt_hash": receipt["receipt_hash"]})
    if len(leases) > CHECKPOINT_LIMIT:
        raise ValueError("CHECKPOINT_FULL_HOLD")
    return {"schema": CHECKPOINT_SCHEMA, "leases": leases,
            "last_receipt": receipt["receipt_hash"],
            "authority_effect": "NONE", "execution_effect": "NONE"}


def persist_checkpoint(*, issue: int, token: str, comment_id: int | None,
                       state: dict, receipt: dict, now_epoch: int | None = None) -> dict:
    """D1 queue metadata, not a successful task or permission to dispatch."""
    if issue != 734 or receipt.get("disposition") != "REVIEW_READY":
        return {"status": "NO_WRITE"}
    new_state = next_lease(state, receipt, now_epoch=int(time.time()) if now_epoch is None else now_epoch)
    body = CHECKPOINT_MARKER + "\n" + json.dumps(new_state, sort_keys=True, separators=(",", ":"))
    path = f"/repos/{REPO}/issues/{issue}/comments" if comment_id is None else f"/repos/{REPO}/issues/comments/{comment_id}"
    response = github_json(path, token=token, method="POST" if comment_id is None else "PATCH", body={"body": body})
    if not isinstance(response, dict) or not isinstance(response.get("id"), int):
        raise ValueError("CHECKPOINT_WRITE_UNVERIFIED")
    return {"status": "QUEUED_UNEXECUTED", "comment_id": response["id"],
            "attempt": new_state["leases"][-1]["attempt"],
            "next_review_epoch": new_state["leases"][-1]["expires_epoch"]}

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
        state = {"schema": CHECKPOINT_SCHEMA, "leases": [], "authority_effect": "NONE", "execution_effect": "NONE"}
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
            completed_fingerprints=checkpoint_exclusions(state, now_epoch=int(time.time())))
        # Never let a perpetually unexecuted lease disappear from the operator queue.
        exhausted = sorted({x["issue"] for x in state["leases"]
                            if x["state"] == "EXHAUSTED_UNEXECUTED"})
        if exhausted:
            receipt["unexecuted_escalations"] = exhausted[:20]
            receipt["unexecuted_escalation_count"] = len(exhausted)
            receipt["receipt_hash"] = stable_hash({k: v for k, v in receipt.items()
                                                    if k != "receipt_hash"})
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