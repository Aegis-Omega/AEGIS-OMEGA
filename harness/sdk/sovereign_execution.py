"""Automaton-3 operator-sovereign execution reference model.

This module is the single authority-decision path for consequential AEGIS work.
It is deterministic at its hashed boundaries and fail-closed. Ed25519 verification
uses the CI-pinned ``cryptography`` package; unavailable crypto denies authority.
Absolute paths and timestamps are observational metadata and never enter deterministic roots.
"""
from __future__ import annotations

import copy
import binascii
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


_POLICY_FIELDS = frozenset((
    "minimum_validated_runs",
    "approval",
    "workspace",
    "replay",
    "rollback",
    "external_idempotency",
))


def validate_consequence_policy(policy: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Enforce constitutional safety floors independently of policy data."""
    if not isinstance(policy, Mapping) or set(policy) != set(ACTION_CLASSES):
        raise SovereignExecutionError("POLICY_CLASSES_INVALID")
    validated: dict[str, dict[str, Any]] = {}
    for action_class in ACTION_CLASSES:
        record = policy.get(action_class)
        if not isinstance(record, Mapping) or set(record) != _POLICY_FIELDS:
            raise SovereignExecutionError(f"POLICY_FIELDS_INVALID:{action_class}")
        minimum = record.get("minimum_validated_runs")
        if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0:
            raise SovereignExecutionError(f"POLICY_MINIMUM_RUNS_INVALID:{action_class}")
        if action_class != D0 and minimum < MIN_VALIDATED_RUNS:
            raise SovereignExecutionError(f"POLICY_MINIMUM_RUNS_BELOW_FLOOR:{action_class}")
        approval = record.get("approval")
        if approval not in ("NONE", "EXPLICIT"):
            raise SovereignExecutionError(f"POLICY_APPROVAL_INVALID:{action_class}")
        if action_class in (D2, D3, D4) and approval != "EXPLICIT":
            raise SovereignExecutionError(f"POLICY_EXPLICIT_APPROVAL_REQUIRED:{action_class}")
        expected_workspace = "READ_ONLY" if action_class == D0 else "REPOSITORY"
        if record.get("workspace") != expected_workspace:
            raise SovereignExecutionError(f"POLICY_WORKSPACE_INVALID:{action_class}")
        replay = record.get("replay")
        if not isinstance(replay, bool):
            raise SovereignExecutionError(f"POLICY_REPLAY_INVALID:{action_class}")
        if action_class != D0 and not replay:
            raise SovereignExecutionError(f"POLICY_REPLAY_REQUIRED:{action_class}")
        expected_rollback = {
            D0: "NONE",
            D1: "REQUIRED",
            D2: "REQUIRED",
            D3: "COMPENSATION_OR_IDEMPOTENCY",
            D4: "COMPENSATION_OR_IDEMPOTENCY",
        }[action_class]
        if record.get("rollback") != expected_rollback:
            raise SovereignExecutionError(f"POLICY_ROLLBACK_INVALID:{action_class}")
        external_idempotency = record.get("external_idempotency")
        if not isinstance(external_idempotency, bool):
            raise SovereignExecutionError(f"POLICY_EXTERNAL_IDEMPOTENCY_INVALID:{action_class}")
        if action_class in (D3, D4) and not external_idempotency:
            raise SovereignExecutionError(f"POLICY_EXTERNAL_IDEMPOTENCY_REQUIRED:{action_class}")
        validated[action_class] = copy.deepcopy(dict(record))
    return validated


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(domain: str, value: Any) -> str:
    return sha256_hex(canonical_bytes({"domain": domain, "value": value}))


def _ed25519_sign(*, private_key_hex: str, domain: str, value: Any) -> str:
    if not isinstance(private_key_hex, str) or not re.fullmatch(r"[0-9a-f]{64}", private_key_hex):
        raise SovereignExecutionError("SIGNING_PRIVATE_KEY_INVALID")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise SovereignExecutionError("SIGNATURE_PROVIDER_UNAVAILABLE") from exc
    try:
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
        return key.sign(canonical_bytes({"domain": domain, "value": value})).hex()
    except (ValueError, binascii.Error) as exc:
        raise SovereignExecutionError("SIGNING_PRIVATE_KEY_INVALID") from exc


def _ed25519_verify(*, public_key_hex: str, signature_hex: str, domain: str, value: Any, invalid_code: str) -> None:
    if not isinstance(public_key_hex, str) or not re.fullmatch(r"[0-9a-f]{64}", public_key_hex):
        raise SovereignExecutionError("SIGNING_PUBLIC_KEY_INVALID")
    if not isinstance(signature_hex, str) or not re.fullmatch(r"[0-9a-f]{128}", signature_hex):
        raise SovereignExecutionError(invalid_code)
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise SovereignExecutionError("SIGNATURE_PROVIDER_UNAVAILABLE") from exc
    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(signature_hex), canonical_bytes({"domain": domain, "value": value}))
    except InvalidSignature as exc:
        raise SovereignExecutionError(invalid_code) from exc
    except (ValueError, binascii.Error) as exc:
        raise SovereignExecutionError("SIGNING_PUBLIC_KEY_INVALID") from exc


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
    schema_version: str
    reference: str
    issuer_key_id: str
    operator_identity: str
    authority_domain: str
    action_class: str
    source_commit: str
    workspace_binding: str
    policy_root: str
    registry_root: str
    identity_root: str
    action_digest: str
    target_digest: str
    requested_capability: str
    valid_through_generation: int
    signature: str
    state: str = "APPROVED"

    def signing_body(self) -> dict[str, Any]:
        body = asdict(self)
        body.pop("signature")
        return body

    def validate_shape(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("APPROVAL_SCHEMA_UNSUPPORTED")
        if self.state != "APPROVED":
            raise SovereignExecutionError("APPROVAL_NOT_ACTIVE")
        for name in ("reference", "issuer_key_id", "operator_identity", "authority_domain", "requested_capability"):
            _assert_authority_string(name, getattr(self, name))
        if self.action_class not in ACTION_CLASSES:
            raise SovereignExecutionError("APPROVAL_ACTION_CLASS_INVALID")
        _assert_git("source_commit", self.source_commit)
        for name in ("workspace_binding", "policy_root", "registry_root", "identity_root", "action_digest", "target_digest"):
            _assert_hash(name, getattr(self, name))
        if isinstance(self.valid_through_generation, bool) or not isinstance(self.valid_through_generation, int) or self.valid_through_generation < 0:
            raise SovereignExecutionError("APPROVAL_GENERATION_INVALID")
        if not isinstance(self.signature, str) or not re.fullmatch(r"[0-9a-f]{128}", self.signature):
            raise SovereignExecutionError("APPROVAL_SIGNATURE_INVALID")

    @property
    def root(self) -> str:
        self.validate_shape()
        return canonical_hash("AEGIS_APPROVAL_GRANT_V1", asdict(self))


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
    action_digest: str
    expected_pre_state: str
    workspace_mode: str
    current_generation: int
    approval_reference: str = "NONE"
    rollback_reference: str = "NONE"
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
    approval_grant_root: str
    denial_codes: tuple[str, ...]
    decision_root: str

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("POLICY_DECISION_SCHEMA_UNSUPPORTED")
        if self.outcome not in (ADMITTED, DENIED):
            raise SovereignExecutionError("POLICY_DECISION_OUTCOME_INVALID")
        if self.action_class not in ACTION_CLASSES:
            raise SovereignExecutionError("POLICY_DECISION_ACTION_CLASS_INVALID")
        if not re.fullmatch(r"(?:0\.[0-9]{6}|1\.000000)", self.authority_score):
            raise SovereignExecutionError("POLICY_DECISION_SCORE_INVALID")
        for name in ("target_digest", "identity_root", "workspace_binding", "registry_root", "policy_root", "approval_grant_root", "decision_root"):
            _assert_hash(name, getattr(self, name))
        for name in ("authority_domain", "requested_capability", "tool"):
            _assert_authority_string(name, getattr(self, name))
        if tuple(sorted(set(self.denial_codes))) != self.denial_codes:
            raise SovereignExecutionError("POLICY_DECISION_DENIAL_CODES_NONCANONICAL")
        if self.outcome == ADMITTED and self.denial_codes:
            raise SovereignExecutionError("ADMITTED_POLICY_DECISION_HAS_DENIAL_CODES")
        if self.outcome == DENIED and not self.denial_codes:
            raise SovereignExecutionError("DENIED_POLICY_DECISION_REQUIRES_CODE")
        if self.outcome == DENIED and self.authority_score != "0.000000":
            raise SovereignExecutionError("DENIED_POLICY_DECISION_HAS_AUTHORITY")
        body = asdict(self)
        root = body.pop("decision_root")
        if root != canonical_hash("AEGIS_POLICY_DECISION_V1", body):
            raise SovereignExecutionError("POLICY_DECISION_ROOT_MISMATCH")


class AuthorityEvaluator:
    def __init__(
        self,
        *,
        policy: Mapping[str, Mapping[str, Any]] | None,
        registry: Mapping[str, CapabilityEvidence] | None,
        repository_root: str | Path | None = None,
        trusted_operator_keys: Mapping[str, str] | None = None,
        allow_working_tree_evidence_for_tests: bool = False,
    ):
        self.policy = validate_consequence_policy(policy) if policy is not None else None
        self.registry = dict(registry) if registry is not None else None
        self.repository_root = Path(repository_root).resolve() if repository_root is not None else None
        self.policy_root = canonical_hash("AEGIS_CONSEQUENCE_POLICY_V1", self.policy) if self.policy is not None else ZERO_HASH
        self.trusted_operator_keys = dict(trusted_operator_keys or {})
        self.allow_working_tree_evidence_for_tests = allow_working_tree_evidence_for_tests
        self._issued_decision_roots: set[str] = set()
        self._lock = threading.RLock()

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
        for name in ("action_digest", "expected_pre_state"):
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
        if isinstance(request.current_generation, bool) or not isinstance(request.current_generation, int) or request.current_generation < 0:
            reasons.append("CURRENT_GENERATION_INVALID")

        if policy:
            required_workspace = policy.get("workspace")
            if request.workspace_mode != required_workspace:
                reasons.append("WORKSPACE_MODE_MISMATCH")
            rollback_mode = policy.get("rollback")
            if rollback_mode == "REQUIRED" and request.rollback_reference == "NONE":
                reasons.append("ROLLBACK_REFERENCE_REQUIRED")
            if rollback_mode == "COMPENSATION_OR_IDEMPOTENCY" and request.idempotency_key == "NONE" and request.compensation_reference == "NONE":
                reasons.append("COMPENSATION_OR_IDEMPOTENCY_REQUIRED")

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
            elif self.repository_root is None:
                reasons.append("EVIDENCE_RESOLVER_UNAVAILABLE")
            else:
                for ref in evidence.evidence_refs:
                    try:
                        canonical_ref = _repository_blob_path(ref)
                    except SovereignExecutionError:
                        if isinstance(ref, str) and (PurePosixPath(ref).is_absolute() or ".." in PurePosixPath(ref).parts):
                            reasons.append("EVIDENCE_OUTSIDE_REPOSITORY")
                        else:
                            reasons.append("EVIDENCE_REFERENCE_INVALID")
                        continue
                    if self.allow_working_tree_evidence_for_tests:
                        candidate = (self.repository_root / canonical_ref).resolve(strict=False)
                        try:
                            candidate.relative_to(self.repository_root)
                        except ValueError:
                            reasons.append("EVIDENCE_OUTSIDE_REPOSITORY")
                            continue
                        exists = candidate.is_file()
                    else:
                        exists = git_blob_exists(self.repository_root, request.source_commit, canonical_ref)
                    if not exists:
                        reasons.append("EVIDENCE_UNRESOLVED")
            if not reasons:
                score_micros = evidence.confidence_micros * evidence.recency_micros * (1_000_000 - evidence.failure_rate_micros) // 1_000_000 // 1_000_000

        if policy and policy.get("approval") == "EXPLICIT":
            if approval is None:
                reasons.append("APPROVAL_MISSING")
            else:
                try:
                    approval.validate_shape()
                except SovereignExecutionError as exc:
                    reasons.append(str(exc))
                approval_bindings = (
                    (approval.reference, request.approval_reference, "APPROVAL_REFERENCE_MISMATCH"),
                    (approval.authority_domain, request.authority_domain, "APPROVAL_DOMAIN_MISMATCH"),
                    (approval.action_class, request.action_class, "APPROVAL_ACTION_CLASS_MISMATCH"),
                    (approval.source_commit, request.source_commit, "APPROVAL_SOURCE_COMMIT_MISMATCH"),
                    (approval.workspace_binding, request.workspace_binding, "APPROVAL_WORKSPACE_MISMATCH"),
                    (approval.policy_root, request.policy_root, "APPROVAL_POLICY_MISMATCH"),
                    (approval.registry_root, request.registry_root, "APPROVAL_REGISTRY_MISMATCH"),
                    (approval.identity_root, request.identity_root, "APPROVAL_IDENTITY_MISMATCH"),
                    (approval.action_digest, request.action_digest, "APPROVAL_ACTION_DIGEST_MISMATCH"),
                    (approval.target_digest, canonical_hash("AEGIS_AUTHORITY_TARGET_V1", request.target), "APPROVAL_TARGET_MISMATCH"),
                    (approval.requested_capability, request.requested_capability, "APPROVAL_CAPABILITY_MISMATCH"),
                )
                for actual, expected, code in approval_bindings:
                    if actual != expected:
                        reasons.append(code)
                if approval.valid_through_generation < request.current_generation:
                    reasons.append("APPROVAL_EXPIRED")
                public_key_hex = self.trusted_operator_keys.get(approval.issuer_key_id)
                if public_key_hex is None:
                    reasons.append("APPROVAL_ISSUER_UNTRUSTED")
                else:
                    try:
                        _ed25519_verify(
                            public_key_hex=public_key_hex,
                            signature_hex=approval.signature,
                            domain="AEGIS_APPROVAL_GRANT_V1",
                            value=approval.signing_body(),
                            invalid_code="APPROVAL_SIGNATURE_INVALID",
                        )
                    except SovereignExecutionError as exc:
                        reasons.append(str(exc))

        if policy and policy.get("external_idempotency"):
            if request.idempotency_key == "NONE" and request.compensation_reference == "NONE":
                reasons.append("EXTERNAL_EFFECT_REQUIRES_IDEMPOTENCY_OR_COMPENSATION")

        approval_grant_root = ZERO_HASH
        if approval is not None:
            try:
                approval_grant_root = approval.root
            except SovereignExecutionError:
                approval_grant_root = ZERO_HASH
        reasons = sorted(set(reasons))
        outcome = ADMITTED if not reasons else DENIED
        if outcome == DENIED:
            score_micros = 0
        body = {
            "schema_version": SCHEMA_VERSION,
            "outcome": outcome,
            "authority_score": f"{score_micros / 1_000_000:.6f}",
            "action_class": request.action_class if request.action_class in ACTION_CLASSES else D0,
            "authority_domain": request.authority_domain if isinstance(request.authority_domain, str) and SAFE_ID_RE.fullmatch(request.authority_domain) else "INVALID",
            "requested_capability": request.requested_capability if isinstance(request.requested_capability, str) and SAFE_ID_RE.fullmatch(request.requested_capability) else "INVALID",
            "tool": request.tool if isinstance(request.tool, str) and SAFE_ID_RE.fullmatch(request.tool) else "INVALID",
            "target_digest": canonical_hash("AEGIS_AUTHORITY_TARGET_V1", request.target),
            "identity_root": request.identity_root,
            "workspace_binding": request.workspace_binding,
            "registry_root": request.registry_root,
            "policy_root": request.policy_root,
            "approval_grant_root": approval_grant_root,
            "denial_codes": tuple(reasons),
        }
        root = canonical_hash("AEGIS_POLICY_DECISION_V1", body)
        decision = PolicyDecision(**body, decision_root=root)
        decision.validate()
        with self._lock:
            self._issued_decision_roots.add(decision.decision_root)
        return decision

    def verify_issued_decision(self, decision: PolicyDecision) -> None:
        decision.validate()
        with self._lock:
            if decision.decision_root not in self._issued_decision_roots:
                raise SovereignExecutionError("POLICY_DECISION_NOT_ISSUED")


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
    holder_identity_root: str
    lease_generation: int
    fencing_token_digest: str
    expected_parent_state: str
    action_digest: str
    denial_codes: tuple[str, ...]
    receipt_root: str

    def validate(self) -> None:
        if self.operation not in ("ACQUIRE", "AUTHORIZE_WRITE", "ADVANCE", "REVOKE"):
            raise SovereignExecutionError("LEASE_RECEIPT_OPERATION_INVALID")
        if self.outcome not in (ADMITTED, DENIED):
            raise SovereignExecutionError("LEASE_RECEIPT_OUTCOME_INVALID")
        _assert_authority_string("authority_domain", self.authority_domain)
        for name in ("holder_identity_root", "fencing_token_digest", "expected_parent_state", "action_digest"):
            _assert_hash(name, getattr(self, name))
        if isinstance(self.lease_generation, bool) or not isinstance(self.lease_generation, int) or self.lease_generation < 0:
            raise SovereignExecutionError("LEASE_RECEIPT_GENERATION_INVALID")
        if tuple(sorted(set(self.denial_codes))) != self.denial_codes:
            raise SovereignExecutionError("LEASE_RECEIPT_DENIAL_CODES_NONCANONICAL")
        if self.outcome == ADMITTED and self.denial_codes:
            raise SovereignExecutionError("ADMITTED_LEASE_RECEIPT_HAS_DENIAL_CODES")
        if self.outcome == DENIED and not self.denial_codes:
            raise SovereignExecutionError("DENIED_LEASE_RECEIPT_REQUIRES_CODE")
        body = asdict(self)
        root = body.pop("receipt_root")
        if root != canonical_hash("AEGIS_LEASE_RECEIPT_V1", body):
            raise SovereignExecutionError("LEASE_RECEIPT_ROOT_MISMATCH")


class WriterLeaseManager:
    def __init__(self) -> None:
        self._leases: dict[str, WriterLease] = {}
        self._generation: dict[str, int] = {}
        self._authorized_actions: dict[tuple[str, int, str], LeaseReceipt] = {}
        self._issued_receipt_roots: set[str] = set()
        self._consumed_authorization_receipts: set[str] = set()
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
            receipt = self._lease_receipt("ACQUIRE", authority_domain, holder_identity_root, generation, token, expected_parent_state, ZERO_HASH, reasons)
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
            cached = self._authorized_actions.get(key)
            if cached is not None and not reasons:
                return cached
            receipt = self._lease_receipt("AUTHORIZE_WRITE", authority_domain, holder_identity_root, lease_generation, fencing_token, expected_parent_state, action_digest, reasons)
            if receipt.outcome == ADMITTED:
                self._authorized_actions[key] = receipt
            return receipt

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
            holder = lease.holder_identity_root if lease else ZERO_HASH
            return self._lease_receipt("ADVANCE", authority_domain, holder, generation, fencing_token, new_parent_state, ZERO_HASH, reasons)

    def revoke(self, authority_domain: str, holder_identity_root: str) -> LeaseReceipt:
        with self._lock:
            reasons: list[str] = []
            lease = self._leases.get(authority_domain)
            if lease is None: reasons.append("LEASE_MISSING")
            elif lease.holder_identity_root != holder_identity_root: reasons.append("LEASE_HOLDER_MISMATCH")
            generation = lease.lease_generation if lease else self._generation.get(authority_domain, 0)
            token = lease.fencing_token if lease else ZERO_HASH
            if not reasons: del self._leases[authority_domain]
            parent = lease.expected_parent_state if lease else ZERO_HASH
            return self._lease_receipt("REVOKE", authority_domain, holder_identity_root, generation, token, parent, ZERO_HASH, reasons)

    def current(self, authority_domain: str) -> WriterLease | None:
        with self._lock:
            return self._leases.get(authority_domain)

    def verify_issued_receipt(self, receipt: LeaseReceipt) -> None:
        receipt.validate()
        with self._lock:
            if receipt.receipt_root not in self._issued_receipt_roots:
                raise SovereignExecutionError("LEASE_RECEIPT_NOT_ISSUED")

    def consume_authorization(self, receipt: LeaseReceipt) -> None:
        with self._lock:
            self.verify_issued_receipt(receipt)
            if receipt.operation != "AUTHORIZE_WRITE" or receipt.outcome != ADMITTED:
                raise SovereignExecutionError("LEASE_AUTHORIZATION_NOT_ADMITTED")
            if receipt.receipt_root in self._consumed_authorization_receipts:
                raise SovereignExecutionError("LEASE_AUTHORIZATION_ALREADY_CONSUMED")
            lease = self._leases.get(receipt.authority_domain)
            if lease is None:
                raise SovereignExecutionError("LEASE_NO_LONGER_CURRENT")
            bindings = (
                (lease.holder_identity_root, receipt.holder_identity_root, "LEASE_CURRENT_HOLDER_MISMATCH"),
                (lease.lease_generation, receipt.lease_generation, "LEASE_CURRENT_GENERATION_MISMATCH"),
                (lease.expected_parent_state, receipt.expected_parent_state, "LEASE_CURRENT_PARENT_MISMATCH"),
                (canonical_hash("AEGIS_FENCE_TOKEN_REDACTION_V1", lease.fencing_token), receipt.fencing_token_digest, "LEASE_CURRENT_FENCE_MISMATCH"),
            )
            for actual, expected, code in bindings:
                if actual != expected:
                    raise SovereignExecutionError(code)
            self._consumed_authorization_receipts.add(receipt.receipt_root)

    def _lease_receipt(self, operation: str, domain: str, holder_identity_root: str, generation: int, token: str, expected_parent_state: str, action_digest: str, reasons: Sequence[str]) -> LeaseReceipt:
        safe_hash = lambda value: value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) else ZERO_HASH
        body = {"operation": operation, "outcome": ADMITTED if not reasons else DENIED, "authority_domain": domain, "holder_identity_root": safe_hash(holder_identity_root), "lease_generation": generation, "fencing_token_digest": canonical_hash("AEGIS_FENCE_TOKEN_REDACTION_V1", token), "expected_parent_state": safe_hash(expected_parent_state), "action_digest": safe_hash(action_digest), "denial_codes": tuple(sorted(set(reasons)))}
        receipt = LeaseReceipt(**body, receipt_root=canonical_hash("AEGIS_LEASE_RECEIPT_V1", body))
        receipt.validate()
        self._issued_receipt_roots.add(receipt.receipt_root)
        return receipt


DURABLE_STATUSES = ("PLANNED", "ADMITTED", "RUNNING", "WAITING_FOR_APPROVAL", "BLOCKED", "RETRYING", "DENIED", "FAILED", "COMPLETED", "CANCELLED", "ORPHANED")
DURABLE_TERMINAL_STATUSES = frozenset(("DENIED", "FAILED", "COMPLETED", "CANCELLED", "ORPHANED"))
# In-process capability held only by the terminal receipt factory. Public
# registry transitions can never manufacture a terminal commit by supplying a
# boolean escape hatch or an arbitrary receipt hash.
_TERMINAL_COMMIT_CAPABILITY = object()
DURABLE_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "PLANNED": frozenset(("ADMITTED", "DENIED", "CANCELLED")),
    "ADMITTED": frozenset(("RUNNING", "DENIED", "CANCELLED")),
    "RUNNING": frozenset(("WAITING_FOR_APPROVAL", "BLOCKED", "RETRYING", "DENIED", "FAILED", "COMPLETED", "CANCELLED")),
    "WAITING_FOR_APPROVAL": frozenset(("RUNNING", "DENIED", "CANCELLED")),
    "BLOCKED": frozenset(("RUNNING", "DENIED", "FAILED", "CANCELLED")),
    "RETRYING": frozenset(("RUNNING", "FAILED", "COMPLETED", "CANCELLED")),
}

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


def durable_execution_record_root(record: DurableExecutionRecord) -> str:
    for name in ("workflow_identity", "owner", "current_phase", "cancellation_state"):
        _assert_authority_string(name, getattr(record, name))
    _assert_git("source_commit", record.source_commit)
    for name in ("workspace_binding", "lease_holder", "parent_state_root", "current_receipt_root"):
        _assert_hash(name, getattr(record, name))
    if record.status not in DURABLE_STATUSES:
        raise SovereignExecutionError("DURABLE_STATUS_INVALID")
    for name in ("last_completed_transition", "retry_count", "last_heartbeat_generation"):
        value = getattr(record, name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise SovereignExecutionError(f"DURABLE_INTEGER_INVALID:{name}")
    if record.next_retry is not None and (
        isinstance(record.next_retry, bool) or not isinstance(record.next_retry, int) or record.next_retry < 0
    ):
        raise SovereignExecutionError("DURABLE_INTEGER_INVALID:next_retry")
    if tuple(sorted(set(record.current_authority))) != record.current_authority:
        raise SovereignExecutionError("DURABLE_AUTHORITY_NONCANONICAL")
    for value in (*record.current_authority, *record.used_external_actions):
        _assert_authority_string("durable_authority_or_action", value)
    for name in ("pending_external_action", "failure_state"):
        value = getattr(record, name)
        if value:
            _assert_authority_string(name, value)
    body = asdict(record)
    body["used_external_actions"] = sorted(record.used_external_actions)
    return canonical_hash("AEGIS_DURABLE_EXECUTION_V1", body)


class DurableExecutionRegistry:
    def __init__(self, lease_manager: WriterLeaseManager):
        self._records: dict[str, DurableExecutionRecord] = {}
        self._leases = lease_manager
        self._lock = threading.RLock()

    def register(self, execution_id: str, record: DurableExecutionRecord) -> str:
        with self._lock:
            if execution_id in self._records: raise SovereignExecutionError("DURABLE_EXECUTION_ALREADY_REGISTERED")
            durable_execution_record_root(record)
            if record.status != "PLANNED": raise SovereignExecutionError("DURABLE_MUST_REGISTER_AS_PLANNED")
            self._records[execution_id] = copy.deepcopy(record)
            return self.root(execution_id)

    def transition(self, execution_id: str, *, status: str, phase: str, transition_sequence: int, receipt_root: str) -> str:
        with self._lock:
            record = self._require(execution_id)
            if record.status in DURABLE_TERMINAL_STATUSES: raise SovereignExecutionError("DURABLE_TERMINAL_STATE")
            if status not in DURABLE_STATUSES: raise SovereignExecutionError("DURABLE_STATUS_INVALID")
            if status in DURABLE_TERMINAL_STATUSES: raise SovereignExecutionError("DURABLE_TERMINAL_COMMIT_REQUIRED")
            if status not in DURABLE_TRANSITIONS.get(record.status, frozenset()): raise SovereignExecutionError("DURABLE_TRANSITION_INVALID")
            if transition_sequence != record.last_completed_transition + 1: raise SovereignExecutionError("DURABLE_SEQUENCE_INVALID")
            _assert_hash("receipt_root", receipt_root)
            _assert_authority_string("phase", phase)
            record.status, record.current_phase = status, phase
            record.last_completed_transition = transition_sequence
            record.current_receipt_root = receipt_root
            return self.root(execution_id)

    def heartbeat(self, execution_id: str, generation: int) -> str:
        with self._lock:
            record = self._require(execution_id)
            if generation <= record.last_heartbeat_generation: raise SovereignExecutionError("HEARTBEAT_NOT_MONOTONE")
            record.last_heartbeat_generation = generation
            return self.root(execution_id)

    def _commit_terminal_transition(
        self,
        execution_id: str,
        *,
        status: str,
        phase: str,
        transition_sequence: int,
        receipt: Any,
        commit_capability: object,
    ) -> str:
        if commit_capability is not _TERMINAL_COMMIT_CAPABILITY:
            raise SovereignExecutionError("DURABLE_TERMINAL_COMMIT_CAPABILITY_INVALID")
        # MutationReceipt is defined later in this module. The lookup occurs
        # when the method executes, after module initialization is complete.
        if not isinstance(receipt, MutationReceipt):
            raise SovereignExecutionError("DURABLE_TERMINAL_RECEIPT_INVALID")
        if status not in DURABLE_TERMINAL_STATUSES:
            raise SovereignExecutionError("DURABLE_TERMINAL_STATUS_REQUIRED")
        with self._lock:
            record = self._require(execution_id)
            if record.status in DURABLE_TERMINAL_STATUSES:
                raise SovereignExecutionError("DURABLE_TERMINAL_STATE")
            if status not in DURABLE_TRANSITIONS.get(record.status, frozenset()):
                raise SovereignExecutionError("DURABLE_TRANSITION_INVALID")
            if transition_sequence != record.last_completed_transition + 1:
                raise SovereignExecutionError("DURABLE_SEQUENCE_INVALID")
            _assert_authority_string("phase", phase)
            receipt.validate()
            record.status = status
            record.current_phase = phase
            record.last_completed_transition = transition_sequence
            record.current_receipt_root = receipt.root
            record.current_authority = ()
            return self.root(execution_id)

    def mark_orphaned(self, execution_id: str, current_generation: int, maximum_gap: int) -> str:
        with self._lock, self._leases._lock:
            record = self._require(execution_id)
            if record.status in DURABLE_TERMINAL_STATUSES: raise SovereignExecutionError("DURABLE_TERMINAL_STATE")
            if current_generation - record.last_heartbeat_generation <= maximum_gap: raise SovereignExecutionError("ORPHAN_THRESHOLD_NOT_REACHED")
            held = record.current_authority
            if record.lease_holder:
                for domain in held:
                    lease = self._leases.current(domain)
                    if lease is None or lease.holder_identity_root != record.lease_holder:
                        raise SovereignExecutionError("DURABLE_LEASE_STATE_DIVERGED")
                for domain in held:
                    receipt = self._leases.revoke(domain, record.lease_holder)
                    if receipt.outcome != ADMITTED:
                        raise SovereignExecutionError("DURABLE_LEASE_REVOCATION_FAILED")
            record.status = "ORPHANED"; record.current_authority = ()
            return self.root(execution_id)

    def cancel(self, execution_id: str) -> str:
        with self._lock, self._leases._lock:
            record = self._require(execution_id)
            if record.status in DURABLE_TERMINAL_STATUSES: raise SovereignExecutionError("DURABLE_TERMINAL_STATE")
            held = record.current_authority
            for domain in held:
                lease = self._leases.current(domain)
                if lease is None or lease.holder_identity_root != record.lease_holder:
                    raise SovereignExecutionError("DURABLE_LEASE_STATE_DIVERGED")
            for domain in held:
                receipt = self._leases.revoke(domain, record.lease_holder)
                if receipt.outcome != ADMITTED:
                    raise SovereignExecutionError("DURABLE_LEASE_REVOCATION_FAILED")
            record.status = "CANCELLED"; record.cancellation_state = "REVOKED"; record.current_authority = ()
            return self.root(execution_id)

    def claim_external_action(self, execution_id: str, idempotency_key: str) -> str:
        with self._lock:
            record = self._require(execution_id)
            if record.status not in ("RUNNING", "RETRYING"): raise SovereignExecutionError("DURABLE_NOT_RUNNING")
            if idempotency_key in record.used_external_actions: raise SovereignExecutionError("DUPLICATE_EXTERNAL_ACTION")
            _assert_authority_string("idempotency_key", idempotency_key)
            record.used_external_actions.add(idempotency_key)
            record.pending_external_action = idempotency_key
            return self.root(execution_id)

    def get(self, execution_id: str) -> DurableExecutionRecord:
        with self._lock:
            return copy.deepcopy(self._require(execution_id))

    def root(self, execution_id: str) -> str:
        with self._lock:
            return durable_execution_record_root(self._require(execution_id))

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
class AuthorityDecisionReceipt:
    receipt_version: str
    issuer_key_id: str
    execution_identity_root: str
    source_commit: str
    workspace_binding: str
    expected_pre_state: str
    skills_root: str
    policy_decision_root: str
    policy_root: str
    registry_root: str
    approval_grant_root: str
    authority_score: str
    authority_domain: str
    action_class: str
    requested_capability: str
    tool: str
    target: str
    requested_action_digest: str
    outcome: str
    denial_codes: tuple[str, ...]
    signature: str

    def signing_body(self) -> dict[str, Any]:
        body = asdict(self)
        body.pop("signature")
        return body

    def validate(self) -> None:
        if self.receipt_version != SCHEMA_VERSION: raise SovereignExecutionError("AUTHORITY_RECEIPT_SCHEMA_UNSUPPORTED")
        _assert_git("source_commit", self.source_commit)
        for name in ("execution_identity_root", "workspace_binding", "expected_pre_state", "skills_root", "policy_decision_root", "policy_root", "registry_root", "approval_grant_root", "target", "requested_action_digest"):
            _assert_hash(name, getattr(self, name))
        if self.outcome not in (ADMITTED, DENIED): raise SovereignExecutionError("AUTHORITY_RECEIPT_OUTCOME_INVALID")
        if self.action_class not in ACTION_CLASSES: raise SovereignExecutionError("AUTHORITY_RECEIPT_ACTION_CLASS_INVALID")
        for name in ("issuer_key_id", "authority_domain", "requested_capability", "tool"):
            _assert_authority_string(name, getattr(self, name))
        if not re.fullmatch(r"[0-9a-f]{128}", self.signature):
            raise SovereignExecutionError("AUTHORITY_RECEIPT_SIGNATURE_INVALID")
        if not re.fullmatch(r"(?:0\.[0-9]{6}|1\.000000)", self.authority_score):
            raise SovereignExecutionError("AUTHORITY_RECEIPT_SCORE_INVALID")
        if tuple(sorted(set(self.denial_codes))) != self.denial_codes:
            raise SovereignExecutionError("AUTHORITY_RECEIPT_DENIAL_CODES_NONCANONICAL")
        if self.outcome == ADMITTED and self.denial_codes:
            raise SovereignExecutionError("ADMITTED_AUTHORITY_RECEIPT_HAS_DENIAL_CODES")
        if self.outcome == DENIED and not self.denial_codes:
            raise SovereignExecutionError("DENIED_AUTHORITY_RECEIPT_REQUIRES_CODE")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_AUTHORITY_DECISION_RECEIPT_V1", asdict(self))

    def verify_signature(self, trusted_authority_keys: Mapping[str, str]) -> None:
        self.validate()
        public_key = trusted_authority_keys.get(self.issuer_key_id)
        if public_key is None:
            raise SovereignExecutionError("AUTHORITY_RECEIPT_ISSUER_UNTRUSTED")
        _ed25519_verify(
            public_key_hex=public_key,
            signature_hex=self.signature,
            domain="AEGIS_AUTHORITY_DECISION_RECEIPT_V1",
            value=self.signing_body(),
            invalid_code="AUTHORITY_RECEIPT_SIGNATURE_INVALID",
        )


@dataclass(frozen=True)
class MutationReceipt:
    receipt_version: str
    execution_identity_root: str
    workspace_binding: str
    policy_decision_root: str
    authority_receipt_root: str
    lease_authorization_receipt_root: str
    durable_execution_root: str
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
        for name in ("execution_identity_root", "workspace_binding", "policy_decision_root", "authority_receipt_root", "lease_authorization_receipt_root", "durable_execution_root", "pre_state_digest", "requested_action_digest", "result_digest", "post_state_digest", "parent_receipt"):
            _assert_hash(name, getattr(self, name))
        if self.action_class not in ACTION_CLASSES: raise SovereignExecutionError("RECEIPT_ACTION_CLASS_INVALID")
        for name in ("authority_domain", "tool"):
            _assert_authority_string(name, getattr(self, name))
        if not re.fullmatch(r"(?:0\.[0-9]{6}|1\.000000)", self.authority_score):
            raise SovereignExecutionError("RECEIPT_AUTHORITY_SCORE_INVALID")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise SovereignExecutionError("RECEIPT_SEQUENCE_INVALID")
        if self.outcome not in ("SUCCEEDED", "DENIED", "FAILED", "ROLLED_BACK"): raise SovereignExecutionError("RECEIPT_OUTCOME_INVALID")
        _assert_authority_string("denial_code", self.denial_code)
        if self.outcome in ("DENIED", "FAILED", "ROLLED_BACK") and self.denial_code == "NONE":
            raise SovereignExecutionError("TERMINAL_OUTCOME_CODE_REQUIRED")
        if self.outcome == "SUCCEEDED" and self.denial_code != "NONE":
            raise SovereignExecutionError("SUCCESS_RECEIPT_HAS_OUTCOME_CODE")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_MUTATION_RECEIPT_V1", deterministic_redaction(asdict(self)))


class ReceiptChain:
    def __init__(self) -> None:
        self._receipts: list[MutationReceipt] = []
        self._lock = threading.RLock()

    def next_link(self) -> tuple[str, int]:
        with self._lock:
            return (self._receipts[-1].root if self._receipts else ZERO_HASH, len(self._receipts))

    def append(self, receipt: MutationReceipt) -> str:
        with self._lock:
            receipt.validate()
            expected_sequence = len(self._receipts)
            expected_parent = self._receipts[-1].root if self._receipts else ZERO_HASH
            if receipt.sequence != expected_sequence: raise SovereignExecutionError("RECEIPT_CHAIN_SEQUENCE_BREAK")
            if receipt.parent_receipt != expected_parent: raise SovereignExecutionError("RECEIPT_CHAIN_PARENT_BREAK")
            self._receipts.append(receipt)
            return receipt.root

    def verify(self) -> str:
        with self._lock:
            previous = ZERO_HASH
            for index, receipt in enumerate(self._receipts):
                if receipt.sequence != index or receipt.parent_receipt != previous: raise SovereignExecutionError("RECEIPT_CHAIN_BROKEN")
                previous = receipt.root
            return previous


def _parse_policy(raw: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    if raw.get("schema_version") != SCHEMA_VERSION or raw.get("classes") is None:
        raise SovereignExecutionError("POLICY_INVALID")
    if set(raw) != {"schema_version", "classes"}:
        raise SovereignExecutionError("POLICY_SCHEMA_DRIFT")
    policy = validate_consequence_policy(raw["classes"])
    return policy, canonical_hash("AEGIS_CONSEQUENCE_POLICY_V1", policy)


def load_policy(path: str | Path) -> tuple[dict[str, Any], str]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SovereignExecutionError("POLICY_INVALID")
    return _parse_policy(raw)


def _repository_blob_path(path: str) -> str:
    if not isinstance(path, str) or not path or "\\" in path or ":" in path or "\x00" in path:
        raise SovereignExecutionError("REPOSITORY_BLOB_PATH_INVALID")
    try:
        _assert_authority_string("repository_blob_path", path)
    except SovereignExecutionError as exc:
        raise SovereignExecutionError("REPOSITORY_BLOB_PATH_INVALID") from exc
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or any(part in ("", ".", "..") for part in parsed.parts):
        raise SovereignExecutionError("REPOSITORY_BLOB_PATH_INVALID")
    rendered = parsed.as_posix()
    if rendered != path:
        raise SovereignExecutionError("REPOSITORY_BLOB_PATH_NONCANONICAL")
    return rendered


def git_show_json(repository_root: str | Path, source_commit: str, repository_path: str) -> dict[str, Any]:
    root = Path(repository_root).resolve(strict=True)
    _assert_git("source_commit", source_commit)
    path = _repository_blob_path(repository_path)
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "show", f"{source_commit}:{path}"],
            check=True,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise SovereignExecutionError(f"COMMIT_BOUND_BLOB_UNAVAILABLE:{path}") from exc
    try:
        raw = json.loads(result.stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SovereignExecutionError(f"COMMIT_BOUND_JSON_INVALID:{path}") from exc
    if not isinstance(raw, dict):
        raise SovereignExecutionError(f"COMMIT_BOUND_JSON_INVALID:{path}")
    return raw


def git_blob_exists(repository_root: str | Path, source_commit: str, repository_path: str) -> bool:
    root = Path(repository_root).resolve(strict=True)
    _assert_git("source_commit", source_commit)
    path = _repository_blob_path(repository_path)
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f"{source_commit}:{path}"],
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def load_policy_from_commit(*, repository_root: str | Path, source_commit: str, policy_path: str) -> tuple[dict[str, Any], str]:
    return _parse_policy(git_show_json(repository_root, source_commit, policy_path))


def git_remote(root: str | Path) -> str:
    try:
        result = subprocess.run(["git", "-C", str(root), "config", "--get", "remote.origin.url"], check=True, text=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SovereignExecutionError("REMOTE_ORIGIN_UNAVAILABLE") from exc
    return canonical_remote(result.stdout.strip())


def git_head(root: str | Path) -> str:
    try:
        result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, text=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SovereignExecutionError("SOURCE_COMMIT_UNAVAILABLE") from exc
    head = result.stdout.strip()
    _assert_git("source_commit", head)
    return head


def decision_dict(decision: PolicyDecision) -> dict[str, Any]:
    return asdict(decision)


def compute_skill_registry_root(tree: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(tree))
    payload.pop("registry_root", None)
    payload.pop("genesis_seal", None)
    return sha256_hex(canonical_bytes({"domain": "AEGIS_SKILL_REGISTRY_V2", "registry": payload}))


def compute_capability_registry_root(*, skills_root: str, capability_map: Mapping[str, Any]) -> str:
    _assert_hash("skills_root", skills_root)
    if not isinstance(capability_map, Mapping):
        raise SovereignExecutionError("CAPABILITY_MAP_INVALID")
    return canonical_hash(
        "AEGIS_CAPABILITY_REGISTRY_V1",
        {
            "skills_root": skills_root,
            "capability_map": copy.deepcopy(dict(capability_map)),
        },
    )


def _build_capability_registry(*, repository_root: str | Path, tree: Mapping[str, Any], mapping: Mapping[str, Any]) -> tuple[dict[str, CapabilityEvidence], str, str]:
    root = Path(repository_root).resolve(strict=True)
    if not isinstance(tree, Mapping) or not isinstance(mapping, Mapping):
        raise SovereignExecutionError("CAPABILITY_REGISTRY_INVALID")
    skills_root = compute_skill_registry_root(tree)
    if tree.get("registry_root") != skills_root or tree.get("genesis_seal") != skills_root:
        raise SovereignExecutionError("SKILL_REGISTRY_ROOT_MISMATCH")
    if mapping.get("schema_version") != SCHEMA_VERSION or not isinstance(mapping.get("capabilities"), dict):
        raise SovereignExecutionError("CAPABILITY_MAP_INVALID")
    skills = {item.get("skill_id"): item for item in tree.get("skills", []) if isinstance(item, dict) and isinstance(item.get("skill_id"), str)}
    registry: dict[str, CapabilityEvidence] = {}
    for capability, config in mapping["capabilities"].items():
        try:
            _assert_authority_string("capability", capability)
        except SovereignExecutionError as exc:
            raise SovereignExecutionError("CAPABILITY_MAP_CAPABILITY_INVALID") from exc
        if not isinstance(config, dict) or set(config) != {"skill_id", "allowed_action_classes", "allowed_tools"}:
            raise SovereignExecutionError("CAPABILITY_MAP_RECORD_INVALID")
        skill_id = config.get("skill_id")
        try:
            _assert_authority_string("skill_id", skill_id)
        except SovereignExecutionError as exc:
            raise SovereignExecutionError("CAPABILITY_MAP_SKILL_ID_INVALID") from exc
        skill = skills.get(skill_id)
        if skill is None:
            raise SovereignExecutionError("CAPABILITY_MAP_SKILL_UNRESOLVED")
        allowed_action_classes = config.get("allowed_action_classes")
        allowed_tools = config.get("allowed_tools")
        if (
            not isinstance(allowed_action_classes, list)
            or not allowed_action_classes
            or any(item not in ACTION_CLASSES for item in allowed_action_classes)
            or len(set(allowed_action_classes)) != len(allowed_action_classes)
        ):
            raise SovereignExecutionError("CAPABILITY_MAP_ACTION_CLASSES_INVALID")
        if not isinstance(allowed_tools, list) or not allowed_tools or len(set(allowed_tools)) != len(allowed_tools):
            raise SovereignExecutionError("CAPABILITY_MAP_TOOLS_INVALID")
        try:
            for tool in allowed_tools:
                _assert_authority_string("allowed_tool", tool)
        except SovereignExecutionError as exc:
            raise SovereignExecutionError("CAPABILITY_MAP_TOOLS_INVALID") from exc
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
            allowed_action_classes=tuple(allowed_action_classes),
            allowed_tools=tuple(allowed_tools),
        )
    registry_root = compute_capability_registry_root(skills_root=skills_root, capability_map=mapping)
    return registry, skills_root, registry_root


def load_capability_registry(*, repository_root: str | Path, skill_tree_path: str | Path, capability_map_path: str | Path) -> tuple[dict[str, CapabilityEvidence], str, str]:
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
    return _build_capability_registry(repository_root=root, tree=tree, mapping=mapping)


def load_capability_registry_from_commit(
    *,
    repository_root: str | Path,
    source_commit: str,
    skill_tree_path: str,
    capability_map_path: str,
) -> tuple[dict[str, CapabilityEvidence], str, str]:
    tree = git_show_json(repository_root, source_commit, skill_tree_path)
    mapping = git_show_json(repository_root, source_commit, capability_map_path)
    return _build_capability_registry(repository_root=repository_root, tree=tree, mapping=mapping)


def verify_live_authority_roots(
    identity: ExecutionIdentityEnvelope,
    *,
    skills_root: str,
    registry_root: str,
    policy_root: str,
) -> None:
    identity.validate()
    for name, value in (("skills_root", skills_root), ("registry_root", registry_root), ("policy_root", policy_root)):
        _assert_hash(name, value)
    if identity.skills_root != skills_root:
        raise SovereignExecutionError("SKILLS_ROOT_MISMATCH")
    if identity.registry_root != registry_root:
        raise SovereignExecutionError("CAPABILITY_REGISTRY_ROOT_MISMATCH")
    if identity.policy_root != policy_root:
        raise SovereignExecutionError("POLICY_ROOT_MISMATCH")


def make_authority_decision_receipt(*, identity: ExecutionIdentityEnvelope, request: AuthorityRequest, decision: PolicyDecision, evaluator: AuthorityEvaluator, issuer_key_id: str, issuer_private_key_hex: str) -> AuthorityDecisionReceipt:
    evaluator.verify_issued_decision(decision)
    identity_root = identity.root
    expected_target = canonical_hash("AEGIS_AUTHORITY_TARGET_V1", request.target)
    bindings = (
        (request.identity_root, identity_root, "AUTHORITY_REQUEST_IDENTITY_MISMATCH"),
        (request.workspace_binding, identity.workspace_binding, "AUTHORITY_REQUEST_WORKSPACE_MISMATCH"),
        (request.source_commit, identity.source_commit, "AUTHORITY_REQUEST_SOURCE_COMMIT_MISMATCH"),
        (request.registry_root, identity.registry_root, "AUTHORITY_REQUEST_REGISTRY_MISMATCH"),
        (request.policy_root, identity.policy_root, "AUTHORITY_REQUEST_POLICY_MISMATCH"),
        (request.action_digest, identity.action_digest, "AUTHORITY_REQUEST_ACTION_MISMATCH"),
        (request.expected_pre_state, identity.expected_pre_state, "AUTHORITY_REQUEST_PRE_STATE_MISMATCH"),
        (request.authority_domain, identity.authority_domain, "AUTHORITY_REQUEST_DOMAIN_MISMATCH"),
        (request.requested_capability, identity.requested_capability, "AUTHORITY_REQUEST_CAPABILITY_MISMATCH"),
        (request.tool, identity.tool_identity, "AUTHORITY_REQUEST_TOOL_MISMATCH"),
        (decision.identity_root, identity_root, "AUTHORITY_DECISION_IDENTITY_MISMATCH"),
        (decision.workspace_binding, identity.workspace_binding, "AUTHORITY_DECISION_WORKSPACE_MISMATCH"),
        (decision.registry_root, identity.registry_root, "AUTHORITY_DECISION_REGISTRY_MISMATCH"),
        (decision.policy_root, identity.policy_root, "AUTHORITY_DECISION_POLICY_MISMATCH"),
        (decision.action_class, request.action_class, "AUTHORITY_DECISION_ACTION_CLASS_MISMATCH"),
        (decision.authority_domain, request.authority_domain, "AUTHORITY_DECISION_DOMAIN_MISMATCH"),
        (decision.requested_capability, request.requested_capability, "AUTHORITY_DECISION_CAPABILITY_MISMATCH"),
        (decision.tool, request.tool, "AUTHORITY_DECISION_TOOL_MISMATCH"),
        (decision.target_digest, expected_target, "AUTHORITY_DECISION_TARGET_MISMATCH"),
    )
    for actual, expected, code in bindings:
        if actual != expected:
            raise SovereignExecutionError(code)
    unsigned = {
        "receipt_version": SCHEMA_VERSION,
        "issuer_key_id": issuer_key_id,
        "execution_identity_root": identity_root,
        "source_commit": identity.source_commit,
        "workspace_binding": identity.workspace_binding,
        "expected_pre_state": identity.expected_pre_state,
        "skills_root": identity.skills_root,
        "policy_decision_root": decision.decision_root,
        "policy_root": decision.policy_root,
        "registry_root": decision.registry_root,
        "approval_grant_root": decision.approval_grant_root,
        "authority_score": decision.authority_score,
        "authority_domain": decision.authority_domain,
        "action_class": decision.action_class,
        "requested_capability": decision.requested_capability,
        "tool": decision.tool,
        "target": decision.target_digest,
        "requested_action_digest": identity.action_digest,
        "outcome": decision.outcome,
        "denial_codes": tuple(decision.denial_codes),
    }
    signature = _ed25519_sign(
        private_key_hex=issuer_private_key_hex,
        domain="AEGIS_AUTHORITY_DECISION_RECEIPT_V1",
        value=unsigned,
    )
    receipt = AuthorityDecisionReceipt(**unsigned, signature=signature)
    receipt.validate()
    return receipt


def make_terminal_mutation_receipt(
    *,
    identity: ExecutionIdentityEnvelope,
    request: AuthorityRequest,
    decision: PolicyDecision,
    evaluator: AuthorityEvaluator,
    authority_receipt: AuthorityDecisionReceipt,
    trusted_authority_keys: Mapping[str, str],
    lease_manager: WriterLeaseManager,
    lease_authorization_receipt: LeaseReceipt,
    durable_registry: DurableExecutionRegistry,
    execution_id: str,
    receipt_chain: ReceiptChain,
    result: Any,
    post_state_digest: str,
    terminal_outcome: str,
    denial_code: str = "NONE",
) -> MutationReceipt:
    if decision.outcome != ADMITTED:
        raise SovereignExecutionError("TERMINAL_RECEIPT_REQUIRES_ADMITTED_AUTHORITY")
    if terminal_outcome not in ("SUCCEEDED", "DENIED", "FAILED", "ROLLED_BACK"):
        raise SovereignExecutionError("TERMINAL_RECEIPT_OUTCOME_INVALID")
    evaluator.verify_issued_decision(decision)
    identity_root = identity.root
    request_bindings = (
        (request.identity_root, identity_root, "TERMINAL_REQUEST_IDENTITY_MISMATCH"),
        (request.workspace_binding, identity.workspace_binding, "TERMINAL_REQUEST_WORKSPACE_MISMATCH"),
        (request.source_commit, identity.source_commit, "TERMINAL_REQUEST_SOURCE_COMMIT_MISMATCH"),
        (request.registry_root, identity.registry_root, "TERMINAL_REQUEST_REGISTRY_MISMATCH"),
        (request.policy_root, identity.policy_root, "TERMINAL_REQUEST_POLICY_MISMATCH"),
        (request.action_digest, identity.action_digest, "TERMINAL_REQUEST_ACTION_MISMATCH"),
        (request.expected_pre_state, identity.expected_pre_state, "TERMINAL_REQUEST_PRE_STATE_MISMATCH"),
        (request.authority_domain, identity.authority_domain, "TERMINAL_REQUEST_DOMAIN_MISMATCH"),
        (request.requested_capability, identity.requested_capability, "TERMINAL_REQUEST_CAPABILITY_MISMATCH"),
        (request.tool, identity.tool_identity, "TERMINAL_REQUEST_TOOL_MISMATCH"),
    )
    for actual, expected, code in request_bindings:
        if actual != expected:
            raise SovereignExecutionError(code)
    authority_receipt.verify_signature(trusted_authority_keys)
    lease_manager.verify_issued_receipt(lease_authorization_receipt)
    if authority_receipt.outcome != ADMITTED:
        raise SovereignExecutionError("TERMINAL_RECEIPT_REQUIRES_ADMITTED_AUTHORITY_RECEIPT")
    authority_bindings = (
        (authority_receipt.policy_decision_root, decision.decision_root, "TERMINAL_AUTHORITY_DECISION_MISMATCH"),
        (authority_receipt.execution_identity_root, decision.identity_root, "TERMINAL_AUTHORITY_IDENTITY_MISMATCH"),
        (authority_receipt.source_commit, identity.source_commit, "TERMINAL_AUTHORITY_SOURCE_COMMIT_MISMATCH"),
        (authority_receipt.workspace_binding, decision.workspace_binding, "TERMINAL_AUTHORITY_WORKSPACE_MISMATCH"),
        (authority_receipt.expected_pre_state, identity.expected_pre_state, "TERMINAL_AUTHORITY_PRE_STATE_MISMATCH"),
        (authority_receipt.skills_root, identity.skills_root, "TERMINAL_AUTHORITY_SKILLS_ROOT_MISMATCH"),
        (authority_receipt.policy_root, decision.policy_root, "TERMINAL_AUTHORITY_POLICY_MISMATCH"),
        (authority_receipt.registry_root, decision.registry_root, "TERMINAL_AUTHORITY_REGISTRY_MISMATCH"),
        (authority_receipt.approval_grant_root, decision.approval_grant_root, "TERMINAL_AUTHORITY_APPROVAL_MISMATCH"),
        (authority_receipt.authority_score, decision.authority_score, "TERMINAL_AUTHORITY_SCORE_MISMATCH"),
        (authority_receipt.authority_domain, decision.authority_domain, "TERMINAL_AUTHORITY_DOMAIN_MISMATCH"),
        (authority_receipt.action_class, decision.action_class, "TERMINAL_AUTHORITY_ACTION_CLASS_MISMATCH"),
        (authority_receipt.requested_capability, decision.requested_capability, "TERMINAL_AUTHORITY_CAPABILITY_MISMATCH"),
        (authority_receipt.tool, decision.tool, "TERMINAL_AUTHORITY_TOOL_MISMATCH"),
        (authority_receipt.target, decision.target_digest, "TERMINAL_AUTHORITY_TARGET_MISMATCH"),
    )
    for actual, expected, code in authority_bindings:
        if actual != expected:
            raise SovereignExecutionError(code)
    lease_bindings = (
        (lease_authorization_receipt.operation, "AUTHORIZE_WRITE", "TERMINAL_LEASE_OPERATION_INVALID"),
        (lease_authorization_receipt.authority_domain, authority_receipt.authority_domain, "TERMINAL_LEASE_DOMAIN_MISMATCH"),
        (lease_authorization_receipt.holder_identity_root, authority_receipt.execution_identity_root, "TERMINAL_LEASE_HOLDER_MISMATCH"),
        (lease_authorization_receipt.expected_parent_state, identity.expected_pre_state, "TERMINAL_LEASE_PARENT_MISMATCH"),
        (lease_authorization_receipt.action_digest, authority_receipt.requested_action_digest, "TERMINAL_LEASE_ACTION_MISMATCH"),
    )
    for actual, expected, code in lease_bindings:
        if actual != expected:
            raise SovereignExecutionError(code)
    if lease_authorization_receipt.outcome != ADMITTED:
        raise SovereignExecutionError("TERMINAL_RECEIPT_REQUIRES_ADMITTED_LEASE")
    if terminal_outcome in ("DENIED", "FAILED", "ROLLED_BACK") and post_state_digest != identity.expected_pre_state:
        raise SovereignExecutionError("NON_SUCCESS_TERMINAL_STATE_CHANGED")
    expected_status = {
        "SUCCEEDED": "COMPLETED",
        "ROLLED_BACK": "COMPLETED",
        "DENIED": "DENIED",
        "FAILED": "FAILED",
    }[terminal_outcome]
    _assert_authority_string("execution_id", execution_id)
    _assert_hash("post_state_digest", post_state_digest)

    # The chain position, durable pre-commit record, terminal registry transition,
    # and append are one in-process critical section. No caller supplies roots.
    with lease_manager._lock, receipt_chain._lock, durable_registry._lock:
        durable_execution_record = durable_registry.get(execution_id)
        if terminal_outcome in ("SUCCEEDED", "FAILED", "ROLLED_BACK") and durable_execution_record.status not in ("RUNNING", "RETRYING"):
            raise SovereignExecutionError("TERMINAL_DURABLE_NOT_EXECUTING")
        if terminal_outcome == "DENIED" and durable_execution_record.status not in ("PLANNED", "ADMITTED", "RUNNING", "WAITING_FOR_APPROVAL", "BLOCKED"):
            raise SovereignExecutionError("TERMINAL_DURABLE_DENIAL_STATE_INVALID")
        if durable_execution_record.workspace_binding != authority_receipt.workspace_binding:
            raise SovereignExecutionError("TERMINAL_DURABLE_WORKSPACE_MISMATCH")
        if durable_execution_record.lease_holder != authority_receipt.execution_identity_root:
            raise SovereignExecutionError("TERMINAL_DURABLE_HOLDER_MISMATCH")
        if durable_execution_record.parent_state_root != identity.expected_pre_state:
            raise SovereignExecutionError("TERMINAL_DURABLE_PARENT_MISMATCH")
        if authority_receipt.authority_domain not in durable_execution_record.current_authority:
            raise SovereignExecutionError("TERMINAL_DURABLE_AUTHORITY_MISSING")
        durable_execution_root = durable_execution_record_root(durable_execution_record)
        parent_receipt, sequence = receipt_chain.next_link()
        receipt = MutationReceipt(
            receipt_version=SCHEMA_VERSION,
            execution_identity_root=authority_receipt.execution_identity_root,
            workspace_binding=authority_receipt.workspace_binding,
            policy_decision_root=decision.decision_root,
            authority_receipt_root=authority_receipt.root,
            lease_authorization_receipt_root=lease_authorization_receipt.receipt_root,
            durable_execution_root=durable_execution_root,
            authority_score=decision.authority_score,
            authority_domain=decision.authority_domain,
            action_class=decision.action_class,
            tool=decision.tool,
            target=decision.target_digest,
            pre_state_digest=identity.expected_pre_state,
            requested_action_digest=authority_receipt.requested_action_digest,
            result_digest=canonical_hash("AEGIS_ACTION_RESULT_V1", deterministic_redaction(result)),
            post_state_digest=post_state_digest,
            parent_receipt=parent_receipt,
            sequence=sequence,
            outcome=terminal_outcome,
            denial_code=denial_code,
        )
        receipt.validate()
        lease_manager.consume_authorization(lease_authorization_receipt)
        advance_receipt = lease_manager.advance(
            authority_domain=authority_receipt.authority_domain,
            fencing_token=lease_manager.current(authority_receipt.authority_domain).fencing_token,
            new_parent_state=post_state_digest,
        )
        if advance_receipt.outcome != ADMITTED:
            raise SovereignExecutionError("TERMINAL_LEASE_ADVANCE_FAILED")
        revoke_receipt = lease_manager.revoke(authority_receipt.authority_domain, authority_receipt.execution_identity_root)
        if revoke_receipt.outcome != ADMITTED:
            raise SovereignExecutionError("TERMINAL_LEASE_REVOCATION_FAILED")
        durable_registry._commit_terminal_transition(
            execution_id,
            status=expected_status,
            phase={"SUCCEEDED": "completed", "ROLLED_BACK": "rolled-back", "DENIED": "denied", "FAILED": "failed"}[terminal_outcome],
            transition_sequence=durable_execution_record.last_completed_transition + 1,
            receipt=receipt,
            commit_capability=_TERMINAL_COMMIT_CAPABILITY,
        )
        receipt_chain.append(receipt)
        terminal_record = durable_registry.get(execution_id)
        if terminal_record.current_receipt_root != receipt.root or terminal_record.status != expected_status:
            raise SovereignExecutionError("TERMINAL_DURABLE_COMMIT_MISMATCH")
        return receipt
