#!/usr/bin/env python3
"""Fail-closed structural validation only; proof verification is not implemented."""

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DAG = ROOT / "docs/rh/RH_PROOF_OBLIGATION_DAG_V1.json"
RECEIPT = ROOT / "docs/rh/external/AEGIS_RH_ASTRA_ENV_RECEIPT_V1.json"
REQUIRED = {
    "id", "statement", "formal_statement", "dependencies", "status",
    "source_path", "theorem_name", "exact_head", "assumptions",
    "counterexamples_checked", "verification_method", "authority_ceiling",
}
ALLOWED = {
    "PROVED_MACHINE_CHECKED", "PROVED_PAPER_LEVEL", "NUMERICALLY_VERIFIED",
    "CONDITIONAL", "ASSUMPTION_BEARING", "SEMANTIC_BRIDGE_OPEN", "MISSING",
    "REFUTED",
}
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_receipt(bundle: Path | None) -> list[str]:
    receipt = json.loads(RECEIPT.read_text())
    require(receipt["schema"] == "AEGIS_RH_ASTRA_ENV_RECEIPT_V1", "invalid receipt schema")
    require(receipt["rh_status"] == "NOT_PROVEN", "receipt must remain NOT_PROVEN")
    require(receipt["authority_effect"] == "NONE", "receipt authority_effect must be NONE")
    require(receipt["claim_promotion"] == "BLOCKED", "receipt claim_promotion must be BLOCKED")
    require(receipt["execution_release"] == "BLOCKED", "receipt execution_release must be BLOCKED")
    require(bool(SHA1.fullmatch(receipt["frontier_sha"])), "invalid frontier_sha")
    require(bool(SHA256.fullmatch(receipt["receipt_sha256"])), "invalid receipt_sha256")
    require(
        receipt["provenance"]["verification_status"] == "UNVERIFIED_EXTERNAL_CLAIM",
        "receipt must remain UNVERIFIED_EXTERNAL_CLAIM",
    )
    require(isinstance(receipt["files"], dict) and bool(receipt["files"]), "empty or invalid receipt files")
    for name, expected in receipt["files"].items():
        require(
            bool(name) and name not in {".", ".."} and "/" not in name
            and "\\" not in name and ":" not in name and "\x00" not in name,
            f"unsafe artifact name: {name}",
        )
        require(bool(SHA256.fullmatch(expected)), f"{name}: invalid expected digest")

    failures = []
    if bundle is not None:
        for name, expected in receipt["files"].items():
            path = bundle / name
            if not path.is_file():
                failures.append(f"missing: {name}")
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                failures.append(f"digest mismatch: {name}")
    return failures


def validate_dag() -> tuple[int, str]:
    data = json.loads(DAG.read_text())
    require(data["schema_version"] == "RH_PROOF_OBLIGATION_DAG_V1", "invalid DAG schema")
    status = data["rh_status"]
    require(status in {"PROVEN", "NOT_PROVEN"}, "invalid RH status")
    # Status strings, source names and hashes alone cannot establish a proof.
    require(status != "PROVEN", "PROVEN requires bound proof verification; not implemented")
    require(data["authority_effect"] == "NONE", "DAG authority_effect must be NONE")
    require(data["claim_promotion"] == "BLOCKED", "DAG claim_promotion must be BLOCKED")
    nodes = data["nodes"]
    require(isinstance(nodes, list) and bool(nodes), "empty or invalid DAG nodes")
    ids = {node["id"] for node in nodes}
    require(len(ids) == len(nodes), "duplicate node id")
    for node in nodes:
        missing = REQUIRED - node.keys()
        require(not missing, f"{node.get('id')}: missing {sorted(missing)}")
        require(node["status"] in ALLOWED, f"{node['id']}: unknown status")
        require(node["authority_ceiling"] in ALLOWED, f"{node['id']}: unknown authority ceiling")
        require(set(node["dependencies"]) <= ids, f"{node['id']}: unknown dependency")
        require(bool(SHA1.fullmatch(node["exact_head"])), f"{node['id']}: invalid exact_head")
        if node["status"] != "PROVED_MACHINE_CHECKED":
            require(
                node["authority_ceiling"] != "PROVED_MACHINE_CHECKED",
                f"{node['id']}: authority ceiling exceeds verification status",
            )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        require(node_id not in visiting, f"dependency cycle at {node_id}")
        if node_id in visited:
            return
        visiting.add(node_id)
        node = next(item for item in nodes if item["id"] == node_id)
        for dependency in node["dependencies"]:
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in ids:
        visit(node_id)
    return len(nodes), status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, help="verify supplied ASTRA payload directory")
    args = parser.parse_args()
    try:
        count, status = validate_dag()
        failures = validate_receipt(args.bundle)
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
        raise SystemExit(f"RH audit rejected: {error}") from error
    if failures:
        raise SystemExit("ASTRA bundle rejected:\n" + "\n".join(failures))
    suffix = " and ASTRA payload byte digests" if args.bundle else " and external receipt structure"
    print(f"validated {count} RH DAG nodes{suffix}; status={status}")


if __name__ == "__main__":
    main()
