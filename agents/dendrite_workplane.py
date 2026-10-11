"""Compose the existing issue, dendrite, relay and evolution modules (information only).

This is a read-only compiler and optional explicitly invoked local spool writer,
not a new agent dispatcher, evaluator, admission gate or autonomous skill mutator.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from agents.dendrite_mesh import HEAD_RE, digest
from agents.dendrite_system import EvidencePacket, spread_packets
from agents.issue_evolution import compile_graph, evolve_issues, spread_issue_graph

SCHEMA = "AEGIS_UNIFIED_EVOLUTION_WORKPLANE_V1"
_TOPIC_TO_SOURCE_ROLE = {
    "research": ("cognitive", "corpus_ingestor"),
    "formal": ("formal", "applied_science"),
    "engineering": ("engineering", "engineering"),
    "security": ("security", "cybersecurity"),
    "commerce": ("revenue", "strategy"),
    "operations": ("operations", "platform_engineering"),
}


def observe_evolution(tree_path: str | Path, lineage_path: str | Path) -> dict[str, Any]:
    """Inspect the REAL existing EvolutionEngine, always with apply_changes=False."""
    from agents.evolution import AdaptiveLineage, EvolutionEngine

    tree = Path(tree_path)
    lineage = Path(lineage_path)
    if not tree.is_file() or not lineage.is_file():
        raise ValueError("EXISTING_EVOLUTION_INPUTS_MISSING")
    history = AdaptiveLineage.load(lineage)
    valid, bad = history.verify_chain()
    if not valid:
        raise ValueError(f"EXISTING_EVOLUTION_LINEAGE_INVALID:{bad}")
    original_root = history.terminal_hash()
    engine = EvolutionEngine(tree_path=str(tree), lineage=history)
    verdicts = engine.tick(apply_changes=False)
    if history.terminal_hash() != original_root:
        raise ValueError("EVOLUTION_DRY_RUN_MUTATED_LINEAGE")
    return {
        "status": "READ_ONLY_OBSERVATION",
        "lineage_root": original_root,
        "skills_observed": len(verdicts),
        "candidate_tier_changes_not_approved": sum(bool(v.eligible_tier) for v in verdicts),
        "promotion_applied": False,
        "authority_effect": "NONE",
    }


def _route_lessons(graph: Mapping[str, Any], evolution_round: Mapping[str, Any],
                   source_head: str) -> list[dict[str, Any]]:
    nodes = {node["key"]: node for node in graph["nodes"]}
    packets = []
    for index, pointer in enumerate(evolution_round["cross_issue_lessons"]):
        src, target = pointer["source_issue"], pointer["recipient_issue"]
        if src not in nodes or target not in nodes:
            raise ValueError("UNKNOWN_CROSS_ISSUE_ENDPOINT")
        dest = nodes[target]
        topic = dest["topic"]
        source, origin = _TOPIC_TO_SOURCE_ROLE[topic]
        channel = "QUARANTINE" if "needs-operator" in dest["labels"] else "CANDIDATE"
        if channel == "QUARANTINE" and source != "cognitive":
            origin = "cybersecurity"
        body = {"from_issue": src, "to_issue": target,
                "edge_kind": pointer["relationship"],
                "trial_receipt_hashes": pointer["source_trial_receipts"],
                "evidence_status": "UNVERIFIED_EVOLUTION_LESSON_POINTER",
                "authority_effect": "NONE"}
        packets.append(EvidencePacket(source, topic, origin, source_head,
                                      digest(body), index, json.dumps(body, sort_keys=True),
                                      channel))
    return [spread_packets(packets[i:i + 32], ttl=5)
            for i in range(0, len(packets), 32)]


def compose(snapshot: Mapping[str, Any], *, source_head: str,
            trials: list[Mapping[str, Any]] | None = None,
            skill_tree: str | Path | None = None,
            lineage: str | Path | None = None) -> dict[str, Any]:
    """Compile ALL issue states, then propagate bounded shards in existing mesh."""
    if not isinstance(source_head, str) or not HEAD_RE.fullmatch(source_head):
        raise ValueError("INVALID_WORKPLANE_SOURCE_HEAD")
    if (skill_tree is None) != (lineage is None):
        raise ValueError("EVOLUTION_INPUT_PAIR_REQUIRED")
    graph = compile_graph(snapshot)
    evolution_round = evolve_issues(graph, [] if trials is None else trials)
    if evolution_round["issue_count"] != graph["node_count"]:
        raise ValueError("WORKPLANE_NODE_COUNT_MISMATCH")
    main_routes = [spread_issue_graph(graph, source_head=source_head,
                                      start=i, limit=32)["routing"]
                   for i in range(0, graph["node_count"], 32)]
    if sum(len(x["events"]) for x in main_routes) != graph["node_count"]:
        raise ValueError("WORKPLANE_INCOMPLETE_PROPAGATION")
    lesson_routes = _route_lessons(graph, evolution_round, source_head)
    observed = (observe_evolution(skill_tree, lineage)
                if skill_tree is not None else {"status": "NOT_REQUESTED",
                                                   "promotion_applied": False})
    body = {
        "schema": SCHEMA,
        "source_head": source_head,
        "snapshot_hash": graph["snapshot_sha256"],
        "graph_receipt": graph["receipt_hash"],
        "evolution_receipt": evolution_round["receipt_hash"],
        "node_count": graph["node_count"],
        "dependency_edges": len([e for e in graph["edges"] if e["kind"] == "depends_on"]),
        "relationships": len(graph["edges"]),
        "unresolved_relations": len(graph["unresolved_references"]),
        "issue_evolution": evolution_round,
        "issue_route_shards": main_routes,
        "lesson_route_shards": lesson_routes,
        "existing_skill_evolution": observed,
        "transport": "IN_MEMORY_BY_DEFAULT",
        "source_authenticity": "NOT_VERIFIED",
        "benchmark_status": "SELF_REPORTED_OR_NOT_RUN",
        "production_admission": "DENIED",
        "skill_promotion": "DENIED",
        "execution_effect": "NONE",
        "authority_effect": "NONE",
    }
    return {**body, "receipt_hash": digest(body)}


def publish(plan: Mapping[str, Any], *, root: str | Path,
            key_file: str | Path | None = None,
            key_id: str | None = None) -> dict[str, Any]:
    """Explicitly publish plan batches via existing local transport (no agent)."""
    from agents.dendrite_attestation import publish_for_pipeline
    if not isinstance(plan, Mapping) or plan.get("schema") != SCHEMA or (
        plan.get("receipt_hash") != digest({k: v for k, v in plan.items()
                                            if k != "receipt_hash"})
    ):
        raise ValueError("WORKPLANE_RECEIPT_INVALID")
    if bool(key_file) != bool(key_id):
        raise ValueError("RELAY_KEY_ARGUMENTS_INCOMPLETE")
    outputs = []
    for route in plan["issue_route_shards"] + plan["lesson_route_shards"]:
        outputs.append(publish_for_pipeline(route, root, key_file=key_file,
                                            key_id=key_id))
    return {"schema": "AEGIS_UNIFIED_WORKPLANE_PUBLISH_V1",
            "workplane_receipt": plan["receipt_hash"], "batches": outputs,
            "authority_effect": "NONE", "execution_effect": "NONE",
            "delivery": "LOCAL_SPOOL_ONLY"}


def _load_bounded(path: str | Path, limit: int) -> Any:
    with Path(path).open("rb") as f:
        raw = f.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("INPUT_FILE_TOO_LARGE")
    return json.loads(raw)


def main() -> None:
    p = argparse.ArgumentParser(description="AEGIS existing-module unified evolution workplane")
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--source-head", required=True)
    p.add_argument("--trials", type=Path)
    p.add_argument("--skill-tree", type=Path)
    p.add_argument("--lineage", type=Path)
    p.add_argument("--spool-dir", type=Path)
    p.add_argument("--relay-key-file", type=Path)
    p.add_argument("--relay-key-id")
    args = p.parse_args()
    try:
        if bool(args.relay_key_file) != bool(args.relay_key_id):
            raise ValueError("RELAY_KEY_ARGUMENTS_INCOMPLETE")
        if args.relay_key_file and not args.spool_dir:
            raise ValueError("RELAY_AUTH_REQUIRES_SPOOL")
        plan = compose(_load_bounded(args.snapshot, 4_000_000),
                       source_head=args.source_head,
                       trials=_load_bounded(args.trials, 2_000_000) if args.trials else None,
                       skill_tree=args.skill_tree, lineage=args.lineage)
        result = {"plan": plan}
        if args.spool_dir:
            result["local_publish"] = publish(plan, root=args.spool_dir,
                                               key_file=args.relay_key_file,
                                               key_id=args.relay_key_id)
    except (ValueError, TypeError, KeyError, OSError) as ex:
        p.error(f"{type(ex).__name__}: {ex}")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
