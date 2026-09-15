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
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

from harness.sdk.sovereign_execution import ZERO_HASH, canonical_hash
from harness.sdk.transition_receipts import ExecutionReceipt, TransitionIdentity

EFFECT_WITNESS_KIND = "EFFECT_WITNESS_V1"
VERIFY_EFFECT_STATUS = "does not implement VerifyEffect"
PLATFORM_EXECUTION_ADAPTER_IDENTITY = "aegis.platform-execution-effect-adapter"
PLATFORM_EXECUTION_ADAPTER_VERSION = "1.0.0"
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


class _ProcessLocalIssuanceRegistry:
    """Identity-and-snapshot registry; a Python process is not a security sandbox."""

    def __init__(self) -> None:
        self._entries: dict[int, tuple[weakref.ReferenceType[Any], str]] = {}
        self._lock = threading.RLock()

    def register(self, value: Any, *, root: str) -> None:
        object_id = id(value)

        def remove(dead_reference: weakref.ReferenceType[Any]) -> None:
            with self._lock:
                current = self._entries.get(object_id)
                if current is not None and current[0] is dead_reference:
                    self._entries.pop(object_id, None)

        reference = weakref.ref(value, remove)
        with self._lock:
            self._entries[object_id] = (reference, root)

    def contains(self, value: Any, *, root: str) -> bool:
        with self._lock:
            entry = self._entries.get(id(value))
            return entry is not None and entry[0]() is value and entry[1] == root


def _close_fd_safely(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass


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

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_EFFECT_OBSERVATION_HANDLE_V1", asdict(self))


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


_ISSUED_EFFECT_WITNESSES = _ProcessLocalIssuanceRegistry()


def _register_issued_effect_witness(witness: EffectWitness) -> None:
    """Record one adapter-produced witness object for this process-local reference."""
    _ISSUED_EFFECT_WITNESSES.register(witness, root=witness.root)


def _is_process_local_issued_effect_witness(witness: EffectWitness) -> bool:
    """Nominal local-reference provenance check; not cryptographic attestation."""
    return _ISSUED_EFFECT_WITNESSES.contains(witness, root=witness.root)


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
        self._allowed_root = Path(allowed_root).resolve(strict=False)
        self.max_observation_bytes = DEFAULT_MAX_OBSERVATION_BYTES
        self._issued_observation_handles = _ProcessLocalIssuanceRegistry()
        self._root_scope_lock = threading.RLock()
        self._root_fd: int | None = None
        self._root_identity: tuple[int, int] | None = None
        self._root_finalizer: weakref.finalize | None = None

    @property
    def allowed_root(self) -> Path:
        return self._allowed_root

    @allowed_root.setter
    def allowed_root(self, value: Path) -> None:
        del value
        raise EffectAdapterError("EFFECT_ADAPTER_SCOPE_MISMATCH")

    def _assert_root_scope_locked(self) -> None:
        if self._root_fd is None or self._root_identity is None:
            raise EffectAdapterError("EFFECT_ADAPTER_SCOPE_UNAVAILABLE")
        try:
            descriptor_stat = os.fstat(self._root_fd)
            path_stat = os.stat(self._allowed_root, follow_symlinks=False)
        except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
            raise EffectAdapterError("EFFECT_ADAPTER_SCOPE_MISMATCH") from exc
        descriptor_identity = (int(descriptor_stat.st_dev), int(descriptor_stat.st_ino))
        path_identity = (int(path_stat.st_dev), int(path_stat.st_ino))
        if (
            not stat_module.S_ISDIR(descriptor_stat.st_mode)
            or not stat_module.S_ISDIR(path_stat.st_mode)
            or descriptor_identity != self._root_identity
            or path_identity != self._root_identity
        ):
            raise EffectAdapterError("EFFECT_ADAPTER_SCOPE_MISMATCH")

    def _acquire_root_descriptor(self) -> int:
        required = ("O_DIRECTORY", "O_NOFOLLOW")
        if os.name != "posix" or any(not hasattr(os, name) for name in required):
            raise EffectAdapterError("EFFECT_RACE_RESISTANT_OPEN_UNAVAILABLE")
        with self._root_scope_lock:
            if self._root_fd is None:
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                root_fd: int | None = None
                try:
                    root_fd = os.open(os.fspath(self._allowed_root), flags)
                    root_stat = os.fstat(root_fd)
                    if not stat_module.S_ISDIR(root_stat.st_mode):
                        raise EffectAdapterError("EFFECT_ALLOWED_ROOT_UNAVAILABLE")
                except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
                    if root_fd is not None:
                        _close_fd_safely(root_fd)
                    raise EffectAdapterError("EFFECT_ALLOWED_ROOT_UNAVAILABLE") from exc
                except Exception:
                    if root_fd is not None:
                        _close_fd_safely(root_fd)
                    raise
                assert root_fd is not None
                self._root_fd = root_fd
                self._root_identity = (int(root_stat.st_dev), int(root_stat.st_ino))
                self._root_finalizer = weakref.finalize(self, _close_fd_safely, root_fd)
            self._assert_root_scope_locked()
            try:
                return os.dup(self._root_fd)
            except OSError as exc:
                raise EffectAdapterError("EFFECT_ADAPTER_SCOPE_UNAVAILABLE") from exc

    def _adapter_scope_commitment(self) -> str:
        with self._root_scope_lock:
            root_fd = self._acquire_root_descriptor()
            _close_fd_safely(root_fd)
            self._assert_root_scope_locked()
            assert self._root_identity is not None
            return canonical_hash(
                "AEGIS_FILESYSTEM_ADAPTER_SCOPE_V1",
                {
                    "allowed_root": self._allowed_root.as_posix(),
                    "filesystem_device": self._root_identity[0],
                    "filesystem_inode": self._root_identity[1],
                    "adapter_identity": self.identity,
                    "adapter_version": self.version,
                },
            )

    def _handle_issuance_root(self, handle: EffectObservationHandle) -> str:
        return canonical_hash(
            "AEGIS_EFFECT_OBSERVATION_HANDLE_ISSUANCE_V1",
            {
                "handle_root": handle.root,
                "adapter_scope_commitment": self._adapter_scope_commitment(),
            },
        )

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

    @staticmethod
    @contextmanager
    def _opened_fd(path: Any, flags: int, *, dir_fd: int | None = None) -> Iterator[int]:
        """Open one descriptor and make its close operation structurally explicit."""
        if dir_fd is None:
            fd = os.open(path, flags)
        else:
            fd = os.open(path, flags, dir_fd=dir_fd)
        try:
            yield fd
        finally:
            os.close(fd)

    @contextmanager
    def _open_beneath_allowed_root(self, *, target_identity: str) -> Iterator[int]:
        """Yield a descriptor-relative file handle and close every descriptor on exit."""
        required = ("O_DIRECTORY", "O_NOFOLLOW")
        if os.name != "posix" or any(not hasattr(os, name) for name in required):
            raise EffectAdapterError("EFFECT_RACE_RESISTANT_OPEN_UNAVAILABLE")

        file_flags = os.O_RDONLY | os.O_NOFOLLOW
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW

        parts = Path(target_identity).parts
        if not parts or any(part in ("", ".", "..") for part in parts):
            raise EffectAdapterError("EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT")

        with ExitStack() as descriptors:
            try:
                root_fd = self._acquire_root_descriptor()
                descriptors.callback(_close_fd_safely, root_fd)
            except (FileNotFoundError, NotADirectoryError, PermissionError, OSError) as exc:
                raise EffectAdapterError("EFFECT_ALLOWED_ROOT_UNAVAILABLE") from exc
            dir_fd = root_fd
            for part in parts[:-1]:
                try:
                    next_fd = descriptors.enter_context(
                        self._opened_fd(part, directory_flags, dir_fd=dir_fd)
                    )
                except FileNotFoundError:
                    raise
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise EffectAdapterError("EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT") from exc
                    if exc.errno in (errno.EACCES, errno.EPERM):
                        raise EffectAdapterError("EFFECT_TARGET_NOT_REGULAR_FILE") from exc
                    raise
                dir_fd = next_fd

            try:
                file_fd = descriptors.enter_context(
                    self._opened_fd(parts[-1], file_flags, dir_fd=dir_fd)
                )
            except FileNotFoundError:
                raise
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise EffectAdapterError("EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT") from exc
                if exc.errno in (errno.EISDIR, errno.ENOTDIR, errno.EACCES, errno.EPERM):
                    raise EffectAdapterError("EFFECT_TARGET_NOT_REGULAR_FILE") from exc
                raise
            yield file_fd

    def _observe_state(self, target: Path) -> FilesystemStateObservation:
        _, target_identity = self._resolve_target(target)
        limit = getattr(self, "max_observation_bytes", DEFAULT_MAX_OBSERVATION_BYTES)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise EffectAdapterError("EFFECT_OBSERVATION_SIZE_BOUND_INVALID")

        try:
            with self._open_beneath_allowed_root(target_identity=target_identity) as fd:
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
        except FileNotFoundError:
            return self._missing_observation(target_identity=target_identity)

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
        self._issued_observation_handles.register(
            result,
            root=self._handle_issuance_root(result),
        )
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
        if not self._issued_observation_handles.contains(
            handle,
            root=self._handle_issuance_root(handle),
        ):
            raise EffectAdapterError("EFFECT_OBSERVATION_HANDLE_UNISSUED")
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
        supported_adapters = {
            (FilesystemEffectAdapter.identity, FilesystemEffectAdapter.version),
            (PLATFORM_EXECUTION_ADAPTER_IDENTITY, PLATFORM_EXECUTION_ADAPTER_VERSION),
        }
        return (
            witness.witness_kind == EFFECT_WITNESS_KIND
            and (witness.adapter_identity, witness.adapter_version) in supported_adapters
            and _is_process_local_issued_effect_witness(witness)
        )
    except (EffectAdapterError, ValueError, TypeError, AttributeError):
        return False
