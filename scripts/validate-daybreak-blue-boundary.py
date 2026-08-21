#!/usr/bin/env python3
"""Validate the fail-closed external-dispatch and platform-startup boundary.

This is a static/runtime contract check, not a penetration test. It verifies that
untrusted public GitHub activity cannot directly authorize model-spend dispatch
and that the Cloud Run image cannot start cost-incurring routes without an
explicit authentication secret.
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
    }

    violations = sorted(name for name, passed in checks.items() if not passed)
    body: dict[str, object] = {
        "schema_version": "1.0.0",
        "receipt_kind": RECEIPT_KIND,
        "outcome": "ADMITTED" if not violations else "DENIED",
        "authority": "EVIDENCE_ONLY",
        "checks": checks,
        "violation_count": len(violations),
        "violations": violations,
        "artifacts": {
            ".github/workflows/agent-dispatch.yml": _sha256(WORKFLOW),
            "vertex/Dockerfile": _sha256(DOCKERFILE),
            "vertex/startup_guard.py": _sha256(STARTUP_GUARD),
        },
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
