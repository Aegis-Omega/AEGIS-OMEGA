#!/usr/bin/env python3
"""
AEGIS Evidence DAG Reactor (AEDR-DAG).

A read-only, fail-closed repository topology analyzer. It separates Git ancestry,
semantic dependency, authority classification, evidence bindings, and conflict
relations. Its output has authority NONE and may only recommend PROPOSE_* actions.

No repository mutation API is implemented here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

SCHEMA_VERSION = "1.0.0"
GENERATOR_VERSION = "0.1.0"
RECEIPT_KIND = "AEGIS_AEDR_DAG_RECEIPT_V1"
AUTHORITY = "NONE"

VALID_COMPARE_STATUS = frozenset({"ahead", "behind", "identical", "diverged"})


@dataclass(frozen=True)
class PRNode:
    number: int
    head_sha: str
    base_sha: str
    base_ref: str
    draft: bool
    mergeable: str
    authority_domains: frozenset[str] = frozenset()
    git_parents: tuple[str, ...] = ()
    semantic_dependencies: tuple[int, ...] = ()
    evidence_receipts: tuple[str, ...] = ()


@dataclass(frozen=True)
class AncestryRelation:
    base_sha: str
    head_sha: str
    merge_base_sha: str
    ahead_by: int
    behind_by: int
    status: str

    def __post_init__(self) -> None:
        if self.status not in VALID_COMPARE_STATUS:
            raise ValueError(f"invalid Git compare status: {self.status}")
        if self.ahead_by < 0 or self.behind_by < 0:
            raise ValueError("ahead_by/behind_by must be non-negative")

    @property
    def base_is_ancestor(self) -> bool:
        return self.status in {"ahead", "identical"} and self.behind_by == 0


@dataclass(frozen=True)
class PairAncestry:
    base_pr: int
    head_pr: int
    relation: AncestryRelation


@dataclass(frozen=True)
class HeadDelta:
    pr_number: int
    from_sha: str
    to_sha: str
    changed_paths: tuple[str, ...]


@dataclass(frozen=True)
class SupersessionEvidence:
    candidate_pr: int
    replaced_pr: int
    required_behavior_replaced: frozenset[str] = frozenset()
    verified_behavior_candidate: frozenset[str] = frozenset()
    required_falsifiers_replaced: frozenset[str] = frozenset()
    verified_falsifiers_candidate: frozenset[str] = frozenset()
    unique_files_disposition_complete: bool = False
    assumptions_candidate: frozenset[str] = frozenset()
    assumptions_replaced: frozenset[str] = frozenset()
    security_exposure_candidate: int = 0
    security_exposure_replaced: int = 0
    no_authority_widening: bool = False
    exact_head_green_dominance_receipt: str = ""


@dataclass(frozen=True)
class RepositorySnapshot:
    repository: str
    main_sha: str
    nodes: tuple[PRNode, ...]
    ancestry: tuple[PairAncestry, ...] = ()
    stack_edges: tuple[tuple[int, int], ...] = ()  # (child, current parent PR)
    semantic_edges: tuple[tuple[int, int], ...] = ()  # (consumer, provider PR)
    overlap_pairs: tuple[tuple[int, int], ...] = ()
    head_deltas: tuple[HeadDelta, ...] = ()
    generated_paths: frozenset[str] = frozenset()
    branch_protection_enabled: bool | None = None
    ruleset_enforcements: tuple[str, ...] = ()
    open_pr_count: int = 0
    draft_pr_count: int = 0
    nondraft_pr_count: int = 0


@dataclass(frozen=True)
class Anomaly:
    code: str
    prs: tuple[int, ...]
    detail: str
    proposed_action: str


@dataclass(frozen=True)
class SupersessionDecision:
    established: bool
    failed_conditions: tuple[str, ...]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _node_map(snapshot: RepositorySnapshot) -> dict[int, PRNode]:
    nodes = {node.number: node for node in snapshot.nodes}
    if len(nodes) != len(snapshot.nodes):
        raise ValueError("duplicate PR number in snapshot")
    return nodes


def _relation_map(snapshot: RepositorySnapshot) -> dict[tuple[int, int], AncestryRelation]:
    relations: dict[tuple[int, int], AncestryRelation] = {}
    for pair in snapshot.ancestry:
        key = (pair.base_pr, pair.head_pr)
        if key in relations:
            raise ValueError(f"duplicate ancestry observation for {key}")
        relations[key] = pair.relation
    return relations


def evaluate_supersession(
    candidate: PRNode,
    replaced: PRNode,
    evidence: SupersessionEvidence,
) -> SupersessionDecision:
    """Return ESTABLISHED only when all explicit dominance obligations hold."""
    failed: list[str] = []
    if candidate.authority_domains != replaced.authority_domains:
        failed.append("authority_domain_mismatch")
    if not evidence.required_behavior_replaced <= evidence.verified_behavior_candidate:
        failed.append("behavior_not_dominated")
    if not evidence.required_falsifiers_replaced <= evidence.verified_falsifiers_candidate:
        failed.append("falsifiers_not_dominated")
    if not evidence.unique_files_disposition_complete:
        failed.append("unique_files_unresolved")
    if not evidence.assumptions_candidate <= evidence.assumptions_replaced:
        failed.append("assumption_regression")
    if evidence.security_exposure_candidate > evidence.security_exposure_replaced:
        failed.append("security_exposure_regression")
    if not evidence.no_authority_widening:
        failed.append("authority_widening_not_excluded")
    if not evidence.exact_head_green_dominance_receipt:
        failed.append("missing_exact_head_dominance_receipt")
    if evidence.candidate_pr != candidate.number or evidence.replaced_pr != replaced.number:
        failed.append("supersession_evidence_identity_mismatch")
    return SupersessionDecision(not failed, tuple(failed))


def analyze_snapshot(
    snapshot: RepositorySnapshot,
    supersession_claims: Sequence[SupersessionEvidence] = (),
) -> tuple[Anomaly, ...]:
    nodes = _node_map(snapshot)
    relations = _relation_map(snapshot)
    anomalies: list[Anomaly] = []

    # Git parent freshness is a Git fact, not a semantic lineage label.
    for child_number, parent_number in snapshot.stack_edges:
        child = nodes[child_number]
        parent = nodes[parent_number]
        relation = relations.get((parent_number, child_number))
        if relation is None:
            anomalies.append(Anomaly(
                "ANCESTRY_UNMEASURED",
                (parent_number, child_number),
                "current parent -> child Git ancestry has no mechanical compare observation",
                "PROPOSE_RESTACK",
            ))
            continue
        if child.base_sha != parent.head_sha and not relation.base_is_ancestor:
            anomalies.append(Anomaly(
                "STALE_PARENT",
                (parent_number, child_number),
                (
                    f"child declared base {child.base_sha} differs from current parent "
                    f"{parent.head_sha}; compare={relation.status}, "
                    f"merge_base={relation.merge_base_sha}"
                ),
                "PROPOSE_RESTACK",
            ))

    # A semantic dependency is satisfied by ancestry only if the provider's
    # current head is in the consumer's current history.
    for consumer_number, provider_number in snapshot.semantic_edges:
        relation = relations.get((provider_number, consumer_number))
        if relation is None or not relation.base_is_ancestor:
            detail = "semantic provider current head is not ancestry-bound to consumer"
            if relation is not None:
                detail += (
                    f"; compare={relation.status}, merge_base={relation.merge_base_sha}, "
                    f"ahead={relation.ahead_by}, behind={relation.behind_by}"
                )
            anomalies.append(Anomaly(
                "MISSING_SEMANTIC_JOIN",
                (provider_number, consumer_number),
                detail,
                "PROPOSE_SEMANTIC_JOIN",
            ))

    # Divergence plus declared overlap is not supersession.
    for left, right in snapshot.overlap_pairs:
        relation = relations.get((left, right)) or relations.get((right, left))
        if relation is None:
            anomalies.append(Anomaly(
                "OVERLAP_ANCESTRY_UNMEASURED",
                (left, right),
                "overlap candidate lacks mechanical Git compare observation",
                "PROPOSE_SUPERSESSION_REVIEW",
            ))
        elif relation.status == "diverged":
            anomalies.append(Anomaly(
                "DIVERGENT_OVERLAP",
                (left, right),
                (
                    f"compare=diverged, merge_base={relation.merge_base_sha}, "
                    f"ahead={relation.ahead_by}, behind={relation.behind_by}; "
                    "supersession is not inferred"
                ),
                "PROPOSE_SUPERSESSION_REVIEW",
            ))

    # Generated-only drift is still receipt drift: it changes the exact head.
    generated = snapshot.generated_paths
    for delta in snapshot.head_deltas:
        paths = frozenset(delta.changed_paths)
        if paths and paths <= generated:
            anomalies.append(Anomaly(
                "GENERATED_ONLY_HEAD_DRIFT",
                (delta.pr_number,),
                (
                    f"receipt/source head moved {delta.from_sha}->{delta.to_sha} "
                    f"through generated-only paths {sorted(paths)}"
                ),
                "PROPOSE_GENERATED_STATE_REBIND",
            ))

    # Missing evidence is explicit; never synthesize a success.
    for node in snapshot.nodes:
        if node.authority_domains and not node.evidence_receipts:
            anomalies.append(Anomaly(
                "MISSING_RECEIPT",
                (node.number,),
                "classified authority domain has no exact-head evidence receipt in this snapshot",
                "PROPOSE_EVIDENCE_REBIND",
            ))

    for claim in supersession_claims:
        candidate = nodes[claim.candidate_pr]
        replaced = nodes[claim.replaced_pr]
        decision = evaluate_supersession(candidate, replaced, claim)
        if not decision.established:
            anomalies.append(Anomaly(
                "SUPERSESSION_NOT_ESTABLISHED",
                (claim.candidate_pr, claim.replaced_pr),
                "failed=" + ",".join(decision.failed_conditions),
                "PROPOSE_SUPERSESSION_REVIEW",
            ))

    anomalies.sort(key=lambda item: (item.code, item.prs, item.detail))
    return tuple(anomalies)


def snapshot_payload(snapshot: RepositorySnapshot) -> dict[str, Any]:
    def node_payload(node: PRNode) -> dict[str, Any]:
        return {
            "number": node.number,
            "head_sha": node.head_sha,
            "base_sha": node.base_sha,
            "base_ref": node.base_ref,
            "draft": node.draft,
            "mergeable": node.mergeable,
            "authority_domains": sorted(node.authority_domains),
            "git_parents": list(node.git_parents),
            "semantic_dependencies": list(node.semantic_dependencies),
            "evidence_receipts": list(node.evidence_receipts),
        }

    return {
        "repository": snapshot.repository,
        "main_sha": snapshot.main_sha,
        "nodes": [node_payload(node) for node in sorted(snapshot.nodes, key=lambda n: n.number)],
        "ancestry": [
            {
                "base_pr": pair.base_pr,
                "head_pr": pair.head_pr,
                "relation": asdict(pair.relation),
            }
            for pair in sorted(snapshot.ancestry, key=lambda p: (p.base_pr, p.head_pr))
        ],
        "stack_edges": [list(edge) for edge in sorted(snapshot.stack_edges)],
        "semantic_edges": [list(edge) for edge in sorted(snapshot.semantic_edges)],
        "overlap_pairs": [list(edge) for edge in sorted(snapshot.overlap_pairs)],
        "head_deltas": [asdict(delta) for delta in sorted(snapshot.head_deltas, key=lambda d: d.pr_number)],
        "generated_paths": sorted(snapshot.generated_paths),
        "branch_protection_enabled": snapshot.branch_protection_enabled,
        "ruleset_enforcements": list(snapshot.ruleset_enforcements),
        "census": {
            "open": snapshot.open_pr_count,
            "draft": snapshot.draft_pr_count,
            "non_draft": snapshot.nondraft_pr_count,
        },
    }


def build_receipt(snapshot: RepositorySnapshot, anomalies: Sequence[Anomaly]) -> dict[str, Any]:
    snap = snapshot_payload(snapshot)
    anomaly_payload = [asdict(item) for item in anomalies]
    recommendations = sorted({item.proposed_action for item in anomalies})
    body: dict[str, Any] = {
        "receipt_kind": RECEIPT_KIND,
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "authority": AUTHORITY,
        "mutation_authority": "NONE",
        "snapshot_sha256": sha256_json(snap),
        "snapshot": snap,
        "anomalies": anomaly_payload,
        "recommended_actions": recommendations,
        "signature": {
            "state": "NOT_ESTABLISHED",
            "authority": "NONE",
            "note": "content-addressed only; external CI/OIDC attestation may bind this artifact",
        },
    }
    body["receipt_sha256"] = sha256_json(body)
    return body


def validate_receipt(receipt: Mapping[str, Any]) -> None:
    if receipt.get("authority") != "NONE" or receipt.get("mutation_authority") != "NONE":
        raise ValueError("AEDR receipt authority must remain NONE")
    actions = receipt.get("recommended_actions")
    if not isinstance(actions, list) or any(
        not isinstance(action, str) or not action.startswith("PROPOSE_")
        for action in actions
    ):
        raise ValueError("AEDR may emit only PROPOSE_* recommendations")
    provided = receipt.get("receipt_sha256")
    if not isinstance(provided, str):
        raise ValueError("missing receipt_sha256")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    if sha256_json(body) != provided:
        raise ValueError("receipt digest mismatch")


class GitHubLiveSnapshotBuilder:
    """Read-only GitHub REST adapter. Current SHAs are discovered, never embedded."""

    def __init__(self, repository: str, token: str | None = None) -> None:
        if repository.count("/") != 1:
            raise ValueError("repository must be owner/name")
        self.repository = repository
        self.token = token or ""

    def _request_json(self, path: str) -> Any:
        url = f"https://api.github.com/repos/{self.repository}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "aegis-aedr-dag/0.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers)
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def _try_request_json(self, path: str) -> tuple[int, Any | None]:
        try:
            return 200, self._request_json(path)
        except HTTPError as exc:
            if exc.code in {403, 404}:
                return exc.code, None
            raise

    def _open_pulls(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self._request_json(f"/pulls?state=open&per_page=100&page={page}")
            if not isinstance(batch, list):
                raise ValueError("GitHub pulls response is not a list")
            result.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return result

    def _compare(self, base_sha: str, head_sha: str) -> tuple[AncestryRelation, tuple[str, ...]]:
        data = self._request_json(f"/compare/{quote(base_sha)}...{quote(head_sha)}")
        relation = AncestryRelation(
            base_sha=base_sha,
            head_sha=head_sha,
            merge_base_sha=str(data["merge_base_commit"]["sha"]),
            ahead_by=int(data["ahead_by"]),
            behind_by=int(data["behind_by"]),
            status=str(data["status"]),
        )
        paths = tuple(sorted(str(item["filename"]) for item in data.get("files", [])))
        return relation, paths

    def build(self, semantic_manifest: Mapping[str, Any] | None = None) -> RepositorySnapshot:
        manifest = semantic_manifest or {}
        repo = self._request_json("")
        default_branch = str(repo["default_branch"])
        default_commit = self._request_json(f"/commits/{quote(default_branch)}")
        main_sha = str(default_commit["sha"])

        pulls = self._open_pulls()
        authority_map = {
            int(k): frozenset(map(str, v))
            for k, v in dict(manifest.get("authority_domains", {})).items()
        }
        semantic_map = {
            int(k): tuple(sorted(int(item) for item in v))
            for k, v in dict(manifest.get("semantic_dependencies", {})).items()
        }
        receipt_map = {
            int(k): tuple(sorted(map(str, v)))
            for k, v in dict(manifest.get("evidence_receipts", {})).items()
        }

        head_refs: dict[str, int] = {}
        node_list: list[PRNode] = []
        for item in pulls:
            number = int(item["number"])
            head_ref = str(item["head"]["ref"])
            head_refs[head_ref] = number
            node_list.append(PRNode(
                number=number,
                head_sha=str(item["head"]["sha"]),
                base_sha=str(item["base"]["sha"]),
                base_ref=str(item["base"]["ref"]),
                draft=bool(item.get("draft", False)),
                mergeable="UNKNOWN",
                authority_domains=authority_map.get(number, frozenset()),
                semantic_dependencies=semantic_map.get(number, ()),
                evidence_receipts=receipt_map.get(number, ()),
            ))

        nodes = {node.number: node for node in node_list}
        stack_edges = tuple(sorted(
            (node.number, head_refs[node.base_ref])
            for node in node_list
            if node.base_ref in head_refs and head_refs[node.base_ref] != node.number
        ))
        semantic_edges = tuple(sorted(
            (consumer, provider)
            for consumer, providers in semantic_map.items()
            if consumer in nodes
            for provider in providers
            if provider in nodes
        ))
        overlap_pairs = tuple(sorted(
            tuple(map(int, pair))
            for pair in manifest.get("overlap_pairs", [])
            if len(pair) == 2 and int(pair[0]) in nodes and int(pair[1]) in nodes
        ))

        pair_set = {
            (parent, child) for child, parent in stack_edges
        } | {
            (provider, consumer) for consumer, provider in semantic_edges
        } | set(overlap_pairs)

        ancestry: list[PairAncestry] = []
        for base_pr, head_pr in sorted(pair_set):
            relation, _ = self._compare(nodes[base_pr].head_sha, nodes[head_pr].head_sha)
            ancestry.append(PairAncestry(base_pr, head_pr, relation))

        generated_paths = frozenset(map(str, manifest.get("generated_paths", [])))
        receipt_heads = {int(k): str(v) for k, v in dict(manifest.get("receipt_heads", {})).items()}
        deltas: list[HeadDelta] = []
        for pr_number, old_sha in sorted(receipt_heads.items()):
            node = nodes.get(pr_number)
            if node is None or old_sha == node.head_sha:
                continue
            _, paths = self._compare(old_sha, node.head_sha)
            deltas.append(HeadDelta(pr_number, old_sha, node.head_sha, paths))

        protection_code, _ = self._try_request_json(
            f"/branches/{quote(default_branch)}/protection"
        )
        protection_enabled: bool | None
        if protection_code == 200:
            protection_enabled = True
        elif protection_code == 404:
            protection_enabled = False
        else:
            protection_enabled = None

        _, rulesets_data = self._try_request_json("/rulesets")
        enforcements: tuple[str, ...] = ()
        if isinstance(rulesets_data, list):
            enforcements = tuple(sorted(str(item.get("enforcement", "unknown")) for item in rulesets_data))

        draft_count = sum(1 for node in node_list if node.draft)
        return RepositorySnapshot(
            repository=self.repository,
            main_sha=main_sha,
            nodes=tuple(sorted(node_list, key=lambda n: n.number)),
            ancestry=tuple(ancestry),
            stack_edges=stack_edges,
            semantic_edges=semantic_edges,
            overlap_pairs=overlap_pairs,
            head_deltas=tuple(deltas),
            generated_paths=generated_paths,
            branch_protection_enabled=protection_enabled,
            ruleset_enforcements=enforcements,
            open_pr_count=len(node_list),
            draft_pr_count=draft_count,
            nondraft_pr_count=len(node_list) - draft_count,
        )


def snapshot_from_json(data: Mapping[str, Any]) -> RepositorySnapshot:
    nodes = tuple(PRNode(
        number=int(item["number"]),
        head_sha=str(item["head_sha"]),
        base_sha=str(item["base_sha"]),
        base_ref=str(item["base_ref"]),
        draft=bool(item["draft"]),
        mergeable=str(item.get("mergeable", "UNKNOWN")),
        authority_domains=frozenset(map(str, item.get("authority_domains", []))),
        git_parents=tuple(map(str, item.get("git_parents", []))),
        semantic_dependencies=tuple(map(int, item.get("semantic_dependencies", []))),
        evidence_receipts=tuple(map(str, item.get("evidence_receipts", []))),
    ) for item in data.get("nodes", []))
    ancestry = tuple(PairAncestry(
        base_pr=int(item["base_pr"]),
        head_pr=int(item["head_pr"]),
        relation=AncestryRelation(**item["relation"]),
    ) for item in data.get("ancestry", []))
    deltas = tuple(HeadDelta(
        pr_number=int(item["pr_number"]),
        from_sha=str(item["from_sha"]),
        to_sha=str(item["to_sha"]),
        changed_paths=tuple(map(str, item.get("changed_paths", []))),
    ) for item in data.get("head_deltas", []))
    census = dict(data.get("census", {}))
    return RepositorySnapshot(
        repository=str(data["repository"]),
        main_sha=str(data["main_sha"]),
        nodes=nodes,
        ancestry=ancestry,
        stack_edges=tuple(tuple(map(int, edge)) for edge in data.get("stack_edges", [])),
        semantic_edges=tuple(tuple(map(int, edge)) for edge in data.get("semantic_edges", [])),
        overlap_pairs=tuple(tuple(map(int, edge)) for edge in data.get("overlap_pairs", [])),
        head_deltas=deltas,
        generated_paths=frozenset(map(str, data.get("generated_paths", []))),
        branch_protection_enabled=data.get("branch_protection_enabled"),
        ruleset_enforcements=tuple(map(str, data.get("ruleset_enforcements", []))),
        open_pr_count=int(census.get("open", len(nodes))),
        draft_pr_count=int(census.get("draft", sum(1 for n in nodes if n.draft))),
        nondraft_pr_count=int(census.get("non_draft", sum(1 for n in nodes if not n.draft))),
    )


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only AEGIS Repository DAG Consolidation Reactor")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--snapshot", type=Path, help="analyze a deterministic snapshot JSON")
    mode.add_argument("--repo", help="build a live GitHub snapshot for owner/name")
    parser.add_argument("--semantic-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if args.snapshot:
        snapshot = snapshot_from_json(_load_json(args.snapshot))
    else:
        manifest = _load_json(args.semantic_manifest) if args.semantic_manifest else {}
        snapshot = GitHubLiveSnapshotBuilder(
            args.repo,
            token=os.environ.get("GITHUB_TOKEN"),
        ).build(manifest)

    anomalies = analyze_snapshot(snapshot)
    receipt = build_receipt(snapshot, anomalies)
    validate_receipt(receipt)
    rendered = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
