"""PR-2 provider-neutral effect observation boundary with a filesystem reference adapter.

EPISTEMIC STATUS: REFERENCE_EFFECT_OBSERVATION_ONLY

This module can produce adapter-bound EffectEvidence candidates (`EffectWitness`)
from independent pre/post observations. It deliberately does not implement
VerifyEffect, EffectReceipt production, VerifyTransition, atomic admission, or
EffectBoundAdmission.
"""
from __future__ import annotations

import errno
import hashlib
import os
import re
import stat as stat_module
import threading
import weakref
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from harness.sdk.sovereign_execution import ZERO_HASH, canonical_hash
from harness.sdk.transition_receipts import ExecutionReceipt, TransitionIdentity

EFFECT_WITNESS_KIND = "EFFECT_WITNESS_V1"
VERIFY_EFFECT_STATUS = "does not implement VerifyEffect"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_MAX_OBSERVATION_BYTES = 16 * 1024 * 1024
OBSERVATION_READ_CHUNK_BYTES = 64 * 1024


class EffectAdapterError(ValueError):
    """Raised when independent effect observation cannot be established safely."""


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise EffectAdapterError(f"{name}:INVALID_SHA256")


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise EffectAdapterError(f"{name}:INVALID_VALUE")


@dataclass(frozen=True)
class EffectObservationHandle:
    transition_id: str
    target_identity: str
    observed_pre_state_commitment: str
    pre_observation_provenance: str
    adapter_identity: str
    adapter_version: str
    observation_id: str

    def validate(self) -> None:
        for name in (
            "transition_id",
            "observed_pre_state_commitment",
            "pre_observation_provenance",
            "observation_id",
        ):
            _require_hash(name, getattr(self, name))
        for name in ("target_identity", "adapter_identity", "adapter_version"):
            _require_text(name, getattr(self, name))


@dataclass(frozen=True)
class EffectWitness:
    """EffectEvidence candidate produced by an independent observation path."""

    witness_kind: str
    transition_id: str
    execution_instance_id: str
    target_identity: str
    observed_pre_state_commitment: str
    observed_post_state_commitment: str
    effect_changed: bool
    pre_observation_provenance: str
    post_observation_provenance: str
    adapter_identity: str
    adapter_version: str

    def validate(self) -> None:
        if self.witness_kind != EFFECT_WITNESS_KIND:
            raise EffectAdapterError("EFFECT_WITNESS_KIND_MISMATCH")
        for name in (
            "transition_id",
            "observed_pre_state_commitment",
            "observed_post_state_commitment",
            "pre_observation_provenance",
            "post_observation_provenance",
        ):
            _require_hash(name, getattr(self, name))
        for name in (
            "execution_instance_id",
            "target_identity",
            "adapter_identity",
            "adapter_version",
        ):
            _require_text(name, getattr(self, name))
        if not isinstance(self.effect_changed, bool):
            raise EffectAdapterError("effect_changed:INVALID_BOOLEAN")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_EFFECT_WITNESS_V1", asdict(self))


_ISSUED_EFFECT_WITNESSES: weakref.WeakValueDictionary[str, EffectWitness] = weakref.WeakValueDictionary()
_ISSUED_EFFECT_WITNESSES_LOCK = threading.RLock()


def _register_issued_effect_witness(witness: EffectWitness) -> None:
    """Record one adapter-produced witness object for this process-local reference."""
    root = witness.root
    with _ISSUED_EFFECT_WITNESSES_LOCK:
        _ISSUED_EFFECT_WITNESSES[root] = witness


def _is_process_local_issued_effect_witness(witness: EffectWitness) -> bool:
    """Nominal local-reference provenance check; not cryptographic attestation."""
    root = witness.root
    with _ISSUED_EFFECT_WITNESSES_LOCK:
        return _ISSUED_EFFECT_WITNESSES.get(root) is witness


@dataclass(frozen=True)
class FilesystemStateObservation:
    target_identity: str
    exists: bool
    content_sha256: str
    size_bytes: int
    device: int
    inode: int
    mtime_ns: int


class FilesystemEffectAdapter:
    """Reference adapter deriving EffectEvidence from fresh filesystem observations."""

    identity = "aegis.filesystem-effect-adapter"
    version = "1.0.0"

    def __init__(self, *, allowed_root: Path):
        self.allowed_root = Path(allowed_root).resolve(strict=False)
        self.max_observation_bytes = DEFAULT_MAX_OBSERVATION_BYTES

    def _resolve_target(self, target: Path) -> tuple[Path, str]:
        """Lexically bind a target beneath allowed_root without following target symlinks."""
        root = Path(os.path.abspath(os.fspath(self.allowed_root)))
        candidate = Path(os.path.abspath(os.fspath(Path(target))))
        try:
            common = Path(os.path.commonpath((os.fspath(root), os.fspath(candidate))))
        except ValueError as exc:
            raise EffectAdapterError("EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT") from exc
        if common != root:
            raise EffectAdapterError("EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT")
        target_identity = os.path.relpath(os.fspath(candidate), os.fspath(root))
        if target_identity in ("", "."):
            raise EffectAdapterError("EFFECT_TARGET_NOT_REGULAR_FILE")
        parts = Path(target_identity).parts
        if not parts or any(part in ("", ".", "..") for part in parts):
            raise EffectAdapterError("EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT")
        return candidate, Path(target_identity).as_posix()

    @staticmethod
    def _missing_observation(*, target_identity: str) -> FilesystemStateObservation:
        return FilesystemStateObservation(
            target_identity=target_identity,
            exists=False,
            content_sha256=ZERO_HASH,
            size_bytes=0,
            device=0,
            inode=0,
            mtime_ns=0,
        )

    def _open_beneath_allowed_root(self, *, target_identity: str) -> int:
        """Open a regular-file candidate descriptor-relative with symlink following disabled."""
        required = ("O_DIRECTORY", "O_NOFOLLOW")
        if os.name != "posix" or any(not hasattr(os, name) for name in required):
            raise EffectAdapterError("EFFECT_RACE_RESISTANT_OPEN_UNAVAILABLE")

        root_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        file_flags = os.O_RDONLY | os.O_NOFOLLOW
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW

        parts = Path(target_identity).parts
        if not parts or any(part in ("", ".", "..") for part in parts):
            raise EffectAdapterError("EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT")

        try:
            root_fd = os.open(os.fspath(self.allowed_root), root_flags)
        except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
            raise EffectAdapterError("EFFECT_ALLOWED_ROOT_UNAVAILABLE") from exc

        opened_dirs: list[int] = []
        dir_fd = root_fd
        try:
            for part in parts[:-1]:
                try:
                    next_fd = os.open(part, directory_flags, dir_fd=dir_fd)
                except FileNotFoundError:
                    raise
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise EffectAdapterError("EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT") from exc
                    if exc.errno in (errno.EACCES, errno.EPERM):
                        raise EffectAdapterError("EFFECT_TARGET_NOT_REGULAR_FILE") from exc
                    raise
                opened_dirs.append(next_fd)
                dir_fd = next_fd

            try:
                return os.open(parts[-1], file_flags, dir_fd=dir_fd)
            except FileNotFoundError:
                raise
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise EffectAdapterError("EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT") from exc
                if exc.errno in (errno.EISDIR, errno.ENOTDIR, errno.EACCES, errno.EPERM):
                    raise EffectAdapterError("EFFECT_TARGET_NOT_REGULAR_FILE") from exc
                raise
        finally:
            for opened_fd in reversed(opened_dirs):
                os.close(opened_fd)
            os.close(root_fd)

    def _observe_state(self, target: Path) -> FilesystemStateObservation:
        _, target_identity = self._resolve_target(target)
        limit = getattr(self, "max_observation_bytes", DEFAULT_MAX_OBSERVATION_BYTES)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise EffectAdapterError("EFFECT_OBSERVATION_SIZE_BOUND_INVALID")

        try:
            fd = self._open_beneath_allowed_root(target_identity=target_identity)
        except FileNotFoundError:
            return self._missing_observation(target_identity=target_identity)

        try:
            stat_before = os.fstat(fd)
            if not stat_module.S_ISREG(stat_before.st_mode):
                raise EffectAdapterError("EFFECT_TARGET_NOT_REGULAR_FILE")
            if int(stat_before.st_size) > limit:
                raise EffectAdapterError("EFFECT_TARGET_TOO_LARGE")

            digest = hashlib.sha256()
            total = 0
            while True:
                remaining_probe = limit - total + 1
                read_size = min(OBSERVATION_READ_CHUNK_BYTES, max(1, remaining_probe))
                chunk = os.read(fd, read_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise EffectAdapterError("EFFECT_TARGET_TOO_LARGE")
                digest.update(chunk)

            stat_after = os.fstat(fd)
            stable_fields_before = (
                int(stat_before.st_dev),
                int(stat_before.st_ino),
                int(stat_before.st_size),
                int(stat_before.st_mtime_ns),
            )
            stable_fields_after = (
                int(stat_after.st_dev),
                int(stat_after.st_ino),
                int(stat_after.st_size),
                int(stat_after.st_mtime_ns),
            )
            if stable_fields_before != stable_fields_after or int(stat_after.st_size) != total:
                raise EffectAdapterError("EFFECT_TARGET_CHANGED_DURING_OBSERVATION")

            return FilesystemStateObservation(
                target_identity=target_identity,
                exists=True,
                content_sha256=digest.hexdigest(),
                size_bytes=total,
                device=int(stat_after.st_dev),
                inode=int(stat_after.st_ino),
                mtime_ns=int(stat_after.st_mtime_ns),
            )
        finally:
            os.close(fd)

    @staticmethod
    def _state_commitment(observation: FilesystemStateObservation) -> str:
        return canonical_hash(
            "AEGIS_FILESYSTEM_EFFECT_STATE_V1",
            {
                "target_identity": observation.target_identity,
                "exists": observation.exists,
                "content_sha256": observation.content_sha256,
                "size_bytes": observation.size_bytes,
            },
        )

    def _observation_id(self, *, transition_id: str, target_identity: str, pre_state_commitment: str) -> str:
        return canonical_hash(
            "AEGIS_EFFECT_OBSERVATION_HANDLE_V1",
            {
                "transition_id": transition_id,
                "target_identity": target_identity,
                "pre_state_commitment": pre_state_commitment,
                "adapter_identity": self.identity,
                "adapter_version": self.version,
            },
        )

    def _observation_provenance(
        self,
        *,
        transition_id: str,
        phase: str,
        observation: FilesystemStateObservation,
        state_commitment: str,
        observation_id: str,
        execution_instance_id: str | None = None,
    ) -> str:
        value: dict[str, Any] = {
            "transition_id": transition_id,
            "phase": phase,
            "target_identity": observation.target_identity,
            "state_commitment": state_commitment,
            "content_sha256": observation.content_sha256,
            "size_bytes": observation.size_bytes,
            "filesystem_device": observation.device,
            "filesystem_inode": observation.inode,
            "filesystem_mtime_ns": observation.mtime_ns,
            "adapter_identity": self.identity,
            "adapter_version": self.version,
            "observation_id": observation_id,
        }
        if execution_instance_id is not None:
            value["execution_instance_id"] = execution_instance_id
        return canonical_hash("AEGIS_EFFECT_OBSERVATION_PROVENANCE_V1", value)

    def prepare_observation(self, *, transition: TransitionIdentity, target: Path) -> EffectObservationHandle:
        transition_id = transition.root
        observation = self._observe_state(Path(target))
        pre_commitment = self._state_commitment(observation)
        if pre_commitment != transition.pre_state_commitment:
            raise EffectAdapterError("EFFECT_PRE_STATE_COMMITMENT_MISMATCH")
        observation_id = self._observation_id(
            transition_id=transition_id,
            target_identity=observation.target_identity,
            pre_state_commitment=pre_commitment,
        )
        provenance = self._observation_provenance(
            transition_id=transition_id,
            phase="PRE",
            observation=observation,
            state_commitment=pre_commitment,
            observation_id=observation_id,
        )
        result = EffectObservationHandle(
            transition_id=transition_id,
            target_identity=observation.target_identity,
            observed_pre_state_commitment=pre_commitment,
            pre_observation_provenance=provenance,
            adapter_identity=self.identity,
            adapter_version=self.version,
            observation_id=observation_id,
        )
        result.validate()
        return result

    def observe_effect(
        self,
        *,
        transition: TransitionIdentity,
        handle: EffectObservationHandle,
        execution_receipt: ExecutionReceipt,
    ) -> EffectWitness:
        transition_id = transition.root
        handle.validate()
        execution_receipt.validate()
        if handle.transition_id != transition_id:
            raise EffectAdapterError("EFFECT_TRANSITION_BINDING_MISMATCH")
        if execution_receipt.transition_id != transition_id:
            raise EffectAdapterError("EFFECT_EXECUTION_TRANSITION_MISMATCH")
        if handle.adapter_identity != self.identity or handle.adapter_version != self.version:
            raise EffectAdapterError("EFFECT_ADAPTER_BINDING_MISMATCH")
        if handle.observed_pre_state_commitment != transition.pre_state_commitment:
            raise EffectAdapterError("EFFECT_PRE_STATE_COMMITMENT_MISMATCH")
        expected_observation_id = self._observation_id(
            transition_id=transition_id,
            target_identity=handle.target_identity,
            pre_state_commitment=handle.observed_pre_state_commitment,
        )
        if handle.observation_id != expected_observation_id:
            raise EffectAdapterError("EFFECT_OBSERVATION_HANDLE_MISMATCH")
        post_target = self.allowed_root / handle.target_identity
        observation = self._observe_state(post_target)
        if observation.target_identity != handle.target_identity:
            raise EffectAdapterError("EFFECT_OBSERVATION_HANDLE_MISMATCH")
        post_commitment = self._state_commitment(observation)
        post_provenance = self._observation_provenance(
            transition_id=transition_id,
            phase="POST",
            observation=observation,
            state_commitment=post_commitment,
            observation_id=handle.observation_id,
            execution_instance_id=execution_receipt.execution_instance_id,
        )
        witness = EffectWitness(
            witness_kind=EFFECT_WITNESS_KIND,
            transition_id=transition_id,
            execution_instance_id=execution_receipt.execution_instance_id,
            target_identity=handle.target_identity,
            observed_pre_state_commitment=handle.observed_pre_state_commitment,
            observed_post_state_commitment=post_commitment,
            effect_changed=post_commitment != handle.observed_pre_state_commitment,
            pre_observation_provenance=handle.pre_observation_provenance,
            post_observation_provenance=post_provenance,
            adapter_identity=self.identity,
            adapter_version=self.version,
        )
        witness.validate()
        _register_issued_effect_witness(witness)
        return witness


def filesystem_state_commitment(*, allowed_root: Path, target: Path) -> str:
    adapter = FilesystemEffectAdapter(allowed_root=allowed_root)
    return adapter._state_commitment(adapter._observe_state(Path(target)))


def is_adapter_bound_effect_evidence(*, witness: EffectWitness) -> bool:
    """Process-local adapter-issued EffectEvidence check; not cryptographic attestation."""
    try:
        witness.validate()
        return (
            witness.witness_kind == EFFECT_WITNESS_KIND
            and witness.adapter_identity == FilesystemEffectAdapter.identity
            and witness.adapter_version == FilesystemEffectAdapter.version
            and _is_process_local_issued_effect_witness(witness)
        )
    except (EffectAdapterError, ValueError, TypeError, AttributeError):
        return False
