#!/usr/bin/env python3
"""Deterministic, exact-head repository knowledge snapshots.

This module is intentionally authority-neutral.  It observes a Git commit/tree and
produces content-addressed repository knowledge suitable for later admission gates;
it does not mutate repository state or grant execution authority.
"""
from __future__ import annotations

import hashlib
import re
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "1"
LEGACY_INVENTORY_PATH = "reports/inventory.json"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _git_text(repo: Path, *args: str) -> str:
    return _git(repo, *args).stdout.strip()


def _canonical_json(value: Any) -> bytes:
    """Return one deterministic JSON encoding used by every receipt digest."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _category(path: str) -> str:
    normalized = path.lower()
    name = normalized.rsplit("/", 1)[-1]

    if normalized.startswith(".github/workflows/") and normalized.endswith((".yml", ".yaml")):
        return "workflow"
    if normalized.startswith("agents/") or "/agents/" in normalized:
        return "agent"
    if normalized.startswith("supabase/migrations/"):
        return "migration"
    if normalized.startswith("formal/") or "/formal/" in normalized or normalized.endswith(".v"):
        return "formal"
    if (
        normalized.startswith("tests/")
        or "/tests/" in normalized
        or name.startswith("test_")
        or name.startswith("test-")
    ):
        return "test"
    if normalized.startswith("docs/") or "/docs/" in normalized or normalized.endswith(".md"):
        return "documentation"
    if normalized.startswith("scripts/") or "/scripts/" in normalized:
        return "script"
    if normalized.startswith("harness/") or "/harness/" in normalized:
        return "harness"
    return "source"


def _tracked_artifacts(repo: Path) -> list[dict[str, str]]:
    """Enumerate the exact HEAD tree, independent of working-tree modifications."""
    raw = _git_text(repo, "ls-tree", "-r", "-z", "--full-tree", "HEAD")
    artifacts: list[dict[str, str]] = []

    if not raw:
        return artifacts

    for record in raw.split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode, object_type, object_sha = metadata.split(" ", 2)
        artifacts.append(
            {
                "path": path,
                "category": _category(path),
                "mode": mode,
                "object_type": object_type,
                "object_sha": object_sha,
            }
        )

    artifacts.sort(key=lambda item: item["path"])
    return artifacts


def _legacy_inventory(repo: Path, source_head_sha: str) -> dict[str, Any]:
    result = _git(repo, "show", f"{source_head_sha}:{LEGACY_INVENTORY_PATH}", check=False)
    if result.returncode != 0:
        return {
            "path": LEGACY_INVENTORY_PATH,
            "state": "ABSENT",
            "declared_head": None,
        }

    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {
            "path": LEGACY_INVENTORY_PATH,
            "state": "INVALID_JSON",
            "declared_head": None,
        }

    declared_head = payload.get("generated_from") if isinstance(payload, dict) else None
    if not isinstance(declared_head, str) or not declared_head:
        state = "MISSING_DECLARED_HEAD"
        declared_head = None
    elif declared_head == source_head_sha:
        state = "CURRENT_DECLARED_HEAD"
    else:
        state = "STALE_DECLARED_HEAD"

    return {
        "path": LEGACY_INVENTORY_PATH,
        "state": state,
        "declared_head": declared_head,
    }


def build_snapshot(
    repo: str | Path,
    *,
    repository_id: int,
    repository_full_name: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic knowledge snapshot bound to the checked-out Git HEAD."""
    root = Path(repo)
    source_head_sha = _git_text(root, "rev-parse", "HEAD")
    source_tree_sha = _git_text(root, "rev-parse", "HEAD^{tree}")
    artifacts = _tracked_artifacts(root)

    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "knowledge_status": "ESTABLISHED",
        "repository_id": repository_id,
        "repository_full_name": repository_full_name,
        "source_head_sha": source_head_sha,
        "source_tree_sha": source_tree_sha,
        "artifacts": artifacts,
        "artifacts_digest": _digest(artifacts),
        "legacy_inventory": _legacy_inventory(root, source_head_sha),
    }
    snapshot["snapshot_digest"] = _digest(snapshot)
    return snapshot


def _append_once(reasons: list[str], code: str) -> None:
    if code not in reasons:
        reasons.append(code)


def verify_snapshot_document(
    snapshot: Mapping[str, Any],
    *,
    expected_repository_id: int | None = None,
) -> dict[str, Any]:
    """Verify the snapshot's internal content addressing without consulting Git."""
    reasons: list[str] = []

    if snapshot.get("schema_version") != SCHEMA_VERSION:
        _append_once(reasons, "SCHEMA_VERSION_MISMATCH")
    if snapshot.get("knowledge_status") != "ESTABLISHED":
        _append_once(reasons, "KNOWLEDGE_STATUS_NOT_ESTABLISHED")
    if expected_repository_id is not None and snapshot.get("repository_id") != expected_repository_id:
        _append_once(reasons, "REPOSITORY_ID_MISMATCH")

    artifacts = snapshot.get("artifacts")
    if not isinstance(artifacts, list):
        _append_once(reasons, "ARTIFACTS_INVALID")
    else:
        paths = [item.get("path") for item in artifacts if isinstance(item, dict)]
        if len(paths) != len(artifacts) or any(not isinstance(path, str) for path in paths):
            _append_once(reasons, "ARTIFACTS_INVALID")
        elif paths != sorted(paths) or len(paths) != len(set(paths)):
            _append_once(reasons, "ARTIFACT_ORDER_INVALID")

        if snapshot.get("artifacts_digest") != _digest(artifacts):
            _append_once(reasons, "ARTIFACTS_DIGEST_MISMATCH")

    supplied_snapshot_digest = snapshot.get("snapshot_digest")
    unsigned = dict(snapshot)
    unsigned.pop("snapshot_digest", None)
    if supplied_snapshot_digest != _digest(unsigned):
        _append_once(reasons, "SNAPSHOT_DIGEST_MISMATCH")

    return {
        "status": "DENIED" if reasons else "ESTABLISHED",
        "reason_codes": reasons,
    }


def verify_snapshot(
    repo: str | Path,
    snapshot: Mapping[str, Any],
    *,
    expected_repository_id: int | None = None,
) -> dict[str, Any]:
    """Fail closed unless an internally valid snapshot still matches exact Git HEAD."""
    root = Path(repo)
    document = verify_snapshot_document(snapshot, expected_repository_id=expected_repository_id)
    reasons = list(document["reason_codes"])

    current_head_sha = _git_text(root, "rev-parse", "HEAD")
    current_tree_sha = _git_text(root, "rev-parse", "HEAD^{tree}")

    if snapshot.get("source_head_sha") != current_head_sha:
        _append_once(reasons, "SOURCE_HEAD_MISMATCH")
    if snapshot.get("source_tree_sha") != current_tree_sha:
        _append_once(reasons, "SOURCE_TREE_MISMATCH")

    return {
        "status": "DENIED" if reasons else "ESTABLISHED",
        "reason_codes": reasons,
        "current_head_sha": current_head_sha,
        "current_tree_sha": current_tree_sha,
    }


def _artifact_identity(item: Mapping[str, Any]) -> tuple[Any, Any, Any]:
    return (item.get("mode"), item.get("object_type"), item.get("object_sha"))


def compute_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Compute a deterministic path/object-exact delta between two snapshots."""
    before_items = {
        item["path"]: item
        for item in before.get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    after_items = {
        item["path"]: item
        for item in after.get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }

    before_paths = set(before_items)
    after_paths = set(after_items)
    added = sorted(after_paths - before_paths)
    deleted = sorted(before_paths - after_paths)
    modified = sorted(
        path
        for path in before_paths & after_paths
        if _artifact_identity(before_items[path]) != _artifact_identity(after_items[path])
    )

    delta: dict[str, Any] = {
        "from_head_sha": before.get("source_head_sha"),
        "to_head_sha": after.get("source_head_sha"),
        "added": added,
        "deleted": deleted,
        "modified": modified,
    }
    delta["delta_digest"] = _digest(delta)
    return delta



# Exported image receipts prove packaged bytes only. They are NOT independently
# signed build attestations and never grant operational authority.
RUNTIME_EXPORT_SCHEMA = "aegis-runtime-export/1"
_HEX40 = re.compile(r"^[a-f0-9]{40}$")


def _image_path(repo_path: str) -> str | None:
    if repo_path in ("vertex/serve.py", "serve.py"):
        return "serve.py"
    if repo_path.startswith(("agents/", "harness/")):
        name = repo_path.rsplit("/", 1)[-1]
        if name == ".env" or name.startswith(".env.") or name.endswith(".pyc") or "__pycache__" in repo_path.split("/"):
            return None
        return repo_path
    return None


def build_runtime_export_manifest(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Select tracked image files from a verified exact-head snapshot."""
    if verify_snapshot_document(snapshot)["status"] != "ESTABLISHED":
        raise ValueError("SOURCE_SNAPSHOT_INVALID")
    if not _HEX40.fullmatch(str(snapshot.get("source_head_sha", ""))) or not _HEX40.fullmatch(str(snapshot.get("source_tree_sha", ""))):
        raise ValueError("SOURCE_SHA_INVALID")
    files: list[dict[str, str]] = []
    for item in snapshot["artifacts"]:
        name = _image_path(item["path"])
        if name is None:
            continue
        if item["object_type"] != "blob" or item["mode"] not in ("100644", "100755"):
            raise ValueError("RUNTIME_SOURCE_NONREGULAR")
        if not _HEX40.fullmatch(item["object_sha"]):
            raise ValueError("RUNTIME_SOURCE_BLOB_INVALID")
        files.append({"path": name, "git_blob_sha": item["object_sha"]})
    files.sort(key=lambda x: x["path"])
    names = [x["path"] for x in files]
    if "serve.py" not in names or names != sorted(set(names)):
        raise ValueError("RUNTIME_SOURCE_INCOMPLETE")
    record = {
        "schema": RUNTIME_EXPORT_SCHEMA,
        "source_head_sha": snapshot["source_head_sha"],
        "source_tree_sha": snapshot["source_tree_sha"],
        "source_snapshot_digest": snapshot["snapshot_digest"],
        "files": files,
        "authority": "CONTENT_OBSERVATION_ONLY",
        "attestation": "NOT_PRESENT",
    }
    record["manifest_digest"] = _digest(record)
    return record


def verify_runtime_export_manifest(image_root: str | Path, manifest: Mapping[str, Any], *, expected_head: str) -> dict[str, Any]:
    """Compare image files with a manifest, without Git or elevated authority."""
    if not isinstance(manifest, Mapping):
        return {"status": "DENIED", "reason_codes": ["MANIFEST_INVALID"]}
    errors: set[str] = set()
    unsigned = dict(manifest)
    digest = unsigned.pop("manifest_digest", None)
    if digest != _digest(unsigned):
        errors.add("MANIFEST_DIGEST_MISMATCH")
    if manifest.get("schema") != RUNTIME_EXPORT_SCHEMA:
        errors.add("MANIFEST_SCHEMA_INVALID")
    if manifest.get("authority") != "CONTENT_OBSERVATION_ONLY" or manifest.get("attestation") != "NOT_PRESENT":
        errors.add("AUTHORITY_CLAIM_INVALID")
    if not _HEX40.fullmatch(str(expected_head)) or manifest.get("source_head_sha") != expected_head:
        errors.add("SOURCE_HEAD_MISMATCH")
    if not _HEX40.fullmatch(str(manifest.get("source_tree_sha", ""))):
        errors.add("SOURCE_TREE_INVALID")
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        records = []
        errors.add("FILE_INVENTORY_INVALID")
    expected: dict[str, str] = {}
    names: list[str] = []
    for item in records:
        if not isinstance(item, dict):
            errors.add("FILE_INVENTORY_INVALID")
            continue
        name, blob = item.get("path"), item.get("git_blob_sha")
        if not isinstance(name, str) or _image_path(name) != name:
            errors.add("FILE_PATH_INVALID")
            continue
        if not _HEX40.fullmatch(str(blob)):
            errors.add("FILE_BLOB_INVALID")
            continue
        names.append(name)
        expected[name] = blob
    if names != sorted(names) or len(names) != len(set(names)) or "serve.py" not in names:
        errors.add("FILE_INVENTORY_ORDER_INVALID")
    root = Path(image_root)
    actual: set[str] = set()
    for dirname in ("agents", "harness"):
        directory = root / dirname
        if directory.is_symlink() or not directory.is_dir():
            errors.add("PACKAGE_DIRECTORY_MISSING")
            continue
        for item in directory.rglob("*"):
            name = item.relative_to(root).as_posix()
            if item.is_symlink():
                errors.add("SYMLINK_DENIED")
            elif item.is_file() and _image_path(name) is not None:
                actual.add(name)
    if (root / "serve.py").is_file():
        actual.add("serve.py")
    if actual != set(expected):
        errors.add("FILE_SET_MISMATCH")
    for name, sha in expected.items():
        target = root / name
        try:
            if target.is_symlink() or not target.is_file():
                errors.add("FILE_MISSING_OR_SYMLINK")
                continue
            body = target.read_bytes()
            raw = b"blob " + str(len(body)).encode("ascii") + b"\0" + body
            if hashlib.sha1(raw).hexdigest() != sha:
                errors.add("FILE_CONTENT_MISMATCH")
        except OSError:
            errors.add("FILE_UNREADABLE")
    return {
        "status": "DENIED" if errors else "CONTENT_MATCH_ONLY",
        "reason_codes": sorted(errors),
        "source_head_sha": manifest.get("source_head_sha"),
        "source_tree_sha": manifest.get("source_tree_sha"),
        "manifest_digest": digest,
        "authority": "NOT_GRANTED",
        "attestation": "NOT_PRESENT",
    }



__all__ = [
    "build_snapshot",
    "compute_delta",
    "verify_snapshot",
    "verify_snapshot_document",
    "build_runtime_export_manifest",
    "verify_runtime_export_manifest",
]
