#!/usr/bin/env python3
"""Fetch an exact open-weight model snapshot and emit a provenance receipt.

Network transfer is explicit because model snapshots may be tens or hundreds of
GB. The command refuses to download unless `--operator-approved-download` is
present. Download success is evidence only; it does not activate the model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "models" / "model-artifacts.v1.json"


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_id")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--operator-approved-download", action="store_true")
    args = parser.parse_args()

    if not args.operator_approved_download:
        raise SystemExit("large upstream model download requires --operator-approved-download")

    index: dict[str, Any] = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    package = index["packages"].get(args.package_id)
    if not isinstance(package, dict):
        raise SystemExit(f"unknown package: {args.package_id}")
    if package["weight_availability"] != "OPEN_WEIGHTS":
        raise SystemExit("only OPEN_WEIGHTS packages can be fetched")
    source = package["source"]
    if source.get("kind") != "huggingface":
        raise SystemExit("only exact Hugging Face sources are supported")
    if source.get("revision_kind") != "FULL_COMMIT_SHA" or len(source.get("revision", "")) != 40:
        raise SystemExit("download denied: source is not bound to an exact 40-character revision")
    if package["license"].get("redistribution_status") != "PERMITTED_BY_DECLARED_LICENSE":
        raise SystemExit("download denied: redistribution/license status is not admitted")

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise SystemExit("install huggingface_hub before fetching model artifacts") from exc

    destination = args.destination.resolve()
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    snapshot_path = Path(
        snapshot_download(
            repo_id=source["repo_id"],
            revision=source["revision"],
            local_dir=str(destination),
            local_dir_use_symlinks=False,
        )
    ).resolve()

    expected = {record["path"]: record["sha256"] for record in package["files"]}
    verified_manifest_files: list[dict[str, Any]] = []
    for relative, expected_sha in sorted(expected.items()):
        path = snapshot_path / relative
        if not path.is_file():
            raise SystemExit(f"required manifest file missing from exact snapshot: {relative}")
        actual = sha256_file(path)
        if actual != expected_sha:
            raise SystemExit(
                f"upstream digest mismatch for {relative}: expected {expected_sha}, got {actual}"
            )
        verified_manifest_files.append(
            {
                "path": relative,
                "sha256": actual,
                "size_bytes": path.stat().st_size,
            }
        )

    all_files = sorted(p for p in snapshot_path.rglob("*") if p.is_file())
    total_bytes = sum(path.stat().st_size for path in all_files)
    receipt = {
        "receipt_kind": "MODEL_UPSTREAM_FETCH_RECEIPT_V1",
        "package_id": args.package_id,
        "source": source,
        "license": package["license"],
        "snapshot_path": str(snapshot_path),
        "file_count": len(all_files),
        "total_bytes": total_bytes,
        "verified_manifest_files": verified_manifest_files,
        "outcome": "SOURCE_FETCHED_EXACT_REVISION",
        "authority": "EVIDENCE_ONLY",
    }
    encoded = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
