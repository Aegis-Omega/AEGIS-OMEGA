"""Provider-neutral execution-identity bootstrap for the AEGIS MCP surface.

The bootstrap binds a provider/model/session to the live repository HEAD,
commit-bound authority roots, exact requested action and current organism state.
It never creates approvals, authority signer keys or policy decisions.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from agents.organism import GENESIS, OrganismStore, default_store_path
from harness.sdk.sovereign_execution import (
    ExecutionIdentityEnvelope,
    canonical_hash,
    compute_workspace_binding,
    git_head,
    git_remote,
    load_capability_registry_from_commit,
    load_policy_from_commit,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _branch_ref(root: Path, source_commit: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    branch = result.stdout.strip() if result.returncode == 0 else "HEAD"
    return f"refs/heads/{branch}" if branch and branch != "HEAD" else f"detached:{source_commit[:16]}"


def _approval_reference() -> str:
    raw = os.environ.get("AEGIS_APPROVAL_GRANT_JSON")
    if not raw:
        return "NONE"
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("APPROVAL_MALFORMED") from exc
    reference = value.get("reference") if isinstance(value, dict) else None
    if not isinstance(reference, str) or not reference:
        raise ValueError("APPROVAL_REFERENCE_MISSING")
    return reference


def _organism_state_root() -> str:
    path = default_store_path()
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        return GENESIS
    return OrganismStore(path).state_root()


def build_provider_session(payload: dict[str, Any]) -> dict[str, Any]:
    provider = payload["provider"]
    model = payload["model"]
    session = payload["session"]
    action_class = payload["action_class"]
    authority_domain = payload["authority_domain"]
    requested_capability = payload["requested_capability"]
    tool = payload["tool"]
    target = payload["target"]
    action = payload["action"]
    if not isinstance(action, dict):
        raise ValueError("ACTION_MUST_BE_OBJECT")

    source_commit = git_head(REPO_ROOT)
    repository_identity = git_remote(REPO_ROOT)
    policy, policy_root = load_policy_from_commit(
        repository_root=REPO_ROOT,
        source_commit=source_commit,
        policy_path="harness/policies/consequence-policy.v1.json",
    )
    registry, skills_root, registry_root = load_capability_registry_from_commit(
        repository_root=REPO_ROOT,
        source_commit=source_commit,
        skill_tree_path="harness/skill_tree.json",
        capability_map_path="harness/policies/capability-map.v1.json",
    )
    del policy
    if requested_capability not in registry:
        raise ValueError("UNMAPPED_CAPABILITY")

    approval_reference = _approval_reference()
    workspace_binding = compute_workspace_binding(
        repository_remote=repository_identity,
        repository_root=".",
        project_identity="AEGIS-OMEGA",
        source_commit=source_commit,
        operator_authorization=approval_reference,
    )
    state_root = _organism_state_root()
    action_digest = canonical_hash("AEGIS_REQUESTED_ACTION_V1", action)
    input_digest = canonical_hash(
        "AEGIS_PROVIDER_ACTION_INPUT_V1",
        {
            "provider": provider,
            "model": model,
            "session": session,
            "action_class": action_class,
            "authority_domain": authority_domain,
            "requested_capability": requested_capability,
            "tool": tool,
            "target": target,
            "action_digest": action_digest,
            "state_root": state_root,
        },
    )
    nonce_root = canonical_hash(
        "AEGIS_PROVIDER_SESSION_NONCE_V1",
        {
            "source_commit": source_commit,
            "provider": provider,
            "model": model,
            "session": session,
            "tool": tool,
            "action_digest": action_digest,
            "state_root": state_root,
        },
    )
    identity = ExecutionIdentityEnvelope(
        schema_version="1.0.0",
        repository_identity=repository_identity,
        repository_root=".",
        source_commit=source_commit,
        branch_or_ref=_branch_ref(REPO_ROOT, source_commit),
        project_identity="AEGIS-OMEGA",
        workspace_root=".",
        workspace_binding=workspace_binding,
        parent_state_root=state_root,
        skills_root=skills_root,
        registry_root=registry_root,
        policy_root=policy_root,
        actor_class="provider-agent",
        actor_identity=f"provider:{provider}",
        model_identity=f"model:{model}",
        session_identity=f"session:{session}",
        physical_executor="executor:aegis-mcp",
        tool_identity=tool,
        workflow_identity="workflow:cross-provider-organism",
        authority_domain=authority_domain,
        requested_capability=requested_capability,
        observed_authority="0.000000",
        approval_reference=approval_reference,
        input_digest=input_digest,
        action_digest=action_digest,
        expected_pre_state=state_root,
        deterministic_nonce=f"nonce:{nonce_root}",
    )
    # Validation is deliberately performed before any result is returned.
    identity_root = identity.root
    workspace = {
        "actual_cwd": str(REPO_ROOT),
        "remote_origin": repository_identity,
        "mutation_target": str(REPO_ROOT / payload.get("mutation_target", ".")),
        "path_views": {},
    }
    return {
        "identity": asdict(identity),
        "identity_root": identity_root,
        "workspace": workspace,
        "state_root": state_root,
        "capability": requested_capability,
        "authority": "IDENTITY_ONLY_NOT_AUTHORIZATION",
    }
