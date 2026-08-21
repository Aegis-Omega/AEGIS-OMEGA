#!/usr/bin/env python3
"""Validate the fail-closed Daybreak Blue security boundary.

This is a local contract verifier, not an authority producer. It checks the
public-event dispatch boundary, authenticated production startup, hardened
service overlay, and the presence of the concurrent/trim-aware audit-chain v2.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Callable

RECEIPT_KIND = "AEGIS_DAYBREAK_BLUE_BOUNDARY_RECEIPT_V1"
ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "agent-dispatch.yml"
DOCKERFILE = ROOT / "vertex" / "Dockerfile"
STARTUP_GUARD = ROOT / "vertex" / "startup_guard.py"
SECURE_SERVE = ROOT / "vertex" / "secure_serve.py"
AUDIT_CHAIN = ROOT / "vertex" / "audit_chain_v2.py"
AUTO_GATE = ROOT / "scripts" / "auto-gate.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_guard() -> ModuleType:
    spec = importlib.util.spec_from_file_location("aegis_startup_guard", STARTUP_GUARD)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load vertex/startup_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _raises_system_exit(fn: Callable[[], object]) -> bool:
    try:
        fn()
    except SystemExit:
        return True
    return False


def validate() -> dict[str, object]:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    guard_text = STARTUP_GUARD.read_text(encoding="utf-8")
    secure_text = SECURE_SERVE.read_text(encoding="utf-8")
    audit_text = AUDIT_CHAIN.read_text(encoding="utf-8")
    auto_gate_text = AUTO_GATE.read_text(encoding="utf-8")
    guard = _load_guard()

    checks: dict[str, bool] = {
        "issue_open_is_not_dispatch_trigger": "types: [opened, labeled]" not in workflow
        and "types: [labeled]" in workflow,
        "issue_dispatch_requires_explicit_label": "aegis-dispatch-approved" in workflow,
        "pr_and_comment_dispatch_require_trusted_association": "OWNER|MEMBER|COLLABORATOR" in workflow
        and "PR_ASSOCIATION" in workflow
        and "COMMENT_ASSOCIATION" in workflow,
        "workflow_run_rejects_fork_origin": "WF_HEAD_REPOSITORY" in workflow
        and "CURRENT_REPOSITORY" in workflow
        and '[ "$WF_HEAD_REPOSITORY" != "$CURRENT_REPOSITORY" ]' in workflow,
        "untrusted_payload_is_compact_json": "jq -cn" in workflow
        and "printf 'payload=%s\\n'" in workflow,
        "dispatch_requires_secret": "secrets.AEGIS_PLATFORM_API_KEY" in workflow
        and 'if [ -z "$AEGIS_PLATFORM_API_KEY" ]' in workflow,
        "dispatch_authenticates_to_proxy": 'x-api-key: $AEGIS_PLATFORM_API_KEY' in workflow,
        "dispatch_requires_https": 'https://*)' in workflow and "--proto '=https'" in workflow,
        "dispatch_network_call_is_bounded": "--fail-with-body" in workflow
        and "--connect-timeout 5" in workflow
        and "--max-time 30" in workflow,
        "docker_executes_startup_guard": "COPY vertex/startup_guard.py /app/startup_guard.py" in dockerfile
        and 'CMD ["python", "startup_guard.py"]' in dockerfile,
        "docker_packages_security_overlay": "COPY vertex/secure_serve.py /app/secure_serve.py" in dockerfile
        and "COPY vertex/audit_chain_v2.py /app/audit_chain_v2.py" in dockerfile,
        "startup_guard_starts_security_overlay": '"secure_serve:app"' in guard_text,
        "startup_guard_has_no_network_dependency": "import requests" not in guard_text
        and "import httpx" not in guard_text,
        "missing_platform_key_fails_closed": _raises_system_exit(
            lambda: guard.require_platform_api_key({})
        ),
        "short_platform_key_fails_closed": _raises_system_exit(
            lambda: guard.require_platform_api_key({"PLATFORM_API_KEY": "too-short"})
        ),
        "strong_platform_key_is_accepted": guard.require_platform_api_key(
            {"PLATFORM_API_KEY": "A" * 32}
        )
        == "A" * 32,
        "invalid_port_fails_closed": _raises_system_exit(
            lambda: guard.validated_port({"PORT": "70000"})
        ),
        "valid_port_is_accepted": guard.validated_port({"PORT": "8080"}) == "8080",
        "sensitive_operational_routes_are_protected": '"/metrics"' in secure_text
        and '"/v1/audit"' in secure_text
        and '"/agents/roles"' in secure_text
        and "hmac.compare_digest" in secure_text,
        "audit_chain_uses_redis_cas": "_APPEND_CAS_LUA" in audit_text
        and "expected_seq" in audit_text
        and "expected_tail" in audit_text
        and "AUDIT_CHAIN_CONTENTION_RETRY_EXHAUSTED" in audit_text,
        "audit_chain_has_trim_anchor": "anchor_key" in audit_text
        and "previous_entry_hash" in audit_text
        and "next_sequence" in audit_text
        and "LTRIM" in audit_text,
        "audit_chain_rejects_unprovable_legacy_trim": "AUDIT_CHAIN_LEGACY_TRIMMED_WITHOUT_ANCHOR" in audit_text,
        "auto_gate_has_no_shell_execution": "shell=True" not in auto_gate_text,
        "auto_gate_requires_explicit_budget": 'parser.add_argument("--budget", type=float, required=True' in auto_gate_text,
        "auto_gate_does_not_stage_repository_wide": '"add", "-A"' not in auto_gate_text
        and '"git", "add", "--", *exact_paths' in auto_gate_text,
        "auto_gate_blocks_canonical_push": 'branch in {"main", "master"}' in auto_gate_text,
    }

    violations = sorted(name for name, passed in checks.items() if not passed)
    artifacts = {
        ".github/workflows/agent-dispatch.yml": _sha256(WORKFLOW),
        "scripts/auto-gate.py": _sha256(AUTO_GATE),
        "vertex/Dockerfile": _sha256(DOCKERFILE),
        "vertex/startup_guard.py": _sha256(STARTUP_GUARD),
        "vertex/secure_serve.py": _sha256(SECURE_SERVE),
        "vertex/audit_chain_v2.py": _sha256(AUDIT_CHAIN),
    }
    body: dict[str, object] = {
        "schema_version": "1.1.0",
        "receipt_kind": RECEIPT_KIND,
        "outcome": "ADMITTED" if not violations else "DENIED",
        "authority": "EVIDENCE_ONLY",
        "checks": checks,
        "violation_count": len(violations),
        "violations": violations,
        "artifacts": artifacts,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    body["receipt_hash"] = hashlib.sha256(
        RECEIPT_KIND.encode() + b"\x00" + canonical
    ).hexdigest()
    return body


def main() -> int:
    receipt = validate()
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["outcome"] == "ADMITTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
