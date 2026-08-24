#!/usr/bin/env python3
"""Package verified PUBLIC open-model bytes into repo-owned release assets.

Private operator weights are deliberately rejected here. They use a separate
private/encrypted packaging path so a public-repository release command can
never publish plaintext private checkpoints by accident.

The default mode is local-only and side-effect free outside the staging directory.
`--upload` is deliberately guarded by `--operator-approved-upload`; publishing a
large model mirror is an external effect and must not happen implicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
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


def asset_prefix(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/")
    readable = normalized.replace("/", "__")
    path_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{path_hash}__{readable}"


def copy_chunked(source: Path, destination: Path, chunk_max: int, *, relative_path: str) -> list[dict[str, Any]]:
    destination.mkdir(parents=True, exist_ok=True)
    parts: list[dict[str, Any]] = []
    prefix = asset_prefix(relative_path)
    with source.open("rb") as src:
        index = 0
        while True:
            chunk = src.read(chunk_max)
            if not chunk:
                break
            name = f"{prefix}.part-{index:05d}"
            part_path = destination / name
            if part_path.exists():
                raise SystemExit(f"release asset collision: {name}")
            part_path.write_bytes(chunk)
            parts.append({"asset": name, "size_bytes": len(chunk), "sha256": hashlib.sha256(chunk).hexdigest()})
            index += 1
    return parts


def run_checked(argv: list[str]) -> None:
    subprocess.run(argv, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_id")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--repo", help="owner/name for optional GitHub release upload")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--operator-approved-upload", action="store_true")
    args = parser.parse_args()

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    package = index["packages"].get(args.package_id)
    if not isinstance(package, dict):
        raise SystemExit(f"unknown package: {args.package_id}")
    if package["weight_availability"] != "PUBLIC_OPEN_WEIGHTS":
        raise SystemExit("only PUBLIC_OPEN_WEIGHTS packages may use the public release packager")
    source = package["source"]
    if source.get("revision_kind") != "FULL_COMMIT_SHA" or len(source.get("revision", "")) != 40:
        raise SystemExit("refusing mirror: exact 40-char upstream source revision is required")
    if package["license"].get("redistribution_status") != "PERMITTED_BY_DECLARED_LICENSE":
        raise SystemExit("refusing mirror: redistribution permission is not established")

    source_dir = args.source_dir.resolve()
    if not source_dir.is_dir():
        raise SystemExit(f"source directory does not exist: {source_dir}")

    staging = args.staging_dir.resolve()
    if staging.exists():
        shutil.rmtree(staging)
    asset_dir = staging / "assets"
    asset_dir.mkdir(parents=True)
    chunk_max = int(index["storage_policy"]["release_asset_chunk_max_bytes"])

    files: list[dict[str, Any]] = []
    for path in sorted(p for p in source_dir.rglob("*") if p.is_file()):
        relative = path.relative_to(source_dir).as_posix()
        original_sha = sha256_file(path)
        parts = copy_chunked(path, asset_dir, chunk_max, relative_path=relative)
        files.append({"path": relative, "size_bytes": path.stat().st_size, "sha256": original_sha, "parts": parts})

    release_manifest = {
        "schema_version": "1.1.0",
        "receipt_kind": "MODEL_RELEASE_MANIFEST_V1",
        "package_id": args.package_id,
        "authority": "EVIDENCE_ONLY",
        "confidentiality": "PUBLIC",
        "source": source,
        "license": package["license"],
        "release_tag": package["mirror"]["release_tag"],
        "chunk_max_bytes": chunk_max,
        "files": files,
    }
    manifest_path = staging / "MODEL_RELEASE_MANIFEST.json"
    manifest_path.write_text(json.dumps(release_manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    manifest_sha = sha256_file(manifest_path)
    (staging / "MODEL_RELEASE_MANIFEST.sha256").write_text(f"{manifest_sha}  MODEL_RELEASE_MANIFEST.json\n", encoding="utf-8")

    print(f"MODEL_RELEASE_STAGED package={args.package_id} files={len(files)} manifest_sha256={manifest_sha}")

    if args.upload:
        if not args.operator_approved_upload:
            raise SystemExit("--upload requires --operator-approved-upload")
        if not args.repo:
            raise SystemExit("--upload requires --repo owner/name")
        tag = package["mirror"]["release_tag"]
        if not tag:
            raise SystemExit("package has no release tag")
        run_checked([
            "gh", "release", "create", tag, "--repo", args.repo,
            "--title", f"AEGIS model artifact: {args.package_id}",
            "--notes", "Proof-bound public model artifact mirror. Model bytes are capability/evidence only, never authority.",
        ])
        upload_paths = [str(p) for p in sorted(asset_dir.iterdir())]
        upload_paths.extend([str(manifest_path), str(staging / "MODEL_RELEASE_MANIFEST.sha256")])
        run_checked(["gh", "release", "upload", tag, "--repo", args.repo, *upload_paths])
        print(f"MODEL_RELEASE_UPLOADED package={args.package_id} tag={tag}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
