"""Issue-wide, authority-neutral evolution overlay for AEGIS's existing work board.

Reads GitHub Issues snapshots; compiles explicit cross-issue dendrites and an
evolution experiment contract for EACH issue. It does not execute work, edit
issues, promote a skill, change tiers or approve a PR. External issue text is
untrusted data. Reuses the existing dendrite role/route and evidence concepts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from agents.dendrite_mesh import canonical, digest, HEAD_RE
from agents.dendrite_system import EvidencePacket, spread_packets

SCHEMA = "AEGIS_ISSUE_EVOLUTION_GRAPH_V1"
EVAL_SCHEMA = "AEGIS_ISSUE_EVOLUTION_TRIAL_V1"
REPOS = frozenset({
    "Aegis-Omega/AEGIS-OMEGA", "Aegis-Omega/AegisOmega",
    "tarikskalic33/formal-conjectures", "tarikskalic33/sovereign-guard",
})
ISSUE_REF = re.compile(r"(?<![A-Za-z0-9/])#([1-9][0-9]{0,6})(?![0-9])")
DEP_WORD = re.compile(r"\b(?:depends on|dependencies|dependency|blocked by|requires|prerequisite)\b", re.I)
PARENT_WORD = re.compile(r"\b(?:parent|epic)\b", re.I)
MAX_ISSUES = 2048
MAX_BODY = 60_000
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _valid_repo(repo: str) -> None:
    if repo not in REPOS:
        raise ValueError("REPOSITORY_NOT_ALLOWLISTED")


def fetch_open_issues(repo: str, *, token: str | None = None,
                      max_pages: int = 20) -> dict[str, Any]:
    """Explicit read-only online inventory. No mutation or inferred permission."""
    _valid_repo(repo)
    if not 1 <= max_pages <= 20:
        raise ValueError("INVALID_PAGE_BOUND")
    results: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        url = f"https://api.github.com/repos/{repo}/issues?state=open&per_page=100&page={page}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "aegis-issue-evolution-readonly",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise ValueError("GITHUB_PAGE_NOT_OK")
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("GITHUB_PAGE_OVERSIZED")
        batch = json.loads(raw)
        if not isinstance(batch, list) or len(batch) > 100:
            raise ValueError("GITHUB_PAGE_MALFORMED")
        results.extend(batch)
        if len(batch) < 100:
            return {"repository": repo, "issues": results, "complete_pages": True,
                    "acquisition": "GITHUB_READ_ONLY_API", "pages": page}
    raise ValueError("GITHUB_PAGINATION_INCOMPLETE")


def _issue(raw: Mapping[str, Any], repo: str) -> dict[str, Any] | None:
    if not isinstance(raw, Mapping):
        raise ValueError("ISSUE_MALFORMED")
    if "pull_request" in raw:
        return None
    n = raw.get("number")
    title = raw.get("title")
    body = raw.get("body") or ""
    if (type(n) is not int or not 1 <= n <= 9_999_999
            or not isinstance(title, str) or not 0 < len(title) <= 800
            or not isinstance(body, str) or len(body) > MAX_BODY):
        raise ValueError("ISSUE_FIELDS_INVALID")
    labels = raw.get("labels") or []
    if not isinstance(labels, list) or len(labels) > 64:
        raise ValueError("ISSUE_LABELS_INVALID")
    outlabels = []
    for lbl in labels:
        value = lbl if isinstance(lbl, str) else lbl.get("name") if isinstance(lbl, Mapping) else None
        if not isinstance(value, str) or len(value) > 120:
            raise ValueError("ISSUE_LABEL_INVALID")
        outlabels.append(value)
    lines = body.splitlines()
    deps, parents, related = set(), set(), set()
    for line in lines:
        # Honor only explicit references, NOT LLM-inferred relations.
        if len(line) > 3000:
            continue
        ids = set(int(i) for i in ISSUE_REF.findall(line))
        if DEP_WORD.search(line):
            deps.update(ids)
        elif PARENT_WORD.search(line):
            parents.update(ids)
        else:
            related.update(ids)
    deps.discard(n); parents.discard(n); related.discard(n)
    return {"key": f"{repo}#{n}", "number": n, "title": title,
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "updated_at": raw.get("updated_at") if isinstance(raw.get("updated_at"), str) else None,
            "labels": sorted(set(outlabels)),
            "explicit_dependencies": sorted(deps), "explicit_parents": sorted(parents),
            "explicit_related": sorted(related),
            "repo": repo}


def _domain(title: str, labels: list[str]) -> str:
    value = (title + " " + " ".join(labels)).lower()
    # A topic is a routing classification, NOT evidence that an agent is capable.
    if any(x in value for x in ("riemann", "qform", "weil", "theorem", "lean", "proof/")):
        return "formal"
    if any(x in value for x in ("incident", "security", "policy", "authority", "governance")):
        return "security"
    if any(x in value for x in ("revenue", "paid", "sales", "billing", "cost", "finance")):
        return "commerce"
    if any(x in value for x in ("ui", "design", "visual", "mobile", "ux", "graphics", "media")):
        return "engineering"
    if any(x in value for x in ("research", "intelligence", "science", "benchmark", "evaluation")):
        return "research"
    return "engineering"


def _evolution_contract(node: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "issue": node["key"],
        "schema": "AEGIS_ISSUE_EVOLUTION_CONTRACT_V1",
        "policy": "CANDIDATE_ONLY_NO_SELF_PROMOTION",
        "baseline": "MUST_BE_MEASURED_ON_FROZEN_MATCHED_TASKS",
        "candidate_variants": ["decomposition", "algorithm", "tool_order",
                               "skill", "research_method", "workflow", "design"],
        "minimum_paired_holdout": 30,
        "sign_test_one_sided_alpha_max": 0.01,
        "safety_regression_budget": 0,
        "independent_outcome_verification": "REQUIRED",
        "source_authentication": "NOT_ESTABLISHED",
        "retain_negative_results": True,
        "rollback": "REQUIRED_BEFORE_ADMISSION",
        "authority_effect": "NONE",
        "skill_tier_effect": "NONE",
        "current_status": "NOT_EVALUATED",
    }


def compile_graph(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != {
        "repository", "issues", "complete_pages", "acquisition", "pages"
    }:
        raise ValueError("ISSUE_SNAPSHOT_SCHEMA_INVALID")
    repo = snapshot["repository"]
    _valid_repo(repo)
    if snapshot["complete_pages"] is not True or snapshot["acquisition"] not in {
        "GITHUB_READ_ONLY_API", "EXPLICIT_OFFLINE_FIXTURE"
    } or type(snapshot["pages"]) is not int or not 1 <= snapshot["pages"] <= 20:
        raise ValueError("ISSUE_SNAPSHOT_INCOMPLETE")
    source = snapshot["issues"]
    if not isinstance(source, list) or len(source) > MAX_ISSUES:
        raise ValueError("ISSUE_SNAPSHOT_SIZE_INVALID")
    entries = [_issue(item, repo) for item in source]
    entries = [x for x in entries if x is not None]
    keys = [x["number"] for x in entries]
    if len(keys) != len(set(keys)):
        raise ValueError("ISSUE_SNAPSHOT_DUPLICATE")
    known = set(keys)
    nodes = []
    edges = []
    unresolved = []
    for node in sorted(entries, key=lambda x: x["number"]):
        node["topic"] = _domain(node["title"], node["labels"])
        node["evolution"] = _evolution_contract(node)
        nodes.append(node)
        for kind, field in (("depends_on", "explicit_dependencies"),
                            ("parent", "explicit_parents"), ("related", "explicit_related")):
            for target in node[field]:
                edge = {"from": node["key"], "to": f"{repo}#{target}", "kind": kind}
                (edges if target in known else unresolved).append(edge)
    # Dependency cycles are denied: related links can be cyclic, dependencies cannot.
    deps = {x["key"]: [] for x in nodes}
    for edge in edges:
        if edge["kind"] == "depends_on":
            deps[edge["from"]].append(edge["to"])
    visiting, done = set(), set()
    def visit(k: str) -> None:
        if k in visiting:
            raise ValueError("ISSUE_DEPENDENCY_CYCLE")
        if k in done:
            return
        visiting.add(k)
        for nxt in deps[k]:
            visit(nxt)
        visiting.remove(k)
        done.add(k)
    for key in deps:
        visit(key)
    body = {"schema": SCHEMA, "repository": repo, "acquisition": snapshot["acquisition"],
            "source_coverage": "GITHUB_RESPONSE_UNAUTHENTICATED_BY_OFFLINE_COMPILER",
            "snapshot_sha256": digest(snapshot), "node_count": len(nodes),
            "nodes": nodes, "edges": sorted(edges, key=lambda e: (e["from"], e["kind"], e["to"])),
            "unresolved_references": sorted(unresolved, key=lambda e: (e["from"], e["kind"], e["to"])),
            "evolution_status": "CANDIDATES_ONLY_NO_AUTOMATIC_PROMOTION",
            "authority_effect": "NONE", "execution_effect": "NONE"}
    return {**body, "receipt_hash": digest(body)}


def spread_issue_graph(graph: Mapping[str, Any], *, source_head: str,
                       start: int = 0, limit: int = 32) -> dict[str, Any]:
    """Diffuse bounded metadata, not issue bodies or executable instructions."""
    if not isinstance(graph, Mapping) or graph.get("receipt_hash") != digest({
        k: v for k, v in graph.items() if k != "receipt_hash"
    }):
        raise ValueError("ISSUE_GRAPH_DIGEST_INVALID")
    if not isinstance(source_head, str) or not HEAD_RE.fullmatch(source_head):
        raise ValueError("ISSUE_GRAPH_SOURCE_HEAD_INVALID")
    if type(start) is not int or start < 0 or type(limit) is not int or not 1 <= limit <= 32:
        raise ValueError("ISSUE_GRAPH_SLICE_INVALID")
    nodes = graph["nodes"][start:start + limit]
    if not nodes:
        raise ValueError("ISSUE_GRAPH_SLICE_EMPTY")
    packets = []
    for i, node in enumerate(nodes):
        # Actual source record is the issue snapshot field hash, not a proof of work.
        summary = json.dumps({"issue": node["key"], "title": node["title"][:300],
                              "topic": node["topic"], "dependencies": node["explicit_dependencies"],
                              "evolution_status": "NOT_EVALUATED",
                              "authority_effect": "NONE"}, ensure_ascii=True, sort_keys=True)
        # No self-asserted code-run or competence evidence.
        routing = {"research": ("cognitive", "corpus_ingestor"),
                   "formal": ("formal", "applied_science"),
                   "security": ("security", "cybersecurity"),
                   "commerce": ("revenue", "strategy"),
                   "engineering": ("engineering", "engineering"),
                   "operations": ("operations", "platform_engineering")}
        source, origin = routing[node["topic"]]
        channel = "QUARANTINE" if "needs-operator" in node["labels"] else "CANDIDATE"
        if channel == "QUARANTINE" and source != "cognitive":
            origin = "cybersecurity"
        packets.append(EvidencePacket(source, node["topic"], origin,
                                      source_head, digest(node), start+i, summary,
                                      channel))
    routed = spread_packets(packets, ttl=5)
    return {"schema": "AEGIS_ISSUE_EVOLUTION_DENDRITE_V1",
            "graph_receipt_hash": graph["receipt_hash"], "routing": routed,
            "authority_effect": "NONE", "execution_effect": "NONE"}


def evaluate_trial(trial: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic proposal-screen. Claimed measurements are NOT authenticated."""
    keys = {"schema", "issue", "baseline", "candidate", "pre_registered_metric",
            "holdout_digest", "paired_results", "rollback_ref"}
    if not isinstance(trial, Mapping) or set(trial) != keys or trial["schema"] != EVAL_SCHEMA:
        raise ValueError("TRIAL_SCHEMA_INVALID")
    if not isinstance(trial["issue"], str) or not re.fullmatch(
        r"(?:Aegis-Omega/(?:AEGIS-OMEGA|AegisOmega)|tarikskalic33/(?:formal-conjectures|sovereign-guard))#[1-9][0-9]{0,6}",
        trial["issue"],
    ):
        raise ValueError("TRIAL_ISSUE_INVALID")
    if not isinstance(trial["baseline"], str) or not isinstance(trial["candidate"], str) or (
        trial["baseline"] == trial["candidate"] or not HEAD_RE.fullmatch(trial["baseline"])
        or not HEAD_RE.fullmatch(trial["candidate"])
    ):
        raise ValueError("TRIAL_REVISIONS_INVALID")
    if trial["pre_registered_metric"] not in {"accuracy", "task_success", "quality"}:
        raise ValueError("TRIAL_METRIC_INVALID")
    if not isinstance(trial["holdout_digest"], str) or not HEX64.fullmatch(trial["holdout_digest"]):
        raise ValueError("TRIAL_HOLDOUT_INVALID")
    if not isinstance(trial["rollback_ref"], str) or trial["rollback_ref"] != trial["baseline"]:
        raise ValueError("TRIAL_ROLLBACK_INVALID")
    rows = trial["paired_results"]
    if not isinstance(rows, list) or not 30 <= len(rows) <= 500:
        raise ValueError("TRIAL_PAIR_COUNT_INVALID")
    ids = set()
    wins = losses = ties = safety_regressions = 0
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "task_id", "baseline_score", "candidate_score", "safety_regression"
        }:
            raise ValueError("TRIAL_PAIR_SCHEMA_INVALID")
        tid = row["task_id"]
        if not isinstance(tid, str) or not 1 <= len(tid) <= 120 or tid in ids:
            raise ValueError("TRIAL_TASK_ID_INVALID")
        ids.add(tid)
        a,b = row["baseline_score"], row["candidate_score"]
        if (type(a) not in (int, float) or type(b) not in (int, float)
            or not math.isfinite(a) or not math.isfinite(b) or not 0 <= a <= 1 or not 0 <= b <= 1):
            raise ValueError("TRIAL_SCORE_INVALID")
        if type(row["safety_regression"]) is not bool:
            raise ValueError("TRIAL_SAFETY_INVALID")
        safety_regressions += int(row["safety_regression"])
        wins += b > a
        losses += b < a
        ties += b == a
    n = wins+losses
    # One-sided exact sign test; no Gaussian approximation, never confuse p with independent verification.
    p_value = sum(math.comb(n,k) for k in range(wins,n+1)) / (2**n) if n else 1.0
    passed = wins > losses and n >= 30 and p_value <= 0.01 and not safety_regressions
    body = {"schema": "AEGIS_ISSUE_EVOLUTION_SCREEN_V1",
            "issue": trial["issue"], "trial_hash": digest(trial),
            "wins": wins, "losses": losses, "ties": ties,
            "paired_count": len(rows), "safety_regressions": safety_regressions,
            "sign_test_one_sided_p": p_value,
            "candidate_screen": "NEEDS_INDEPENDENT_VERIFICATION" if passed else "RETAIN_AS_UNPROMOTED_LESSON",
            "outcome_evidence": "SELF_REPORTED_UNVERIFIED",
            "production_admission": "DENIED", "skill_promotion": "DENIED",
            "authority_effect": "NONE", "execution_effect": "NONE"}
    return {**body, "receipt_hash": digest(body)}



def evolve_issues(graph: Mapping[str, Any], trials: list[Mapping[str, Any]]) -> dict[str, Any]:
    """One bounded issue-wide learning round; retains losses, never promotes.

    Candidate generation is metadata-only until an independently executed
    implementation/benchmark exists. No model prompts or Git writes.
    """
    if (not isinstance(graph, Mapping) or graph.get("schema") != SCHEMA or
        graph.get("receipt_hash") != digest({k:v for k,v in graph.items()
                                             if k != "receipt_hash"})):
        raise ValueError("EVOLUTION_GRAPH_INVALID")
    if not isinstance(trials, list) or len(trials) > 256:
        raise ValueError("EVOLUTION_TRIALS_INVALID")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("EVOLUTION_NODES_INVALID")
    seen_issues = {node["key"] for node in nodes}
    indexed: dict[str, list[dict[str, Any]]] = {k:[] for k in seen_issues}
    seen_candidates = set()
    for raw in trials:
        verdict = evaluate_trial(raw)
        if verdict["issue"] not in indexed:
            raise ValueError("EVOLUTION_UNLINKED_ISSUE")
        fingerprint = (verdict["issue"], raw["candidate"], raw["holdout_digest"])
        if fingerprint in seen_candidates:
            raise ValueError("EVOLUTION_DUPLICATE_CANDIDATE")
        seen_candidates.add(fingerprint)
        indexed[verdict["issue"]].append({
            "candidate": raw["candidate"], "baseline": raw["baseline"],
            "screen": verdict["candidate_screen"], "screen_receipt": verdict["receipt_hash"],
            "holdout_digest": raw["holdout_digest"], "sign_test_p": verdict["sign_test_one_sided_p"],
            "wins": verdict["wins"], "losses": verdict["losses"],
            "safety_regressions": verdict["safety_regressions"],
            "source_verification": "NOT_PERFORMED",
            "authority_effect": "NONE",
        })
    states = []
    for node in nodes:
        # Each issue has its own evolving variant family, even when it has no
        # experimental outcomes yet. Do not assert that these mutations ran.
        variants = []
        for name in node["evolution"]["candidate_variants"]:
            payload = {"issue": node["key"], "kind": name,
                       "baseline_issue_body_sha256": node["body_sha256"]}
            variants.append({"proposal_id": digest(payload), "kind": name,
                             "status": "NOT_EXECUTED", "recipe": payload})
        records = sorted(indexed[node["key"]],
                         key=lambda x: (x["candidate"], x["holdout_digest"]))
        states.append({
            "issue": node["key"], "topic": node["topic"],
            "evolution_contract": node["evolution"],
            "proposals": variants,
            "history": records,  # negative outcomes preserved
            "next_action": "EXTERNAL_REVIEW_REQUIRED" if any(
                r["screen"] == "NEEDS_INDEPENDENT_VERIFICATION" for r in records
            ) else "NO_VERIFIED_IMPROVEMENT",
            "skill_tier_effect": "NONE", "authority_effect": "NONE",
        })
    # Cross-issue dendrites are explicit dependency/relationship edges only;
    # feedback NEVER gains higher epistemic status by being forwarded.
    shared = [
        {"source_issue": edge["from"], "recipient_issue": edge["to"],
         "relationship": edge["kind"],
         "message_kind": "UNVERIFIED_EVOLUTION_LESSON_POINTER",
         "source_trial_receipts": [r["screen_receipt"] for r in
                                   indexed[edge["from"]]],
         "authority_effect": "NONE"}
        for edge in graph["edges"] if indexed[edge["from"]]
    ]
    body = {"schema": "AEGIS_ISSUE_EVOLUTION_ROUND_V1",
            "graph_receipt_hash": graph["receipt_hash"], "issue_count": len(states),
            "trial_count": len(trials), "issues": states,
            "cross_issue_lessons": shared,
            "outcome_verification": "NOT_PERFORMED",
            "promotion": "DENIED",
            "execution_effect": "NONE", "authority_effect": "NONE"}
    return {**body, "receipt_hash": digest(body)}


def main() -> None:
    p=argparse.ArgumentParser(description="AEGIS issue-wide evolution metadata (non-executing)")
    sub=p.add_subparsers(dest="command",required=True)
    graph=sub.add_parser("graph")
    graph.add_argument("--snapshot",type=Path)
    graph.add_argument("--live-repo",choices=sorted(REPOS))
    graph.add_argument("--source-head")
    graph.add_argument("--start",type=int,default=0)
    graph.add_argument("--limit",type=int,default=32)
    evaluation=sub.add_parser("evaluate")
    evaluation.add_argument("--trial",type=Path,required=True)
    rounds=sub.add_parser("round")
    rounds.add_argument("--graph",type=Path,required=True)
    rounds.add_argument("--trials",type=Path,required=True)
    args=p.parse_args()
    try:
        if args.command=="graph":
            if bool(args.snapshot)==bool(args.live_repo):
                raise ValueError("REQUIRE_EXACTLY_ONE_SNAPSHOT_SOURCE")
            if args.snapshot:
                with args.snapshot.open("rb") as f:
                    raw=f.read(4_000_001)
                if len(raw)>4_000_000: raise ValueError("SNAPSHOT_FILE_TOO_LARGE")
                snapshot=json.loads(raw)
            else:
                import os
                snapshot=fetch_open_issues(args.live_repo,token=os.environ.get("GITHUB_TOKEN"))
            result=compile_graph(snapshot)
            if args.source_head:
                result={"graph":result,"dendrite":spread_issue_graph(
                    result,source_head=args.source_head,start=args.start,limit=args.limit)}
        elif args.command=="evaluate":
            with args.trial.open("rb") as f:
                raw=f.read(150_001)
            if len(raw)>150_000: raise ValueError("TRIAL_FILE_TOO_LARGE")
            result=evaluate_trial(json.loads(raw))
        else:
            with args.graph.open("rb") as f:
                g=f.read(4_000_001)
            with args.trials.open("rb") as f:
                t=f.read(2_000_001)
            if len(g)>4_000_000 or len(t)>2_000_000:
                raise ValueError("EVOLUTION_ROUND_INPUT_TOO_LARGE")
            result=evolve_issues(json.loads(g),json.loads(t))
    except (ValueError,TypeError,OSError,UnicodeError) as exc:
        p.error(type(exc).__name__+": "+str(exc))
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=="__main__":
    main()
