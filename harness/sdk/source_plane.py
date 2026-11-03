#!/usr/bin/env python3
"""AEGIS Source Plane V1: pinned, sparse, READ-ONLY GitHub source access.

This is an additive adapter to harness/sdk/repository_knowledge.py, NOT a
replacement for Git, Pando, Scion, branch protections, or authorization gates.

Only immutable commit and blob endpoints are used. No Git clones, checkouts,
refs updates, branches, merges, deployments, or persistent caches are created.
A manifest does not grant an agent authority to write.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import importlib.util
import os
import re
import sys
import subprocess
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import Future
from threading import Lock
from typing import Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCHEMA_VERSION = "aegis.source-plane.v1"
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAX_JSON_BYTES = 12 * 1024 * 1024
MAX_BLOB_BYTES = 2 * 1024 * 1024


class SourcePlaneError(ValueError):
    """Fail-closed source resolution, authentication, or integrity error."""


def canonical_bytes(value: object) -> bytes:
    # Matches the serialization used by AEGIS repository_knowledge._canonical_json.
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def validate_repo(value: str) -> str:
    if not isinstance(value, str) or not _REPO.fullmatch(value) or ".." in value:
        raise SourcePlaneError("invalid repository owner/name")
    return value


def validate_sha(value: str) -> str:
    if not isinstance(value, str) or not _FULL_SHA.fullmatch(value):
        raise SourcePlaneError("require an exact lowercase 40-character SHA-1 commit/object ID")
    return value


def validate_path(value: str) -> tuple[str, ...]:
    if (not isinstance(value, str) or not value or "\\" in value or
            "\x00" in value or value.startswith("/")):
        raise SourcePlaneError("invalid relative repository file path")
    parts = tuple(value.split("/"))
    if len(parts) > 32 or len(value.encode("utf-8")) > 1024:
        raise SourcePlaneError("repository path exceeds safe limits")
    if any(part in ("", ".", "..") for part in parts):
        raise SourcePlaneError("invalid relative repository file path")
    return parts


def git_blob_oid(blob: bytes) -> str:
    """Git SHA-1 object ID, not plain SHA-1(content)."""
    return hashlib.sha1(b"blob " + str(len(blob)).encode("ascii") + b"\0" + blob).hexdigest()


def default_transport(api_path: str, token: str | None) -> bytes:
    """One GET to approved public GitHub REST API; no arbitrary URL accepted."""
    if not api_path.startswith("/repos/") or "//" in api_path:
        raise SourcePlaneError("unsupported API path")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "AEGIS-source-plane-v1",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request("https://api.github.com" + api_path, headers=headers, method="GET")
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            raw = response.read(MAX_JSON_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        # Never include URL query or authentication material in diagnostics.
        raise SourcePlaneError("GitHub read unavailable or not permitted") from exc
    if len(raw) > MAX_JSON_BYTES:
        raise SourcePlaneError("API response exceeds safe size limit")
    return raw


class LocalGitTransport:
    """Offline, read-only transport backed by *existing* Git object stores.

    A pinned allowlist makes the mapping explicit. No clone/fetch/checkout/mutation.
    Every object is verified against its Git SHA-1 object ID before return.
    """

    _ROUTE = re.compile(
        r"^/repos/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/git/(commits|trees|blobs)/([0-9a-f]{40})$"
    )
    MAX_OBJECT_BYTES = 8 * 1024 * 1024

    def __init__(self, repositories: Mapping[str, str | Path]) -> None:
        if not repositories:
            raise SourcePlaneError("local transport needs an explicit repository mapping")
        self.roots: dict[str, Path] = {}
        for repo, path in repositories.items():
            validate_repo(repo)
            root = Path(path).resolve(strict=True)
            if not root.is_dir():
                raise SourcePlaneError("local repository root is not a directory")
            try:
                name = self._git(root, "rev-parse", "--show-toplevel", limit=4096).decode().strip()
                fmt = self._git(root, "rev-parse", "--show-object-format", limit=128).decode().strip()
            except (ValueError, UnicodeDecodeError) as exc:
                raise SourcePlaneError("local repository is unavailable") from exc
            if Path(name).resolve() != root or fmt != "sha1":
                raise SourcePlaneError("local repository must be exact worktree root using Git SHA-1")
            self.roots[repo] = root

    @staticmethod
    def _git(root: Path, *args: str, limit: int = MAX_OBJECT_BYTES) -> bytes:
        try:
            result = subprocess.run(
                ["git", "--no-pager", "-C", str(root), *args],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, timeout=12, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SourcePlaneError("local Git object lookup unavailable") from exc
        if result.returncode != 0 or len(result.stdout) > limit:
            raise SourcePlaneError("local Git object missing or exceeds size limit")
        return result.stdout

    def _object(self, root: Path, kind: str, sha: str) -> bytes:
        validate_sha(sha)
        found = self._git(root, "cat-file", "-t", sha, limit=128).decode("ascii").strip()
        if found != kind:
            raise SourcePlaneError("local Git object type mismatch")
        size_text = self._git(root, "cat-file", "-s", sha, limit=128).decode("ascii").strip()
        try:
            size = int(size_text)
        except ValueError as exc:
            raise SourcePlaneError("local Git object size unavailable") from exc
        if size > self.MAX_OBJECT_BYTES:
            raise SourcePlaneError("local Git object exceeds safe size limit")
        raw = self._git(root, "cat-file", kind, sha)
        if len(raw) != size:
            raise SourcePlaneError("local Git object size mismatch")
        actual = hashlib.sha1(kind.encode("ascii") + b" " + str(size).encode("ascii") + b"\0" + raw).hexdigest()
        if actual != sha:
            raise SourcePlaneError("local Git object hash mismatch")
        return raw

    @staticmethod
    def _entries(raw: bytes) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        offset = 0
        while offset < len(raw):
            space = raw.find(b" ", offset)
            nul = raw.find(b"\0", space + 1)
            if space < 0 or nul < 0 or nul + 21 > len(raw):
                raise SourcePlaneError("invalid raw Git tree entry")
            try:
                mode = raw[offset:space].decode("ascii")
                path = raw[space + 1:nul].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SourcePlaneError("unsupported non-UTF8 Git tree path") from exc
            sha = raw[nul + 1:nul + 21].hex()
            offset = nul + 21
            if mode == "40000":
                entry_kind, mode = "tree", "040000"
            elif mode in ("100644", "100755", "120000"):
                entry_kind = "blob"
            elif mode == "160000":
                entry_kind = "commit"
            else:
                raise SourcePlaneError("unsupported raw Git tree entry mode")
            if not path or "/" in path or "\0" in path:
                raise SourcePlaneError("invalid raw Git tree entry path")
            entries.append({"path": path, "sha": sha, "mode": mode, "type": entry_kind})
        return entries

    def __call__(self, api_path: str, token: str | None = None) -> bytes:
        if token is not None:
            raise SourcePlaneError("local Git transport never accepts credentials")
        match = self._ROUTE.fullmatch(api_path)
        if not match:
            raise SourcePlaneError("local Git transport denied unrecognized route")
        owner, name, route, sha = match.groups()
        repo = f"{owner}/{name}"
        root = self.roots.get(repo)
        if root is None:
            raise SourcePlaneError("repository not explicitly mapped")
        kind = {"commits": "commit", "trees": "tree", "blobs": "blob"}[route]
        raw = self._object(root, kind, sha)
        if kind == "commit":
            first = raw.split(b"\n", 1)[0]
            if not first.startswith(b"tree "):
                raise SourcePlaneError("Git commit has no root tree")
            try:
                tree_sha = validate_sha(first[5:].decode("ascii"))
            except UnicodeDecodeError as exc:
                raise SourcePlaneError("invalid root Git tree") from exc
            value: dict[str, object] = {"sha": sha, "tree": {"sha": tree_sha}}
        elif kind == "tree":
            value = {"sha": sha, "truncated": False, "tree": self._entries(raw)}
        else:
            value = {"sha": sha, "size": len(raw), "encoding": "base64",
                     "content": base64.b64encode(raw).decode("ascii")}
        return canonical_bytes(value)


def verify_local_repository_binding(
    manifest: Mapping[str, object], repositories: Mapping[str, str | Path]
) -> dict[str, object]:
    """Check manifest vs exact local HEAD using the existing repo knowledge API.

    Does not establish remote permissions, approval, or deployment authority.
    Requires harness/sdk/repository_knowledge.py from the canonical AEGIS tree.
    """
    doc = verify_manifest_document(manifest)
    if doc["status"] != "ESTABLISHED":
        return doc
    canonical_module = Path(__file__).with_name("repository_knowledge.py")
    if not canonical_module.is_file():
        raise SourcePlaneError("canonical AEGIS repository_knowledge module missing")
    try:
        spec = importlib.util.spec_from_file_location("aegis_canonical_repository_knowledge", canonical_module)
        if spec is None or spec.loader is None:
            raise SourcePlaneError("canonical AEGIS repository_knowledge module unavailable")
        knowledge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(knowledge)
        build_snapshot = knowledge.build_snapshot
        verify_snapshot = knowledge.verify_snapshot
    except (ImportError, AttributeError, OSError) as exc:
        raise SourcePlaneError("canonical AEGIS repository_knowledge module unavailable") from exc
    reasons: list[str] = []
    # A recomputed digest alone does not prove content; re-read immutable local
    # Git objects and compare independently reconstructed identity + blob digest.
    plane = SourcePlane(transport=LocalGitTransport(repositories))
    for item in manifest["artifacts"]:
        expected = plane.artifact(ArtifactRequest(item["repository"], item["commit_sha"], item["path"]))
        if expected != item:
            reasons.append(f"ARTIFACT_CONTENT_MISMATCH:{item['repository']}:{item['path']}")
    snapshots: dict[str, dict[str, object]] = {}
    for repo, path in repositories.items():
        validate_repo(repo)
        # Repository numeric identity is not inferred from a name; zero here is a
        # local-only sentinel. Remote authorization MUST NOT use this receipt.
        snap = build_snapshot(path, repository_id=0, repository_full_name=repo)
        verified = verify_snapshot(path, snap, expected_repository_id=0)
        if verified["status"] != "ESTABLISHED":
            reasons.append(f"REPOSITORY_KNOWLEDGE_DENIED:{repo}")
        snapshots[repo] = snap
    for item in manifest["artifacts"]:
        repo = item["repository"]
        snap = snapshots.get(repo)
        if snap is None or item["commit_sha"] != snap["source_head_sha"]:
            reasons.append(f"SOURCE_HEAD_MISMATCH:{repo}")
            continue
        if item["tree_sha"] != snap["source_tree_sha"]:
            reasons.append(f"SOURCE_TREE_MISMATCH:{repo}")
        by_path = {i["path"]: i for i in snap["artifacts"]}
        tracked = by_path.get(item["path"])
        if tracked is None or tracked["object_sha"] != item["blob_sha1"] or tracked["mode"] != item["mode"]:
            reasons.append(f"GIT_TREE_CONTENT_MISMATCH:{repo}:{item['path']}")
    return {"status": "DENIED" if reasons else "ESTABLISHED",
            "reason_codes": sorted(set(reasons)), "authority": "NONE"}


@dataclass(frozen=True)
class ArtifactRequest:
    repository: str
    commit_sha: str
    path: str

    def __post_init__(self) -> None:
        validate_repo(self.repository)
        validate_sha(self.commit_sha)
        validate_path(self.path)


class SourcePlane:
    """Exact-commit source reads. Per-instance cache is memory-only and repo-scoped."""

    def __init__(self, *, transport: Callable[[str, str | None], bytes] = default_transport,
                 token: str | None = None, max_blob_bytes: int = MAX_BLOB_BYTES) -> None:
        if max_blob_bytes < 0 or max_blob_bytes > MAX_BLOB_BYTES:
            raise SourcePlaneError("invalid blob size limit")
        self.transport = transport
        self.token = token
        self.max_blob_bytes = max_blob_bytes
        self._api_cache: dict[str, Mapping[str, object]] = {}
        # A request keyed by immutable Git object path has one in-flight owner.
        # Different object paths can load in parallel without locking transport I/O.
        self._cache_lock = Lock()
        self._inflight: dict[str, Future[Mapping[str, object]]] = {}
        self._blob_cache: dict[tuple[str, str], bytes] = {}

    def _get(self, api_path: str) -> Mapping[str, object]:
        """Deduplicate concurrent immutable Git object reads, without serializing I/O.

        A failed read is never admitted to the cache, and all concurrent callers
        receive the failure. A later request may retry using the same instance.
        """
        with self._cache_lock:
            cached = self._api_cache.get(api_path)
            if cached is not None:
                return cached
            pending = self._inflight.get(api_path)
            owner = pending is None
            if owner:
                pending = Future()
                self._inflight[api_path] = pending
        assert pending is not None
        if not owner:
            return pending.result()
        try:
            raw = self.transport(api_path, self.token)
            if len(raw) > MAX_JSON_BYTES:
                raise SourcePlaneError("API response exceeds safe size limit")
            try:
                value = json.loads(raw)
            except (ValueError, UnicodeDecodeError) as exc:
                raise SourcePlaneError("GitHub API returned invalid JSON") from exc
            if not isinstance(value, dict):
                raise SourcePlaneError("GitHub API returned non-object")
        except BaseException as exc:
            with self._cache_lock:
                self._inflight.pop(api_path, None)
                pending.set_exception(exc)
            raise
        with self._cache_lock:
            self._api_cache[api_path] = value
            self._inflight.pop(api_path, None)
            pending.set_result(value)
        return value

    @staticmethod
    def _prefix(repo: str) -> str:
        owner, name = validate_repo(repo).split("/", 1)
        return f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}"

    def commit_tree(self, repo: str, sha: str) -> str:
        validate_sha(sha)
        value = self._get(self._prefix(repo) + "/git/commits/" + sha)
        if value.get("sha") != sha:
            raise SourcePlaneError("commit SHA does not match requested immutable revision")
        tree = value.get("tree")
        if not isinstance(tree, dict):
            raise SourcePlaneError("commit tree missing")
        return validate_sha(tree.get("sha"))

    def resolve_file(self, request: ArtifactRequest) -> dict[str, str]:
        """Walk only the necessary tree path, never a recursive repository listing."""
        prefix = self._prefix(request.repository)
        root_tree_sha = self.commit_tree(request.repository, request.commit_sha)
        tree_sha = root_tree_sha
        parts = validate_path(request.path)
        for offset, part in enumerate(parts):
            value = self._get(prefix + "/git/trees/" + tree_sha)
            if value.get("sha") != tree_sha or value.get("truncated") is True:
                raise SourcePlaneError("GitHub tree identity missing, stale, or truncated")
            entries = value.get("tree")
            if not isinstance(entries, list):
                raise SourcePlaneError("tree entries missing")
            matches = [entry for entry in entries
                       if isinstance(entry, dict) and entry.get("path") == part]
            if len(matches) != 1:
                raise SourcePlaneError("requested file not found or ambiguous")
            entry = matches[0]
            object_sha = validate_sha(entry.get("sha"))
            is_final = offset == len(parts) - 1
            if is_final:
                if entry.get("type") != "blob" or entry.get("mode") not in ("100644", "100755", "120000"):
                    raise SourcePlaneError("path is not an ordinary Git blob")
                return {"repository": request.repository, "commit_sha": request.commit_sha,
                        "tree_sha": root_tree_sha, "path": request.path,
                        "mode": entry["mode"], "blob_sha1": object_sha}
            if entry.get("type") != "tree":
                raise SourcePlaneError("intermediate path is not a Git tree")
            tree_sha = object_sha
        raise SourcePlaneError("invalid empty file path")

    def blob_bytes(self, repo: str, blob_sha1: str) -> bytes:
        validate_repo(repo)
        validate_sha(blob_sha1)
        key = (repo, blob_sha1)
        if key in self._blob_cache:
            return self._blob_cache[key]
        value = self._get(self._prefix(repo) + "/git/blobs/" + blob_sha1)
        if value.get("sha") != blob_sha1 or value.get("encoding") != "base64":
            raise SourcePlaneError("blob object identity/encoding mismatch")
        size = value.get("size")
        if type(size) is not int or size < 0 or size > self.max_blob_bytes:
            raise SourcePlaneError("blob is too large or lacks a trustworthy size")
        data = value.get("content")
        if not isinstance(data, str):
            raise SourcePlaneError("GitHub blob content missing")
        try:
            raw = base64.b64decode(data, validate=False)
            # Validate strictly after stripping only base64 line separators emitted by GitHub.
            clean = data.replace("\n", "").replace("\r", "")
            if base64.b64decode(clean, validate=True) != raw:
                raise SourcePlaneError("blob base64 content invalid")
        except (ValueError, binascii.Error) as exc:
            raise SourcePlaneError("blob base64 content invalid") from exc
        if len(raw) != size or git_blob_oid(raw) != blob_sha1:
            raise SourcePlaneError("blob content fails Git object hash verification")
        self._blob_cache[key] = raw
        return raw

    def artifact(self, request: ArtifactRequest) -> dict[str, object]:
        identity = self.resolve_file(request)
        blob = self.blob_bytes(request.repository, identity["blob_sha1"])
        return {**identity, "size": len(blob),
                "content_sha256": hashlib.sha256(blob).hexdigest(),
                "verification": "GIT_BLOB_SHA1_MATCH"}

    def manifest(self, requests: Sequence[ArtifactRequest]) -> dict[str, object]:
        if not requests or len(requests) > 100:
            raise SourcePlaneError("manifest requires 1 to 100 file requests")
        ordered = sorted(set(requests), key=lambda x: (x.repository, x.commit_sha, x.path))
        artifacts = [self.artifact(request) for request in ordered]
        body: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "access": "READ_ONLY",
            "authority": "NONE",
            "source_binding": "EXACT_COMMIT_SHA",
            "artifacts": artifacts,
        }
        body["manifest_sha256"] = canonical_sha256({"domain": SCHEMA_VERSION, "payload": body})
        return body


def verify_manifest_document(manifest: Mapping[str, object]) -> dict[str, object]:
    """Check document integrity and schema, not GitHub's live remote state.

    A successfully verified digest does NOT independently verify blob bytes and
    does not authorize execution. For blob verification, fetch via SourcePlane.
    """
    reasons: list[str] = []
    for key, expected in (("schema_version", SCHEMA_VERSION), ("access", "READ_ONLY"),
                          ("authority", "NONE"), ("source_binding", "EXACT_COMMIT_SHA")):
        if manifest.get(key) != expected:
            reasons.append(f"INVALID_{key.upper()}")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not (1 <= len(artifacts) <= 100):
        reasons.append("INVALID_ARTIFACT_LIST")
    else:
        identities: list[tuple[str, str, str]] = []
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                reasons.append("INVALID_ARTIFACT")
                break
            try:
                repo = validate_repo(artifact.get("repository"))
                commit = validate_sha(artifact.get("commit_sha"))
                validate_sha(artifact.get("tree_sha"))
                path = artifact.get("path")
                validate_path(path)
                validate_sha(artifact.get("blob_sha1"))
                digest = artifact.get("content_sha256")
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise SourcePlaneError("invalid SHA-256")
                if artifact.get("mode") not in ("100644", "100755", "120000"):
                    raise SourcePlaneError("invalid file mode")
                size = artifact.get("size")
                if type(size) is not int or size < 0 or size > MAX_BLOB_BYTES:
                    raise SourcePlaneError("invalid blob size")
                if artifact.get("verification") != "GIT_BLOB_SHA1_MATCH":
                    raise SourcePlaneError("missing blob verification claim")
                identities.append((repo, commit, path))
            except SourcePlaneError:
                reasons.append("INVALID_ARTIFACT")
                break
        if identities != sorted(set(identities)):
            reasons.append("UNSORTED_OR_DUPLICATE_ARTIFACTS")
    unsigned = dict(manifest)
    supplied = unsigned.pop("manifest_sha256", None)
    if supplied != canonical_sha256({"domain": SCHEMA_VERSION, "payload": unsigned}):
        reasons.append("MANIFEST_DIGEST_MISMATCH")
    return {"status": "DENIED" if reasons else "ESTABLISHED",
            "reason_codes": reasons}


def parse_artifact(value: str) -> ArtifactRequest:
    try:
        repo_and_rev, path = value.split(":", 1)
        repo, sha = repo_and_rev.split("@", 1)
    except ValueError as exc:
        raise SourcePlaneError("expected owner/repo@40-character-sha:path") from exc
    return ArtifactRequest(repo, sha, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-repo", action="append", default=[],
                        help="owner/repo=/absolute/existing/git/worktree (read-only)")
    parser.add_argument("--verify-local-head", action="store_true",
                        help="require AEGIS repository_knowledge.py and matching local HEAD")
    parser.add_argument("--artifact", action="append", required=True,
                        help="owner/repo@exact-40-char-sha:path, may repeat")
    arguments = parser.parse_args(argv)
    try:
        requests = [parse_artifact(item) for item in arguments.artifact]
        if arguments.local_repo:
            locations = {}
            for entry in arguments.local_repo:
                repo, delim, root = entry.partition("=")
                if not delim or not root or repo in locations:
                    raise SourcePlaneError("local repository mapping must be unique owner/repo=absolute-path")
                locations[validate_repo(repo)] = Path(root)
            manifest = SourcePlane(transport=LocalGitTransport(locations)).manifest(requests)
            if arguments.verify_local_head:
                verification = verify_local_repository_binding(manifest, locations)
                if verification["status"] != "ESTABLISHED":
                    raise SourcePlaneError("local repository knowledge denied: " + ",".join(verification["reason_codes"]))
        else:
            if arguments.verify_local_head:
                raise SourcePlaneError("local HEAD verification requires --local-repo")
            manifest = SourcePlane(token=os.environ.get("GITHUB_TOKEN")).manifest(requests)
    except SourcePlaneError as exc:
        print(f"SOURCE_PLANE_DENIED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
