"""AEGIS Ω: issue, dendrite, lineage, registry and authority contract spine.

An informational "token" is only a content address, NEVER a capability or
currency. Scores remain unverified. No skill or tier promotion, tool execution,
on-chain action, payment or production mutation occurs.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from agents.dendrite_mesh import digest, HEAD_RE, DIGEST_RE
from agents.issue_evolution import SCHEMA as ISSUE_SCHEMA, evolve_issues, spread_issue_graph

SCHEMA = "AEGIS_SOVEREIGN_EVOLUTION_CONTRACT_SPINE_V1"
TOKEN_SCHEMA = "AEGIS_INFORMATIONAL_EVOLUTION_TOKEN_V1"
MAX_COUNTEREXAMPLES = 256
MAX_FILE_BYTES = 4_000_000
ISSUE_KEY = re.compile(
    r"(?:Aegis-Omega/(?:AEGIS-OMEGA|AegisOmega)|"
    r"tarikskalic33/(?:formal-conjectures|sovereign-guard))#[1-9][0-9]{0,6}\Z"
)


def _lineage_checkpoint(lineage: Any | None) -> dict[str, Any]:
    """Reuse the actual AdaptiveLineage replay, not a claimed valid flag."""
    if lineage is None:
        return {"status": "NOT_INSPECTED", "root": None}
    from agents.evolution import AdaptiveLineage
    if not isinstance(lineage, AdaptiveLineage):
        raise ValueError("LINEAGE_TYPE_INVALID")
    valid, bad = lineage.verify_chain()
    if not valid:
        raise ValueError("LINEAGE_HASH_CHAIN_INVALID_AT_" + str(bad))
    root = lineage.terminal_hash()
    if not isinstance(root, str) or not DIGEST_RE.fullmatch(root):
        raise ValueError("LINEAGE_ROOT_INVALID")
    return {"status": "LOCAL_HASH_CHAIN_CONSISTENT_NOT_AUTHENTICATED", "root": root}


def _registry_checkpoint(registry: Mapping[str, Any] | None) -> dict[str, Any]:
    """Reuse the existing sealed skill registry computation."""
    if registry is None:
        return {"status": "NOT_INSPECTED", "root": None}
    from harness.sdk.skill_authority import compute_registry_root
    if not isinstance(registry, Mapping):
        raise ValueError("SKILL_REGISTRY_TYPE_INVALID")
    root = registry.get("registry_root")
    if not isinstance(root, str) or not DIGEST_RE.fullmatch(root):
        raise ValueError("SKILL_REGISTRY_UNSEALED")
    if root != compute_registry_root(registry):
        raise ValueError("SKILL_REGISTRY_ROOT_MISMATCH")
    return {"status": "LOCAL_REGISTRY_DIGEST_MATCHED_NOT_ATTESTED", "root": root}


def _negative_knowledge(references: list[Mapping[str, Any]],
                        issue_keys: set[str]) -> dict[str, list[dict[str, str]]]:
    """Bind explicit Foundry witness records to issues without promoting status."""
    if not isinstance(references, list) or len(references) > MAX_COUNTEREXAMPLES:
        raise ValueError("COUNTEREXAMPLE_LIST_INVALID")
    result: dict[str, list[dict[str, str]]] = {k: [] for k in issue_keys}
    seen = set()
    for ref in references:
        if not isinstance(ref, Mapping) or set(ref) != {"issue", "witness"}:
            raise ValueError("COUNTEREXAMPLE_REFERENCE_INVALID")
        issue = ref["issue"]
        witness = ref["witness"]
        if not isinstance(issue, str) or not ISSUE_KEY.fullmatch(issue) or issue not in result:
            raise ValueError("COUNTEREXAMPLE_ISSUE_UNRESOLVED")
        if not isinstance(witness, Mapping) or witness.get("kind") != "AEGIS_REPLAYABLE_COUNTEREXAMPLE_V1":
            raise ValueError("COUNTEREXAMPLE_SCHEMA_INVALID")
        if (witness.get("outcome") != "COUNTEREXAMPLE_DISCOVERED"
                or witness.get("admission") != "NOT_ADMITTED"
                or witness.get("authority_granted") is not False
                or not isinstance(witness.get("witness"), Mapping)):
            raise ValueError("COUNTEREXAMPLE_STATE_INVALID")
        fingerprint = (issue, digest(witness))
        if fingerprint in seen:
            raise ValueError("COUNTEREXAMPLE_DUPLICATE")
        seen.add(fingerprint)
        result[issue].append({
            "record_digest": fingerprint[1],
            "status": "UNVERIFIED_COUNTEREXAMPLE_CANDIDATE",
            "effect": "OBSERVATION_ONLY",
        })
    return {k: sorted(v, key=lambda x: x["record_digest"]) for k, v in result.items()}


def compose_spine(*, graph: Mapping[str, Any], trials: list[Mapping[str, Any]],
                  source_head: str, lineage: Any | None = None,
                  registry: Mapping[str, Any] | None = None,
                  counterexamples: list[Mapping[str, Any]] | None = None,
                  check_authority: bool = False) -> dict[str, Any]:
    """Content-bound view across existing AEGIS systems; zero operational effects."""
    if not isinstance(source_head, str) or not HEAD_RE.fullmatch(source_head):
        raise ValueError("SOURCE_HEAD_INVALID")
    # Existing reducer validates graph, trial pairing and self-promotion denial.
    evolution = evolve_issues(graph, trials)
    if graph.get("schema") != ISSUE_SCHEMA or graph.get("receipt_hash") != evolution["graph_receipt_hash"]:
        raise ValueError("ISSUE_GRAPH_BINDING_MISMATCH")
    nodes = graph["nodes"]
    if not isinstance(nodes, list) or len(nodes) != evolution["issue_count"]:
        raise ValueError("ISSUE_NODE_COUNT_MISMATCH")
    issue_keys = [x["issue"] for x in evolution["issues"]]
    if len(set(issue_keys)) != len(issue_keys):
        raise ValueError("ISSUE_KEYS_DUPLICATED")
    negative = _negative_knowledge(
        counterexamples if counterexamples is not None else [], set(issue_keys))
    chain = _lineage_checkpoint(lineage)
    skill_root = _registry_checkpoint(registry)
    batches = []
    # Route informational metadata via the existing bounded 32-node graph.
    for start in range(0, len(nodes), 32):
        routed = spread_issue_graph(graph, source_head=source_head, start=start,
                                    limit=min(32, len(nodes) - start))
        batches.append({
            "index": len(batches), "start": start,
            "count": len(routed["routing"]["events"]),
            "receipt_hash": routed["routing"]["receipt_hash"],
            "source_graph_root": routed["graph_receipt_hash"],
            "authority_effect": "NONE",
        })
    issue_tokens = []
    node_map = {n["key"]: n for n in nodes}
    for state in evolution["issues"]:
        issue = state["issue"]
        body = {
            "schema": TOKEN_SCHEMA, "issue": issue,
            "graph_receipt_hash": graph["receipt_hash"],
            "evolution_round_hash": evolution["receipt_hash"],
            "issue_contract_digest": digest(state["evolution_contract"]),
            "proposal_ids": sorted(p["proposal_id"] for p in state["proposals"]),
            "trial_receipts": sorted(r["screen_receipt"] for r in state["history"]),
            "negative_knowledge": negative[issue],
            "lineage_checkpoint": chain["root"],
            "skill_registry_checkpoint": skill_root["root"],
            "source_head": source_head,
            "operator_required": "needs-operator" in node_map[issue]["labels"],
            "claims_verified": False,
            "self_promotion": "DENIED",
            "authority_effect": "NONE", "execution_effect": "NONE",
        }
        issue_tokens.append({**body, "token_id": digest(body)})
    links = sorted(evolution["cross_issue_lessons"],
                   key=lambda x: (x["source_issue"], x["recipient_issue"], x["relationship"]))
    connected = Counter([e["from"] for e in graph["edges"]] +
                        [e["to"] for e in graph["edges"]])
    authority = {"status": "NOT_EVALUATED", "decision": "DENIED_BY_DEFAULT"}
    if check_authority:
        # The sole existing authority client remains responsible for D0
        # observation; a contract token cannot act as a capability.
        from harness.sdk.authority_client import authorize_from_environment
        observation = authorize_from_environment(
            action_class="D0", authority_domain="knowledge",
            requested_capability="issue_evolution_observation",
            tool="evolution_contract_spine", target=graph["receipt_hash"],
            action={"schema": SCHEMA, "graph": graph["receipt_hash"],
                    "evolution": evolution["receipt_hash"], "effect": "NONE"},
        )
        authority = {"status": "EXISTING_EVALUATOR_OBSERVED",
                     "decision": observation.get("outcome", "DENIED"),
                     "decision_root": observation.get("decision_root"),
                     "denial_codes": observation.get("denial_codes", [])}
    body = {
        "schema": SCHEMA, "source_head": source_head,
        "issue_graph_root": graph["receipt_hash"],
        "evolution_round_root": evolution["receipt_hash"],
        "source_replay": "SNAPSHOT_AND_HASH_CONSISTENCY_ONLY",
        "issue_count": len(issue_tokens), "trial_count": evolution["trial_count"],
        "cross_issue_lesson_count": len(links),
        "connected_issue_count": sum(bool(connected[k]) for k in issue_keys),
        "counterexample_count": sum(len(v) for v in negative.values()),
        "lineage": chain, "skill_registry": skill_root,
        "authority_observation": authority, "dendrite_batches": batches,
        "issue_contract_tokens": issue_tokens, "cross_issue_lessons": links,
        "token_meaning": "CONTENT_ADDRESS_ONLY_NOT_A_CAPABILITY",
        "external_benchmark_verified": False,
        "source_publisher_authenticated": False,
        "independent_review": "NOT_PERFORMED",
        "improvement_admission": "DENIED",
        "skill_tier_effect": "NONE",
        "authority_effect": "NONE", "execution_effect": "NONE",
    }
    return {**body, "receipt_hash": digest(body)}


def _read_bounded(path: Path, bound: int = MAX_FILE_BYTES) -> Any:
    with path.open("rb") as stream:
        raw = stream.read(bound + 1)
    if len(raw) > bound:
        raise ValueError("CONTRACT_INPUT_TOO_LARGE")
    return json.loads(raw)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AEGIS unified issue evolution observation (non-executing)")
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--trials", type=Path, required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--lineage", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--counterexamples", type=Path)
    parser.add_argument("--authority-probe", action="store_true",
                        help="Read-only observation via existing AuthorityEvaluator")
    args = parser.parse_args()
    try:
        from agents.evolution import AdaptiveLineage
        result = compose_spine(
            graph=_read_bounded(args.graph), trials=_read_bounded(args.trials),
            source_head=args.source_head,
            lineage=AdaptiveLineage.load(args.lineage) if args.lineage else None,
            registry=_read_bounded(args.registry) if args.registry else None,
            counterexamples=_read_bounded(args.counterexamples) if args.counterexamples else None,
            check_authority=args.authority_probe,
        )
    except (ValueError, TypeError, OSError, UnicodeError, KeyError) as exc:
        parser.error(f"{type(exc).__name__}: {exc}")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
