#!/usr/bin/env python3
"""Build the evidence-only AEGIS WorkID lineage graph.

PR-backed work receives the stable identity ``pr:<number>``.  Legacy branch-only
work is not allowed to disappear: it receives a content-seeded migration ID and
is marked UNKNOWN_FAIL_CLOSED until a durable WorkID registry/decision binds it.
A branch name is never used as the identity of PR-backed work.

This script does not merge, delete, admit, or authorize work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

UNIVERSE_SCHEMA = "AEGIS_RECONCILIATION_UNIVERSE_V1"
SPINES_SCHEMA = "AEGIS_RECONCILIATION_SPINES_V1"
OUTPUT_SCHEMA = "AEGIS_WORK_LINEAGE_V1"
DIGEST_DOMAIN = b"AEGIS_WORK_LINEAGE_V1\0"
OBJECTIVE_DOMAIN = b"AEGIS_WORK_OBJECTIVE_V1\0"
LEGACY_WORK_DOMAIN = b"AEGIS_LEGACY_WORK_ID_V1\0"
HEX40_64 = re.compile(r"^[0-9a-f]{40,64}$")
WORK_ID_RE = re.compile(r"^(?:pr:[1-9][0-9]*|legacy-tip:[0-9a-f]{64})$")


class WorkLineageError(ValueError):
    pass


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkLineageError(f"INVALID_JSON:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise WorkLineageError(f"ROOT_NOT_OBJECT:{path}")
    return value


def compact_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(domain: bytes, value: Mapping[str, Any]) -> str:
    return hashlib.sha256(domain + compact_json(value)).hexdigest()


def normalize_title(value: str) -> str:
    return " ".join(value.split()).strip().casefold()


def objective_digest(title: str) -> str:
    body = {"normalized_title": normalize_title(title)}
    return digest(OBJECTIVE_DOMAIN, body)


def validate_universe(doc: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != UNIVERSE_SCHEMA:
        raise WorkLineageError("UNSUPPORTED_UNIVERSE_SCHEMA")
    if doc.get("authority") != "DISCOVERY_EVIDENCE_ONLY":
        raise WorkLineageError("UNIVERSE_AUTHORITY_UNSUPPORTED")
    if not isinstance(doc.get("discovery_complete"), bool):
        raise WorkLineageError("UNIVERSE_COMPLETENESS_INVALID")
    main = doc.get("canonical_main")
    if not isinstance(main, dict) or not isinstance(main.get("sha"), str) or not HEX40_64.fullmatch(main["sha"]):
        raise WorkLineageError("CANONICAL_MAIN_INVALID")
    if not isinstance(doc.get("pull_requests"), list) or not isinstance(doc.get("branches"), list):
        raise WorkLineageError("UNIVERSE_COLLECTION_INVALID")


def validate_spines(doc: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != SPINES_SCHEMA:
        raise WorkLineageError("UNSUPPORTED_SPINES_SCHEMA")
    active = doc.get("active_spine")
    historical = doc.get("historical_reconciled")
    side = doc.get("side_lineages")
    if not isinstance(active, list) or not all(isinstance(x, str) for x in active):
        raise WorkLineageError("ACTIVE_SPINE_INVALID")
    if len(active) != len(set(active)):
        raise WorkLineageError("ACTIVE_SPINE_DUPLICATE")
    if not isinstance(historical, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in historical.items()):
        raise WorkLineageError("HISTORICAL_RECONCILED_INVALID")
    if not isinstance(side, list) or not all(isinstance(group, list) and all(isinstance(x, str) for x in group) for group in side):
        raise WorkLineageError("SIDE_LINEAGES_INVALID")
    declared = list(active) + list(historical.keys()) + list(historical.values()) + [x for group in side for x in group]
    if not all(re.fullmatch(r"pr:[1-9][0-9]*", x) for x in declared):
        raise WorkLineageError("DECLARED_WORK_ID_INVALID")


def pr_items(universe: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    prs = universe["pull_requests"]
    assert isinstance(prs, list)
    head_sha_to_id: dict[str, str] = {}
    head_ref_to_id: dict[str, str] = {}
    for pr in prs:
        if not isinstance(pr, dict):
            raise WorkLineageError("PR_NOT_OBJECT")
        number = pr.get("number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise WorkLineageError("PR_NUMBER_INVALID")
        head_sha = pr.get("head_sha")
        head_ref = pr.get("head_ref")
        if not isinstance(head_sha, str) or not HEX40_64.fullmatch(head_sha):
            raise WorkLineageError(f"PR_HEAD_INVALID:{number}")
        if not isinstance(head_ref, str) or not head_ref:
            raise WorkLineageError(f"PR_HEAD_REF_INVALID:{number}")
        work_id = f"pr:{number}"
        if head_sha in head_sha_to_id and head_sha_to_id[head_sha] != work_id:
            # Two PRs may occasionally share a head.  We retain both PR identities;
            # SHA lookup for parentage becomes ambiguous and therefore unavailable.
            head_sha_to_id[head_sha] = ""
        else:
            head_sha_to_id[head_sha] = work_id
        if head_ref in head_ref_to_id and head_ref_to_id[head_ref] != work_id:
            head_ref_to_id[head_ref] = ""
        else:
            head_ref_to_id[head_ref] = work_id
    return [], head_sha_to_id, head_ref_to_id


def resolve_parent_work_ids(
    pr: Mapping[str, Any], head_sha_to_id: Mapping[str, str], head_ref_to_id: Mapping[str, str]
) -> list[str]:
    base_sha = pr.get("base_sha")
    base_ref = pr.get("base_ref")
    candidates: set[str] = set()
    if isinstance(base_sha, str):
        by_sha = head_sha_to_id.get(base_sha)
        if by_sha:
            candidates.add(by_sha)
    if isinstance(base_ref, str):
        by_ref = head_ref_to_id.get(base_ref)
        if by_ref:
            candidates.add(by_ref)
    # If name and SHA disagree, the parent relation is ambiguous.  Do not invent a
    # parent edge; the classification layer will fail closed on the missing edge.
    if len(candidates) > 1:
        return []
    return sorted(candidates)


def build_pr_work_items(
    universe: Mapping[str, Any], spines: Mapping[str, Any]
) -> list[dict[str, Any]]:
    prs = universe["pull_requests"]
    assert isinstance(prs, list)
    _, head_sha_to_id, head_ref_to_id = pr_items(universe)
    active = set(spines["active_spine"])
    historical: Mapping[str, str] = spines["historical_reconciled"]
    side_ids = {x for group in spines["side_lineages"] for x in group}
    main_sha = universe["canonical_main"]["sha"]

    # Compute parent edges first so lineage roots can be resolved recursively.
    records: dict[str, dict[str, Any]] = {}
    for pr in prs:
        assert isinstance(pr, dict)
        work_id = f"pr:{pr['number']}"
        parents = resolve_parent_work_ids(pr, head_sha_to_id, head_ref_to_id)
        if work_id in active:
            classification = "ACTIVE_SPINE"
        elif work_id in historical:
            classification = "HISTORICAL_EVIDENCE_ONLY"
        else:
            classification = "UNKNOWN_FAIL_CLOSED"

        records[work_id] = {
            "work_id": work_id,
            "identity_source": "GITHUB_PR_NUMBER",
            "identity_stability": "STABLE",
            "pr_number": pr["number"],
            "title": pr["title"],
            "objective_digest": objective_digest(str(pr["title"])),
            "current_ref": pr["head_ref"],
            "current_head": pr["head_sha"],
            "base_ref": pr["base_ref"],
            "base_sha": pr["base_sha"],
            "parent_work_ids": parents,
            "lineage_root": None,
            "state": pr["state"],
            "draft": pr["draft"],
            "verification_state": "NOT_REEVALUATED_BY_RECONCILIATION",
            "admission_state": "NOT_CLASSIFIED_FOR_ADMISSION",
            "classification": classification,
            "declared_side_lineage": work_id in side_ids,
            "superseded_by": historical.get(work_id),
        }

    def root_for(work_id: str, visiting: set[str] | None = None) -> str:
        visiting = set() if visiting is None else set(visiting)
        if work_id in visiting:
            raise WorkLineageError(f"LINEAGE_CYCLE:{work_id}")
        visiting.add(work_id)
        record = records[work_id]
        if record["lineage_root"] is not None:
            return str(record["lineage_root"])
        parents = record["parent_work_ids"]
        if not parents:
            # Direct-to-main work shares the canonical lineage anchor.  An isolated
            # PR with a non-main but unresolved parent instead anchors to its base SHA
            # so the missing relation is visible rather than silently attached to main.
            root = main_sha if record["base_sha"] == main_sha else record["base_sha"]
        else:
            parent_roots = {root_for(parent, visiting) for parent in parents}
            root = next(iter(parent_roots)) if len(parent_roots) == 1 else digest(
                b"AEGIS_MULTI_PARENT_LINEAGE_V1\0", {"roots": sorted(parent_roots)}
            )
        record["lineage_root"] = root
        return str(root)

    for work_id in sorted(records):
        root_for(work_id)
    return [records[key] for key in sorted(records, key=lambda x: int(x.split(":", 1)[1]))]


def build_legacy_branch_items(
    universe: Mapping[str, Any], pr_work_items: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    pr_heads = {str(item["current_head"]) for item in pr_work_items}
    pr_refs = {str(item["current_ref"]) for item in pr_work_items}
    main_sha = str(universe["canonical_main"]["sha"])
    branches = universe["branches"]
    assert isinstance(branches, list)
    result: list[dict[str, Any]] = []
    for branch in branches:
        if not isinstance(branch, dict):
            raise WorkLineageError("BRANCH_NOT_OBJECT")
        name = branch.get("branch")
        tip = branch.get("tip")
        if not isinstance(name, str) or not isinstance(tip, str) or not HEX40_64.fullmatch(tip):
            raise WorkLineageError("BRANCH_IDENTITY_INVALID")
        if name == "main" or tip == main_sha:
            continue
        if tip in pr_heads or name in pr_refs or branch.get("pr_numbers"):
            continue
        work_hash = hashlib.sha256(LEGACY_WORK_DOMAIN + tip.encode("ascii")).hexdigest()
        result.append({
            "work_id": f"legacy-tip:{work_hash}",
            "identity_source": "LEGACY_CONTENT_TIP_MIGRATION_SEED",
            "identity_stability": "SNAPSHOT_SEEDED_PENDING_REGISTRY",
            "pr_number": None,
            "title": None,
            "objective_digest": None,
            "current_ref": name,
            "current_head": tip,
            "base_ref": None,
            "base_sha": None,
            "parent_work_ids": [],
            "lineage_root": tip,
            "state": "REACHABLE_REF",
            "draft": None,
            "verification_state": "NOT_REEVALUATED_BY_RECONCILIATION",
            "admission_state": "NOT_CLASSIFIED_FOR_ADMISSION",
            "classification": "UNKNOWN_FAIL_CLOSED",
            "declared_side_lineage": False,
            "superseded_by": None,
        })
    result.sort(key=lambda item: item["work_id"])
    return result


def build_work_lineage(universe: Mapping[str, Any], spines: Mapping[str, Any]) -> dict[str, Any]:
    validate_universe(universe)
    validate_spines(spines)
    pr_work = build_pr_work_items(universe, spines)
    legacy = build_legacy_branch_items(universe, pr_work)
    work_items = sorted(pr_work + legacy, key=lambda item: item["work_id"])
    by_id = {item["work_id"]: item for item in work_items}

    active = list(spines["active_spine"])
    missing_active = [work_id for work_id in active if work_id not in by_id]
    if missing_active:
        raise WorkLineageError("ACTIVE_SPINE_WORK_MISSING:" + ",".join(missing_active))

    declared = set(active)
    declared.update(spines["historical_reconciled"].keys())
    declared.update(spines["historical_reconciled"].values())
    declared.update(x for group in spines["side_lineages"] for x in group)
    missing_declared = sorted(work_id for work_id in declared if work_id not in by_id)

    body: dict[str, Any] = {
        "schema_version": OUTPUT_SCHEMA,
        "authority": "LINEAGE_DISCOVERY_EVIDENCE_ONLY",
        "repository": universe["repository"],
        "source_universe_manifest_sha256": universe.get("manifest_sha256"),
        "canonical_main": universe["canonical_main"],
        "discovery_complete": universe["discovery_complete"],
        "active_spine": active,
        "historical_reconciled": dict(sorted(spines["historical_reconciled"].items())),
        "side_lineages": spines["side_lineages"],
        "missing_declared_work_ids": missing_declared,
        "work_items": work_items,
        "branch_creation_authority": "LINEAGE_RESOLVER_REQUIRED",
        "rules": [
            "WORK_ID_IS_NOT_BRANCH_NAME",
            "UNKNOWN_WORK_FAILS_CLOSED",
            "ACTIVE_SPINE_DECLARATION_IS_NOT_MERGE_AUTHORITY",
            "HISTORICAL_RECONCILED_WORK_REMAINS_SEARCHABLE_EVIDENCE",
        ],
    }
    return {**body, "manifest_sha256": digest(DIGEST_DOMAIN, body)}


def validate_output(doc: Mapping[str, Any]) -> None:
    if doc.get("schema_version") != OUTPUT_SCHEMA:
        raise WorkLineageError("OUTPUT_SCHEMA_INVALID")
    items = doc.get("work_items")
    if not isinstance(items, list):
        raise WorkLineageError("OUTPUT_WORK_ITEMS_INVALID")
    ids = [item.get("work_id") for item in items if isinstance(item, dict)]
    if len(ids) != len(items) or len(ids) != len(set(ids)):
        raise WorkLineageError("OUTPUT_WORK_ID_DUPLICATE_OR_INVALID")
    if not all(isinstance(work_id, str) and WORK_ID_RE.fullmatch(work_id) for work_id in ids):
        raise WorkLineageError("OUTPUT_WORK_ID_FORMAT_INVALID")
    body = dict(doc)
    actual = body.pop("manifest_sha256", None)
    expected = digest(DIGEST_DOMAIN, body)
    if actual != expected:
        raise WorkLineageError("OUTPUT_DIGEST_MISMATCH")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", required=True, type=Path)
    parser.add_argument("--spines", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        universe = load_object(args.universe)
        spines = load_object(args.spines)
        doc = build_work_lineage(universe, spines)
        validate_output(doc)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except WorkLineageError as exc:
        print(f"work-lineage: FAIL_CLOSED {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "schema_version": doc["schema_version"],
        "work_item_count": len(doc["work_items"]),
        "active_spine_count": len(doc["active_spine"]),
        "missing_declared_work_ids": len(doc["missing_declared_work_ids"]),
        "manifest_sha256": doc["manifest_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
