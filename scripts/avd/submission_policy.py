from __future__ import annotations

import hashlib
import stat
from pathlib import Path


class SubmissionPolicyError(RuntimeError):
    pass


def _snapshot_files(root: Path) -> dict[str, str]:
    root = root.resolve()
    if not root.is_dir():
        raise SubmissionPolicyError("SUBMISSION_ROOT_NOT_DIRECTORY")
    out: dict[str, str] = {}
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if ".git" in rel.parts:
            raise SubmissionPolicyError("GIT_METADATA_FORBIDDEN")
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise SubmissionPolicyError("SYMLINK_FORBIDDEN")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise SubmissionPolicyError("SPECIAL_FILE_FORBIDDEN")
        out[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def validate_submission_surface(
    baseline_root: Path,
    candidate_root: Path,
    *,
    allowed_path: Path,
) -> tuple[str, ...]:
    """Require the candidate delta to touch exactly one authorized source path.

    AVD-00 begins from a RED baseline where the production target is absent,
    so adding that one file is valid. Any mutation of the frozen spec, import
    shadow, extra helper module, generated file or deletion is rejected before
    Coq executes.
    """
    baseline = _snapshot_files(baseline_root)
    candidate = _snapshot_files(candidate_root)
    paths = sorted(set(baseline) | set(candidate))
    changed = tuple(path for path in paths if baseline.get(path) != candidate.get(path))
    allowed = allowed_path.as_posix()

    unauthorized = [path for path in changed if path != allowed]
    if unauthorized:
        raise SubmissionPolicyError(
            "UNAUTHORIZED_PATH_CHANGE:" + ",".join(unauthorized)
        )
    if changed != (allowed,):
        raise SubmissionPolicyError("TARGET_PRODUCTION_FILE_NOT_SOLE_DELTA")
    if allowed not in candidate:
        raise SubmissionPolicyError("TARGET_PRODUCTION_FILE_MISSING")
    return changed
