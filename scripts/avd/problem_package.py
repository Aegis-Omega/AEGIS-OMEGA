from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .anchor import AVD00_ANCHOR
from .bundle_commitment import canonical_bundle_bytes
from .crypto_util import avd_digest, canonical_json_bytes


_PROTOCOL = "AVD_PROBLEM_PACKAGE_V1"
_SPEC_PATH = "sovereign-omega-v2/formal/tests/Weil/CornO0MorphismBridgeSpec.v"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


class ProblemPackageError(RuntimeError):
    pass


def _require_sha40(name: str, value: str) -> str:
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise ProblemPackageError(f"{name.upper()}_SHA_INVALID")
    return value


def _require_relative_path(name: str, value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ProblemPackageError(f"{name.upper()}_INVALID")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ProblemPackageError(f"{name.upper()}_INVALID")
    if path.as_posix() != value:
        raise ProblemPackageError(f"{name.upper()}_INVALID")
    return value


def _snapshot_member(root: Path, relative: str) -> Path:
    member = (root / relative).resolve(strict=False)
    try:
        member.relative_to(root)
    except ValueError as exc:
        raise ProblemPackageError("SNAPSHOT_PATH_ESCAPES_ROOT") from exc
    return member


def _record(label: bytes, payload: bytes) -> bytes:
    return (
        len(label).to_bytes(8, "big")
        + label
        + len(payload).to_bytes(8, "big")
        + payload
    )


@dataclass(frozen=True)
class ProblemPackageV1:
    protocol_version: str
    anchor_commit_sha: str
    anchor_tree_sha: str
    target_path: str
    spec_path: str
    canonical_coq_logical_path: str
    snapshot_sha256: str
    h_problem: str
    authority_class: str = "NONE"

    @classmethod
    def compute(
        cls,
        *,
        snapshot_root: Path,
        anchor_commit_sha: str,
        anchor_tree_sha: str,
        target_path: str,
        spec_path: str,
        canonical_coq_logical_path: str,
    ) -> "ProblemPackageV1":
        """Commit to a sanitized historical challenge snapshot and public contract.

        This function deliberately does *not* claim that caller-supplied snapshot
        bytes are equal to the Git tree named by ``anchor_tree_sha``. It binds the
        declared historical identities into H_P and enforces the frozen AVD-00
        contract; a separate trusted reconstruction/equality receipt is required
        before tree-equivalence authority can be claimed.
        """
        anchor_commit_sha = _require_sha40("anchor_commit", anchor_commit_sha)
        anchor_tree_sha = _require_sha40("anchor_tree", anchor_tree_sha)
        target_path = _require_relative_path("target_path", target_path)
        spec_path = _require_relative_path("spec_path", spec_path)

        if anchor_commit_sha != AVD00_ANCHOR.anchor_commit_sha:
            raise ProblemPackageError("ANCHOR_COMMIT_IDENTITY_MISMATCH")
        if anchor_tree_sha != AVD00_ANCHOR.anchor_tree_sha:
            raise ProblemPackageError("ANCHOR_TREE_IDENTITY_MISMATCH")
        if target_path != AVD00_ANCHOR.target_production_file:
            raise ProblemPackageError("TARGET_PATH_MISMATCH")
        if spec_path != _SPEC_PATH:
            raise ProblemPackageError("FROZEN_SPEC_PATH_MISMATCH")
        if canonical_coq_logical_path != AVD00_ANCHOR.canonical_coq_logical_path:
            raise ProblemPackageError("COQ_LOGICAL_PATH_MISMATCH")

        root = Path(snapshot_root).resolve()
        if not root.is_dir():
            raise ProblemPackageError("SNAPSHOT_ROOT_NOT_DIRECTORY")

        target = _snapshot_member(root, target_path)
        # A historical challenge package must not contain the future production
        # solution in any filesystem form, including a symlink placeholder.
        if target.exists() or target.is_symlink():
            raise ProblemPackageError("FUTURE_SOLUTION_PRESENT_IN_PROBLEM_PACKAGE")

        spec = _snapshot_member(root, spec_path)
        if not spec.is_file() or spec.is_symlink():
            raise ProblemPackageError("FROZEN_SPEC_MISSING")

        try:
            bundle = canonical_bundle_bytes(root)
        except ValueError as exc:
            raise ProblemPackageError(str(exc)) from exc

        snapshot_sha256 = hashlib.sha256(bundle).hexdigest()
        if _SHA64.fullmatch(snapshot_sha256) is None:  # defensive invariant
            raise ProblemPackageError("SNAPSHOT_DIGEST_INVALID")

        public_contract = {
            "protocol_version": _PROTOCOL,
            "anchor_commit_sha": anchor_commit_sha,
            "anchor_tree_sha": anchor_tree_sha,
            "target_path": target_path,
            "spec_path": spec_path,
            "canonical_coq_logical_path": canonical_coq_logical_path,
            "snapshot_sha256": snapshot_sha256,
            "future_solution_absent": True,
            "authority_class": "NONE",
        }
        contract_bytes = canonical_json_bytes(public_contract)
        preimage = (
            b"AEGIS-AVD-PROBLEM-PACKAGE-V1\x00"
            + _record(b"PUBLIC_CONTRACT", contract_bytes)
            + _record(b"SNAPSHOT", bundle)
        )
        h_problem = avd_digest("PROBLEM", preimage)
        if _SHA64.fullmatch(h_problem) is None:  # defensive invariant
            raise ProblemPackageError("PROBLEM_DIGEST_INVALID")

        return cls(
            protocol_version=_PROTOCOL,
            anchor_commit_sha=anchor_commit_sha,
            anchor_tree_sha=anchor_tree_sha,
            target_path=target_path,
            spec_path=spec_path,
            canonical_coq_logical_path=canonical_coq_logical_path,
            snapshot_sha256=snapshot_sha256,
            h_problem=h_problem,
            authority_class="NONE",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "anchor_commit_sha": self.anchor_commit_sha,
            "anchor_tree_sha": self.anchor_tree_sha,
            "target_path": self.target_path,
            "spec_path": self.spec_path,
            "canonical_coq_logical_path": self.canonical_coq_logical_path,
            "snapshot_sha256": self.snapshot_sha256,
            "h_problem": self.h_problem,
            "authority_class": self.authority_class,
        }
