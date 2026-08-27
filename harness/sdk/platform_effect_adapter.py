"""Independent effect observation for durable platform-execution creation."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import weakref
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from harness.sdk.effect_adapters import (
    EFFECT_WITNESS_KIND,
    PLATFORM_EXECUTION_ADAPTER_IDENTITY,
    PLATFORM_EXECUTION_ADAPTER_VERSION,
    EffectAdapterError,
    EffectObservationHandle,
    EffectWitness,
    _register_issued_effect_witness,
)
from harness.sdk.sovereign_execution import canonical_hash
from harness.sdk.transition_receipts import ExecutionReceipt, TransitionIdentity

_EXECUTION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
_MAX_RESPONSE_BYTES = 1024 * 1024
PLATFORM_CONTRACT_VERSION = "1.0.0"


class _ObservationHandleRegistry:
    """Process-local, identity-bound provenance for issued observation handles."""

    def __init__(self) -> None:
        self._entries: weakref.WeakValueDictionary[str, EffectObservationHandle] = (
            weakref.WeakValueDictionary()
        )
        self._lock = threading.RLock()

    def register(self, value: EffectObservationHandle, *, root: str) -> None:
        with self._lock:
            self._entries[root] = value

    def contains(self, value: EffectObservationHandle, *, root: str) -> bool:
        with self._lock:
            return self._entries.get(root) is value


@dataclass(frozen=True)
class PlatformHttpResponse:
    status_code: int
    contract_version: str
    git_sha: str
    body_digest: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class PlatformExecutionObservation:
    target_identity: str
    execution_id: str
    exists: bool
    response: PlatformHttpResponse


@dataclass(frozen=True)
class PlatformArtifactProvenance:
    target_identity: str
    contract_version: str
    git_sha: str
    pre_response_digest: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        del req, fp, code, msg, headers, newurl
        return None


def _validated_bridge_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.rstrip("/"))
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise EffectAdapterError("PLATFORM_BRIDGE_URL_INVALID")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise EffectAdapterError("PLATFORM_BRIDGE_URL_INVALID")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _require_execution_id(execution_id: str) -> None:
    if not isinstance(execution_id, str) or not _EXECUTION_ID_RE.fullmatch(execution_id):
        raise EffectAdapterError("PLATFORM_EXECUTION_ID_INVALID")


def platform_execution_target(execution_id: str) -> str:
    _require_execution_id(execution_id)
    return f"/platform/executions/{execution_id}"


def platform_execution_state_commitment(*, execution_id: str, exists: bool) -> str:
    return canonical_hash(
        "AEGIS_PLATFORM_EXECUTION_STATE_V1",
        {"target_identity": platform_execution_target(execution_id), "exists": exists},
    )


def platform_execution_absent_commitment(execution_id: str) -> str:
    return platform_execution_state_commitment(execution_id=execution_id, exists=False)


def request_platform_json(
    *,
    bridge_url: str,
    api_key: str,
    method: str,
    path: str,
    body: Mapping[str, Any] | None = None,
    timeout_seconds: float = 5.0,
) -> PlatformHttpResponse:
    """Perform one bounded, no-redirect JSON request without exposing credentials."""
    base = _validated_bridge_url(bridge_url)
    if not api_key:
        raise EffectAdapterError("PLATFORM_API_KEY_UNAVAILABLE")
    if not path.startswith("/") or "?" in path or "#" in path:
        raise EffectAdapterError("PLATFORM_REQUEST_PATH_INVALID")
    encoded = None if body is None else json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        f"{base}{path}",
        data=encoded,
        method=method,
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        response = opener.open(request, timeout=timeout_seconds)
    except urllib.error.HTTPError as exc:
        response = exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EffectAdapterError("PLATFORM_OBSERVATION_UNAVAILABLE") from exc
    try:
        raw = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise EffectAdapterError("PLATFORM_RESPONSE_TOO_LARGE")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EffectAdapterError("PLATFORM_RESPONSE_NOT_JSON") from exc
        if not isinstance(payload, dict):
            raise EffectAdapterError("PLATFORM_RESPONSE_NOT_OBJECT")
        contract_version = response.headers.get("X-Contract-Version", "")
        git_sha = response.headers.get("X-Git-SHA", "")
        if not contract_version:
            raise EffectAdapterError("PLATFORM_CONTRACT_VERSION_UNAVAILABLE")
        if not _GIT_SHA_RE.fullmatch(git_sha):
            raise EffectAdapterError("PLATFORM_GIT_SHA_INVALID")
        return PlatformHttpResponse(
            status_code=int(response.status),
            contract_version=contract_version,
            git_sha=git_sha,
            body_digest=hashlib.sha256(raw).hexdigest(),
            payload=payload,
        )
    finally:
        response.close()


class PlatformExecutionEffectAdapter:
    """Read-only adapter that proves absent-before and present-after by fresh GETs."""

    identity = PLATFORM_EXECUTION_ADAPTER_IDENTITY
    version = PLATFORM_EXECUTION_ADAPTER_VERSION

    def __init__(self, *, bridge_url: str, api_key: str, timeout_seconds: float = 5.0):
        self.bridge_url = _validated_bridge_url(bridge_url)
        if not api_key:
            raise EffectAdapterError("PLATFORM_API_KEY_UNAVAILABLE")
        self._api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._issued_observation_handles = _ObservationHandleRegistry()
        self._pre_observations: dict[str, PlatformExecutionObservation] = {}

    def _scope_commitment(self) -> str:
        return canonical_hash(
            "AEGIS_PLATFORM_EFFECT_ADAPTER_SCOPE_V1",
            {
                "bridge_url": self.bridge_url,
                # Integrity/lineage commitment for a random bearer token; this is
                # not password verification and intentionally preserves the V1 digest.
                "credential_binding": hashlib.sha256(
                    self._api_key.encode("utf-8"), usedforsecurity=False
                ).hexdigest(),
                "adapter_identity": self.identity,
                "adapter_version": self.version,
            },
        )

    @staticmethod
    def _handle_root(handle: EffectObservationHandle) -> str:
        handle.validate()
        return canonical_hash("AEGIS_EFFECT_OBSERVATION_HANDLE_V1", asdict(handle))

    def _handle_issuance_root(self, handle: EffectObservationHandle) -> str:
        return canonical_hash(
            "AEGIS_EFFECT_OBSERVATION_HANDLE_ISSUANCE_V1",
            {
                "handle_root": self._handle_root(handle),
                "adapter_scope_commitment": self._scope_commitment(),
            },
        )

    def _observe(self, execution_id: str) -> PlatformExecutionObservation:
        target = platform_execution_target(execution_id)
        response = request_platform_json(
            bridge_url=self.bridge_url,
            api_key=self._api_key,
            method="GET",
            path=target,
            timeout_seconds=self.timeout_seconds,
        )
        payload = response.payload
        if response.status_code == 404:
            if payload.get("code") != "NOT_FOUND" or payload.get("execution_id") != execution_id:
                raise EffectAdapterError("PLATFORM_ABSENCE_EVIDENCE_INVALID")
            return PlatformExecutionObservation(target, execution_id, False, response)
        if response.status_code != 200:
            raise EffectAdapterError("PLATFORM_OBSERVATION_STATUS_INVALID")
        data = payload.get("data")
        if (
            payload.get("contract_version") != response.contract_version
            or payload.get("execution_id") != execution_id
            or payload.get("is_replay_reconstructable") is not True
            or not isinstance(data, dict)
            or data.get("execution_id") != execution_id
            or data.get("status") not in ("pending", "running", "complete", "error")
        ):
            raise EffectAdapterError("PLATFORM_PRESENT_EVIDENCE_INVALID")
        return PlatformExecutionObservation(target, execution_id, True, response)

    @staticmethod
    def _state_commitment(observation: PlatformExecutionObservation) -> str:
        return canonical_hash(
            "AEGIS_PLATFORM_EXECUTION_STATE_V1",
            {"target_identity": observation.target_identity, "exists": observation.exists},
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

    def prepare_observation(self, *, transition: TransitionIdentity, execution_id: str) -> EffectObservationHandle:
        transition_id = transition.root
        observation = self._observe(execution_id)
        if observation.response.contract_version != PLATFORM_CONTRACT_VERSION:
            raise EffectAdapterError("PLATFORM_CONTRACT_VERSION_UNSUPPORTED")
        if observation.response.git_sha != transition.source_commit:
            raise EffectAdapterError("PLATFORM_SOURCE_COMMIT_MISMATCH")
        if observation.exists:
            raise EffectAdapterError("PLATFORM_EXECUTION_PRE_STATE_ALREADY_EXISTS")
        pre_commitment = self._state_commitment(observation)
        if pre_commitment != transition.pre_state_commitment:
            raise EffectAdapterError("EFFECT_PRE_STATE_COMMITMENT_MISMATCH")
        observation_id = self._observation_id(
            transition_id=transition_id,
            target_identity=observation.target_identity,
            pre_state_commitment=pre_commitment,
        )
        provenance = canonical_hash(
            "AEGIS_PLATFORM_EFFECT_OBSERVATION_PROVENANCE_V1",
            {
                "transition_id": transition_id,
                "phase": "PRE",
                "target_identity": observation.target_identity,
                "state_commitment": pre_commitment,
                "http_status": observation.response.status_code,
                "response_digest": observation.response.body_digest,
                "contract_version": observation.response.contract_version,
                "git_sha": observation.response.git_sha,
                "observation_id": observation_id,
            },
        )
        handle = EffectObservationHandle(
            transition_id=transition_id,
            target_identity=observation.target_identity,
            observed_pre_state_commitment=pre_commitment,
            pre_observation_provenance=provenance,
            adapter_identity=self.identity,
            adapter_version=self.version,
            observation_id=observation_id,
        )
        handle.validate()
        self._issued_observation_handles.register(handle, root=self._handle_issuance_root(handle))
        self._pre_observations[self._handle_root(handle)] = observation
        return handle

    def artifact_provenance(self, *, handle: EffectObservationHandle) -> PlatformArtifactProvenance:
        handle.validate()
        if not self._issued_observation_handles.contains(handle, root=self._handle_issuance_root(handle)):
            raise EffectAdapterError("EFFECT_OBSERVATION_HANDLE_UNISSUED")
        observation = self._pre_observations.get(self._handle_root(handle))
        if observation is None:
            raise EffectAdapterError("PLATFORM_PRE_OBSERVATION_UNAVAILABLE")
        return PlatformArtifactProvenance(
            target_identity=observation.target_identity,
            contract_version=observation.response.contract_version,
            git_sha=observation.response.git_sha,
            pre_response_digest=observation.response.body_digest,
        )

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
        if handle.transition_id != transition_id or execution_receipt.transition_id != transition_id:
            raise EffectAdapterError("EFFECT_TRANSITION_BINDING_MISMATCH")
        if handle.adapter_identity != self.identity or handle.adapter_version != self.version:
            raise EffectAdapterError("EFFECT_ADAPTER_BINDING_MISMATCH")
        if handle.observed_pre_state_commitment != transition.pre_state_commitment:
            raise EffectAdapterError("EFFECT_PRE_STATE_COMMITMENT_MISMATCH")
        if not self._issued_observation_handles.contains(handle, root=self._handle_issuance_root(handle)):
            raise EffectAdapterError("EFFECT_OBSERVATION_HANDLE_UNISSUED")
        pre_observation = self._pre_observations.get(self._handle_root(handle))
        if pre_observation is None:
            raise EffectAdapterError("PLATFORM_PRE_OBSERVATION_UNAVAILABLE")
        execution_id = execution_receipt.execution_instance_id
        if handle.target_identity != platform_execution_target(execution_id):
            raise EffectAdapterError("EFFECT_OBSERVATION_HANDLE_MISMATCH")
        first = self._observe(execution_id)
        if (
            first.response.contract_version != pre_observation.response.contract_version
            or first.response.git_sha != pre_observation.response.git_sha
        ):
            raise EffectAdapterError("PLATFORM_ARTIFACT_PROVENANCE_CHANGED")
        second = self._observe(execution_id)
        if (
            second.response.contract_version != pre_observation.response.contract_version
            or second.response.git_sha != pre_observation.response.git_sha
        ):
            raise EffectAdapterError("PLATFORM_ARTIFACT_PROVENANCE_CHANGED")
        if not first.exists or not second.exists or first.target_identity != second.target_identity:
            raise EffectAdapterError("PLATFORM_EFFECT_NOT_OBSERVED")
        post_commitment = self._state_commitment(second)
        post_provenance = canonical_hash(
            "AEGIS_PLATFORM_EFFECT_OBSERVATION_PROVENANCE_V1",
            {
                "transition_id": transition_id,
                "phase": "POST_INDEPENDENT_DOUBLE_READ",
                "target_identity": second.target_identity,
                "state_commitment": post_commitment,
                "execution_instance_id": execution_id,
                "first_response_digest": first.response.body_digest,
                "second_response_digest": second.response.body_digest,
                "first_git_sha": first.response.git_sha,
                "second_git_sha": second.response.git_sha,
                "observation_id": handle.observation_id,
            },
        )
        witness = EffectWitness(
            witness_kind=EFFECT_WITNESS_KIND,
            transition_id=transition_id,
            execution_instance_id=execution_id,
            target_identity=second.target_identity,
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
