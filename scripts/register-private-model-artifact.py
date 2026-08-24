#!/usr/bin/env python3
"""Create a repo-safe manifest fragment for operator-private model weights.

This tool hashes private checkpoint bytes locally. It never uploads them and it
never records the absolute source path. The emitted `opaque_ref` is supplied by
the operator and should identify a private storage slot without revealing a
secret-bearing URL, token, or local filesystem location.

The resulting package remains evidence/capability configuration only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def checkpoint_content_root(files: list[dict[str, Any]]) -> str:
    payload = {
        "domain": "AEGIS_PRIVATE_MODEL_CONTENT_ROOT_V1",
        "files": [
            {
                "path": item["path"],
                "sha256": item["sha256"],
                "size_bytes": item["size_bytes"],
            }
            for item in files
        ],
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--opaque-ref", required=True, help="non-secret private storage identifier")
    parser.add_argument("--checkout-path", required=True, help="must live below models/weights/")
    parser.add_argument("--manifest-path", required=True, help="repo-relative non-secret manifest path")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()
    if not source_dir.is_dir():
        raise SystemExit(f"source directory does not exist: {source_dir}")
    if not args.checkout_path.startswith("models/weights/"):
        raise SystemExit("--checkout-path must live below models/weights/")
    if "://" in args.opaque_ref or args.opaque_ref.startswith("/"):
        raise SystemExit("--opaque-ref must be an opaque identifier, not a URL or absolute path")

    files: list[dict[str, Any]] = []
    for path in sorted(p for p in source_dir.rglob("*") if p.is_file()):
        relative = path.relative_to(source_dir).as_posix()
        files.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "required_for_local_execution": True,
            }
        )
    if not files:
        raise SystemExit("private checkpoint directory contains no files")

    content_root = checkpoint_content_root(files)
    package = {
        "family": args.family,
        "provider": args.provider,
        "weight_availability": "PRIVATE_OPERATOR_WEIGHTS",
        "license": {"spdx": None, "redistribution_status": "PRIVATE_OPERATOR_ONLY"},
        "source": {
            "kind": "operator_private",
            "opaque_ref": args.opaque_ref,
            "revision": content_root,
            "revision_kind": "PRIVATE_CONTENT_ROOT",
            "content_root_sha256": content_root,
        },
        "checkpoint": {
            "declared_shard_count": len(files),
            "complete_shard_digest_set": True,
        },
        "files": [
            {
                "path": item["path"],
                "sha256": item["sha256"],
                "required_for_local_execution": item["required_for_local_execution"],
            }
            for item in files
        ],
        "checkout_path": args.checkout_path,
        "mirror": {
            "state": "PRIVATE_SOURCE_REGISTERED_NOT_YET_MIRRORED",
            "backend": "operator_private_store",
            "release_tag": None,
            "manifest_path": args.manifest_path,
        },
    }
    output = {
        "schema_version": "1.1.0",
        "package_id": args.package_id,
        "authority": "EVIDENCE_ONLY",
        "confidentiality": "OPERATOR_PRIVATE",
        "package": package,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    receipt = {
        "receipt_kind": "PRIVATE_MODEL_REGISTRATION_RECEIPT_V1",
        "package_id": args.package_id,
        "content_root_sha256": content_root,
        "file_count": len(files),
        "total_bytes": sum(item["size_bytes"] for item in files),
        "opaque_ref": args.opaque_ref,
        "source_path_disclosed": False,
        "upload_performed": False,
        "authority": "EVIDENCE_ONLY",
    }
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
