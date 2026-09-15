"""Request-bound GitHub OIDC identity projection for Agent Dispatch."""
from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from harness.sdk.authority_client import AuthorityContext
from harness.sdk.sovereign_execution import (
    SCHEMA_VERSION,
    ZERO_HASH,
    ExecutionIdentityEnvelope,
    canonical_hash,
    compute_workspace_binding,
    load_capability_registry,
    load_policy,
)


ISSUER = "https://token.actions.githubusercontent.com"
REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
REPOSITORY_ID = "1095915905"
REMOTE = "https://github.com/Aegis-Omega/AEGIS-OMEGA.git"
TRUSTED_REF = "refs/heads/main"
TRUSTED_WORKFLOW_REF = (
    "Aegis-Omega/AEGIS-OMEGA/.github/workflows/"
    "agent-dispatch.yml@refs/heads/main"
)
ALLOWED_EVENTS = frozenset({"workflow_run", "issues", "issue_comment"})
GIT_SHA = re.compile(r"^[0-9a-f]{40,64}$")


@dataclass(frozen=True)
class VerifiedGitHubOIDCClaims:
    issuer: str
    audience: str
    subject: str
    repository: str
    repository_id: str
    repository_owner: str
    ref: str
    sha: str
    workflow_ref: str
    workflow_sha: str
    event_name: str
    actor_id: str
    run_id: str
    run_attempt: str
    runner_environment: str
    token_id: str


def _validate_claims(
    claims: VerifiedGitHubOIDCClaims,
    *,
    request_digest: str,
) -> None:
    expected_audience = f"aegis-agent-dispatch:{request_digest}"
    checks = (
        (claims.issuer == ISSUER, "OIDC_ISSUER_MISMATCH"),
        (claims.audience == expected_audience, "OIDC_AUDIENCE_MISMATCH"),
        (claims.repository == REPOSITORY, "OIDC_REPOSITORY_MISMATCH"),
        (claims.repository_id == REPOSITORY_ID, "OIDC_REPOSITORY_ID_MISMATCH"),
        (claims.repository_owner == "Aegis-Omega", "OIDC_OWNER_MISMATCH"),
        (claims.ref == TRUSTED_REF, "OIDC_REF_UNTRUSTED"),
        (claims.workflow_ref == TRUSTED_WORKFLOW_REF, "OIDC_WORKFLOW_UNTRUSTED"),
        (claims.workflow_sha == claims.sha, "OIDC_WORKFLOW_SHA_MISMATCH"),
        (claims.event_name in ALLOWED_EVENTS, "OIDC_EVENT_UNTRUSTED"),
        (bool(GIT_SHA.fullmatch(claims.sha)), "OIDC_SHA_INVALID"),
        (bool(claims.token_id), "OIDC_TOKEN_ID_MISSING"),
    )
    for valid, code in checks:
        if not valid:
            raise ValueError(code)


def _decode_segment(segment: str, *, code: str) -> bytes:
    try:
        return base64.b64decode(
            segment + "=" * (-len(segment) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(code) from exc


def _json_object(segment: str, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(_decode_segment(segment, code=code))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(code) from exc
    if not isinstance(value, dict):
        raise ValueError(code)
    return value


def _required_string(payload: dict[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"OIDC_CLAIM_MISSING:{name}")
    return value


def verify_github_oidc_token(
    *,
    token: str,
    request_body: dict[str, Any],
    jwks: dict[str, Any],
    now: int | None = None,
) -> VerifiedGitHubOIDCClaims:
    """Verify one GitHub RS256 token and bind it to the exact request digest."""
    parts = token.split(".") if isinstance(token, str) else []
    if len(parts) != 3:
        raise ValueError("OIDC_TOKEN_MALFORMED")
    header = _json_object(parts[0], code="OIDC_HEADER_MALFORMED")
    payload = _json_object(parts[1], code="OIDC_PAYLOAD_MALFORMED")
    if header.get("alg") != "RS256" or header.get("typ") != "JWT":
        raise ValueError("OIDC_ALGORITHM_UNTRUSTED")
    kid = _required_string(header, "kid")

    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not isinstance(keys, list):
        raise ValueError("OIDC_JWKS_MALFORMED")
    matches = [
        key for key in keys
        if isinstance(key, dict)
        and key.get("kid") == kid
        and key.get("kty") == "RSA"
        and key.get("alg") in (None, "RS256")
        and key.get("use") in (None, "sig")
    ]
    if len(matches) != 1:
        raise ValueError("OIDC_SIGNING_KEY_UNAVAILABLE")
    key = matches[0]
    try:
        modulus = int.from_bytes(_decode_segment(key["n"], code="OIDC_JWK_MALFORMED"), "big")
        exponent = int.from_bytes(_decode_segment(key["e"], code="OIDC_JWK_MALFORMED"), "big")
        public_key = rsa.RSAPublicNumbers(exponent, modulus).public_key()
        public_key.verify(
            _decode_segment(parts[2], code="OIDC_SIGNATURE_MALFORMED"),
            f"{parts[0]}.{parts[1]}".encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except (InvalidSignature, KeyError, TypeError, ValueError) as exc:
        raise ValueError("OIDC_SIGNATURE_INVALID") from exc

    current = int(time.time()) if now is None else now
    for name in ("iat", "nbf", "exp"):
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"OIDC_CLAIM_MISSING:{name}")
    if payload["iat"] > current + 30 or payload["nbf"] > current + 30:
        raise ValueError("OIDC_TOKEN_NOT_YET_VALID")
    if payload["exp"] < current - 30:
        raise ValueError("OIDC_TOKEN_EXPIRED")

    claims = VerifiedGitHubOIDCClaims(
        issuer=_required_string(payload, "iss"),
        audience=_required_string(payload, "aud"),
        subject=_required_string(payload, "sub"),
        repository=_required_string(payload, "repository"),
        repository_id=_required_string(payload, "repository_id"),
        repository_owner=_required_string(payload, "repository_owner"),
        ref=_required_string(payload, "ref"),
        sha=_required_string(payload, "sha"),
        workflow_ref=_required_string(payload, "workflow_ref"),
        workflow_sha=_required_string(payload, "workflow_sha"),
        event_name=_required_string(payload, "event_name"),
        actor_id=_required_string(payload, "actor_id"),
        run_id=_required_string(payload, "run_id"),
        run_attempt=_required_string(payload, "run_attempt"),
        runner_environment=_required_string(payload, "runner_environment"),
        token_id=_required_string(payload, "jti"),
    )
    request_digest = canonical_hash("AEGIS_AGENT_DISPATCH_REQUEST_V1", request_body)
    _validate_claims(claims, request_digest=request_digest)
    return claims


def dispatch_replay_key(*, token_id: str, request_body: dict[str, Any]) -> str:
    if not isinstance(token_id, str) or not token_id:
        raise ValueError("OIDC_TOKEN_ID_MISSING")
    commitment = canonical_hash(
        "AEGIS_AGENT_DISPATCH_REPLAY_FENCE_V1",
        {
            "token_id": token_id,
            "request_digest": canonical_hash(
                "AEGIS_AGENT_DISPATCH_REQUEST_V1", request_body
            ),
        },
    )
    return f"aegis:dispatch:oidc-replay:{commitment}"


def build_dispatch_authority_context(
    *,
    claims: VerifiedGitHubOIDCClaims,
    request_body: dict[str, Any],
    action: dict[str, Any],
    repository_root: str | Path,
    expected_source_commit: str,
) -> AuthorityContext:
    root = Path(repository_root).resolve()
    request_digest = canonical_hash("AEGIS_AGENT_DISPATCH_REQUEST_V1", request_body)
    _validate_claims(claims, request_digest=request_digest)
    if claims.sha != expected_source_commit:
        raise ValueError("OIDC_IMAGE_SHA_MISMATCH")

    _, policy_root = load_policy(root / "harness/policies/consequence-policy.v1.json")
    _, registry_root = load_capability_registry(
        repository_root=root,
        skill_tree_path=root / "harness/skill_tree.json",
        capability_map_path=root / "harness/policies/capability-map.v1.json",
    )
    approval_reference = f"github-oidc:{claims.token_id}"
    workspace_binding = compute_workspace_binding(
        repository_remote=REMOTE,
        repository_root=".",
        project_identity="AEGIS-OMEGA",
        source_commit=claims.sha,
        operator_authorization=approval_reference,
    )
    action_digest = canonical_hash("AEGIS_REQUESTED_ACTION_V1", action)
    identity = ExecutionIdentityEnvelope(
        schema_version=SCHEMA_VERSION,
        repository_identity=REMOTE,
        repository_root=".",
        source_commit=claims.sha,
        branch_or_ref=claims.ref,
        project_identity="AEGIS-OMEGA",
        workspace_root=".",
        workspace_binding=workspace_binding,
        parent_state_root=ZERO_HASH,
        skills_root=registry_root,
        registry_root=registry_root,
        policy_root=policy_root,
        actor_class="github-actions",
        actor_identity=f"github-actor:{claims.actor_id}",
        model_identity="runtime-selected-after-admission",
        session_identity=f"github-run:{claims.run_id}:{claims.run_attempt}",
        physical_executor=f"github-actions:{claims.runner_environment}",
        tool_identity="agents.coordinator:dispatch",
        workflow_identity=f"github-workflow:{claims.run_id}:{claims.run_attempt}",
        authority_domain="agent:dispatch",
        requested_capability="coordinator.dispatch",
        observed_authority="github-oidc-verified",
        approval_reference=approval_reference,
        input_digest=request_digest,
        action_digest=action_digest,
        expected_pre_state=registry_root,
        deterministic_nonce=canonical_hash(
            "AEGIS_AGENT_DISPATCH_NONCE_V1",
            {"token_id": claims.token_id, "action_digest": action_digest},
        ),
    )
    return AuthorityContext(
        identity=identity,
        workspace_observation={
            "actual_cwd": str(root),
            "remote_origin": REMOTE,
            "mutation_target": str(root),
            "path_views": {},
        },
    )
