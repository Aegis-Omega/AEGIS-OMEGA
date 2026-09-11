#!/usr/bin/env python3
"""Fail-closed structural validator for the RH audit DAG."""

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


def validate_receipt(bundle: Path | None) -> list[str]:
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["schema"] == "AEGIS_RH_ASTRA_ENV_RECEIPT_V1"
    assert receipt["rh_status"] == "NOT_PROVEN"
    assert receipt["authority_effect"] == "NONE"
    assert receipt["claim_promotion"] == "BLOCKED"
    assert receipt["execution_release"] == "BLOCKED"
    assert SHA1.fullmatch(receipt["frontier_sha"])
    assert SHA256.fullmatch(receipt["receipt_sha256"])
    assert receipt["provenance"]["verification_status"] == "UNVERIFIED_EXTERNAL_CLAIM"
    for name, expected in receipt["files"].items():
        assert Path(name).name == name, f"unsafe artifact name: {name}"
        assert SHA256.fullmatch(expected), f"{name}: invalid expected digest"

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


def validate_dag() -> int:
    data = json.loads(DAG.read_text())
    assert data["schema_version"] == "RH_PROOF_OBLIGATION_DAG_V1"
    assert data["rh_status"] in {"PROVEN", "NOT_PROVEN"}
    nodes = data["nodes"]
    ids = {node["id"] for node in nodes}
    assert len(ids) == len(nodes), "duplicate node id"
    for node in nodes:
        missing = REQUIRED - node.keys()
        assert not missing, f"{node.get('id')}: missing {sorted(missing)}"
        assert node["status"] in ALLOWED, f"{node['id']}: unknown status"
        assert node["authority_ceiling"] in ALLOWED
        assert set(node["dependencies"]) <= ids, f"{node['id']}: unknown dependency"
        assert SHA1.fullmatch(node["exact_head"]), f"{node['id']}: invalid exact_head"
        if node["status"] != "PROVED_MACHINE_CHECKED":
            assert node["authority_ceiling"] != "PROVED_MACHINE_CHECKED"
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        assert node_id not in visiting, f"dependency cycle at {node_id}"
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
    if data["rh_status"] == "PROVEN":
        assert all(n["status"] == "PROVED_MACHINE_CHECKED" for n in nodes)
    return len(nodes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, help="verify supplied ASTRA payload directory")
    args = parser.parse_args()
    count = validate_dag()
    failures = validate_receipt(args.bundle)
    if failures:
        raise SystemExit("ASTRA bundle rejected:\n" + "\n".join(failures))
    suffix = " and ASTRA payload" if args.bundle else " and external receipt structure"
    print(f"validated {count} RH DAG nodes{suffix}; status=NOT_PROVEN")


if __name__ == "__main__":
    main()
