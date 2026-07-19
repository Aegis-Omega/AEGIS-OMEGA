"""Automaton-3 operator-sovereign execution reference model.

This module is the single authority-decision path for consequential AEGIS work.
It is standard-library only, deterministic at its hashed boundaries, and fail-closed.
Absolute paths and timestamps are observational metadata and never enter deterministic roots.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import threading
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

SCHEMA_VERSION = "1.0.0"
ZERO_HASH = "0" * 64
MIN_VALIDATED_RUNS = 3
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40,64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")

D0, D1, D2, D3, D4 = "D0", "D1", "D2", "D3", "D4"
ACTION_CLASSES = (D0, D1, D2, D3, D4)
ADMITTED, DENIED = "ADMITTED", "DENIED"

DEFAULT_POLICY: dict[str, dict[str, Any]] = {
    D0: {"minimum_validated_runs": 0, "approval": "NONE", "workspace": "READ_ONLY", "replay": False, "rollback": "NONE", "external_idempotency": False},
    D1: {"minimum_validated_runs": 3, "approval": "NONE", "workspace": "REPOSITORY", "replay": True, "rollback": "REQUIRED", "external_idempotency": False},
    D2: {"minimum_validated_runs": 3, "approval": "EXPLICIT", "workspace": "REPOSITORY", "replay": True, "rollback": "REQUIRED", "external_idempotency": False},
    D3: {"minimum_validated_runs": 3, "approval": "EXPLICIT", "workspace": "REPOSITORY", "replay": True, "rollback": "COMPENSATION_OR_IDEMPOTENCY", "external_idempotency": True},
    D4: {"minimum_validated_runs": 3, "approval": "EXPLICIT", "workspace": "REPOSITORY", "replay": True, "rollback": "COMPENSATION_OR_IDEMPOTENCY", "external_idempotency": True},
}

REQUIRED_CONSTITUTIONAL_FILES = (
    "CONSTITUTIONAL_DECLARATION.md",
    ".claude.json",
    "skill-hashes.sha256",
    "docs/claims.json",
)

class SovereignExecutionError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(domain: str, value: Any) -> str:
    return sha256_hex(canonical_bytes({"domain": domain, "value": value}))


def _assert_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise SovereignExecutionError(f"{name}:INVALID_SHA256")


def _assert_git(name: str, value: str) -> None:
    if not isinstance(value, str) or not GIT_RE.fullmatch(value):
        raise SovereignExecutionError(f"{name}:INVALID_GIT_OBJECT")


def _unsafe_unicode(value: str) -> bool:
    if unicodedata.normalize("NFC", value) != value:
        return True
    return any(unicodedata.category(ch).startswith("C") for ch in value)


def _assert_authority_string(name: str, value: str, *, allow_url: bool = False) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SovereignExecutionError(f"{name}:EMPTY")
    if _unsafe_unicode(value):
        raise SovereignExecutionError(f"{name}:UNICODE_OR_CONTROL_AMBIGUITY")
    if not allow_url and not SAFE_ID_RE.fullmatch(value):
        raise SovereignExecutionError(f"{name}:UNSAFE_CHARACTERS")


def canonical_remote(remote: str) -> str:
    _assert_authority_string("repository_identity", remote, allow_url=True)
    value = remote.strip()
    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value.removeprefix("git@github.com:")
    if value.startswith("ssh://git@github.com/"):
        value = "https://github.com/" + value.removeprefix("ssh://git@github.com/")
    if not value.startswith("https://github.com/"):
        raise SovereignExecutionError("repository_identity:UNSUPPORTED_REMOTE")
    if not value.endswith(".git"):
        value += ".git"
    return value


def deterministic_redaction(value: Any, sensitive_keys: Iterable[str] = ("secret", "token", "password", "key")) -> Any:
    needles = tuple(item.lower() for item in sensitive_keys)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value, key=str):
            raw = value[key]
            if any(needle in str(key).lower() for needle in needles):
                encoded = canonical_bytes(raw)
                result[str(key)] = {"redacted": True, "sha256": sha256_hex(encoded), "size_bytes": len(encoded)}
            else:
                result[str(key)] = deterministic_redaction(raw, needles)
        return result
    if isinstance(value, list):
        return [deterministic_redaction(item, needles) for item in value]
    return value


@dataclass(frozen=True)
class ExecutionIdentityEnvelope:
    schema_version: str
    repository_identity: str
    repository_root: str
    source_commit: str
    branch_or_ref: str
    project_identity: str
    workspace_root: str
    workspace_binding: str
    parent_state_root: str
    skills_root: str
    registry_root: str
    policy_root: str
    actor_class: str
    actor_identity: str
    model_identity: str
    session_identity: str
    physical_executor: str
    tool_identity: str
    workflow_identity: str
    authority_domain: str
    requested_capability: str
    observed_authority: str
    approval_reference: str
    input_digest: str
    action_digest: str
    expected_pre_state: str
    deterministic_nonce: str

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("IDENTITY_SCHEMA_UNSUPPORTED")
        remote = canonical_remote(self.repository_identity)
        if remote != self.repository_identity:
            raise SovereignExecutionError("REPOSITORY_IDENTITY_NOT_CANONICAL")
        if self.repository_root != "." or self.workspace_root != ".":
            raise SovereignExecutionError("IDENTITY_ROOT_MUST_BE_LOGICAL_REPOSITORY_ROOT")
        _assert_git("source_commit", self.source_commit)
        for name in ("workspace_binding", "parent_state_root", "skills_root", "registry_root", "policy_root", "input_digest", "action_digest", "expected_pre_state"):
            _assert_hash(name, getattr(self, name))
        for name in ("branch_or_ref", "project_identity", "actor_class", "actor_identity", "model_identity", "session_identity", "physical_executor", "tool_identity", "workflow_identity", "authority_domain", "requested_capability", "observed_authority", "approval_reference", "deterministic_nonce"):
            _assert_authority_string(name, getattr(self, name))
        expected = compute_workspace_binding(
            repository_remote=self.repository_identity,
            repository_root=self.repository_root,
            project_identity=self.project_identity,
            source_commit=self.source_commit,
            operator_authorization=self.approval_reference,
        )
        if self.workspace_binding != expected:
            raise SovereignExecutionError("WORKSPACE_BINDING_MISMATCH")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_EXECUTION_IDENTITY_V1", asdict(self))


def compute_workspace_binding(*, repository_remote: str, repository_root: str, project_identity: str, source_commit: str, operator_authorization: str) -> str:
    remote = canonical_remote(repository_remote)
    _assert_git("source_commit", source_commit)
    if repository_root != ".":
        raise SovereignExecutionError("WORKSPACE_LOGICAL_ROOT_INVALID")
    _assert_authority_string("project_identity", project_identity)
    _assert_authority_string("operator_authorization", operator_authorization)
    return canonical_hash("AEGIS_WORKSPACE_BINDING_V1", {
        "repository_remote": remote,
        "repository_root": repository_root,
        "project_identity": project_identity,
        "source_commit": source_commit,
        "operator_authorization": operator_authorization,
    })


@dataclass(frozen=True)
class WorkspaceObservation:
    declared_project: str
    actual_cwd: str
    resolved_repository_root: str
    remote_origin: str
    mutation_target: str
    path_views: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkspaceDecision:
    outcome: str
    workspace_binding: str | None
    denial_codes: tuple[str, ...]
    observation: WorkspaceObservation
    decision_root: str


def _normalize_path_view(value: str) -> str:
    text = value.replace("\\", "/").strip()
    drive = re.match(r"^([A-Za-z]):/(.*)$", text)
    if drive:
        text = f"/mnt/{drive.group(1).lower()}/{drive.group(2)}"
    text = re.sub(r"^//wsl\$/[^/]+", "", text, flags=re.IGNORECASE)
    parts: list[str] = []
    for part in text.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            else:
                return "ESCAPE"
        else:
            parts.append(part.casefold())
    return "/" + "/".join(parts)


def verify_workspace(*, declared_root: str | Path, cwd: str | Path, expected_remote: str, actual_remote: str, project_identity: str, source_commit: str, operator_authorization: str, mutation_target: str | Path, required_files: Sequence[str] = REQUIRED_CONSTITUTIONAL_FILES, path_views: Mapping[str, str] | None = None, selected_nested_root: str | Path | None = None, approved_cross_project_pair: tuple[str, str] | None = None) -> WorkspaceDecision:
    reasons: list[str] = []
    declared = Path(declared_root)
    cwd_path = Path(cwd)
    target = Path(mutation_target)
    views = dict(path_views or {})
    try:
        root = declared.resolve(strict=True)
    except OSError:
        root = declared.absolute()
        reasons.append("REPOSITORY_ROOT_MISSING")
    try:
        cwd_real = cwd_path.resolve(strict=True)
    except OSError:
        cwd_real = cwd_path.absolute()
        reasons.append("CWD_MISSING")
    try:
        target_real = target.resolve(strict=False)
    except OSError:
        target_real = target.absolute()
        reasons.append("MUTATION_TARGET_UNRESOLVED")

    if declared.exists() and declared.absolute() != root:
        reasons.append("REPOSITORY_ROOT_SYMLINKED")
    if cwd_path.exists() and cwd_path.absolute() != cwd_real:
        reasons.append("CWD_SYMLINKED")
    for candidate, code in ((cwd_real, "CWD_OUTSIDE_REPOSITORY"), (target_real, "MUTATION_TARGET_OUTSIDE_REPOSITORY")):
        try:
            candidate.relative_to(root)
        except ValueError:
            reasons.append(code)

    if root.exists():
        for required in required_files:
            candidate = (root / required).resolve(strict=False)
            try:
                candidate.relative_to(root)
            except ValueError:
                reasons.append(f"REQUIRED_FILE_ESCAPES:{required}")
                continue
            if not candidate.is_file():
                reasons.append(f"REQUIRED_FILE_MISSING:{required}")
        if not any(root.iterdir()):
            reasons.append("EMPTY_WORKSPACE")

    try:
        expected_canonical = canonical_remote(expected_remote)
    except SovereignExecutionError:
        expected_canonical = expected_remote
        reasons.append("EXPECTED_REMOTE_INVALID")
    try:
        actual_canonical = canonical_remote(actual_remote)
    except SovereignExecutionError:
        actual_canonical = actual_remote
        reasons.append("REMOTE_ORIGIN_INVALID")
    if actual_canonical != expected_canonical:
        reasons.append("REMOTE_ORIGIN_CHANGED")

    nested: list[Path] = []
    if root.exists():
        current = target_real if target_real.is_dir() else target_real.parent
        while current != root and root in current.parents:
            if (current / ".git").exists():
                nested.append(current)
            current = current.parent
    if nested:
        selected = Path(selected_nested_root).resolve() if selected_nested_root else None
        if selected not in nested:
            reasons.append("NESTED_REPOSITORY_REQUIRES_EXPLICIT_TARGET")

    if approved_cross_project_pair is not None and project_identity not in approved_cross_project_pair:
        reasons.append("CROSS_PROJECT_APPROVAL_MISMATCH")

    if views:
        normalized = {_normalize_path_view(value) for value in views.values()}
        if "ESCAPE" in normalized:
            reasons.append("PATH_VIEW_TRAVERSAL")
        if len(normalized) != 1:
            reasons.append("PATH_VIEW_DISAGREEMENT")

    binding: str | None = None
    if not reasons:
        binding = compute_workspace_binding(
            repository_remote=actual_canonical,
            repository_root=".",
            project_identity=project_identity,
            source_commit=source_commit,
            operator_authorization=operator_authorization,
        )
    observation = WorkspaceObservation(
        declared_project=project_identity,
        actual_cwd=str(cwd_real),
        resolved_repository_root=str(root),
        remote_origin=actual_remote,
        mutation_target=str(target_real),
        path_views=views,
    )
    deterministic = {
        "outcome": ADMITTED if not reasons else DENIED,
        "workspace_binding": binding,
        "denial_codes": sorted(set(reasons)),
        "declared_project": project_identity,
        "remote_origin": actual_canonical,
        "source_commit": source_commit,
        "mutation_target_relative": _relative_or_marker(target_real, root),
    }
    return WorkspaceDecision(deterministic["outcome"], binding, tuple(deterministic["denial_codes"]), observation, canonical_hash("AEGIS_WORKSPACE_DECISION_V1", deterministic))


def _relative_or_marker(path: Path, root: Path) -> str:
    try:
        return PurePosixPath(path.relative_to(root)).as_posix() or "."
    except ValueError:
        return "OUTSIDE_REPOSITORY"


@dataclass(frozen=True)
class CapabilityEvidence:
    capability: str
    skill_id: str
    observation_state: str
    validated_runs: int
    confidence_micros: int
    recency_micros: int
    failure_rate_micros: int
    evidence_refs: tuple[str, ...]
    allowed_action_classes: tuple[str, ...]
    allowed_tools: tuple[str, ...]


@dataclass(frozen=True)
class ApprovalGrant:
    reference: str
    authority_domain: str
    action_class: str
    source_commit: str
    workspace_binding: str
    valid_through_generation: int
    signature_root: str
    state: str = "APPROVED"


@dataclass(frozen=True)
class AuthorityRequest:
    action_class: str
    authority_domain: str
    requested_capability: str
    tool: str
    target: str
    identity_root: str
    workspace_binding: str
    source_commit: str
    registry_root: str
    policy_root: str
    current_generation: int
    approval_reference: str = "NONE"
    idempotency_key: str = "NONE"
    compensation_reference: str = "NONE"


@dataclass(frozen=True)
class PolicyDecision:
    schema_version: str
    outcome: str
    authority_score: str
    action_class: str
    authority_domain: str
    requested_capability: str
    tool: str
    target_digest: str
    identity_root: str
    workspace_binding: str
    registry_root: str
    policy_root: str
    denial_codes: tuple[str, ...]
    decision_root: str


class AuthorityEvaluator:
    def __init__(self, *, policy: Mapping[str, Mapping[str, Any]] | None, registry: Mapping[str, CapabilityEvidence] | None, repository_root: str | Path | None = None):
        self.policy = copy.deepcopy(dict(policy)) if policy is not None else None
        self.registry = dict(registry) if registry is not None else None
        self.repository_root = Path(repository_root).resolve() if repository_root is not None else None
        self.policy_root = canonical_hash("AEGIS_CONSEQUENCE_POLICY_V1", self.policy) if self.policy is not None else ZERO_HASH

    def evaluate(self, request: AuthorityRequest, *, approval: ApprovalGrant | None = None) -> PolicyDecision:
        reasons: list[str] = []
        if self.policy is None:
            reasons.append("AUTHORITY_SERVICE_UNAVAILABLE")
        if self.registry is None:
            reasons.append("REGISTRY_UNAVAILABLE")
        if request.action_class not in ACTION_CLASSES:
            reasons.append("UNKNOWN_ACTION_CLASS")
        policy = self.policy.get(request.action_class) if self.policy and request.action_class in ACTION_CLASSES else None
        if policy is None:
            reasons.append("POLICY_UNAVAILABLE")
        if request.policy_root != self.policy_root:
            reasons.append("POLICY_ROOT_MISMATCH")
        for name in ("identity_root", "workspace_binding", "registry_root", "policy_root"):
            try:
                _assert_hash(name, getattr(request, name))
            except SovereignExecutionError as exc:
                reasons.append(str(exc))
        try:
            _assert_git("source_commit", request.source_commit)
        except SovereignExecutionError as exc:
            reasons.append(str(exc))
        for name in ("authority_domain", "requested_capability", "tool"):
            try:
                _assert_authority_string(name, getattr(request, name))
            except SovereignExecutionError as exc:
                reasons.append(str(exc))

        evidence = self.registry.get(request.requested_capability) if self.registry else None
        score_micros = 0
        if evidence is None:
            reasons.append("UNMAPPED_CAPABILITY")
        else:
            if evidence.capability != request.requested_capability:
                reasons.append("CAPABILITY_RECORD_CONFLICT")
            if request.action_class != D0 and evidence.observation_state != "OBSERVED":
                reasons.append("UNOBSERVED_CAPABILITY")
            minimum = int(policy.get("minimum_validated_runs", MIN_VALIDATED_RUNS)) if policy else MIN_VALIDATED_RUNS
            if evidence.validated_runs < minimum:
                reasons.append("INSUFFICIENT_VALIDATED_RUNS")
            if request.action_class != D0 and evidence.validated_runs < MIN_VALIDATED_RUNS:
                reasons.append("OPERATIONAL_AUTHORITY_REQUIRES_THREE_RUNS")
            if request.action_class not in evidence.allowed_action_classes:
                reasons.append("ACTION_CLASS_NOT_PERMITTED")
            if request.tool not in evidence.allowed_tools:
                reasons.append("TOOL_NOT_PERMITTED")
            if not evidence.evidence_refs:
                reasons.append("EVIDENCE_MISSING")
            elif self.repository_root is not None:
                for ref in evidence.evidence_refs:
                    candidate = (self.repository_root / ref).resolve(strict=False)
                    try:
                        candidate.relative_to(self.repository_root)
                    except ValueError:
                        reasons.append("EVIDENCE_OUTSIDE_REPOSITORY")
                        continue
                    if not candidate.is_file():
                        reasons.append("EVIDENCE_UNRESOLVED")
            if not reasons:
                score_micros = evidence.confidence_micros * evidence.recency_micros * (1_000_000 - evidence.failure_rate_micros) // 1_000_000 // 1_000_000

        if policy and policy.get("approval") == "EXPLICIT":
            if approval is None:
                reasons.append("APPROVAL_MISSING")
            else:
                if approval.state != "APPROVED": reasons.append("APPROVAL_NOT_ACTIVE")
                if approval.reference != request.approval_reference: reasons.append("APPROVAL_REFERENCE_MISMATCH")
                if approval.authority_domain != request.authority_domain: reasons.append("APPROVAL_DOMAIN_MISMATCH")
                if approval.action_class != request.action_class: reasons.append("APPROVAL_ACTION_CLASS_MISMATCH")
                if approval.source_commit != request.source_commit: reasons.append("APPROVAL_SOURCE_COMMIT_MISMATCH")
                if approval.workspace_binding != request.workspace_binding: reasons.append("APPROVAL_WORKSPACE_MISMATCH")
                if approval.valid_through_generation < request.current_generation: reasons.append("APPROVAL_EXPIRED")
                try: _assert_hash("approval.signature_root", approval.signature_root)
                except SovereignExecutionError: reasons.append("APPROVAL_UNSIGNED")

        if policy and policy.get("external_idempotency"):
            if request.idempotency_key == "NONE" and request.compensation_reference == "NONE":
                reasons.append("EXTERNAL_EFFECT_REQUIRES_IDEMPOTENCY_OR_COMPENSATION")

        reasons = sorted(set(reasons))
        outcome = ADMITTED if not reasons else DENIED
        if outcome == DENIED:
            score_micros = 0
        body = {
            "schema_version": SCHEMA_VERSION,
            "outcome": outcome,
            "authority_score": f"{score_micros / 1_000_000:.6f}",
            "action_class": request.action_class,
            "authority_domain": request.authority_domain,
            "requested_capability": request.requested_capability,
            "tool": request.tool,
            "target_digest": canonical_hash("AEGIS_AUTHORITY_TARGET_V1", request.target),
            "identity_root": request.identity_root,
            "workspace_binding": request.workspace_binding,
            "registry_root": request.registry_root,
            "policy_root": request.policy_root,
            "denial_codes": reasons,
        }
        root = canonical_hash("AEGIS_POLICY_DECISION_V1", body)
        return PolicyDecision(**body, decision_root=root)


@dataclass(frozen=True)
class WriterLease:
    schema_version: str
    authority_domain: str
    holder_identity_root: str
    source_commit: str
    lease_generation: int
    fencing_token: str
    expected_parent_state: str


@dataclass(frozen=True)
class LeaseReceipt:
    operation: str
    outcome: str
    authority_domain: str
    lease_generation: int
    fencing_token_digest: str
    denial_codes: tuple[str, ...]
    receipt_root: str


class WriterLeaseManager:
    def __init__(self) -> None:
        self._leases: dict[str, WriterLease] = {}
        self._generation: dict[str, int] = {}
        self._used_actions: set[tuple[str, int, str]] = set()
        self._lock = threading.RLock()

    def acquire(self, *, authority_domain: str, holder_identity_root: str, source_commit: str, expected_parent_state: str) -> tuple[WriterLease | None, LeaseReceipt]:
        with self._lock:
            reasons: list[str] = []
            if authority_domain in self._leases:
                reasons.append("WRITER_ALREADY_ACTIVE")
            try: _assert_hash("holder_identity_root", holder_identity_root)
            except SovereignExecutionError as exc: reasons.append(str(exc))
            try: _assert_git("source_commit", source_commit)
            except SovereignExecutionError as exc: reasons.append(str(exc))
            try: _assert_hash("expected_parent_state", expected_parent_state)
            except SovereignExecutionError as exc: reasons.append(str(exc))
            generation = self._generation.get(authority_domain, 0) + 1
            lease = None
            token = ZERO_HASH
            if not reasons:
                token = canonical_hash("AEGIS_WRITER_FENCE_V1", {"authority_domain": authority_domain, "holder_identity_root": holder_identity_root, "source_commit": source_commit, "lease_generation": generation, "expected_parent_state": expected_parent_state})
                lease = WriterLease(SCHEMA_VERSION, authority_domain, holder_identity_root, source_commit, generation, token, expected_parent_state)
                self._leases[authority_domain] = lease
                self._generation[authority_domain] = generation
            receipt = self._lease_receipt("ACQUIRE", authority_domain, generation, token, reasons)
            return lease, receipt

    def authorize_write(self, *, authority_domain: str, holder_identity_root: str, fencing_token: str, lease_generation: int, expected_parent_state: str, action_digest: str) -> LeaseReceipt:
        with self._lock:
            reasons: list[str] = []
            lease = self._leases.get(authority_domain)
            if lease is None: reasons.append("LEASE_MISSING")
            else:
                if lease.holder_identity_root != holder_identity_root: reasons.append("LEASE_HOLDER_MISMATCH")
                if lease.fencing_token != fencing_token: reasons.append("STALE_FENCING_TOKEN")
                if lease.lease_generation != lease_generation: reasons.append("STALE_LEASE_GENERATION")
                if lease.expected_parent_state != expected_parent_state: reasons.append("PARENT_STATE_MISMATCH")
            try: _assert_hash("action_digest", action_digest)
            except SovereignExecutionError as exc: reasons.append(str(exc))
            key = (authority_domain, lease_generation, action_digest)
            if key in self._used_actions: reasons.append("REPLAYED_AUTHORITATIVE_ACTION")
            if not reasons: self._used_actions.add(key)
            return self._lease_receipt("AUTHORIZE_WRITE", authority_domain, lease_generation, fencing_token, reasons)

    def advance(self, *, authority_domain: str, fencing_token: str, new_parent_state: str) -> LeaseReceipt:
        with self._lock:
            reasons: list[str] = []
            lease = self._leases.get(authority_domain)
            if lease is None: reasons.append("LEASE_MISSING")
            elif lease.fencing_token != fencing_token: reasons.append("STALE_FENCING_TOKEN")
            try: _assert_hash("new_parent_state", new_parent_state)
            except SovereignExecutionError as exc: reasons.append(str(exc))
            generation = lease.lease_generation if lease else self._generation.get(authority_domain, 0)
            if not reasons and lease:
                self._leases[authority_domain] = WriterLease(lease.schema_version, lease.authority_domain, lease.holder_identity_root, lease.source_commit, lease.lease_generation, lease.fencing_token, new_parent_state)
            return self._lease_receipt("ADVANCE", authority_domain, generation, fencing_token, reasons)

    def revoke(self, authority_domain: str, holder_identity_root: str) -> LeaseReceipt:
        with self._lock:
            reasons: list[str] = []
            lease = self._leases.get(authority_domain)
            if lease is None: reasons.append("LEASE_MISSING")
            elif lease.holder_identity_root != holder_identity_root: reasons.append("LEASE_HOLDER_MISMATCH")
            generation = lease.lease_generation if lease else self._generation.get(authority_domain, 0)
            token = lease.fencing_token if lease else ZERO_HASH
            if not reasons: del self._leases[authority_domain]
            return self._lease_receipt("REVOKE", authority_domain, generation, token, reasons)

    def current(self, authority_domain: str) -> WriterLease | None:
        with self._lock:
            return self._leases.get(authority_domain)

    @staticmethod
    def _lease_receipt(operation: str, domain: str, generation: int, token: str, reasons: Sequence[str]) -> LeaseReceipt:
        body = {"operation": operation, "outcome": ADMITTED if not reasons else DENIED, "authority_domain": domain, "lease_generation": generation, "fencing_token_digest": canonical_hash("AEGIS_FENCE_TOKEN_REDACTION_V1", token), "denial_codes": sorted(set(reasons))}
        return LeaseReceipt(**body, receipt_root=canonical_hash("AEGIS_LEASE_RECEIPT_V1", body))


DURABLE_STATUSES = ("PLANNED", "ADMITTED", "RUNNING", "WAITING_FOR_APPROVAL", "BLOCKED", "RETRYING", "DENIED", "COMPLETED", "CANCELLED", "ORPHANED")

@dataclass
class DurableExecutionRecord:
    workflow_identity: str
    owner: str
    source_commit: str
    workspace_binding: str
    current_phase: str
    current_authority: tuple[str, ...]
    last_completed_transition: int
    pending_external_action: str
    retry_count: int
    next_retry: int | None
    cancellation_state: str
    lease_holder: str
    parent_state_root: str
    current_receipt_root: str
    failure_state: str
    status: str
    last_heartbeat_generation: int
    used_external_actions: set[str] = field(default_factory=set, repr=False)


class DurableExecutionRegistry:
    def __init__(self, lease_manager: WriterLeaseManager):
        self._records: dict[str, DurableExecutionRecord] = {}
        self._leases = lease_manager

    def register(self, execution_id: str, record: DurableExecutionRecord) -> str:
        if execution_id in self._records: raise SovereignExecutionError("DURABLE_EXECUTION_ALREADY_REGISTERED")
        if record.status not in DURABLE_STATUSES: raise SovereignExecutionError("DURABLE_STATUS_INVALID")
        if record.status != "PLANNED": raise SovereignExecutionError("DURABLE_MUST_REGISTER_AS_PLANNED")
        self._records[execution_id] = copy.deepcopy(record)
        return self.root(execution_id)

    def transition(self, execution_id: str, *, status: str, phase: str, transition_sequence: int, receipt_root: str) -> str:
        record = self._require(execution_id)
        if record.status in ("CANCELLED", "COMPLETED", "ORPHANED"): raise SovereignExecutionError("DURABLE_TERMINAL_STATE")
        if status not in DURABLE_STATUSES: raise SovereignExecutionError("DURABLE_STATUS_INVALID")
        if transition_sequence != record.last_completed_transition + 1: raise SovereignExecutionError("DURABLE_SEQUENCE_INVALID")
        _assert_hash("receipt_root", receipt_root)
        record.status, record.current_phase = status, phase
        record.last_completed_transition = transition_sequence
        record.current_receipt_root = receipt_root
        return self.root(execution_id)

    def heartbeat(self, execution_id: str, generation: int) -> str:
        record = self._require(execution_id)
        if generation <= record.last_heartbeat_generation: raise SovereignExecutionError("HEARTBEAT_NOT_MONOTONE")
        record.last_heartbeat_generation = generation
        return self.root(execution_id)

    def mark_orphaned(self, execution_id: str, current_generation: int, maximum_gap: int) -> str:
        record = self._require(execution_id)
        if current_generation - record.last_heartbeat_generation <= maximum_gap: raise SovereignExecutionError("ORPHAN_THRESHOLD_NOT_REACHED")
        held = record.current_authority
        record.status = "ORPHANED"; record.current_authority = ()
        if record.lease_holder:
            for domain in held: self._leases.revoke(domain, record.lease_holder)
        return self.root(execution_id)

    def cancel(self, execution_id: str) -> str:
        record = self._require(execution_id)
        record.status = "CANCELLED"; record.cancellation_state = "REVOKED"
        held = record.current_authority; record.current_authority = ()
        for domain in held: self._leases.revoke(domain, record.lease_holder)
        return self.root(execution_id)

    def claim_external_action(self, execution_id: str, idempotency_key: str) -> str:
        record = self._require(execution_id)
        if record.status not in ("RUNNING", "RETRYING"): raise SovereignExecutionError("DURABLE_NOT_RUNNING")
        if idempotency_key in record.used_external_actions: raise SovereignExecutionError("DUPLICATE_EXTERNAL_ACTION")
        _assert_authority_string("idempotency_key", idempotency_key)
        record.used_external_actions.add(idempotency_key)
        record.pending_external_action = idempotency_key
        return self.root(execution_id)

    def get(self, execution_id: str) -> DurableExecutionRecord:
        return copy.deepcopy(self._require(execution_id))

    def root(self, execution_id: str) -> str:
        record = self._require(execution_id)
        body = asdict(record); body["used_external_actions"] = sorted(record.used_external_actions)
        return canonical_hash("AEGIS_DURABLE_EXECUTION_V1", body)

    def _require(self, execution_id: str) -> DurableExecutionRecord:
        if execution_id not in self._records: raise SovereignExecutionError("DURABLE_EXECUTION_UNKNOWN")
        return self._records[execution_id]


@dataclass(frozen=True)
class EventEnvelope:
    sender_identity_root: str
    recipient_or_routing_domain: str
    source_state: str
    capability_request: str
    payload_schema: str
    payload: Mapping[str, Any]
    payload_digest: str
    provenance: str
    policy_decision: str
    parent_event: str
    sequence: int
    receipt_reference: str

    def validate(self, *, expected_sequence: int, expected_parent: str, sender_lease_root: str | None = None, max_payload_bytes: int = 16_384) -> None:
        for name in ("sender_identity_root", "source_state", "payload_digest", "policy_decision", "parent_event", "receipt_reference"):
            _assert_hash(name, getattr(self, name))
        for name in ("recipient_or_routing_domain", "capability_request", "payload_schema", "provenance"):
            _assert_authority_string(name, getattr(self, name))
        if self.sequence != expected_sequence: raise SovereignExecutionError("EVENT_SEQUENCE_INVALID")
        if self.parent_event != expected_parent: raise SovereignExecutionError("EVENT_PARENT_MISMATCH")
        if sender_lease_root is not None and self.sender_identity_root != sender_lease_root: raise SovereignExecutionError("EVENT_SENDER_LEASE_MISMATCH")
        encoded = canonical_bytes(self.payload)
        if len(encoded) > max_payload_bytes: raise SovereignExecutionError("EVENT_PAYLOAD_OVERSIZED")
        if sha256_hex(encoded) != self.payload_digest: raise SovereignExecutionError("EVENT_PAYLOAD_DIGEST_MISMATCH")
        allowed = {"data", "text", "content_type"}
        if any(key not in allowed for key in self.payload): raise SovereignExecutionError("EVENT_PAYLOAD_SCHEMA_DRIFT")
        text = self.payload.get("text")
        if text is not None:
            if not isinstance(text, str) or len(text.encode("utf-8")) > 4096: raise SovereignExecutionError("EVENT_TEXT_INVALID")
            if _unsafe_unicode(text): raise SovereignExecutionError("EVENT_TEXT_UNICODE_OR_CONTROL_AMBIGUITY")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_EVENT_ENVELOPE_V1", {**asdict(self), "payload": deterministic_redaction(self.payload)})


@dataclass(frozen=True)
class MutationReceipt:
    receipt_version: str
    execution_identity_root: str
    workspace_binding: str
    policy_decision_root: str
    authority_score: str
    authority_domain: str
    action_class: str
    tool: str
    target: str
    pre_state_digest: str
    requested_action_digest: str
    result_digest: str
    post_state_digest: str
    parent_receipt: str
    sequence: int
    outcome: str
    denial_code: str

    def validate(self) -> None:
        if self.receipt_version != SCHEMA_VERSION: raise SovereignExecutionError("RECEIPT_SCHEMA_UNSUPPORTED")
        for name in ("execution_identity_root", "workspace_binding", "policy_decision_root", "pre_state_digest", "requested_action_digest", "result_digest", "post_state_digest", "parent_receipt"):
            _assert_hash(name, getattr(self, name))
        if self.sequence < 0: raise SovereignExecutionError("RECEIPT_SEQUENCE_INVALID")
        if self.outcome not in ("SUCCEEDED", "DENIED", "FAILED", "ROLLED_BACK"): raise SovereignExecutionError("RECEIPT_OUTCOME_INVALID")
        if self.outcome == "DENIED" and self.denial_code in ("", "NONE"): raise SovereignExecutionError("DENIAL_CODE_REQUIRED")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_MUTATION_RECEIPT_V1", deterministic_redaction(asdict(self)))


class ReceiptChain:
    def __init__(self) -> None:
        self._receipts: list[MutationReceipt] = []

    def append(self, receipt: MutationReceipt) -> str:
        receipt.validate()
        expected_sequence = len(self._receipts)
        expected_parent = self._receipts[-1].root if self._receipts else ZERO_HASH
        if receipt.sequence != expected_sequence: raise SovereignExecutionError("RECEIPT_CHAIN_SEQUENCE_BREAK")
        if receipt.parent_receipt != expected_parent: raise SovereignExecutionError("RECEIPT_CHAIN_PARENT_BREAK")
        self._receipts.append(receipt)
        return receipt.root

    def verify(self) -> str:
        previous = ZERO_HASH
        for index, receipt in enumerate(self._receipts):
            if receipt.sequence != index or receipt.parent_receipt != previous: raise SovereignExecutionError("RECEIPT_CHAIN_BROKEN")
            previous = receipt.root
        return previous


def load_policy(path: str | Path) -> tuple[dict[str, Any], str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != SCHEMA_VERSION or raw.get("classes") is None:
        raise SovereignExecutionError("POLICY_INVALID")
    policy = raw["classes"]
    for action_class in ACTION_CLASSES:
        if action_class not in policy: raise SovereignExecutionError(f"POLICY_CLASS_MISSING:{action_class}")
    return policy, canonical_hash("AEGIS_CONSEQUENCE_POLICY_V1", policy)


def git_remote(root: str | Path) -> str:
    try:
        result = subprocess.run(["git", "-C", str(root), "config", "--get", "remote.origin.url"], check=True, text=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SovereignExecutionError("REMOTE_ORIGIN_UNAVAILABLE") from exc
    return canonical_remote(result.stdout.strip())


def decision_dict(decision: PolicyDecision) -> dict[str, Any]:
    return asdict(decision)


def compute_skill_registry_root(tree: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(tree))
    payload.pop("registry_root", None)
    payload.pop("genesis_seal", None)
    return sha256_hex(canonical_bytes({"domain": "AEGIS_SKILL_REGISTRY_V2", "registry": payload}))


def load_capability_registry(*, repository_root: str | Path, skill_tree_path: str | Path, capability_map_path: str | Path) -> tuple[dict[str, CapabilityEvidence], str]:
    root = Path(repository_root).resolve(strict=True)
    skill_path = Path(skill_tree_path).resolve(strict=True)
    map_path = Path(capability_map_path).resolve(strict=True)
    for candidate in (skill_path, map_path):
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise SovereignExecutionError("REGISTRY_PATH_OUTSIDE_REPOSITORY") from exc
    tree = json.loads(skill_path.read_text(encoding="utf-8"))
    mapping = json.loads(map_path.read_text(encoding="utf-8"))
    expected = compute_skill_registry_root(tree)
    if tree.get("registry_root") != expected or tree.get("genesis_seal") != expected:
        raise SovereignExecutionError("REGISTRY_ROOT_MISMATCH")
    if mapping.get("schema_version") != SCHEMA_VERSION or not isinstance(mapping.get("capabilities"), dict):
        raise SovereignExecutionError("CAPABILITY_MAP_INVALID")
    skills = {item.get("skill_id"): item for item in tree.get("skills", []) if isinstance(item, dict) and isinstance(item.get("skill_id"), str)}
    registry: dict[str, CapabilityEvidence] = {}
    for capability, config in mapping["capabilities"].items():
        if not isinstance(config, dict):
            raise SovereignExecutionError("CAPABILITY_MAP_RECORD_INVALID")
        skill_id = config.get("skill_id")
        skill = skills.get(skill_id)
        if skill is None:
            continue
        refs = skill.get("evidence_refs", [])
        if not isinstance(refs, list): refs = []
        def micros(field: str) -> int:
            value = skill.get(field, 0.0)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
                return 0
            return int(round(float(value) * 1_000_000))
        registry[capability] = CapabilityEvidence(
            capability=capability,
            skill_id=skill_id,
            observation_state=str(skill.get("observation_state", "UNKNOWN")),
            validated_runs=skill.get("validated_runs", 0) if isinstance(skill.get("validated_runs", 0), int) and not isinstance(skill.get("validated_runs", 0), bool) else 0,
            confidence_micros=micros("confidence"),
            recency_micros=micros("recency_score"),
            failure_rate_micros=micros("failure_rate"),
            evidence_refs=tuple(sorted(str(ref) for ref in refs if isinstance(ref, str) and ref)),
            allowed_action_classes=tuple(config.get("allowed_action_classes", [])),
            allowed_tools=tuple(config.get("allowed_tools", [])),
        )
    return registry, expected


def make_mutation_receipt(*, identity_root: str, workspace_binding: str, decision: PolicyDecision, pre_state_digest: str, action_digest: str, result: Any, post_state_digest: str, parent_receipt: str, sequence: int) -> MutationReceipt:
    outcome = "SUCCEEDED" if decision.outcome == ADMITTED else "DENIED"
    denial = "NONE" if decision.outcome == ADMITTED else (decision.denial_codes[0] if decision.denial_codes else "UNSPECIFIED_DENIAL")
    return MutationReceipt(
        receipt_version=SCHEMA_VERSION,
        execution_identity_root=identity_root,
        workspace_binding=workspace_binding,
        policy_decision_root=decision.decision_root,
        authority_score=decision.authority_score,
        authority_domain=decision.authority_domain,
        action_class=decision.action_class,
        tool=decision.tool,
        target=decision.target_digest,
        pre_state_digest=pre_state_digest,
        requested_action_digest=action_digest,
        result_digest=canonical_hash("AEGIS_ACTION_RESULT_V1", deterministic_redaction(result)),
        post_state_digest=post_state_digest,
        parent_receipt=parent_receipt,
        sequence=sequence,
        outcome=outcome,
        denial_code=denial,
    )
