from __future__ import annotations

import hashlib
import io
import re
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .bundle_commitment import canonical_bundle_bytes


_PROTOCOL = "AVD_GIT_TREE_SNAPSHOT_V1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


class GitTreeSnapshotError(RuntimeError):
    pass


def _require_sha40(name: str, value: str) -> str:
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise GitTreeSnapshotError(f"{name.upper()}_INVALID")
    return value


def _require_relative_path(name: str, value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise GitTreeSnapshotError(f"{name.upper()}_INVALID")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise GitTreeSnapshotError(f"{name.upper()}_INVALID")
    if path.as_posix() != value or ".git" in path.parts:
        raise GitTreeSnapshotError(f"{name.upper()}_INVALID")
    return value


def _git(
    repo_root: Path,
    *args: str,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
        )
    except FileNotFoundError as exc:
        raise GitTreeSnapshotError("GIT_EXECUTABLE_NOT_FOUND") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if isinstance(exc.stderr, str) else b""
        suffix = f":{stderr}" if stderr else ""
        raise GitTreeSnapshotError(f"GIT_COMMAND_FAILED{suffix}") from exc


def _object_exists(repo_root: Path, object_spec: str) -> bool:
    proc = _git(repo_root, "cat-file", "-e", object_spec, check=False)
    return proc.returncode == 0


def _safe_member_path(name: str) -> PurePosixPath:
    if not name or "\\" in name or "\x00" in name:
        raise GitTreeSnapshotError("ARCHIVE_PATH_INVALID")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise GitTreeSnapshotError(f"ARCHIVE_PATH_INVALID:{name}")
    if ".git" in path.parts:
        raise GitTreeSnapshotError("GIT_METADATA_FORBIDDEN")
    return path


def _extract_regular_tree(archive_bytes: bytes, snapshot_root: Path) -> None:
    try:
        tf = tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:")
    except tarfile.TarError as exc:
        raise GitTreeSnapshotError("GIT_ARCHIVE_INVALID") from exc

    with tf:
        for member in tf.getmembers():
            rel = _safe_member_path(member.name)
            destination = snapshot_root.joinpath(*rel.parts)
            resolved_parent = destination.parent.resolve(strict=False)
            try:
                resolved_parent.relative_to(snapshot_root)
            except ValueError as exc:
                raise GitTreeSnapshotError("ARCHIVE_PATH_ESCAPES_SNAPSHOT") from exc

            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                # Symlinks, hardlinks, devices and other special entries create
                # execution/aliasing surfaces not represented by the canonical
                # problem-bundle commitment. Fail closed instead of extracting.
                raise GitTreeSnapshotError(
                    f"NON_REGULAR_GIT_TREE_ENTRY_FORBIDDEN:{member.name}"
                )

            source = tf.extractfile(member)
            if source is None:
                raise GitTreeSnapshotError(f"ARCHIVE_MEMBER_UNREADABLE:{member.name}")
            payload = source.read()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)


@dataclass(frozen=True)
class GitTreeSnapshotV1:
    protocol_version: str
    anchor_commit_sha: str
    anchor_tree_sha: str
    required_path: str
    forbidden_path: str
    archive_sha256: str
    snapshot_sha256: str
    git_tree_verified: bool
    forbidden_path_absent: bool
    authority_class: str = "NONE"

    @classmethod
    def export(
        cls,
        *,
        repo_root: Path,
        snapshot_root: Path,
        anchor_commit_sha: str,
        expected_tree_sha: str,
        required_path: str,
        forbidden_path: str,
    ) -> "GitTreeSnapshotV1":
        """Export one exact local Git commit tree into a sanitized snapshot.

        The Git object database is used only by this trusted preparation step.
        The exported snapshot contains no `.git` metadata and can therefore be
        passed into the later clean-room/problem-package commitment boundary.
        """
        anchor_commit_sha = _require_sha40("anchor_commit_sha", anchor_commit_sha)
        expected_tree_sha = _require_sha40("expected_tree_sha", expected_tree_sha)
        required_path = _require_relative_path("required_path", required_path)
        forbidden_path = _require_relative_path("forbidden_path", forbidden_path)

        repo = Path(repo_root).resolve()
        if not repo.is_dir():
            raise GitTreeSnapshotError("REPOSITORY_ROOT_NOT_DIRECTORY")

        snapshot = Path(snapshot_root).resolve(strict=False)
        try:
            snapshot.relative_to(repo)
        except ValueError:
            pass
        else:
            raise GitTreeSnapshotError("SNAPSHOT_ROOT_INSIDE_REPOSITORY")

        if snapshot.exists():
            if not snapshot.is_dir():
                raise GitTreeSnapshotError("SNAPSHOT_ROOT_NOT_DIRECTORY")
            if any(snapshot.iterdir()):
                raise GitTreeSnapshotError("SNAPSHOT_ROOT_NOT_EMPTY")
        else:
            snapshot.mkdir(parents=True)

        commit_proc = _git(
            repo,
            "rev-parse",
            "--verify",
            f"{anchor_commit_sha}^{{commit}}",
        )
        observed_commit = commit_proc.stdout.strip()
        if observed_commit != anchor_commit_sha:
            raise GitTreeSnapshotError("ANCHOR_COMMIT_MISMATCH")

        tree_proc = _git(repo, "rev-parse", f"{anchor_commit_sha}^{{tree}}")
        observed_tree = tree_proc.stdout.strip()
        if observed_tree != expected_tree_sha:
            raise GitTreeSnapshotError("ANCHOR_TREE_MISMATCH")

        if not _object_exists(repo, f"{anchor_commit_sha}:{required_path}"):
            raise GitTreeSnapshotError("REQUIRED_PATH_MISSING_FROM_ANCHOR_TREE")
        if _object_exists(repo, f"{anchor_commit_sha}:{forbidden_path}"):
            raise GitTreeSnapshotError("FORBIDDEN_PATH_PRESENT_IN_ANCHOR_TREE")

        archive_proc = _git(
            repo,
            "archive",
            "--format=tar",
            anchor_commit_sha,
            text=False,
        )
        archive_bytes = archive_proc.stdout
        if not isinstance(archive_bytes, bytes) or not archive_bytes:
            raise GitTreeSnapshotError("GIT_ARCHIVE_EMPTY")

        try:
            _extract_regular_tree(archive_bytes, snapshot)
            if not (snapshot / required_path).is_file():
                raise GitTreeSnapshotError("REQUIRED_PATH_MISSING_AFTER_EXPORT")
            target = snapshot / forbidden_path
            if target.exists() or target.is_symlink():
                raise GitTreeSnapshotError("FORBIDDEN_PATH_PRESENT_AFTER_EXPORT")
            if (snapshot / ".git").exists():
                raise GitTreeSnapshotError("GIT_METADATA_FORBIDDEN")
            bundle = canonical_bundle_bytes(snapshot)
        except Exception:
            # A failed preparation must not leave a partially trusted snapshot
            # that a later stage could accidentally consume.
            for path in sorted(snapshot.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                if path.is_symlink() or path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    path.rmdir()
            snapshot.rmdir()
            raise

        archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
        snapshot_sha256 = hashlib.sha256(bundle).hexdigest()
        if _SHA64.fullmatch(archive_sha256) is None or _SHA64.fullmatch(snapshot_sha256) is None:
            raise GitTreeSnapshotError("SNAPSHOT_DIGEST_INVALID")

        return cls(
            protocol_version=_PROTOCOL,
            anchor_commit_sha=anchor_commit_sha,
            anchor_tree_sha=observed_tree,
            required_path=required_path,
            forbidden_path=forbidden_path,
            archive_sha256=archive_sha256,
            snapshot_sha256=snapshot_sha256,
            git_tree_verified=True,
            forbidden_path_absent=True,
            authority_class="NONE",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "anchor_commit_sha": self.anchor_commit_sha,
            "anchor_tree_sha": self.anchor_tree_sha,
            "required_path": self.required_path,
            "forbidden_path": self.forbidden_path,
            "archive_sha256": self.archive_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            "git_tree_verified": self.git_tree_verified,
            "forbidden_path_absent": self.forbidden_path_absent,
            "authority_class": self.authority_class,
        }
