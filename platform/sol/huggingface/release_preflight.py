from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any


GIT_OBJECT_RE = re.compile(r"^[0-9a-f]{40,64}$")


class ReleaseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseFile:
    source: Path
    destination: str
    sha256: str
    size_bytes: int


def load_release(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0.0":
        raise ReleaseError("unsupported release schema")
    if data.get("artifact_kind") != "configuration-holon-no-weights":
        raise ReleaseError("release must declare the no-weights artifact kind")
    if data.get("grants_authority") is not False:
        raise ReleaseError("holon release must not grant authority")
    return data


def require_pinned_revision(value: str | None) -> str:
    if value is None or not GIT_OBJECT_RE.fullmatch(value):
        raise ReleaseError("base model revision must be an immutable Hub commit")
    return value


def collect_release_files(repo_root: Path, release: dict[str, Any]) -> list[ReleaseFile]:
    source_root = repo_root / str(release["source_root"])
    model_card = repo_root / str(release["model_card"])
    forbidden = tuple(str(item) for item in release["forbidden_artifact_suffixes"])
    candidates = [(model_card, "README.md")]
    candidates.extend((source_root / rel, rel) for rel in release["artifacts"])

    files: list[ReleaseFile] = []
    for source, destination in candidates:
        if not source.is_file():
            raise ReleaseError(f"missing release artifact: {source.relative_to(repo_root)}")
        if source.suffix.lower() in forbidden:
            raise ReleaseError(f"weight-like artifact is forbidden: {source.name}")
        raw = source.read_bytes()
        files.append(ReleaseFile(source, destination, sha256(raw).hexdigest(), len(raw)))
    return sorted(files, key=lambda item: item.destination)


def build_manifest(release: dict[str, Any], files: list[ReleaseFile], revision: str) -> dict[str, Any]:
    payload = {
        "schema_version": "1.0.0",
        "repository_id": release["repository_id"],
        "artifact_kind": release["artifact_kind"],
        "holon_id": release["holon_id"],
        "base_model": {**release["base_model"], "revision": revision},
        "evidence_tier": release["evidence_tier"],
        "grants_authority": False,
        "files": [
            {"path": item.destination, "sha256": item.sha256, "size_bytes": item.size_bytes}
            for item in files
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**payload, "manifest_digest": sha256(canonical).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a governed oGemma Hub release")
    parser.add_argument("--release", type=Path, default=Path(__file__).with_name("ogemma-release.v1.json"))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--base-revision")
    args = parser.parse_args()

    release = load_release(args.release)
    revision = require_pinned_revision(args.base_revision or release["base_model"].get("revision"))
    if not str(release["repository_id"]).startswith("aegis-omega/"):
        raise ReleaseError("destination must be owned by aegis-omega")
    files = collect_release_files(args.repo_root, release)
    print(json.dumps(build_manifest(release, files, revision), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseError as exc:
        print(f"DENIED: {exc}", file=sys.stderr)
        raise SystemExit(2)
