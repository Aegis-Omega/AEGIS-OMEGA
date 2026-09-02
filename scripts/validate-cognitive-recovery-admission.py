#!/usr/bin/env python3
"""Deterministic, offline Cognitive Recovery Admission V1 verifier.

This milestone is authority-neutral. It does not sign, mutate refs, update main,
modify repository governance, deploy, or grant production recovery authority.
R0-R7 validate bounded recovery evidence. Replay state remains fail-closed and
must be implemented by a later base-owned admission layer before any grant.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator

RECEIPT_KIND = "AEGIS_COGNITIVE_RECOVERY_ADMISSION_RECEIPT_V1"
REQUEST_DOMAIN = "AEGIS_COGNITIVE_RECOVERY_ADMISSION_REQUEST_V1"
PLATFORM_DOMAIN = "AEGIS_PLATFORM_GOVERNANCE_OBSERVATION_V1"
APPROVAL_DOMAIN = "AEGIS_RECOVERY_OPERATOR_APPROVAL_V1"
SCHEMA_VERSION = "1.0.0"
VERIFIER_IDENTITY = "offline:aegis-cognitive-recovery-admission-v1"
REPOSITORY_ID = "Aegis-Omega/AEGIS-OMEGA"
ALL_GATES = frozenset({"R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"})
REQUIRED_PLATFORM_CHECKS = frozenset(
    {
        "Main branch enforcement",
        "aegis / automaton-2",
        "aegis / automaton-3",
    }
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUEST_SCHEMA_PATH = REPO_ROOT / "schemas" / "cognitive-recovery-admission-request.v1.schema.json"

ZERO_PARENT_VALIDATOR_PATH = "scripts/validate-automaton2.py"
ZERO_PARENT_TEST_PATH = "sovereign-omega-v2/python/tests/test_automaton2.py"
WRITER_WORKFLOW_PATH = ".github/workflows/cognitive-manifest-refresh.yml"
MANIFEST_PATH = ".claude.json"
SKILL_HASHES_PATH = "skill-hashes.sha256"

FORBIDDEN_RECOVERY_PATH_PREFIXES = (
    "infra/",
    "terraform/",
    "gcp/",
    "deploy/",
    ".github/workflows/deploy",
)

DIRECT_AUTHORITY_ENABLE_KEYS = frozenset(
    {
        "gcp_enabled",
        "enable_gcp",
        "billing_enabled",
        "enable_billing",
        "deployment_enabled",
        "enable_deployment",
        "provider_enabled",
        "enable_provider",
        "cloud_enabled",
        "enable_cloud",
    }
)
SENSITIVE_AUTHORITY_DOMAINS = frozenset({"gcp", "billing", "deployment", "provider", "cloud"})
NESTED_ENABLE_KEYS = frozenset({"enabled", "enable", "active", "default_enabled"})


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic compact UTF-8 JSON; reject NaN/Infinity."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request_digest(request: dict[str, Any]) -> str:
    """Hash the pre-approval request core.

    ``request_id`` is self-identifying and ``operator_approval_digest`` is a
    post-identity evidence attachment. Excluding the latter breaks the otherwise
    circular dependency where approval must bind the request ID that would in
    turn depend on the approval digest. R7 validates that attachment separately.
    """
    body = {
        key: value
        for key, value in request.items()
        if key not in {"request_id", "operator_approval_digest"}
    }
    return sha256_hex(canonical_bytes({"domain": REQUEST_DOMAIN, "request": body}))


def _domain_digest(
    value: Mapping[str, Any], *, domain: str, envelope_key: str, self_field: str
) -> str:
    body = {key: item for key, item in value.items() if key != self_field}
    return sha256_hex(canonical_bytes({"domain": domain, envelope_key: body}))


def platform_observation_digest(observation: Mapping[str, Any]) -> str:
    return _domain_digest(
        observation,
        domain=PLATFORM_DOMAIN,
        envelope_key="observation",
        self_field="observation_digest",
    )


def operator_approval_digest(approval: Mapping[str, Any]) -> str:
    return _domain_digest(
        approval,
        domain=APPROVAL_DOMAIN,
        envelope_key="approval",
        self_field="approval_digest",
    )


def _parse_rfc3339(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _safe_request_value(request: Mapping[str, Any], key: str, fallback: str) -> str:
    value = request.get(key)
    return value if isinstance(value, str) else fallback


def build_receipt(
    *,
    request: dict[str, Any],
    verified_gates: Iterable[str],
    violations: Iterable[str],
    platform_governance_state: str,
    verifier_code_digest: str,
) -> dict[str, Any]:
    """Build a deterministic authority-bounded admission decision receipt."""
    gates = sorted(set(verified_gates))
    violation_list = sorted(set(violations))
    granted = len(violation_list) == 0 and set(gates) == ALL_GATES

    body: dict[str, Any] = {
        "receipt_kind": RECEIPT_KIND,
        "schema_version": SCHEMA_VERSION,
        "request_digest": request_digest(request),
        "repository_id": _safe_request_value(request, "repository_id", REPOSITORY_ID),
        "candidate_sha": _safe_request_value(request, "candidate_sha", "0" * 40),
        "denied_base_sha": _safe_request_value(request, "denied_base_sha", "0" * 40),
        "trusted_control_plane_sha": _safe_request_value(request, "trusted_control_plane_sha", "0" * 40),
        "recovery_parent_sha": _safe_request_value(request, "recovery_parent_sha", "0" * 40),
        "recovery_receipt_hash": _safe_request_value(request, "recovery_receipt_hash", "0" * 64),
        "writer_workflow_blob": _safe_request_value(request, "writer_workflow_blob", "0" * 40),
        "platform_governance_observation_digest": _safe_request_value(
            request, "platform_governance_observation_digest", "0" * 64
        ),
        "platform_governance_state": platform_governance_state,
        "operator_approval_digest": _safe_request_value(request, "operator_approval_digest", "0" * 64),
        "verified_gates": gates,
        "violations": violation_list,
        "outcome": "RECOVERY_ADMISSION_GRANTED" if granted else "DENIED",
        "scope": "ONE_EXACT_CANONICAL_RECOVERY_TRANSITION",
        "authority": "RECOVERY_ADMISSION_ONLY" if granted else "NONE",
        "mutation_authority": "NONE",
        "verifier_identity": VERIFIER_IDENTITY,
        "verifier_code_digest": verifier_code_digest,
    }
    receipt_hash = sha256_hex(canonical_bytes({"domain": RECEIPT_KIND, "receipt": body}))
    return {**body, "receipt_hash": receipt_hash}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _commit_exists(repo: Path, sha: str) -> bool:
    return _git(repo, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    return _git(repo, "merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def _single_parent(repo: Path, sha: str) -> str | None:
    result = _git(repo, "rev-list", "--parents", "-n", "1", sha)
    if result.returncode != 0:
        return None
    parts = result.stdout.strip().split()
    if len(parts) != 2:
        return None
    return parts[1]


def _blob_sha(repo: Path, commit: str, path: str) -> str | None:
    result = _git(repo, "rev-parse", f"{commit}:{path}")
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value if value else None


def _changed_paths(repo: Path, base: str, candidate: str) -> set[str] | None:
    result = _git(repo, "diff", "--name-only", "--no-renames", base, candidate, "--")
    if result.returncode != 0:
        return None
    return {line for line in result.stdout.splitlines() if line}


def _json_at(repo: Path, commit: str, path: str) -> Any:
    result = _git(repo, "show", f"{commit}:{path}")
    if result.returncode != 0:
        raise ValueError(f"unreadable JSON path {path}")
    return json.loads(result.stdout)


def _valid_relative_path(path: str) -> bool:
    pure = Path(path)
    return bool(path) and not pure.is_absolute() and ".." not in pure.parts and path.replace("\\", "/") == path


def _forbidden_authority_path(path: str) -> bool:
    normalized = path.lstrip("./")
    return any(normalized.startswith(prefix) for prefix in FORBIDDEN_RECOVERY_PATH_PREFIXES)


def _authority_value_enabled(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in {
            "",
            "0",
            "false",
            "off",
            "disabled",
            "none",
            "not_enabled",
            "not_authorized",
        }
    return False


def _semantic_authority_violations(value: Any, *, path: str) -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            normalized = key_text.lower().replace("-", "_")
            child_path = f"{path}.{key_text}"
            if normalized in DIRECT_AUTHORITY_ENABLE_KEYS and _authority_value_enabled(child):
                violations.append(f"R5:FORBIDDEN_AUTHORITY_ENABLE:{child_path}")
            if normalized in SENSITIVE_AUTHORITY_DOMAINS and isinstance(child, Mapping):
                for nested_key, nested_value in child.items():
                    nested_normalized = str(nested_key).lower().replace("-", "_")
                    if nested_normalized in NESTED_ENABLE_KEYS and _authority_value_enabled(nested_value):
                        violations.append(
                            f"R5:FORBIDDEN_AUTHORITY_ENABLE:{child_path}.{nested_key}"
                        )
            violations.extend(_semantic_authority_violations(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(_semantic_authority_violations(child, path=f"{path}[{index}]"))
    return violations


def _gate_r0(request: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    try:
        schema = json.loads(REQUEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = sorted(Draft202012Validator(schema).iter_errors(request), key=lambda error: list(error.path))
        if errors:
            violations.append("R0:REQUEST_SCHEMA_INVALID")
    except (OSError, ValueError, TypeError):
        violations.append("R0:REQUEST_SCHEMA_UNAVAILABLE")

    try:
        if request.get("request_id") != request_digest(request):
            violations.append("R0:REQUEST_DIGEST_MISMATCH")
    except (TypeError, ValueError):
        violations.append("R0:REQUEST_DIGEST_INVALID")

    if request.get("repository_id") != REPOSITORY_ID:
        violations.append("R0:REPOSITORY_ID_MISMATCH")
    return violations


def _gate_r1(repo: Path, request: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    sha_fields = (
        "trusted_control_plane_sha",
        "recovery_parent_sha",
        "denied_base_sha",
        "candidate_sha",
        "zero_parent_repair_sha",
    )
    for field in sha_fields:
        value = request.get(field)
        if not isinstance(value, str) or not _commit_exists(repo, value):
            violations.append(f"R1:UNRESOLVED_{field.upper()}")

    if violations:
        return violations

    trusted = request["trusted_control_plane_sha"]
    parent = request["recovery_parent_sha"]
    denied = request["denied_base_sha"]
    if not _is_ancestor(repo, trusted, parent):
        violations.append("R1:RECOVERY_PARENT_NOT_DESCENDED_FROM_TRUSTED_ROOT")
    if _single_parent(repo, denied) != parent:
        violations.append("R1:DENIED_BASE_PARENT_MISMATCH")
    return violations


def _gate_r2(repo: Path, request: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    candidate = request.get("candidate_sha")
    repair = request.get("zero_parent_repair_sha")
    if not isinstance(candidate, str) or not isinstance(repair, str) or not _is_ancestor(repo, repair, candidate):
        violations.append("R2:CANDIDATE_NOT_DESCENDED_FROM_ZERO_PARENT_REPAIR")
        return violations

    repair_blobs = {
        ZERO_PARENT_VALIDATOR_PATH: request.get("zero_parent_validator_blob"),
        ZERO_PARENT_TEST_PATH: request.get("zero_parent_test_blob"),
        WRITER_WORKFLOW_PATH: request.get("writer_workflow_blob"),
    }
    for path, expected in repair_blobs.items():
        repair_actual = _blob_sha(repo, repair, path)
        candidate_actual = _blob_sha(repo, candidate, path)
        if not isinstance(expected, str) or repair_actual != expected:
            violations.append(f"R2:REPAIR_BLOB_MISMATCH:{path}")
        if not isinstance(expected, str) or candidate_actual != expected:
            violations.append(f"R2:CANDIDATE_BLOB_MISMATCH:{path}")

    candidate_blobs = {
        MANIFEST_PATH: request.get("expected_manifest_blob"),
        SKILL_HASHES_PATH: request.get("expected_skill_hashes_blob"),
    }
    for path, expected in candidate_blobs.items():
        actual = _blob_sha(repo, candidate, path)
        if not isinstance(expected, str) or actual != expected:
            violations.append(f"R2:CANDIDATE_BLOB_MISMATCH:{path}")
    return violations


def _gate_r3(repo: Path, request: dict[str, Any]) -> tuple[list[str], set[str]]:
    violations: list[str] = []
    allowed_raw = request.get("allowed_changed_paths")
    allowed = set(allowed_raw) if isinstance(allowed_raw, list) and all(isinstance(item, str) for item in allowed_raw) else set()
    if not allowed or any(not _valid_relative_path(path) for path in allowed):
        violations.append("R3:INVALID_ALLOWED_PATH_SET")

    denied = request.get("denied_base_sha")
    candidate = request.get("candidate_sha")
    if not isinstance(denied, str) or not isinstance(candidate, str):
        return [*violations, "R3:DIFF_IDENTITY_INVALID"], set()
    changed = _changed_paths(repo, denied, candidate)
    if changed is None:
        return [*violations, "R3:DIFF_UNAVAILABLE"], set()

    outside = sorted(changed - allowed)
    for path in outside:
        violations.append(f"R3:UNCLASSIFIED_CHANGED_PATH:{path}")
    return violations, changed


def _gate_r4(request: dict[str, Any], recovery_evidence: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(recovery_evidence, Mapping):
        return ["R4:RECOVERY_EVIDENCE_MISSING"]

    expected = {
        "receipt_kind": "AEGIS_COGNITIVE_RECOVERY_RECEIPT_V1",
        "outcome": "RECOVERY_VERIFIED",
        "production_admission": "NONE",
        "authority": "NONE",
        "candidate_sha": request.get("candidate_sha"),
        "denied_base_sha": request.get("denied_base_sha"),
        "recovery_parent_sha": request.get("recovery_parent_sha"),
        "receipt_hash": request.get("recovery_receipt_hash"),
        "denied_receipt_hash": request.get("denied_receipt_hash"),
        "recovery_validation_receipt_hash": request.get("counterfactual_admission_receipt_hash"),
        "artifact_digest": request.get("recovery_artifact_digest"),
    }
    violations: list[str] = []
    for field, expected_value in expected.items():
        if recovery_evidence.get(field) != expected_value:
            violations.append(f"R4:EVIDENCE_MISMATCH:{field}")
    return violations


def _gate_r5(repo: Path, request: dict[str, Any], changed_paths: set[str]) -> list[str]:
    violations: list[str] = []
    requested_paths = request.get("allowed_changed_paths")
    candidate_paths = set(requested_paths) if isinstance(requested_paths, list) else set()
    for path in sorted(changed_paths | candidate_paths):
        if isinstance(path, str) and _forbidden_authority_path(path):
            violations.append(f"R5:FORBIDDEN_AUTHORITY_PATH:{path}")

    violations.extend(_semantic_authority_violations(request, path="request"))
    candidate = request.get("candidate_sha")
    if isinstance(candidate, str):
        try:
            manifest = _json_at(repo, candidate, MANIFEST_PATH)
        except (ValueError, json.JSONDecodeError):
            violations.append("R5:CONTROL_MANIFEST_UNREADABLE")
        else:
            violations.extend(_semantic_authority_violations(manifest, path=MANIFEST_PATH))
    else:
        violations.append("R5:CANDIDATE_IDENTITY_INVALID")
    return violations


def _gate_r6(
    request: Mapping[str, Any], platform_observation: Mapping[str, Any] | None
) -> list[str]:
    if not isinstance(platform_observation, Mapping):
        return ["R6:PLATFORM_OBSERVATION_MISSING"]

    violations: list[str] = []
    observation_digest = platform_observation.get("observation_digest")
    try:
        recomputed_digest = platform_observation_digest(platform_observation)
    except (TypeError, ValueError):
        recomputed_digest = None
    if (
        not isinstance(observation_digest, str)
        or observation_digest != recomputed_digest
        or request.get("platform_governance_observation_digest") != observation_digest
    ):
        violations.append("R6:OBSERVATION_DIGEST_MISMATCH")

    if platform_observation.get("schema_version") != SCHEMA_VERSION:
        violations.append("R6:SCHEMA_VERSION_MISMATCH")
    if platform_observation.get("repository_id") != REPOSITORY_ID:
        violations.append("R6:REPOSITORY_ID_MISMATCH")
    if platform_observation.get("observed_for_candidate_sha") != request.get("candidate_sha"):
        violations.append("R6:CANDIDATE_BINDING_MISMATCH")
    if platform_observation.get("state") != "ENFORCED":
        violations.append("R6:PLATFORM_STATE_NOT_ENFORCED")

    ruleset_ids = platform_observation.get("ruleset_ids")
    if not isinstance(ruleset_ids, list) or not ruleset_ids:
        violations.append("R6:RULESET_IDS_MISSING")

    required_checks = platform_observation.get("required_checks")
    observed_checks = set(required_checks) if isinstance(required_checks, list) else set()
    if not REQUIRED_PLATFORM_CHECKS.issubset(observed_checks):
        violations.append("R6:REQUIRED_CHECKS_MISSING")

    observed_at = _parse_rfc3339(platform_observation.get("observed_at"))
    expires_at = _parse_rfc3339(request.get("expires_at"))
    if observed_at is None or expires_at is None:
        violations.append("R6:TIME_BINDING_INVALID")
    elif observed_at > expires_at:
        violations.append("R6:OBSERVATION_AFTER_REQUEST_EXPIRY")

    return violations


def _gate_r7(
    request: Mapping[str, Any], operator_approval: Mapping[str, Any] | None
) -> list[str]:
    if not isinstance(operator_approval, Mapping):
        return ["R7:OPERATOR_APPROVAL_MISSING"]

    violations: list[str] = []
    approval_digest = operator_approval.get("approval_digest")
    try:
        recomputed_digest = operator_approval_digest(operator_approval)
    except (TypeError, ValueError):
        recomputed_digest = None
    if (
        not isinstance(approval_digest, str)
        or approval_digest != recomputed_digest
        or request.get("operator_approval_digest") != approval_digest
    ):
        violations.append("R7:APPROVAL_DIGEST_MISMATCH")

    if operator_approval.get("schema_version") != SCHEMA_VERSION:
        violations.append("R7:SCHEMA_VERSION_MISMATCH")
    if operator_approval.get("request_digest") != request.get("request_id"):
        violations.append("R7:REQUEST_BINDING_MISMATCH")
    if operator_approval.get("candidate_sha") != request.get("candidate_sha"):
        violations.append("R7:CANDIDATE_BINDING_MISMATCH")
    if operator_approval.get("decision") != "APPROVE_RECOVERY_ADMISSION_EVALUATION":
        violations.append("R7:DECISION_NOT_APPROVED")

    return violations


def evaluate(
    *,
    repo: Path,
    request: dict[str, Any],
    recovery_evidence: Mapping[str, Any] | None,
    platform_observation: Mapping[str, Any] | None,
    operator_approval: Mapping[str, Any] | None,
    verifier_code_digest: str,
) -> dict[str, Any]:
    """Evaluate R0-R7 evidence and remain fail-closed on replay state."""
    verified: list[str] = []
    violations: list[str] = []

    r0 = _gate_r0(request)
    violations.extend(r0)
    if not r0:
        verified.append("R0")

    r1 = _gate_r1(repo, request)
    violations.extend(r1)
    if not r1:
        verified.append("R1")

    r2 = _gate_r2(repo, request)
    violations.extend(r2)
    if not r2:
        verified.append("R2")

    r3, changed_paths = _gate_r3(repo, request)
    violations.extend(r3)
    if not r3:
        verified.append("R3")

    r4 = _gate_r4(request, recovery_evidence)
    violations.extend(r4)
    if not r4:
        verified.append("R4")

    r5 = _gate_r5(repo, request, changed_paths)
    violations.extend(r5)
    if not r5:
        verified.append("R5")

    r6 = _gate_r6(request, platform_observation)
    violations.extend(r6)
    if not r6:
        verified.append("R6")

    r7 = _gate_r7(request, operator_approval)
    violations.extend(r7)
    if not r7:
        verified.append("R7")

    # Replay/consumption state is deliberately outside this candidate-controlled
    # offline verifier. Until a base-owned atomic state transition exists, no
    # admission authority may be minted even when all eight evidence gates pass.
    violations.append("R0:REPLAY_STATE_NOT_EVALUATED")

    platform_state = "UNKNOWN"
    if isinstance(platform_observation, Mapping):
        candidate_state = platform_observation.get("state")
        if candidate_state in {"ENFORCED", "DISABLED", "UNKNOWN"}:
            platform_state = candidate_state

    return build_receipt(
        request=request,
        verified_gates=verified,
        violations=violations,
        platform_governance_state=platform_state,
        verifier_code_digest=verifier_code_digest,
    )
