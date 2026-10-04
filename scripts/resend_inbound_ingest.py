#!/usr/bin/env python3
"""Local Resend webhook -> governed AEGIS evidence envelope entrypoint.

This process is intentionally local-only. It performs no network I/O, sends no
mail, fetches no message body/attachment content, dispatches no agent, and adds
no capability grant. Trusted runtime bindings come from environment variables;
the request on stdin remains untrusted data.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.sdk.resend_inbound import (  # noqa: E402
    InboundAdapter,
    LocalJournal,
    Route,
)
from harness.sdk.sovereign_execution import (  # noqa: E402
    AuthorityEvaluator,
    ExecutionIdentityEnvelope,
    load_capability_registry,
    load_policy,
)

MAX_STDIN_BYTES = 131_072
MAX_BASE64_CHARS = 90_000
ENV_IDENTITY = "AEGIS_EXECUTION_IDENTITY_JSON"
ENV_SECRETS = "AEGIS_RESEND_WEBHOOK_SECRETS_JSON"
ENV_ADDRESSES = "AEGIS_RESEND_RECEIVING_ADDRESSES_JSON"
ENV_SCOPE = "AEGIS_RESEND_ENDPOINT_SCOPE"
ENV_DOMAIN = "AEGIS_RESEND_ROUTING_DOMAIN"
ENV_JOURNAL = "AEGIS_RESEND_JOURNAL_PATH"


def _rejected(code: str) -> dict[str, Any]:
    return {"status": "REJECTED", "codes": [code], "external_effect": "NOT_EXECUTED"}


def _json_env(environ: Mapping[str, str], key: str) -> Any:
    raw = environ.get(key)
    if not isinstance(raw, str) or not raw or len(raw) > MAX_STDIN_BYTES:
        raise ValueError("CONFIGURATION_UNAVAILABLE")
    return json.loads(raw)


def _runtime(environ: Mapping[str, str], *, repo_root: Path) -> tuple[tuple[str, ...], Route, ExecutionIdentityEnvelope, AuthorityEvaluator, str, LocalJournal]:
    required = (ENV_IDENTITY, ENV_SECRETS, ENV_ADDRESSES, ENV_SCOPE, ENV_DOMAIN, ENV_JOURNAL)
    if any(not environ.get(key) for key in required):
        raise ValueError("CONFIGURATION_UNAVAILABLE")

    identity_obj = _json_env(environ, ENV_IDENTITY)
    secrets_obj = _json_env(environ, ENV_SECRETS)
    addresses_obj = _json_env(environ, ENV_ADDRESSES)
    if not isinstance(identity_obj, dict):
        raise ValueError("CONFIGURATION_INVALID")
    if not isinstance(secrets_obj, list) or not 1 <= len(secrets_obj) <= 2 or not all(isinstance(x, str) for x in secrets_obj):
        raise ValueError("CONFIGURATION_INVALID")
    if not isinstance(addresses_obj, list) or not addresses_obj or not all(isinstance(x, str) for x in addresses_obj):
        raise ValueError("CONFIGURATION_INVALID")

    journal_path = Path(environ[ENV_JOURNAL])
    if not journal_path.is_absolute():
        raise ValueError("CONFIGURATION_INVALID")

    identity = ExecutionIdentityEnvelope(**identity_obj)
    route = Route(
        endpoint_scope=environ[ENV_SCOPE],
        routing_domain=environ[ENV_DOMAIN],
        receiving_addresses=tuple(addresses_obj),
    )
    policy, _policy_root = load_policy(repo_root / "harness/policies/consequence-policy.v1.json")
    registry, registry_root = load_capability_registry(
        repository_root=repo_root,
        skill_tree_path=repo_root / "harness/skill_tree.json",
        capability_map_path=repo_root / "harness/policies/capability-map.v1.json",
    )
    evaluator = AuthorityEvaluator(policy=policy, registry=registry, repository_root=repo_root)
    journal = LocalJournal(journal_path)
    return tuple(secrets_obj), route, identity, evaluator, registry_root, journal


def run_ingest(request: Any, *, environ: Mapping[str, str] | None = None, repo_root: Path = ROOT) -> dict[str, Any]:
    """Pure orchestration around the already-tested adapter boundary.

    `request` is untrusted. `environ` and `repo_root` are trusted host bindings.
    Returned objects never contain webhook secrets.
    """
    env = os.environ if environ is None else environ
    try:
        if not isinstance(request, dict) or set(request) - {"raw_body_base64", "headers", "method"}:
            return _rejected("REQUEST_INVALID")
        encoded = request.get("raw_body_base64")
        headers = request.get("headers")
        method = request.get("method", "POST")
        if not isinstance(encoded, str) or not encoded or len(encoded) > MAX_BASE64_CHARS:
            return _rejected("RAW_BODY_BASE64_INVALID")
        if not isinstance(headers, list) or len(headers) > 32:
            return _rejected("REQUEST_INVALID")
        normalized_headers: list[tuple[str, str]] = []
        for pair in headers:
            if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(v, str) for v in pair):
                return _rejected("REQUEST_INVALID")
            normalized_headers.append((pair[0], pair[1]))
        if not isinstance(method, str):
            return _rejected("REQUEST_INVALID")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            return _rejected("RAW_BODY_BASE64_INVALID")

        try:
            secrets, route, identity, evaluator, registry_root, journal = _runtime(env, repo_root=repo_root)
        except ValueError as exc:
            code = str(exc) if str(exc) in {"CONFIGURATION_UNAVAILABLE", "CONFIGURATION_INVALID"} else "CONFIGURATION_INVALID"
            return _rejected(code)
        except Exception:
            return _rejected("AUTHORITY_SERVICE_UNAVAILABLE")

        adapter = InboundAdapter(
            secrets=secrets,
            route=route,
            identity=identity,
            evaluator=evaluator,
            registry_root=registry_root,
            journal=journal,
        )
        result = asdict(adapter.handle(raw, normalized_headers, method=method))
        result["external_effect"] = "NOT_EXECUTED"
        return result
    except Exception:
        return _rejected("INGEST_INTERNAL_ERROR")


def main() -> int:
    try:
        raw_stdin = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
        if not raw_stdin or len(raw_stdin) > MAX_STDIN_BYTES:
            result = _rejected("REQUEST_TOO_LARGE")
        else:
            try:
                request = json.loads(raw_stdin.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                request = None
            result = run_ingest(request)
    except Exception:
        result = _rejected("INGEST_INTERNAL_ERROR")
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
