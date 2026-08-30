#!/usr/bin/env python3
"""Behavioral tests for request-bound GitHub Agent Dispatch identity."""
from __future__ import annotations

import base64
import asyncio
import json
import os
import sys
import time
import types
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
runtime_root = os.environ.get("CODEX_PRIMARY_RUNTIME_ROOT")
if runtime_root:
    sys.path.append(
        str(Path(runtime_root) / "dependencies/python/lib/python3.12/site-packages")
    )

# These network clients are imported by the legacy coordinator but are never
# invoked on the authority-denied path exercised below.
if "httpx" not in sys.modules:
    sys.modules["httpx"] = types.ModuleType("httpx")
if "redis.asyncio" not in sys.modules:
    redis_module = types.ModuleType("redis")
    redis_asyncio_module = types.ModuleType("redis.asyncio")
    redis_module.asyncio = redis_asyncio_module
    sys.modules["redis"] = redis_module
    sys.modules["redis.asyncio"] = redis_asyncio_module

from harness.sdk.authority_client import authorize_with_context  # noqa: E402
from harness.sdk.github_dispatch_identity import (  # noqa: E402
    VerifiedGitHubOIDCClaims,
    build_dispatch_authority_context,
    dispatch_replay_key,
    verify_github_oidc_token,
)
from harness.sdk.sovereign_execution import canonical_bytes, canonical_hash  # noqa: E402
from agents.coordinator import dispatch_event, last_dispatch_receipts  # noqa: E402


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _uint(value: int) -> str:
    size = max(1, (value.bit_length() + 7) // 8)
    return _b64url(value.to_bytes(size, "big"))


def _token_and_jwks(request_body: dict) -> tuple[str, dict]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private_key.public_key().public_numbers()
    now = int(time.time())
    claims = {
        "iss": "https://token.actions.githubusercontent.com",
        "aud": "aegis-agent-dispatch:" + canonical_hash(
            "AEGIS_AGENT_DISPATCH_REQUEST_V1", request_body
        ),
        "sub": "repo:Aegis-Omega/AEGIS-OMEGA:ref:refs/heads/main",
        "repository": "Aegis-Omega/AEGIS-OMEGA",
        "repository_id": "1095915905",
        "repository_owner": "Aegis-Omega",
        "ref": "refs/heads/main",
        "sha": "c" * 40,
        "workflow_ref": (
            "Aegis-Omega/AEGIS-OMEGA/.github/workflows/"
            "agent-dispatch.yml@refs/heads/main"
        ),
        "workflow_sha": "c" * 40,
        "event_name": "workflow_run",
        "actor_id": "228550385",
        "run_id": "9001",
        "run_attempt": "1",
        "runner_environment": "github-hosted",
        "jti": "oidc-token-9001",
        "iat": now - 1,
        "nbf": now - 1,
        "exp": now + 300,
    }
    header = {"alg": "RS256", "kid": "test-key", "typ": "JWT"}
    signing_input = (
        _b64url(canonical_bytes(header))
        + "."
        + _b64url(canonical_bytes(claims))
    ).encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    token = signing_input.decode("ascii") + "." + _b64url(signature)
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key",
                "use": "sig",
                "alg": "RS256",
                "n": _uint(public.n),
                "e": _uint(public.e),
            }
        ]
    }
    return token, jwks


class AgentDispatchIdentityTests(TestCase):
    def test_replay_fence_is_bound_to_token_and_exact_request(self) -> None:
        first = {"event_type": "github_ci_failure", "payload": {"run_id": "1"}}
        second = {"event_type": "github_ci_failure", "payload": {"run_id": "2"}}
        try:
            replay_key = dispatch_replay_key
        except (ImportError, AttributeError, NameError) as exc:
            self.fail(f"request-bound replay fence is missing: {exc}")

        key = replay_key(token_id="jti-1", request_body=first)
        self.assertEqual(key, replay_key(token_id="jti-1", request_body=first))
        self.assertNotEqual(key, replay_key(token_id="jti-2", request_body=first))
        self.assertNotEqual(key, replay_key(token_id="jti-1", request_body=second))
        self.assertNotIn("jti-1", key)

    def test_coordinator_uses_request_local_context_for_every_role_decision(self) -> None:
        request_body = {
            "event_type": "github_ci_failure",
            "payload": {"run_id": "33250654595", "head_sha": "a" * 40},
        }
        claims = VerifiedGitHubOIDCClaims(
            issuer="https://token.actions.githubusercontent.com",
            audience="aegis-agent-dispatch:" + canonical_hash(
                "AEGIS_AGENT_DISPATCH_REQUEST_V1", request_body
            ),
            subject="repo:Aegis-Omega/AEGIS-OMEGA:ref:refs/heads/main",
            repository="Aegis-Omega/AEGIS-OMEGA",
            repository_id="1095915905",
            repository_owner="Aegis-Omega",
            ref="refs/heads/main",
            sha="c" * 40,
            workflow_ref=(
                "Aegis-Omega/AEGIS-OMEGA/.github/workflows/"
                "agent-dispatch.yml@refs/heads/main"
            ),
            workflow_sha="c" * 40,
            event_name="workflow_run",
            actor_id="228550385",
            run_id="9001",
            run_attempt="1",
            runner_environment="github-hosted",
            token_id="oidc-token-9001",
        )

        def context_for(action: dict):
            return build_dispatch_authority_context(
                claims=claims,
                request_body=request_body,
                action=action,
                repository_root=REPO_ROOT,
                expected_source_commit="c" * 40,
            )

        with patch.dict(os.environ, {}, clear=True):
            try:
                results = asyncio.run(
                    dispatch_event(
                        request_body["event_type"],
                        request_body["payload"],
                        authority_context_factory=context_for,
                    )
                )
            except TypeError as exc:
                self.fail(f"coordinator lacks request-local authority context: {exc}")

        receipts = last_dispatch_receipts()
        self.assertEqual(results, [])
        self.assertGreater(len(receipts), 0)
        for receipt in receipts:
            self.assertEqual(receipt["outcome"], "DENIED")
            self.assertIn("UNOBSERVED_CAPABILITY", receipt["reason_codes"])
            self.assertNotIn("IDENTITY_UNAVAILABLE", receipt["reason_codes"])

    def test_rs256_token_is_bound_to_the_exact_dispatch_request(self) -> None:
        request_body = {
            "event_type": "github_ci_failure",
            "payload": {"run_id": "33250654595", "head_sha": "a" * 40},
        }
        token, jwks = _token_and_jwks(request_body)

        claims = verify_github_oidc_token(
            token=token,
            request_body=request_body,
            jwks=jwks,
        )
        self.assertEqual(claims.token_id, "oidc-token-9001")
        self.assertEqual(claims.repository_id, "1095915905")

        spliced_request = json.loads(json.dumps(request_body))
        spliced_request["payload"]["head_sha"] = "d" * 40
        with self.assertRaisesRegex(ValueError, "OIDC_AUDIENCE_MISMATCH"):
            verify_github_oidc_token(
                token=token,
                request_body=spliced_request,
                jwks=jwks,
            )

    def test_verified_request_reaches_capability_denial_without_process_environment(self) -> None:
        request_body = {
            "event_type": "github_ci_failure",
            "payload": {
                "run_id": "33250654595",
                "head_sha": "a" * 40,
                "head_branch": "feat/example",
            },
        }
        action = {
            "operation": "agent-dispatch",
            "role": "Engineering",
            "instruction_digest": "b" * 64,
        }
        claims = VerifiedGitHubOIDCClaims(
            issuer="https://token.actions.githubusercontent.com",
            audience="aegis-agent-dispatch:" + canonical_hash(
                "AEGIS_AGENT_DISPATCH_REQUEST_V1", request_body
            ),
            subject="repo:Aegis-Omega/AEGIS-OMEGA:ref:refs/heads/main",
            repository="Aegis-Omega/AEGIS-OMEGA",
            repository_id="1095915905",
            repository_owner="Aegis-Omega",
            ref="refs/heads/main",
            sha="c" * 40,
            workflow_ref=(
                "Aegis-Omega/AEGIS-OMEGA/.github/workflows/"
                "agent-dispatch.yml@refs/heads/main"
            ),
            workflow_sha="c" * 40,
            event_name="workflow_run",
            actor_id="228550385",
            run_id="9001",
            run_attempt="1",
            runner_environment="github-hosted",
            token_id="oidc-token-9001",
        )

        context = build_dispatch_authority_context(
            claims=claims,
            request_body=request_body,
            action=action,
            repository_root=REPO_ROOT,
            expected_source_commit="c" * 40,
        )
        decision = authorize_with_context(
            action_class="D1",
            authority_domain="agent:dispatch",
            requested_capability="coordinator.dispatch",
            tool="agents.coordinator:dispatch",
            target="Engineering",
            action=action,
            context=context,
        )

        self.assertEqual(decision["outcome"], "DENIED")
        self.assertIn("UNOBSERVED_CAPABILITY", decision["denial_codes"])
        self.assertIn("INSUFFICIENT_VALIDATED_RUNS", decision["denial_codes"])
        self.assertNotIn("IDENTITY_UNAVAILABLE", decision["denial_codes"])
        self.assertNotIn("WORKSPACE_DENIED", decision["denial_codes"])
        self.assertEqual(context.identity.source_commit, "c" * 40)
        self.assertEqual(
            context.identity.action_digest,
            canonical_hash("AEGIS_REQUESTED_ACTION_V1", action),
        )

        with self.assertRaisesRegex(ValueError, "OIDC_IMAGE_SHA_MISMATCH"):
            build_dispatch_authority_context(
                claims=claims,
                request_body=request_body,
                action=action,
                repository_root=REPO_ROOT,
                expected_source_commit="d" * 40,
            )


if __name__ == "__main__":
    main()
