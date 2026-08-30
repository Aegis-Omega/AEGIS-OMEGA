#!/usr/bin/env python3
"""Generate provenance_census_v1.json from the GitHub remote.

This script is evidence acquisition only. It never merges, deletes, rebases, or
moves refs. It fails closed if pagination, counts, or critical exact-head facts
cannot be established.

The source snapshot was frozen before the integration branch and later research
children existed.  Therefore v1 keeps two quantities separate:

- baseline/source state: the original 150 heads and 95 open PRs;
- live state: baseline plus explicitly enumerated post-baseline refs/PRs.

A new, unknown branch or PR is *not* silently subtracted.  It causes census
drift until it is classified.  This preserves the frozen census while still
allowing known child research lanes to coexist with the integration branch.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

REPO = "Aegis-Omega/AEGIS-OMEGA"
EXPECTED_BASE = "d83a9c6b35d4bed6bbe0542b5492a84ad7a4795f"
EXPECTED_MAIN = "a34d664d66ae9f7c2e729cd4ccb07b74130c660f"
INTEGRATION_BRANCH = "integration/aegis-universal-intelligence-rh-v1"
INTEGRATION_PR_NUMBER = 342

# These refs/PRs were created after the frozen 150/95 source snapshot and are
# explicitly provenance-classified.  Unknown additions remain fail-closed.
POST_BASELINE_BRANCHES = frozenset(
    {
        INTEGRATION_BRANCH,
        "research/phi-finite-section-congruence-v1",
    }
)
POST_BASELINE_PRS = frozenset({INTEGRATION_PR_NUMBER, 344})

EXPECTED_BASELINE_HEAD_COUNT = 150
EXPECTED_LIVE_HEAD_COUNT = 152
EXPECTED_OPEN_PRS = 95
EXPECTED_DRAFT_PRS = 73
EXPECTED_NONDRAFT_PRS = 22
EXPECTED_LIVE_OPEN_PRS = 97
EXPECTED_LIVE_DRAFT_PRS = 75
EXPECTED_LIVE_NONDRAFT_PRS = 22


@dataclass(frozen=True)
class RemoteHead:
    name: str
    sha: str
    protected: bool


def partition_census_heads(heads: list[RemoteHead]) -> tuple[list[RemoteHead], list[RemoteHead]]:
    """Return (frozen_source_heads, current_live_heads) deterministically."""
    live = sorted(heads, key=lambda head: head.name)
    names = {head.name for head in live}
    missing = sorted(POST_BASELINE_BRANCHES - names)
    if missing:
        raise RuntimeError(f"classified post-baseline ref missing: {missing}")
    baseline = [head for head in live if head.name not in POST_BASELINE_BRANCHES]
    return baseline, live


def partition_census_prs(
    prs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (frozen_source_prs, current_live_prs) with classified children isolated."""
    live = sorted(prs, key=lambda pr: int(pr["number"]))
    numbers = {int(pr["number"]) for pr in live}
    missing = sorted(POST_BASELINE_PRS - numbers)
    if missing:
        raise RuntimeError(f"classified post-baseline PR missing: {missing}")
    baseline = [pr for pr in live if int(pr["number"]) not in POST_BASELINE_PRS]
    return baseline, live


def _request_json(url: str, token: str | None) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "aegis-provenance-census-v1",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"GitHub API returned {response.status}: {url}")
        return json.load(response)


def _paginate(path: str, token: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        sep = "&" if "?" in path else "?"
        url = f"https://api.github.com/repos/{REPO}/{path}{sep}per_page=100&page={page}"
        batch = _request_json(url, token)
        if not isinstance(batch, list):
            raise RuntimeError(f"expected list response for {path}")
        rows.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        if page > 20:
            raise RuntimeError("pagination safety bound exceeded")
    return rows


def _pull_requests(token: str | None) -> list[dict[str, Any]]:
    return _paginate("pulls?state=open", token)


def _draft_counts(prs: list[dict[str, Any]]) -> tuple[int, int]:
    drafts = sum(1 for pr in prs if pr.get("draft") is True)
    return drafts, len(prs) - drafts


def generate(token: str | None) -> dict[str, Any]:
    branches = _paginate("branches", token)
    observed_heads = [
        RemoteHead(
            name=row["name"],
            sha=row["commit"]["sha"],
            protected=bool(row.get("protected", False)),
        )
        for row in branches
    ]
    baseline_heads, live_heads = partition_census_heads(observed_heads)

    observed_prs = _pull_requests(token)
    baseline_prs, live_prs = partition_census_prs(observed_prs)
    drafts, nondrafts = _draft_counts(baseline_prs)
    live_drafts, live_nondrafts = _draft_counts(live_prs)

    main = next((h for h in live_heads if h.name == "main"), None)
    if main is None:
        raise RuntimeError("main branch missing from census")
    if main.sha != EXPECTED_MAIN:
        raise RuntimeError(f"canonical main drift: {main.sha} != {EXPECTED_MAIN}")
    if len(baseline_heads) != EXPECTED_BASELINE_HEAD_COUNT:
        raise RuntimeError(
            f"baseline remote-head count drift: {len(baseline_heads)} != {EXPECTED_BASELINE_HEAD_COUNT}"
        )
    if len(live_heads) != EXPECTED_LIVE_HEAD_COUNT:
        raise RuntimeError(
            f"live remote-head count drift: {len(live_heads)} != {EXPECTED_LIVE_HEAD_COUNT}"
        )
    if (len(baseline_prs), drafts, nondrafts) != (
        EXPECTED_OPEN_PRS,
        EXPECTED_DRAFT_PRS,
        EXPECTED_NONDRAFT_PRS,
    ):
        raise RuntimeError(
            "baseline open-PR census drift: "
            f"{(len(baseline_prs), drafts, nondrafts)} != "
            f"{(EXPECTED_OPEN_PRS, EXPECTED_DRAFT_PRS, EXPECTED_NONDRAFT_PRS)}"
        )
    if (len(live_prs), live_drafts, live_nondrafts) != (
        EXPECTED_LIVE_OPEN_PRS,
        EXPECTED_LIVE_DRAFT_PRS,
        EXPECTED_LIVE_NONDRAFT_PRS,
    ):
        raise RuntimeError(
            "live open-PR census drift: "
            f"{(len(live_prs), live_drafts, live_nondrafts)} != "
            f"{(EXPECTED_LIVE_OPEN_PRS, EXPECTED_LIVE_DRAFT_PRS, EXPECTED_LIVE_NONDRAFT_PRS)}"
        )

    integration_head = next(head for head in live_heads if head.name == INTEGRATION_BRANCH)
    integration_pr = next(pr for pr in live_prs if int(pr["number"]) == INTEGRATION_PR_NUMBER)
    post_baseline_heads = [
        asdict(head) for head in live_heads if head.name in POST_BASELINE_BRANCHES
    ]
    post_baseline_prs = [
        {
            "number": int(pr["number"]),
            "draft": bool(pr.get("draft", False)),
            "head_ref": pr["head"]["ref"],
            "head_sha": pr["head"]["sha"],
            "base_ref": pr["base"]["ref"],
            "base_sha": pr["base"]["sha"],
        }
        for pr in live_prs
        if int(pr["number"]) in POST_BASELINE_PRS
    ]

    return {
        "schema_version": "1.0.0",
        "repository": REPO,
        "base_ref": EXPECTED_BASE,
        "canonical_main_head": EXPECTED_MAIN,
        "census_summary": {
            "total_remote_heads": len(baseline_heads),
            "live_remote_heads_total": len(live_heads),
            "post_baseline_refs_excluded_from_baseline": sorted(POST_BASELINE_BRANCHES),
            "open_prs_total": len(baseline_prs),
            "open_prs_draft": drafts,
            "open_prs_nondraft": nondrafts,
            "live_open_prs_total": len(live_prs),
            "live_open_prs_draft": live_drafts,
            "live_open_prs_nondraft": live_nondrafts,
            "post_baseline_prs_excluded_from_baseline": sorted(POST_BASELINE_PRS),
        },
        "integration_head": asdict(integration_head),
        "integration_pr": {
            "number": int(integration_pr["number"]),
            "draft": bool(integration_pr.get("draft", False)),
            "head_sha": integration_pr["head"]["sha"],
            "base_sha": integration_pr["base"]["sha"],
        },
        "post_baseline_heads": post_baseline_heads,
        "post_baseline_prs": post_baseline_prs,
        "critical_dispositions": {
            "PR_309": {
                "exact_head": "1406aacca95fef02a942621a7060e0b6b14a5809",
                "mergeability": "MERGEABLE",
                "disposition": "DO_NOT_MERGE_DIRECTLY",
                "reason": "Effect path is superseded/evolved by PR #334; direct merge risks regression of the verified resident execution/effect loop.",
            },
            "PR_308": {
                "exact_head": "7972eb16e85cc6ea9d0983b33475e6e77adfe3c8",
                "disposition": "RETAIN_BRANCH_NAME_NORMALIZATION_ONLY",
                "reason": "Removes branch-name divergence from .claude.json; parent_state_hash divergence remains structural and unresolved.",
            },
            "PR_303": {
                "exact_head": "7c94ba577f62e5a9fcd96b9b5ae4859d106db081",
                "disposition": "EXTRACT_ALGEBRAIC_KERNEL",
                "reason": "Contains exact-rational finite certificates and LDLT kernel; do not inherit stale prose head claims.",
            },
            "PR_307": {
                "exact_head": "41ad4ea70c09eb2b88c8457d3b7185c5db4f986a",
                "disposition": "EXTRACT_CONSTRUCTIVE_ORDER",
                "reason": "Machine-binds abstract finite-to-limit order; concrete classical Weil semantics remain separate.",
            },
            "PR_335": {
                "exact_head": "39e0f92507bee7ca0b78be527af1de567b863504",
                "disposition": "EXTRACT_QFORM_EVALUATOR",
                "reason": "Proof-carrying finite evaluator with analytic obligations explicitly OPEN.",
            },
            "PR_338": {
                "exact_head": "97063f9d74c24f3889530cdc366e60f31b3edd48",
                "disposition": "EXTRACT_QUOTIENT_KERNEL",
                "reason": "Exact-rational quotient-stability kernel is machine-bound; constructive-real transport remains OPEN.",
            },
            "PR_339": {
                "exact_head": "2f73e0b7db5037f2640ad1d8ee4128e320709a38",
                "disposition": "RETAIN_EXACT_SOURCE_RECEIPT_BOUNDARY",
                "reason": "Cross-runtime exact-source receipt is useful provenance evidence; aggregate remains blocked by an unbound local component and carries no RH authority.",
            },
            "PR_341": {
                "exact_head": "63b566c7fe7830cecf906bf893bf9615d920fc7c",
                "disposition": "RETAIN_INDEPENDENT_RECONSTRUCTION",
                "reason": "Independently reconstructs finite prime-phase statements and records the index-set boundary; reported historical integration artefacts remain unreachable.",
            },
            "PR_344": {
                "exact_head": "eea6fe818236246b807d3ed707b6bf3f4133c149",
                "disposition": "PARALLEL_EXACT_FINITE_CONGRUENCE_FALSIFIER",
                "reason": "Child research lane from integration@b80139b; exact finite-coordinate congruence only, with no global Weil or RH authority.",
            },
        },
        "remote_heads": [asdict(head) for head in baseline_heads],
        "authority_boundary": {
            "model_output_can_mint_authority": False,
            "agent_swarm_can_mint_authority": False,
            "self_improvement_can_mint_authority": False,
            "required_chain": "DecisionReceipt -> ExecutionReceipt -> EffectObservation -> EffectReceipt -> CompleteVerification -> AtomicAdmission",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/audits/provenance_census_v1.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    payload = generate(token)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.check:
        try:
            with open(args.output, "r", encoding="utf-8") as handle:
                current = handle.read()
        except FileNotFoundError:
            print(f"missing census: {args.output}", file=sys.stderr)
            return 2
        if current != rendered:
            print("provenance census is stale", file=sys.stderr)
            return 2
        print("provenance census verified")
        return 0
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(rendered)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
