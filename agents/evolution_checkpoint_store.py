"""POSIX same-user atomic CAS anchor for existing token-checkpoint snapshots.

This is crash-resistant local storage, NOT an independent trust anchor or WORM.
Never use a HEAD ID read solely from this store as independent proof of history.
No agent dispatch, authority, payments, secrets on disk, GitHub/network, or chain.
"""
from __future__ import annotations

import fcntl
import json
import os
import secrets
import re
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from agents.evolution_token_checkpoint import GENESIS, verify_checkpoint
from agents.evolution_token_lifecycle import canonical, digest

STORE_SCHEMA = "AEGIS_LOCAL_EVOLUTION_CHECKPOINT_ANCHOR_V1"
SNAPSHOT_FIELDS = frozenset({"checkpoint", "events", "observed_at"})
MAX_OBJECT_BYTES = 2_000_000
NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _private_directory(path: Path, *, create: bool = False) -> None:
    if create:
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
    s = path.lstat()
    if (not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid()
            or stat.S_IMODE(s.st_mode) != 0o700):
        raise ValueError("ANCHOR_DIRECTORY_UNSAFE")


def _regular(fd: int) -> None:
    s = os.fstat(fd)
    if (not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid()
            or stat.S_IMODE(s.st_mode) != 0o600 or s.st_nlink != 1):
        raise ValueError("ANCHOR_FILE_UNSAFE")


def _read(path: Path) -> Any:
    fd = os.open(path, os.O_RDONLY | NOFOLLOW)
    try:
        _regular(fd)
        raw = os.read(fd, MAX_OBJECT_BYTES + 1)
        if len(raw) > MAX_OBJECT_BYTES:
            raise ValueError("ANCHOR_OBJECT_TOO_LARGE")
        return json.loads(raw)
    finally:
        os.close(fd)


def _atomic_write(path: Path, content: bytes, *, exclusive: bool) -> None:
    if len(content) > MAX_OBJECT_BYTES:
        raise ValueError("ANCHOR_OBJECT_TOO_LARGE")
    tmp = path.parent / (".tmp-" + secrets.token_hex(16))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600)
    try:
        _regular(fd)
        with os.fdopen(fd, "wb", closefd=False) as f:
            f.write(content)
            f.flush()
            os.fsync(fd)
        if exclusive:
            # Do not replace an already-published content-addressed object.
            try:
                os.link(tmp, path, follow_symlinks=False)
            except FileExistsError:
                # A crash may leave the fsynced immutable object but not HEAD.
                # Resume only if content is exactly equal; never overwrite.
                if canonical(_read(path)) != content:
                    raise ValueError("ANCHOR_OBJECT_COLLISION_OR_TAMPER")
        else:
            os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        os.close(fd)
        if tmp.exists():
            tmp.unlink()


@contextmanager
def _locked(root: Path, *, create: bool):
    if not isinstance(root, Path) or not root.is_absolute():
        raise ValueError("ANCHOR_ROOT_MUST_BE_ABSOLUTE")
    _private_directory(root, create=create)
    objects = root / "objects"
    _private_directory(objects, create=create)
    lockfd = os.open(root / ".anchor.lock", os.O_RDWR | os.O_CREAT | NOFOLLOW, 0o600)
    try:
        _regular(lockfd)
        fcntl.flock(lockfd, fcntl.LOCK_EX)
        yield objects
    finally:
        fcntl.flock(lockfd, fcntl.LOCK_UN)
        os.close(lockfd)


def _head(root: Path) -> dict[str, Any]:
    try:
        head = _read(root / "HEAD.json")
    except FileNotFoundError:
        return {"schema": STORE_SCHEMA, "checkpoint_id": GENESIS, "sequence": -1}
    if (not isinstance(head, dict) or set(head) != {"schema", "checkpoint_id", "sequence"}
            or head["schema"] != STORE_SCHEMA or
            type(head["sequence"]) is not int or head["sequence"] < 0 or
            not isinstance(head["checkpoint_id"], str) or
            not HEX64.fullmatch(head["checkpoint_id"])):
        raise ValueError("ANCHOR_HEAD_INVALID")
    return head


def _snapshot(objects: Path, checkpoint_id: str) -> dict[str, Any]:
    snap = _read(objects / (checkpoint_id + ".json"))
    if not isinstance(snap, dict) or set(snap) != SNAPSHOT_FIELDS:
        raise ValueError("ANCHOR_SNAPSHOT_SCHEMA_INVALID")
    return snap


def _verify_snapshot(snap: Mapping[str, Any], *, spine: Mapping[str, Any],
                     trusted_spine_hash: str, trusted_event_keys: Mapping[str, Any],
                     trusted_checkpoint_keys: Mapping[str, bytes],
                     checkpoint_id: str, expected_previous_id: str | None = None) -> dict[str, Any]:
    return verify_checkpoint(
        spine, snap["events"], snap["observed_at"], snap["checkpoint"],
        trusted_spine_hash=trusted_spine_hash,
        trusted_event_keys=trusted_event_keys,
        trusted_checkpoint_keys=trusted_checkpoint_keys,
        trusted_checkpoint_id=checkpoint_id,
        expected_previous_id=expected_previous_id,
    )


def publish(root: Path, spine: Mapping[str, Any], events: list[Mapping[str, Any]],
            observed_at: list[int], checkpoint: Mapping[str, Any], *,
            expected_current_id: str, trusted_spine_hash: str,
            trusted_event_keys: Mapping[str, Any],
            trusted_checkpoint_keys: Mapping[str, bytes]) -> dict[str, Any]:
    """Atomic local append with CAS, full prior-prefix verification and fsync.

    A separately retained expected_current_id is essential. An operator who
    derives it from the mutable HEAD defeats rollback detection.
    """
    if (not isinstance(expected_current_id, str) or not HEX64.fullmatch(expected_current_id)
            or not isinstance(checkpoint, Mapping)):
        raise ValueError("ANCHOR_ARGUMENT_INVALID")
    cp_id = checkpoint.get("checkpoint_id")
    if not isinstance(cp_id, str) or not HEX64.fullmatch(cp_id):
        raise ValueError("ANCHOR_CHECKPOINT_ID_INVALID")
    snap = {"checkpoint": checkpoint, "events": events, "observed_at": observed_at}
    wire = canonical(snap)
    if len(wire) > MAX_OBJECT_BYTES:
        raise ValueError("ANCHOR_OBJECT_TOO_LARGE")
    with _locked(root, create=True) as objects:
        current = _head(root)
        if current["checkpoint_id"] != expected_current_id:
            raise ValueError("ANCHOR_COMPARE_AND_SWAP_CONFLICT")
        prior = None
        if current["checkpoint_id"] != GENESIS:
            prior = _snapshot(objects, current["checkpoint_id"])
            _verify_snapshot(prior, spine=spine, trusted_spine_hash=trusted_spine_hash,
                             trusted_event_keys=trusted_event_keys,
                             trusted_checkpoint_keys=trusted_checkpoint_keys,
                             checkpoint_id=current["checkpoint_id"])
            if (events[:len(prior["events"])] != prior["events"]
                    or observed_at[:len(prior["observed_at"])] != prior["observed_at"]
                    or len(events) <= len(prior["events"])
                    or checkpoint.get("as_of", -1) < prior["checkpoint"]["as_of"]
                    or any(t < prior["checkpoint"]["as_of"] for t in observed_at[len(prior["observed_at"]):])):
                raise ValueError("ANCHOR_HISTORY_REWRITE_OR_NON_APPEND")
        if (checkpoint.get("checkpoint_sequence") != current["sequence"] + 1 or
                checkpoint.get("previous_checkpoint_id") != current["checkpoint_id"]):
            raise ValueError("ANCHOR_SEQUENCE_OR_PREDECESSOR_INVALID")
        verdict = _verify_snapshot(snap, spine=spine, trusted_spine_hash=trusted_spine_hash,
                                   trusted_event_keys=trusted_event_keys,
                                   trusted_checkpoint_keys=trusted_checkpoint_keys,
                                   checkpoint_id=cp_id, expected_previous_id=current["checkpoint_id"])
        _atomic_write(objects / (cp_id + ".json"), wire, exclusive=True)
        new_head = {"schema": STORE_SCHEMA, "checkpoint_id": cp_id,
                    "sequence": checkpoint["checkpoint_sequence"]}
        _atomic_write(root / "HEAD.json", canonical(new_head), exclusive=False)
    return {"status": "LOCAL_ATOMIC_CAS_COMMITTED_NOT_EXTERNALLY_ANCHORED",
            "checkpoint_id": cp_id, "previous_checkpoint_id": expected_current_id,
            "external_anchor_verified": False, "authority_effect": "NONE",
            "execution_effect": "NONE", "admission": "DENIED"}


def read_pinned(root: Path, spine: Mapping[str, Any], *, trusted_head_id: str,
                trusted_spine_hash: str, trusted_event_keys: Mapping[str, Any],
                trusted_checkpoint_keys: Mapping[str, bytes]) -> dict[str, Any]:
    """Verify a locally stored snapshot against a separately pinned head ID."""
    if not isinstance(trusted_head_id, str) or not HEX64.fullmatch(trusted_head_id):
        raise ValueError("ANCHOR_TRUSTED_HEAD_MISSING")
    with _locked(root, create=False) as objects:
        head = _head(root)
        if head["checkpoint_id"] != trusted_head_id or trusted_head_id == GENESIS:
            raise ValueError("ANCHOR_PIN_MISMATCH_OR_UNINITIALIZED")
        snap = _snapshot(objects, trusted_head_id)
        if snap["checkpoint"].get("checkpoint_sequence") != head["sequence"]:
            raise ValueError("ANCHOR_HEAD_SEQUENCE_MISMATCH")
        verdict = _verify_snapshot(snap, spine=spine,
                                   trusted_spine_hash=trusted_spine_hash,
                                   trusted_event_keys=trusted_event_keys,
                                   trusted_checkpoint_keys=trusted_checkpoint_keys,
                                   checkpoint_id=trusted_head_id)
    return {"status": "LOCAL_PINNED_SNAPSHOT_MATCHED_NOT_EXTERNAL_PROOF",
            "checkpoint_id": trusted_head_id, "checkpoint_verdict": verdict,
            "external_anchor_verified": False, "authority_effect": "NONE",
            "execution_effect": "NONE", "admission": "DENIED"}
