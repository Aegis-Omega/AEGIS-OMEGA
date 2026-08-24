#!/usr/bin/env python3
"""Hydrate model weights from an admitted AEGIS artifact mirror.

Public open weights may be fetched from an AEGIS repository release. Operator-
private weights may only be hydrated from an already-mounted private asset
directory; this command will never download private plaintext bytes from the
public repository.

Successful hydration is evidence only, never execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
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


def verify(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise SystemExit(f"digest mismatch: {path}: expected {expected}, got {actual}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_id")
    parser.add_argument("--repo", help="owner/name for PUBLIC release hydration")
    parser.add_argument("--asset-dir", type=Path, help="already-mounted public/private release assets")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    package = index["packages"].get(args.package_id)
    if not isinstance(package, dict):
        raise SystemExit(f"unknown package: {args.package_id}")

    availability = package["weight_availability"]
    mirror = package["mirror"]
    if availability == "PUBLIC_OPEN_WEIGHTS":
        if mirror["state"] != "MIRRORED_VERIFIED":
            raise SystemExit(f"public package {args.package_id} is not an admitted mirror; state={mirror['state']}")
        expected_confidentiality = "PUBLIC"
    elif availability == "PRIVATE_OPERATOR_WEIGHTS":
        if mirror["state"] != "PRIVATE_MIRRORED_VERIFIED":
            raise SystemExit(f"private package {args.package_id} is not an admitted private mirror; state={mirror['state']}")
        if args.asset_dir is None:
            raise SystemExit("private weights require --asset-dir; public-repository download is forbidden")
        if args.repo:
            raise SystemExit("--repo is forbidden for private plaintext hydration")
        expected_confidentiality = "OPERATOR_PRIVATE"
    else:
        raise SystemExit(f"package {args.package_id} is not a local weight artifact")

    cleanup: tempfile.TemporaryDirectory[str] | None = None
    if args.asset_dir:
        asset_dir = args.asset_dir.resolve()
    else:
        if not args.repo:
            raise SystemExit("--repo is required for public hydration unless --asset-dir is supplied")
        cleanup = tempfile.TemporaryDirectory(prefix="aegis-model-assets-")
        asset_dir = Path(cleanup.name)
        subprocess.run([
            "gh", "release", "download", mirror["release_tag"],
            "--repo", args.repo, "--dir", str(asset_dir),
        ], check=True)

    try:
        release_manifest_path = asset_dir / "MODEL_RELEASE_MANIFEST.json"
        manifest_digest_path = asset_dir / "MODEL_RELEASE_MANIFEST.sha256"
        if not release_manifest_path.is_file() or not manifest_digest_path.is_file():
            raise SystemExit("artifact set is missing manifest or manifest digest")

        digest_line = manifest_digest_path.read_text(encoding="utf-8").strip().split()
        if len(digest_line) < 1:
            raise SystemExit("invalid artifact manifest digest file")
        verify(release_manifest_path, digest_line[0])

        release_manifest: dict[str, Any] = json.loads(release_manifest_path.read_text(encoding="utf-8"))
        if release_manifest.get("package_id") != args.package_id:
            raise SystemExit("artifact manifest package_id mismatch")
        if release_manifest.get("authority") != "EVIDENCE_ONLY":
            raise SystemExit("artifact manifest authority boundary changed")
        if release_manifest.get("confidentiality") != expected_confidentiality:
            raise SystemExit("artifact manifest confidentiality mismatch")
        if release_manifest.get("source") != package.get("source"):
            raise SystemExit("artifact source does not match canonical package source")

        checkout = ROOT / package["checkout_path"]
        if checkout.exists():
            shutil.rmtree(checkout)
        checkout.mkdir(parents=True)

        verified_files: list[dict[str, Any]] = []
        for file_record in release_manifest.get("files", []):
            relative = Path(file_record["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise SystemExit(f"unsafe artifact path: {relative}")
            destination = checkout / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as output:
                for part in file_record["parts"]:
                    asset = asset_dir / part["asset"]
                    if not asset.is_file():
                        raise SystemExit(f"missing artifact asset: {part['asset']}")
                    if asset.stat().st_size != part["size_bytes"]:
                        raise SystemExit(f"size mismatch: {part['asset']}")
                    verify(asset, part["sha256"])
                    with asset.open("rb") as handle:
                        shutil.copyfileobj(handle, output, length=8 * 1024 * 1024)
            if destination.stat().st_size != file_record["size_bytes"]:
                raise SystemExit(f"reconstructed size mismatch: {relative}")
            verify(destination, file_record["sha256"])
            verified_files.append({
                "path": destination.relative_to(ROOT).as_posix(),
                "sha256": file_record["sha256"],
                "size_bytes": file_record["size_bytes"],
            })

        canonical_required = {
            record["path"]: record["sha256"]
            for record in package["files"]
            if record.get("required_for_local_execution")
        }
        release_files = {record["path"]: record["sha256"] for record in release_manifest.get("files", [])}
        for path, expected in canonical_required.items():
            if release_files.get(path) != expected:
                raise SystemExit(f"canonical required file is absent or mismatched in mirror: {path}")

        receipt = {
            "receipt_kind": "MODEL_HYDRATION_RECEIPT_V1",
            "package_id": args.package_id,
            "weight_availability": availability,
            "release_tag": mirror.get("release_tag"),
            "source": package["source"],
            "outcome": "LOCAL_VERIFIED",
            "authority": "EVIDENCE_ONLY",
            "files": verified_files,
        }
        encoded = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
    finally:
        if cleanup is not None:
            cleanup.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
