#!/usr/bin/env python3
"""AEGIS Evidence DAG Reactor (AEDR-DAG).

Read-only, fail-closed analysis of the typed multilayer repository DAG
G_AEGIS = (V, E_git, E_sem, E_auth, E_evidence, E_conflict).

AEDR never merges, closes, rebases, or grants canonical authority. Its output
has authority NONE and may contain only PROPOSE_* recommendations.
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

SCHEMA_VERSION = "1.1.0"
GENERATOR_VERSION = "0.2.0"
RECEIPT_KIND = "AEGIS_AEDR_DAG_RECEIPT_V1"
AUTHORITY = "NONE"
VALID_COMPARE_STATUS = frozenset({"ahead", "behind", "identical", "diverged"})
VALID_CONFLICT_KINDS = frozenset({"OVERLAP", "STALE_ANCESTRY", "COMPETING_IMPLEMENTATION"})
VALID_FILE_DISPOSITIONS = frozenset({"BYTE_EQUIVALENT", "SEMANTIC_REPLACEMENT", "OPEN_OBLIGATION"})


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
class GitEdge:
    base_pr: int
    head_pr: int
    relation: AncestryRelation


@dataclass(frozen=True)
class SemanticEdge:
    consumer_pr: int
    provider_pr: int
    dependency_kind: str = "REQUIRES"
    requires_ancestry_binding: bool = True


@dataclass(frozen=True)
class AuthorityEdge:
    source_pr: int
    target_pr: int
    authority_domain: str
    allowed: bool
    receipt_id: str = ""


@dataclass(frozen=True)
class EvidenceEdge:
    pr_number: int
    head_sha: str
    receipt_id: str
    state: str


@dataclass(frozen=True)
class ConflictEdge:
    left_pr: int
    right_pr: int
    kind: str = "OVERLAP"

    def __post_init__(self) -> None:
        if self.kind not in VALID_CONFLICT_KINDS:
            raise ValueError(f"invalid conflict kind: {self.kind}")


@dataclass(frozen=True)
class HeadDelta:
    pr_number: int
    from_sha: str
    to_sha: str
    changed_paths: tuple[str, ...]


@dataclass(frozen=True)
class FileDisposition:
    path: str
    disposition: str
    receipt_id: str = ""

    def __post_init__(self) -> None:
        if self.disposition not in VALID_FILE_DISPOSITIONS:
            raise ValueError(f"invalid file disposition: {self.disposition}")


@dataclass(frozen=True)
class DominanceReceipt:
    receipt_id: str
    candidate_head_sha: str
    replaced_head_sha: str
    conclusion: str
    authority: str = "NONE"


@dataclass(frozen=True)
class SupersessionEvidence:
    candidate_pr: int
    replaced_pr: int
    required_behavior_replaced: frozenset[str] = frozenset()
    verified_behavior_candidate: frozenset[str] = frozenset()
    required_falsifiers_replaced: frozenset[str] = frozenset()
    verified_falsifiers_candidate: frozenset[str] = frozenset()
    unique_files_replaced: frozenset[str] = frozenset()
    file_dispositions: tuple[FileDisposition, ...] = ()
    assumptions_candidate: frozenset[str] = frozenset()
    assumptions_replaced: frozenset[str] = frozenset()
    security_exposure_candidate: int = 0
    security_exposure_replaced: int = 0
    no_authority_widening: bool = False
    dominance_receipt: DominanceReceipt | None = None


@dataclass(frozen=True)
class RepositorySnapshot:
    repository: str
    main_sha: str
    nodes: tuple[PRNode, ...]
    git_edges: tuple[GitEdge, ...] = ()
    semantic_edges: tuple[SemanticEdge, ...] = ()
    authority_edges: tuple[AuthorityEdge, ...] = ()
    evidence_edges: tuple[EvidenceEdge, ...] = ()
    conflict_edges: tuple[ConflictEdge, ...] = ()
    stack_edges: tuple[tuple[int, int], ...] = ()  # (child, current parent PR)
    head_deltas: tuple[HeadDelta, ...] = ()
    generated_paths: frozenset[str] = frozenset()
    branch_protection_enabled: bool | None = None
    ruleset_enforcements: tuple[str, ...] = ()
    census_scope: str = "UNSPECIFIED"
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
    open_obligations: tuple[str, ...] = ()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _node_map(snapshot: RepositorySnapshot) -> dict[int, PRNode]:
    nodes = {node.number: node for node in snapshot.nodes}
    if len(nodes) != len(snapshot.nodes):
        raise ValueError("duplicate PR number in snapshot")
    return nodes


def _git_map(snapshot: RepositorySnapshot) -> dict[tuple[int, int], AncestryRelation]:
    relations: dict[tuple[int, int], AncestryRelation] = {}
    for edge in snapshot.git_edges:
        key = (edge.base_pr, edge.head_pr)
        if key in relations:
            raise ValueError(f"duplicate Git observation for {key}")
        relations[key] = edge.relation
    return relations


def _validate_references(snapshot: RepositorySnapshot) -> None:
    node_ids = set(_node_map(snapshot))
    refs: list[tuple[str, tuple[int, ...]]] = []
    refs.extend(("git", (e.base_pr, e.head_pr)) for e in snapshot.git_edges)
    refs.extend(("semantic", (e.consumer_pr, e.provider_pr)) for e in snapshot.semantic_edges)
    refs.extend(("authority", (e.source_pr, e.target_pr)) for e in snapshot.authority_edges)
    refs.extend(("evidence", (e.pr_number,)) for e in snapshot.evidence_edges)
    refs.extend(("conflict", (e.left_pr, e.right_pr)) for e in snapshot.conflict_edges)
    refs.extend(("stack", tuple(edge)) for edge in snapshot.stack_edges)
    refs.extend(("head_delta", (e.pr_number,)) for e in snapshot.head_deltas)
    for kind, ids in refs:
        missing = sorted(set(ids) - node_ids)
        if missing:
            raise ValueError(f"{kind} edge references unknown PRs: {missing}")


def evaluate_supersession(candidate: PRNode, replaced: PRNode, evidence: SupersessionEvidence) -> SupersessionDecision:
    """Establish SUPERSEDES only when all eight explicit dominance obligations hold."""
    failed: list[str] = []
    if candidate.authority_domains != replaced.authority_domains:
        failed.append("authority_domain_mismatch")
    if not evidence.required_behavior_replaced <= evidence.verified_behavior_candidate:
        failed.append("behavior_not_dominated")
    if not evidence.required_falsifiers_replaced <= evidence.verified_falsifiers_candidate:
        failed.append("falsifiers_not_dominated")

    dispositions: dict[str, FileDisposition] = {}
    for item in evidence.file_dispositions:
        if item.path in dispositions:
            failed.append(f"duplicate_file_disposition:{item.path}")
        dispositions[item.path] = item
        if item.disposition == "SEMANTIC_REPLACEMENT" and not item.receipt_id:
            failed.append(f"semantic_replacement_without_receipt:{item.path}")
    if set(dispositions) != set(evidence.unique_files_replaced):
        failed.append("unique_files_unresolved")

    if not evidence.assumptions_candidate <= evidence.assumptions_replaced:
        failed.append("assumption_regression")
    if evidence.security_exposure_candidate > evidence.security_exposure_replaced:
        failed.append("security_exposure_regression")
    if not evidence.no_authority_widening:
        failed.append("authority_widening_not_excluded")

    dominance = evidence.dominance_receipt
    if dominance is None:
        failed.append("missing_exact_head_dominance_receipt")
    else:
        if dominance.conclusion != "SUCCESS":
            failed.append("dominance_receipt_not_green")
        if dominance.candidate_head_sha != candidate.head_sha:
            failed.append("dominance_receipt_candidate_head_mismatch")
        if dominance.replaced_head_sha != replaced.head_sha:
            failed.append("dominance_receipt_replaced_head_mismatch")
        if dominance.authority != "NONE":
            failed.append("dominance_receipt_authority_widening")
    if evidence.candidate_pr != candidate.number or evidence.replaced_pr != replaced.number:
        failed.append("supersession_evidence_identity_mismatch")

    open_obligations = tuple(sorted(item.path for item in evidence.file_dispositions if item.disposition == "OPEN_OBLIGATION"))
    return SupersessionDecision(not failed, tuple(failed), open_obligations)


def analyze_snapshot(snapshot: RepositorySnapshot, supersession_claims: Sequence[SupersessionEvidence] = ()) -> tuple[Anomaly, ...]:
    _validate_references(snapshot)
    nodes = _node_map(snapshot)
    relations = _git_map(snapshot)
    anomalies: list[Anomaly] = []

    # E_git: parent freshness is a measured ancestry fact, never a lineage label heuristic.
    for child_number, parent_number in snapshot.stack_edges:
        child, parent = nodes[child_number], nodes[parent_number]
        relation = relations.get((parent_number, child_number))
        if relation is None:
            anomalies.append(Anomaly("ANCESTRY_UNMEASURED", (parent_number, child_number), "current parent -> child Git ancestry has no mechanical compare observation", "PROPOSE_RESTACK"))
            continue
        if child.base_sha != parent.head_sha and not relation.base_is_ancestor:
            anomalies.append(Anomaly("STALE_PARENT", (parent_number, child_number), f"child declared base {child.base_sha} differs from current parent {parent.head_sha}; compare={relation.status}, merge_base={relation.merge_base_sha}", "PROPOSE_RESTACK"))

    # E_sem: ancestry binding is explicit per semantic edge.
    for edge in snapshot.semantic_edges:
        if not edge.requires_ancestry_binding:
            continue
        relation = relations.get((edge.provider_pr, edge.consumer_pr))
        if relation is None or not relation.base_is_ancestor:
            detail = f"{edge.dependency_kind}: semantic provider current head is not ancestry-bound to consumer"
            if relation is not None:
                detail += f"; compare={relation.status}, merge_base={relation.merge_base_sha}, ahead={relation.ahead_by}, behind={relation.behind_by}"
            anomalies.append(Anomaly("MISSING_SEMANTIC_JOIN", (edge.provider_pr, edge.consumer_pr), detail, "PROPOSE_SEMANTIC_JOIN"))

    # E_auth: AEDR records authority bridges but cannot mint their authorization.
    for edge in snapshot.authority_edges:
        if edge.allowed and not edge.receipt_id:
            anomalies.append(Anomaly("UNBOUND_AUTHORITY_TRANSFER", (edge.source_pr, edge.target_pr), f"allowed authority transfer for {edge.authority_domain} has no receipt", "PROPOSE_SECURITY_REVIEW"))

    # E_evidence: only SUCCESS bound to the live exact head counts as current green evidence.
    current_green: set[int] = set()
    for edge in snapshot.evidence_edges:
        node = nodes[edge.pr_number]
        if edge.head_sha != node.head_sha:
            anomalies.append(Anomaly("STALE_EVIDENCE_BINDING", (edge.pr_number,), f"receipt {edge.receipt_id} binds {edge.head_sha}, live head is {node.head_sha}", "PROPOSE_EVIDENCE_REBIND"))
        elif edge.state.upper() == "SUCCESS":
            current_green.add(edge.pr_number)

    # E_conflict: divergence plus overlap is not supersession.
    for edge in snapshot.conflict_edges:
        relation = relations.get((edge.left_pr, edge.right_pr)) or relations.get((edge.right_pr, edge.left_pr))
        if relation is None:
            anomalies.append(Anomaly("CONFLICT_ANCESTRY_UNMEASURED", (edge.left_pr, edge.right_pr), f"{edge.kind} conflict lacks mechanical Git compare observation", "PROPOSE_SUPERSESSION_REVIEW"))
        elif edge.kind in {"OVERLAP", "COMPETING_IMPLEMENTATION"} and relation.status == "diverged":
            anomalies.append(Anomaly("DIVERGENT_OVERLAP", (edge.left_pr, edge.right_pr), f"{edge.kind}: compare=diverged, merge_base={relation.merge_base_sha}, ahead={relation.ahead_by}, behind={relation.behind_by}; supersession is not inferred", "PROPOSE_SUPERSESSION_REVIEW"))

    # Generated-only drift changes exact-head identity without asserting semantic drift.
    for delta in snapshot.head_deltas:
        paths = frozenset(delta.changed_paths)
        if paths and paths <= snapshot.generated_paths:
            anomalies.append(Anomaly("GENERATED_ONLY_HEAD_DRIFT", (delta.pr_number,), f"head moved {delta.from_sha}->{delta.to_sha} through generated-only paths {sorted(paths)}; prior exact-head receipts require rebind", "PROPOSE_GENERATED_STATE_REBIND"))

    for node in snapshot.nodes:
        if node.authority_domains and node.number not in current_green:
            anomalies.append(Anomaly("MISSING_CURRENT_HEAD_GREEN_RECEIPT", (node.number,), "classified authority domain has no SUCCESS evidence bound to the live head", "PROPOSE_EVIDENCE_REBIND"))

    for claim in supersession_claims:
        decision = evaluate_supersession(nodes[claim.candidate_pr], nodes[claim.replaced_pr], claim)
        if not decision.established:
            anomalies.append(Anomaly("SUPERSESSION_NOT_ESTABLISHED", (claim.candidate_pr, claim.replaced_pr), "failed=" + ",".join(decision.failed_conditions), "PROPOSE_SUPERSESSION_REVIEW"))

    anomalies.sort(key=lambda item: (item.code, item.prs, item.detail))
    return tuple(anomalies)


def snapshot_payload(snapshot: RepositorySnapshot) -> dict[str, Any]:
    def node_payload(node: PRNode) -> dict[str, Any]:
        return {"number": node.number, "head_sha": node.head_sha, "base_sha": node.base_sha, "base_ref": node.base_ref, "draft": node.draft, "mergeable": node.mergeable, "authority_domains": sorted(node.authority_domains), "git_parents": list(node.git_parents), "semantic_dependencies": list(node.semantic_dependencies), "evidence_receipts": list(node.evidence_receipts)}

    return {
        "repository": snapshot.repository,
        "main_sha": snapshot.main_sha,
        "nodes": [node_payload(node) for node in sorted(snapshot.nodes, key=lambda n: n.number)],
        "edges": {
            "E_git": [{"base_pr": edge.base_pr, "head_pr": edge.head_pr, "relation": asdict(edge.relation)} for edge in sorted(snapshot.git_edges, key=lambda e: (e.base_pr, e.head_pr))],
            "E_sem": [asdict(edge) for edge in sorted(snapshot.semantic_edges, key=lambda e: (e.consumer_pr, e.provider_pr, e.dependency_kind))],
            "E_auth": [asdict(edge) for edge in sorted(snapshot.authority_edges, key=lambda e: (e.source_pr, e.target_pr, e.authority_domain))],
            "E_evidence": [asdict(edge) for edge in sorted(snapshot.evidence_edges, key=lambda e: (e.pr_number, e.head_sha, e.receipt_id))],
            "E_conflict": [asdict(edge) for edge in sorted(snapshot.conflict_edges, key=lambda e: (e.left_pr, e.right_pr, e.kind))],
        },
        "stack_edges": [list(edge) for edge in sorted(snapshot.stack_edges)],
        "head_deltas": [asdict(delta) for delta in sorted(snapshot.head_deltas, key=lambda d: d.pr_number)],
        "generated_paths": sorted(snapshot.generated_paths),
        "branch_protection_enabled": snapshot.branch_protection_enabled,
        "ruleset_enforcements": list(snapshot.ruleset_enforcements),
        "census": {"scope": snapshot.census_scope, "open": snapshot.open_pr_count, "draft": snapshot.draft_pr_count, "non_draft": snapshot.nondraft_pr_count},
    }


def build_receipt(snapshot: RepositorySnapshot, anomalies: Sequence[Anomaly]) -> dict[str, Any]:
    snap = snapshot_payload(snapshot)
    body: dict[str, Any] = {
        "receipt_kind": RECEIPT_KIND,
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "authority": AUTHORITY,
        "mutation_authority": "NONE",
        "graph_model": "TYPED_MULTILAYER_DAG",
        "snapshot_sha256": sha256_json(snap),
        "snapshot": snap,
        "anomalies": [asdict(item) for item in anomalies],
        "recommended_actions": sorted({item.proposed_action for item in anomalies}),
        "signature": {"state": "NOT_ESTABLISHED", "authority": "NONE", "note": "content-addressed only; external CI/OIDC attestation may prove artifact provenance but cannot grant AEDR mutation/admission authority"},
    }
    body["receipt_sha256"] = sha256_json(body)
    return body


def validate_receipt(receipt: Mapping[str, Any]) -> None:
    if receipt.get("authority") != "NONE" or receipt.get("mutation_authority") != "NONE":
        raise ValueError("AEDR receipt authority must remain NONE")
    actions = receipt.get("recommended_actions")
    if not isinstance(actions, list) or any(not isinstance(action, str) or not action.startswith("PROPOSE_") for action in actions):
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
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "aegis-aedr-dag/0.2.0"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        with urlopen(Request(url, headers=headers), timeout=30) as response:
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
                return result
            page += 1

    def _compare(self, base_sha: str, head_sha: str) -> tuple[AncestryRelation, tuple[str, ...]]:
        data = self._request_json(f"/compare/{quote(base_sha, safe='')}...{quote(head_sha, safe='')}")
        relation = AncestryRelation(base_sha, head_sha, str(data["merge_base_commit"]["sha"]), int(data["ahead_by"]), int(data["behind_by"]), str(data["status"]))
        return relation, tuple(sorted(str(item["filename"]) for item in data.get("files", [])))

    def build(self, semantic_manifest: Mapping[str, Any] | None = None) -> RepositorySnapshot:
        manifest = semantic_manifest or {}
        repo = self._request_json("")
        default_branch = str(repo["default_branch"])
        main_sha = str(self._request_json(f"/commits/{quote(default_branch, safe='')}")["sha"])
        pulls = self._open_pulls()
        authority_map = {int(k): frozenset(map(str, v)) for k, v in dict(manifest.get("authority_domains", {})).items()}
        semantic_map = {int(k): tuple(sorted(int(item) for item in v)) for k, v in dict(manifest.get("semantic_dependencies", {})).items()}
        receipt_labels = {int(k): tuple(sorted(map(str, v))) for k, v in dict(manifest.get("evidence_receipts", {})).items()}

        head_refs: dict[tuple[str, str], int] = {}
        node_list: list[PRNode] = []
        for item in pulls:
            number = int(item["number"])
            head_repo_obj = item["head"].get("repo")
            head_repo = str(head_repo_obj["full_name"]) if isinstance(head_repo_obj, dict) and head_repo_obj.get("full_name") else ""
            if head_repo:
                head_refs[(head_repo, str(item["head"]["ref"]))] = number
            node_list.append(PRNode(number, str(item["head"]["sha"]), str(item["base"]["sha"]), str(item["base"]["ref"]), bool(item.get("draft", False)), "UNKNOWN", authority_map.get(number, frozenset()), (), semantic_map.get(number, ()), receipt_labels.get(number, ())))
        nodes = {node.number: node for node in node_list}

        stack_edges_list: list[tuple[int, int]] = []
        for item in pulls:
            number = int(item["number"])
            base_repo_obj = item["base"].get("repo")
            base_repo = str(base_repo_obj["full_name"]) if isinstance(base_repo_obj, dict) and base_repo_obj.get("full_name") else self.repository
            parent = head_refs.get((base_repo, str(item["base"]["ref"])))
            if parent is not None and parent != number:
                stack_edges_list.append((number, parent))
        stack_edges = tuple(sorted(set(stack_edges_list)))

        semantic_edges = tuple(sorted((SemanticEdge(int(item["consumer_pr"]), int(item["provider_pr"]), str(item.get("dependency_kind", "REQUIRES")), bool(item.get("requires_ancestry_binding", True))) for item in manifest.get("semantic_edges", []) if int(item["consumer_pr"]) in nodes and int(item["provider_pr"]) in nodes), key=lambda e: (e.consumer_pr, e.provider_pr, e.dependency_kind)))
        if not semantic_edges and semantic_map:
            semantic_edges = tuple(sorted((SemanticEdge(consumer, provider) for consumer, providers in semantic_map.items() if consumer in nodes for provider in providers if provider in nodes), key=lambda e: (e.consumer_pr, e.provider_pr)))
        authority_edges = tuple(sorted((AuthorityEdge(int(item["source_pr"]), int(item["target_pr"]), str(item["authority_domain"]), bool(item.get("allowed", False)), str(item.get("receipt_id", ""))) for item in manifest.get("authority_edges", []) if int(item["source_pr"]) in nodes and int(item["target_pr"]) in nodes), key=lambda e: (e.source_pr, e.target_pr, e.authority_domain)))
        evidence_edges = tuple(sorted((EvidenceEdge(int(item["pr_number"]), str(item["head_sha"]), str(item["receipt_id"]), str(item["state"])) for item in manifest.get("evidence_edges", []) if int(item["pr_number"]) in nodes), key=lambda e: (e.pr_number, e.head_sha, e.receipt_id)))
        conflict_edges = tuple(sorted((ConflictEdge(int(item["left_pr"]), int(item["right_pr"]), str(item.get("kind", "OVERLAP"))) for item in manifest.get("conflict_edges", []) if int(item["left_pr"]) in nodes and int(item["right_pr"]) in nodes), key=lambda e: (e.left_pr, e.right_pr, e.kind)))

        pair_set = {(parent, child) for child, parent in stack_edges} | {(edge.provider_pr, edge.consumer_pr) for edge in semantic_edges if edge.requires_ancestry_binding} | {(edge.left_pr, edge.right_pr) for edge in conflict_edges}
        git_edges = tuple(GitEdge(base_pr, head_pr, self._compare(nodes[base_pr].head_sha, nodes[head_pr].head_sha)[0]) for base_pr, head_pr in sorted(pair_set))

        generated_paths = frozenset(map(str, manifest.get("generated_paths", [])))
        receipt_heads = {int(k): str(v) for k, v in dict(manifest.get("receipt_heads", {})).items()}
        deltas: list[HeadDelta] = []
        for pr_number, old_sha in sorted(receipt_heads.items()):
            node = nodes.get(pr_number)
            if node is not None and old_sha != node.head_sha:
                _, paths = self._compare(old_sha, node.head_sha)
                deltas.append(HeadDelta(pr_number, old_sha, node.head_sha, paths))

        protection_code, _ = self._try_request_json(f"/branches/{quote(default_branch, safe='')}/protection")
        protection_enabled = True if protection_code == 200 else False if protection_code == 404 else None
        _, rulesets_data = self._try_request_json("/rulesets")
        enforcements = tuple(sorted(str(item.get("enforcement", "unknown")) for item in rulesets_data)) if isinstance(rulesets_data, list) else ()
        draft_count = sum(1 for node in node_list if node.draft)
        return RepositorySnapshot(self.repository, main_sha, tuple(sorted(node_list, key=lambda n: n.number)), git_edges, semantic_edges, authority_edges, evidence_edges, conflict_edges, stack_edges, tuple(deltas), generated_paths, protection_enabled, enforcements, "FULL_OPEN_PR_CENSUS", len(node_list), draft_count, len(node_list) - draft_count)


def snapshot_from_json(data: Mapping[str, Any]) -> RepositorySnapshot:
    nodes = tuple(PRNode(int(item["number"]), str(item["head_sha"]), str(item["base_sha"]), str(item["base_ref"]), bool(item["draft"]), str(item.get("mergeable", "UNKNOWN")), frozenset(map(str, item.get("authority_domains", []))), tuple(map(str, item.get("git_parents", []))), tuple(map(int, item.get("semantic_dependencies", []))), tuple(map(str, item.get("evidence_receipts", [])))) for item in data.get("nodes", []))
    edges = data.get("edges", {})
    raw_git = edges.get("E_git", data.get("ancestry", []))
    raw_sem = edges.get("E_sem", data.get("semantic_edges", []))
    raw_auth = edges.get("E_auth", data.get("authority_edges", []))
    raw_evidence = edges.get("E_evidence", data.get("evidence_edges", []))
    raw_conflict = edges.get("E_conflict", data.get("conflict_edges", []))
    git_edges = tuple(GitEdge(int(item["base_pr"]), int(item["head_pr"]), AncestryRelation(**item["relation"])) for item in raw_git)
    semantic_edges = tuple(SemanticEdge(int(item[0]), int(item[1])) if isinstance(item, list) else SemanticEdge(int(item["consumer_pr"]), int(item["provider_pr"]), str(item.get("dependency_kind", "REQUIRES")), bool(item.get("requires_ancestry_binding", True))) for item in raw_sem)
    authority_edges = tuple(AuthorityEdge(int(item["source_pr"]), int(item["target_pr"]), str(item["authority_domain"]), bool(item.get("allowed", False)), str(item.get("receipt_id", ""))) for item in raw_auth)
    evidence_edges = tuple(EvidenceEdge(int(item["pr_number"]), str(item["head_sha"]), str(item["receipt_id"]), str(item["state"])) for item in raw_evidence)
    conflict_edges = [ConflictEdge(int(item["left_pr"]), int(item["right_pr"]), str(item.get("kind", "OVERLAP"))) for item in raw_conflict]
    conflict_edges.extend(ConflictEdge(int(item[0]), int(item[1]), "OVERLAP") for item in data.get("overlap_pairs", []))
    deltas = tuple(HeadDelta(int(item["pr_number"]), str(item["from_sha"]), str(item["to_sha"]), tuple(map(str, item.get("changed_paths", [])))) for item in data.get("head_deltas", []))
    census = dict(data.get("census", {}))
    return RepositorySnapshot(str(data["repository"]), str(data["main_sha"]), nodes, git_edges, semantic_edges, authority_edges, evidence_edges, tuple(conflict_edges), tuple(tuple(map(int, edge)) for edge in data.get("stack_edges", [])), deltas, frozenset(map(str, data.get("generated_paths", []))), data.get("branch_protection_enabled"), tuple(map(str, data.get("ruleset_enforcements", []))), str(census.get("scope", data.get("census_scope", "UNSPECIFIED"))), int(census.get("open", len(nodes))), int(census.get("draft", sum(1 for n in nodes if n.draft))), int(census.get("non_draft", sum(1 for n in nodes if not n.draft))))


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
        snapshot = GitHubLiveSnapshotBuilder(args.repo, token=os.environ.get("GITHUB_TOKEN")).build(manifest)
    receipt = build_receipt(snapshot, analyze_snapshot(snapshot))
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
