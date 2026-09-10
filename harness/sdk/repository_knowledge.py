#!/usr/bin/env python3
"""Deterministic, exact-head repository knowledge snapshots.

This module is intentionally authority-neutral. It observes a Git commit/tree and
produces content-addressed repository knowledge suitable for later admission gates;
it does not mutate repository state or grant execution authority.

A complete snapshot enumerates every Git-tracked HEAD entry. Content hints are
bounded navigation aids only: they do not establish semantic understanding or
absence outside the exact tracked source tree.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "1"
LEGACY_INVENTORY_PATH = "reports/inventory.json"
COVERAGE_SCOPE = "all_git_tracked_head_entries"
ABSENCE_CLAIM_BOUNDARY = (
    "exact_head_tracked_content_only; semantic_or_external_absence_not_established"
)


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


def _tracked_artifacts(repo: Path) -> list[dict[str, Any]]:
    """Enumerate the exact HEAD tree, independent of working-tree modifications."""
    raw = _git_text(repo, "ls-tree", "-r", "-z", "--full-tree", "HEAD")
    artifacts: list[dict[str, Any]] = []

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


def _read_objects(repo: Path, shas: Iterable[str]) -> dict[str, bytes]:
    """Read Git objects with bounded request/response streaming.

    One request is flushed and fully consumed before the next. This avoids the
    stdin/stdout deadlock possible when thousands of requests are enqueued before
    object bytes are drained. Memory is bounded by the returned object set in this
    helper; callers use it only for the exact tracked snapshot being built.
    """
    ordered = list(dict.fromkeys(shas))
    if not ordered:
        return {}

    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=repo,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None

    result: dict[str, bytes] = {}
    try:
        for expected_sha in ordered:
            proc.stdin.write(f"{expected_sha}\n".encode("ascii"))
            proc.stdin.flush()
            header = proc.stdout.readline()
            if not header:
                error = proc.stderr.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"git cat-file ended early: {error}")
            parts = header.rstrip(b"\n").split()
            if len(parts) == 2 and parts[1] == b"missing":
                raise RuntimeError(f"git object missing: {expected_sha}")
            if len(parts) != 3:
                raise RuntimeError(f"unexpected git cat-file header: {header!r}")
            actual_sha = parts[0].decode("ascii")
            size = int(parts[2])
            if actual_sha != expected_sha:
                raise RuntimeError(
                    f"git cat-file order mismatch: expected {expected_sha}, got {actual_sha}"
                )
            data = proc.stdout.read(size)
            trailer = proc.stdout.read(1)
            if len(data) != size or trailer != b"\n":
                raise RuntimeError(f"truncated git object: {expected_sha}")
            result[expected_sha] = data

        proc.stdin.close()
        return_code = proc.wait(timeout=30)
        if return_code != 0:
            error = proc.stderr.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"git cat-file failed ({return_code}): {error}")
        return result
    finally:
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if not stream.closed:
                    stream.close()
            except OSError:
                # Teardown is best-effort; process termination below is authoritative cleanup.
                pass
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def _bounded_content_hints(path: str, data: bytes) -> tuple[list[str], str | None]:
    """Return deterministic navigation hints without promoting semantic claims."""
    if b"\0" in data:
        return [], None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [], None

    symbols: list[str] = []
    patterns: list[re.Pattern[str]] = []
    lower = path.lower()
    if lower.endswith(".py"):
        patterns.append(re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)", re.MULTILINE))
    elif lower.endswith((".ts", ".tsx")):
        patterns.append(
            re.compile(
                r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|interface|type|enum|namespace)\s+([A-Za-z_$][\w$]*)",
                re.MULTILINE,
            )
        )
    elif lower.endswith((".js", ".jsx", ".mjs", ".cjs")):
        patterns.append(
            re.compile(
                r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)",
                re.MULTILINE,
            )
        )
    elif lower.endswith(".v"):
        patterns.append(
            re.compile(
                r"^\s*(?:Theorem|Lemma|Definition|Fixpoint|Inductive|Record|Class|Axiom|Parameter)\s+([A-Za-z_]\w*)",
                re.MULTILINE,
            )
        )

    for pattern in patterns:
        for match in pattern.finditer(text):
            symbol = match.group(1)
            if symbol not in symbols:
                symbols.append(symbol)
            if len(symbols) >= 64:
                break
        if len(symbols) >= 64:
            break

    heading: str | None = None
    if lower.endswith((".md", ".mdx")):
        match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
        if match:
            heading = match.group(1).strip()[:240]

    return symbols, heading


def _enrich_artifacts(repo: Path, artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    objects = _read_objects(repo, (item["object_sha"] for item in artifacts))
    enriched: list[dict[str, Any]] = []
    for item in artifacts:
        data = objects[item["object_sha"]]
        symbols, heading = _bounded_content_hints(item["path"], data)
        enriched_item = dict(item)
        enriched_item.update(
            {
                "content_sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
                "symbol_hints": symbols,
                "heading_hint": heading,
            }
        )
        enriched.append(enriched_item)
    return enriched


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
    artifacts = _enrich_artifacts(root, _tracked_artifacts(root))
    tracked_count = len(artifacts)
    indexed_count = len(artifacts)
    coverage = 1.0 if indexed_count == tracked_count else (
        indexed_count / tracked_count if tracked_count else 1.0
    )

    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "knowledge_status": "ESTABLISHED",
        "repository_id": repository_id,
        "repository_full_name": repository_full_name,
        "source_head_sha": source_head_sha,
        "source_tree_sha": source_tree_sha,
        "coverage_scope": COVERAGE_SCOPE,
        "tracked_file_count": tracked_count,
        "eligible_file_count": tracked_count,
        "indexed_file_count": indexed_count,
        "coverage": coverage,
        "absence_claim_boundary": ABSENCE_CLAIM_BOUNDARY,
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
    """Verify snapshot content addressing and complete exact-head coverage."""
    reasons: list[str] = []

    if snapshot.get("schema_version") != SCHEMA_VERSION:
        _append_once(reasons, "SCHEMA_VERSION_MISMATCH")
    if snapshot.get("knowledge_status") != "ESTABLISHED":
        _append_once(reasons, "KNOWLEDGE_STATUS_NOT_ESTABLISHED")
    if expected_repository_id is not None and snapshot.get("repository_id") != expected_repository_id:
        _append_once(reasons, "REPOSITORY_ID_MISMATCH")
    if snapshot.get("coverage_scope") != COVERAGE_SCOPE:
        _append_once(reasons, "COVERAGE_SCOPE_MISMATCH")
    if snapshot.get("absence_claim_boundary") != ABSENCE_CLAIM_BOUNDARY:
        _append_once(reasons, "ABSENCE_CLAIM_BOUNDARY_MISMATCH")

    tracked = snapshot.get("tracked_file_count")
    eligible = snapshot.get("eligible_file_count")
    indexed = snapshot.get("indexed_file_count")
    if (
        type(tracked) is not int
        or type(eligible) is not int
        or type(indexed) is not int
        or tracked < 0
        or eligible < 0
        or indexed < 0
        or not (tracked == eligible == indexed)
        or snapshot.get("coverage") != 1.0
    ):
        _append_once(reasons, "REPOSITORY_COVERAGE_INCOMPLETE")

    artifacts = snapshot.get("artifacts")
    if not isinstance(artifacts, list):
        _append_once(reasons, "ARTIFACTS_INVALID")
    else:
        paths = [item.get("path") for item in artifacts if isinstance(item, dict)]
        if len(paths) != len(artifacts) or any(not isinstance(path, str) for path in paths):
            _append_once(reasons, "ARTIFACTS_INVALID")
        elif paths != sorted(paths) or len(paths) != len(set(paths)):
            _append_once(reasons, "ARTIFACT_ORDER_INVALID")
        if type(indexed) is int and len(artifacts) != indexed:
            _append_once(reasons, "INDEXED_COUNT_MISMATCH")
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            digest = item.get("content_sha256")
            size = item.get("size_bytes")
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                _append_once(reasons, "ARTIFACT_CONTENT_DIGEST_INVALID")
            if type(size) is not int or size < 0:
                _append_once(reasons, "ARTIFACT_SIZE_INVALID")
            if not isinstance(item.get("symbol_hints"), list):
                _append_once(reasons, "ARTIFACT_HINTS_INVALID")

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


__all__ = [
    "build_snapshot",
    "compute_delta",
    "verify_snapshot",
    "verify_snapshot_document",
]
