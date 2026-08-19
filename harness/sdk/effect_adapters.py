"""PR-2 provider-neutral effect observation boundary with a filesystem reference adapter.

EPISTEMIC STATUS: REFERENCE_EFFECT_OBSERVATION_ONLY

This module can produce adapter-bound EffectEvidence candidates (`EffectWitness`)
from independent pre/post observations. It deliberately does not implement
VerifyEffect, EffectReceipt production, VerifyTransition, atomic admission, or
EffectBoundAdmission.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from harness.sdk.sovereign_execution import ZERO_HASH, canonical_hash
from harness.sdk.transition_receipts import ExecutionReceipt, TransitionIdentity

EFFECT_WITNESS_KIND = "EFFECT_WITNESS_V1"
VERIFY_EFFECT_STATUS = "does not implement VerifyEffect"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


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

    def _resolve_target(self, target: Path) -> tuple[Path, str]:
        root = self.allowed_root.resolve(strict=False)
        resolved_target = Path(target).resolve(strict=False)
        if resolved_target != root and root not in resolved_target.parents:
            raise EffectAdapterError("EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT")
        return resolved_target, resolved_target.relative_to(root).as_posix()

    def _observe_state(self, target: Path) -> FilesystemStateObservation:
        resolved_target, target_identity = self._resolve_target(target)
        if not resolved_target.exists():
            return FilesystemStateObservation(
                target_identity=target_identity,
                exists=False,
                content_sha256=ZERO_HASH,
                size_bytes=0,
                device=0,
                inode=0,
                mtime_ns=0,
            )
        if not resolved_target.is_file():
            raise EffectAdapterError("EFFECT_TARGET_NOT_REGULAR_FILE")
        try:
            with resolved_target.open("rb") as stream:
                content = stream.read()
                stat = os.fstat(stream.fileno())
        except FileNotFoundError:
            return FilesystemStateObservation(
                target_identity=target_identity,
                exists=False,
                content_sha256=ZERO_HASH,
                size_bytes=0,
                device=0,
                inode=0,
                mtime_ns=0,
            )
        except (IsADirectoryError, PermissionError) as exc:
            raise EffectAdapterError("EFFECT_TARGET_NOT_REGULAR_FILE") from exc
        return FilesystemStateObservation(
            target_identity=target_identity,
            exists=True,
            content_sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            device=int(stat.st_dev),
            inode=int(stat.st_ino),
            mtime_ns=int(stat.st_mtime_ns),
        )

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
        return witness


def filesystem_state_commitment(*, allowed_root: Path, target: Path) -> str:
    adapter = FilesystemEffectAdapter(allowed_root=allowed_root)
    return adapter._state_commitment(adapter._observe_state(Path(target)))


def is_adapter_bound_effect_evidence(*, witness: EffectWitness) -> bool:
    """Structural EffectEvidence candidate check only; not VerifyEffect."""
    try:
        witness.validate()
        return (
            witness.witness_kind == EFFECT_WITNESS_KIND
            and witness.adapter_identity == FilesystemEffectAdapter.identity
            and witness.adapter_version == FilesystemEffectAdapter.version
        )
    except (EffectAdapterError, ValueError, TypeError, AttributeError):
        return False
