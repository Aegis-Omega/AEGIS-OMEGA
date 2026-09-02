from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any


_TARGET = "sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


class FrozenReferenceError(RuntimeError):
    pass


def _require_sha40(name: str, value: str) -> str:
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise FrozenReferenceError(f"INVALID_{name.upper()}")
    return value


def _require_run_id(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise FrozenReferenceError(f"INVALID_{name.upper()}")
    return value


@dataclass(frozen=True)
class FrozenReferenceV1:
    protocol_version: str
    commit_sha: str
    tree_sha: str
    source_path: str
    source_sha256: str
    dedicated_run_id: int
    formal_attestation_run_id: int
    assumptions_closed: bool

    @classmethod
    def freeze(
        cls,
        *,
        commit_sha: str,
        tree_sha: str,
        source_path: str,
        source_bytes: bytes,
        dedicated_run_id: int,
        dedicated_conclusion: str,
        formal_attestation_run_id: int,
        formal_attestation_conclusion: str,
        assumptions_closed: bool,
    ) -> "FrozenReferenceV1":
        _require_sha40("commit_sha", commit_sha)
        _require_sha40("tree_sha", tree_sha)
        _require_run_id("dedicated_run_id", dedicated_run_id)
        _require_run_id("formal_attestation_run_id", formal_attestation_run_id)

        if source_path != _TARGET:
            raise FrozenReferenceError("REFERENCE_SOURCE_PATH_MISMATCH")
        if not isinstance(source_bytes, bytes) or not source_bytes:
            raise FrozenReferenceError("REFERENCE_SOURCE_EMPTY")
        try:
            text = source_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FrozenReferenceError("REFERENCE_SOURCE_NOT_UTF8") from exc
        if "\x00" in text:
            raise FrozenReferenceError("REFERENCE_SOURCE_CONTAINS_NUL")

        if dedicated_conclusion != "success":
            raise FrozenReferenceError("DEDICATED_RUN_NOT_GREEN")
        if formal_attestation_conclusion != "success":
            raise FrozenReferenceError("FORMAL_ATTESTATION_NOT_GREEN")
        if assumptions_closed is not True:
            raise FrozenReferenceError("ASSUMPTIONS_NOT_CLOSED")

        digest = hashlib.sha256(source_bytes).hexdigest()
        if _SHA64.fullmatch(digest) is None:  # defensive invariant
            raise FrozenReferenceError("REFERENCE_SOURCE_DIGEST_INVALID")

        return cls(
            protocol_version="AVD_FROZEN_REFERENCE_V1",
            commit_sha=commit_sha,
            tree_sha=tree_sha,
            source_path=source_path,
            source_sha256=digest,
            dedicated_run_id=dedicated_run_id,
            formal_attestation_run_id=formal_attestation_run_id,
            assumptions_closed=True,
        )

    @property
    def is_frozen(self) -> bool:
        return (
            self.protocol_version == "AVD_FROZEN_REFERENCE_V1"
            and _SHA40.fullmatch(self.commit_sha) is not None
            and _SHA40.fullmatch(self.tree_sha) is not None
            and self.source_path == _TARGET
            and _SHA64.fullmatch(self.source_sha256) is not None
            and self.dedicated_run_id > 0
            and self.formal_attestation_run_id > 0
            and self.assumptions_closed is True
        )

    def to_dict(self) -> dict[str, Any]:
        if not self.is_frozen:
            raise FrozenReferenceError("REFERENCE_NOT_FROZEN")
        return {
            "protocol_version": self.protocol_version,
            "commit_sha": self.commit_sha,
            "tree_sha": self.tree_sha,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "dedicated_run_id": self.dedicated_run_id,
            "formal_attestation_run_id": self.formal_attestation_run_id,
            "assumptions_closed": self.assumptions_closed,
        }
