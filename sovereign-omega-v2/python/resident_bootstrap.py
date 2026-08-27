#!/usr/bin/env python3
"""Prepare the bridge's owned resident sensor clone, then exec the bridge."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse

BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
GIT_RE = re.compile(r"^[0-9a-f]{40,64}$")


class ResidentBootstrapError(RuntimeError):
    """Fail-closed bootstrap error with a stable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _run_git(
    *args: str,
    cwd: Path | None = None,
    timeout_seconds: int = 120,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ("git", *args),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ResidentBootstrapError("GIT_UNAVAILABLE_OR_TIMED_OUT") from exc


def _canonical_repository_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResidentBootstrapError("REPOSITORY_URL_REQUIRED")
    candidate = value.strip()
    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme in {"http", "https", "ssh", "file"}:
        if parsed.scheme in {"http", "https"} and (not parsed.hostname or parsed.username):
            raise ResidentBootstrapError("REPOSITORY_URL_UNSAFE")
        return candidate.rstrip("/")
    if "://" in candidate or candidate.startswith("-"):
        raise ResidentBootstrapError("REPOSITORY_URL_UNSUPPORTED")
    return str(Path(candidate).expanduser().resolve(strict=True))


def _same_repository(left: str, right: str) -> bool:
    try:
        left_value = _canonical_repository_url(left)
        right_value = _canonical_repository_url(right)
    except (ResidentBootstrapError, OSError):
        return False
    return left_value.removesuffix(".git") == right_value.removesuffix(".git")


def _require_branch(branch: str) -> None:
    if (
        not isinstance(branch, str)
        or not BRANCH_RE.fullmatch(branch)
        or ".." in branch
        or branch.endswith("/")
        or "//" in branch
    ):
        raise ResidentBootstrapError("BRANCH_INVALID")


def prepare_resident_repository(
    *,
    repository_url: str,
    repository_root: str | Path,
    branch: str = "main",
) -> str:
    """Create or refresh one owned, clean sensor clone at the branch head.

    Existing non-repositories, remote mismatches and dirty clones are preserved
    untouched and rejected. This clone is a replaceable observation substrate;
    it is never the operator's canonical working tree.
    """
    canonical_url = _canonical_repository_url(repository_url)
    _require_branch(branch)
    target = Path(repository_root).expanduser().resolve(strict=False)
    if target == Path(target.anchor) or len(target.parts) < 2:
        raise ResidentBootstrapError("REPOSITORY_ROOT_UNSAFE")

    git_marker = target / ".git"
    if target.exists() and not git_marker.exists():
        try:
            has_entries = any(target.iterdir())
        except OSError as exc:
            raise ResidentBootstrapError("REPOSITORY_ROOT_UNAVAILABLE") from exc
        if has_entries:
            raise ResidentBootstrapError("TARGET_NOT_OWNED_REPOSITORY")

    if not git_marker.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        clone = _run_git(
            "clone",
            "--no-tags",
            "--depth=1",
            "--branch",
            branch,
            "--",
            canonical_url,
            str(target),
        )
        if clone.returncode != 0:
            raise ResidentBootstrapError("REPOSITORY_CLONE_FAILED")
    else:
        remote = _run_git("remote", "get-url", "origin", cwd=target)
        if remote.returncode != 0 or not _same_repository(remote.stdout.strip(), canonical_url):
            raise ResidentBootstrapError("REMOTE_MISMATCH")
        dirty = _run_git("status", "--porcelain", "--untracked-files=all", cwd=target)
        if dirty.returncode != 0:
            raise ResidentBootstrapError("REPOSITORY_STATUS_FAILED")
        if dirty.stdout.strip():
            raise ResidentBootstrapError("REPOSITORY_DIRTY")
        pruned = _run_git("worktree", "prune", cwd=target)
        if pruned.returncode != 0:
            raise ResidentBootstrapError("WORKTREE_PRUNE_FAILED")
        fetched = _run_git(
            "fetch",
            "--no-tags",
            "--depth=1",
            "origin",
            branch,
            cwd=target,
        )
        if fetched.returncode != 0:
            raise ResidentBootstrapError("REPOSITORY_FETCH_FAILED")
        checkout = _run_git("checkout", "--detach", "FETCH_HEAD", cwd=target)
        if checkout.returncode != 0:
            raise ResidentBootstrapError("REPOSITORY_CHECKOUT_FAILED")

    head = _run_git("rev-parse", "HEAD", cwd=target)
    if head.returncode != 0 or not GIT_RE.fullmatch(head.stdout.strip()):
        raise ResidentBootstrapError("REPOSITORY_HEAD_INVALID")
    final_status = _run_git("status", "--porcelain", "--untracked-files=all", cwd=target)
    if final_status.returncode != 0 or final_status.stdout.strip():
        raise ResidentBootstrapError("REPOSITORY_NOT_CLEAN_AFTER_BOOTSTRAP")
    return head.stdout.strip()


def main() -> int:
    repository_url = os.environ.get(
        "AEGIS_RESIDENT_REPOSITORY_URL",
        "https://github.com/Aegis-Omega/AEGIS-OMEGA.git",
    )
    repository_root = Path(
        os.environ.get("AEGIS_RESIDENT_REPOSITORY_ROOT", "/app/data/repository")
    )
    branch = os.environ.get("AEGIS_RESIDENT_REPOSITORY_BRANCH", "main")
    head: str | None = None
    try:
        head = prepare_resident_repository(
            repository_url=repository_url,
            repository_root=repository_root,
            branch=branch,
        )
    except ResidentBootstrapError as exc:
        print(
            json.dumps(
                {
                    "event_type": "RESIDENT_BOOTSTRAP_FAILED",
                    "code": exc.code,
                    "knowledge_decision": "UNKNOWN",
                }
            ),
            flush=True,
        )
        # The resident sensor is optional to the pre-existing governance
        # service. Keep the bridge alive, but bind its resident endpoints to an
        # explicit UNKNOWN state so a dirty/missing clone can never be used.
        os.environ["AEGIS_RESIDENT_BOOTSTRAP_STATUS"] = "UNKNOWN"
    else:
        os.environ["AEGIS_RESIDENT_BOOTSTRAP_STATUS"] = "READY"
    os.environ["AEGIS_RESIDENT_REPOSITORY_ROOT"] = str(repository_root)
    if head is not None:
        print(
            json.dumps(
                {
                    "event_type": "RESIDENT_REPOSITORY_READY",
                    "repository_head": head,
                    "authority": "OBSERVATION_SUBSTRATE_ONLY",
                }
            ),
            flush=True,
        )
    bridge_path = Path(__file__).with_name("bridge.py")
    os.execv(sys.executable, (sys.executable, str(bridge_path)))
    return 70


if __name__ == "__main__":
    raise SystemExit(main())
