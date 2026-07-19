"""Governed entry point for the AEGIS agent coordinator.

The implementation remains in :mod:`agents.coordinator_legacy`; this boundary
replaces its neutral routing fallbacks with the evidence-bound V2 authority law.
Unknown, malformed, unobserved, under-validated, or evidence-invalid capability
records receive zero authority and a deterministic denial receipt.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agents import coordinator_legacy as _legacy
from harness.sdk.skill_authority import canonical_bytes, sha256_hex
from harness.sdk.skill_routing import (
    ADMITTED,
    DENIED,
    SkillRoutingReceipt,
    decide_skill_routing,
    record_skill_observation,
)

# Preserve the complete historical coordinator API, including private helpers
# used by existing scripts, before replacing the authority-sensitive symbols.
for _name in dir(_legacy):
    if not _name.startswith("__") and _name not in globals():
        globals()[_name] = getattr(_legacy, _name)

ROLE_RECEIPT_KIND = "AEGIS_COORDINATOR_ROLE_ROUTING_RECEIPT_V1"


@dataclass(frozen=True)
class RoleRoutingReceipt:
    schema_version: str
    receipt_kind: str
    role: str
    outcome: str
    authority_score: float
    capability_receipt_hashes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    receipt_hash: str


class SkillRouter(_legacy.SkillRouter):
    """Coordinator router whose authority semantics are fail-closed."""

    def __init__(
        self,
        *,
        skill_tree_path: str | Path = _legacy.SKILL_TREE_PATH,
        repo_root: str | Path = _legacy._REPO_ROOT,
        capability_map: dict[str, str] | None = None,
    ) -> None:
        self._tree: dict[str, Any] | None = None
        self._skill_tree_path = Path(skill_tree_path)
        self._repo_root = Path(repo_root).resolve()
        self._capability_map = dict(capability_map or _legacy.CAPABILITY_SKILL_MAP)
        self._load_reason_codes: tuple[str, ...] = ()
        self._last_mutation_error: str | None = None

    def _load_tree(self) -> dict[str, Any] | None:
        if self._tree is not None:
            return self._tree

        try:
            raw = self._skill_tree_path.read_text(encoding="utf-8")
        except OSError:
            self._load_reason_codes = ("REGISTRY_FILE_UNAVAILABLE",)
            return None

        try:
            tree = json.loads(raw)
        except json.JSONDecodeError:
            self._load_reason_codes = ("REGISTRY_JSON_MALFORMED",)
            return None

        if not isinstance(tree, dict):
            self._load_reason_codes = ("REGISTRY_ROOT_NOT_OBJECT",)
            return None

        self._tree = tree
        self._load_reason_codes = ()
        return tree

    def reload(self) -> None:
        """Clear cached registry state so the next decision rereads disk."""
        self._tree = None
        self._load_reason_codes = ()

    def _skill_by_id(self, skill_id: str) -> dict[str, Any] | None:
        tree = self._load_tree()
        if tree is None:
            return None
        skills = tree.get("skills")
        if not isinstance(skills, list):
            return None
        for skill in skills:
            if isinstance(skill, dict) and skill.get("skill_id") == skill_id:
                return skill
        return None

    def competency_decision(
        self,
        skill_id: str,
        *,
        capability: str | None = None,
    ) -> SkillRoutingReceipt:
        tree = self._load_tree()
        return decide_skill_routing(
            capability=capability or skill_id,
            skill_id=skill_id,
            skill=self._skill_by_id(skill_id),
            registry=tree,
            repo_root=self._repo_root,
            load_reason_codes=self._load_reason_codes,
        )

    def competency_score(self, skill_id: str) -> float:
        """Return V2 authority score; all unsafe states resolve to zero."""
        return self.competency_decision(skill_id).authority_score

    def capability_decision(self, capability: str) -> SkillRoutingReceipt:
        tree = self._load_tree()
        skill_id = self._capability_map.get(capability)
        skill = self._skill_by_id(skill_id) if skill_id is not None else None
        return decide_skill_routing(
            capability=capability,
            skill_id=skill_id,
            skill=skill,
            registry=tree,
            repo_root=self._repo_root,
            load_reason_codes=self._load_reason_codes,
        )

    def capability_score(self, capability: str) -> float:
        """Resolve capability through the deterministic V2 decision path."""
        return self.capability_decision(capability).authority_score

    def role_routing_receipt(
        self,
        role: "AgentRole",
        task_instruction: str,
        agent_defs: dict[str, Any],
    ) -> RoleRoutingReceipt:
        agent_def = agent_defs.get(role.value, {})
        capabilities = agent_def.get("capabilities", []) if isinstance(agent_def, dict) else []
        reasons: list[str] = []
        decisions: list[SkillRoutingReceipt] = []

        if not isinstance(capabilities, list) or not capabilities:
            reasons.append("NO_DECLARED_CAPABILITIES")
            capabilities = []

        task_lower = task_instruction.lower()
        total = 0.0
        weight = 0.0
        for capability in capabilities:
            if not isinstance(capability, str) or not capability:
                reasons.append("MALFORMED_CAPABILITY")
                continue
            decision = self.capability_decision(capability)
            decisions.append(decision)
            boost = 1.5 if any(
                keyword in task_lower
                for keyword in capability.replace("_", " ").split()
            ) else 1.0
            total += decision.authority_score * boost
            weight += boost

        score = total / weight if weight > 0 else 0.0
        if not any(decision.outcome == ADMITTED for decision in decisions):
            reasons.append("NO_ADMITTED_CAPABILITY")
        if score <= 0.0:
            reasons.append("ZERO_ROLE_AUTHORITY")

        reasons = sorted(set(reasons))
        outcome = ADMITTED if not reasons else DENIED
        if outcome == DENIED:
            score = 0.0

        body = {
            "schema_version": "1.0.0",
            "receipt_kind": ROLE_RECEIPT_KIND,
            "role": role.value,
            "outcome": outcome,
            "authority_score": score,
            "capability_receipt_hashes": tuple(
                decision.receipt_hash for decision in decisions
            ),
            "reason_codes": tuple(reasons),
        }
        receipt_hash = sha256_hex(canonical_bytes({
            "domain": ROLE_RECEIPT_KIND,
            "receipt": body,
        }))
        return RoleRoutingReceipt(**body, receipt_hash=receipt_hash)

    def score_role_for_task(
        self,
        role: "AgentRole",
        task_instruction: str,
        agent_defs: dict[str, Any],
    ) -> float:
        return self.role_routing_receipt(
            role,
            task_instruction,
            agent_defs,
        ).authority_score

    def emit_skill_event(self, capability: str, success: bool) -> None:
        """Record an observation without breaking V2 state or content binding."""
        skill_id = self._capability_map.get(capability)
        tree = self._load_tree()
        if skill_id is None or tree is None:
            self._last_mutation_error = "UNROUTABLE_SKILL_OBSERVATION"
            return

        observed_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
        try:
            updated = record_skill_observation(
                tree,
                skill_id=skill_id,
                success=success,
                observed_at=observed_at,
                repo_root=self._repo_root,
            )
            temporary = self._skill_tree_path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self._skill_tree_path)
        except (OSError, TypeError, ValueError) as exc:
            self._last_mutation_error = type(exc).__name__
            return

        self._tree = updated
        self._last_mutation_error = None


# Patch the implementation module so all historical functions use this boundary.
_legacy.SkillRouter = SkillRouter
_skill_router = SkillRouter()
_legacy._skill_router = _skill_router

_last_dispatch_receipts: tuple[RoleRoutingReceipt, ...] = ()


async def dispatch_event(event_type: str, payload: dict) -> list["AgentResult"]:
    """Dispatch only to roles carrying positive, evidence-bound authority."""
    global _last_dispatch_receipts

    candidate_roles = _legacy.EVENT_ROUTING.get(
        event_type,
        [_legacy.AgentRole.ENGINEERING],
    )
    definitions = _legacy._load_agent_defs()
    agent_defs = definitions.get("agents", {})
    instruction_sample = _legacy._event_to_instruction(
        event_type,
        payload,
        candidate_roles[0],
    )

    indexed_receipts = [
        (
            index,
            role,
            _skill_router.role_routing_receipt(
                role,
                instruction_sample,
                agent_defs,
            ),
        )
        for index, role in enumerate(candidate_roles)
    ]
    _last_dispatch_receipts = tuple(item[2] for item in indexed_receipts)

    admitted = [item for item in indexed_receipts if item[2].outcome == ADMITTED]
    admitted.sort(key=lambda item: (-item[2].authority_score, item[0]))

    results: list[AgentResult] = []
    for _, role, _receipt in admitted:
        task = _legacy.AgentTask(
            task_id=str(_legacy.uuid.uuid4()),
            role=role,
            instruction=_legacy._event_to_instruction(event_type, payload, role),
            context={"event_type": event_type, "payload": payload},
            max_ralph_cycles=3,
        )
        results.append(await _legacy.run_agent(task))
    return results


def last_dispatch_receipts() -> tuple[dict[str, Any], ...]:
    """Return JSON-compatible receipts from the most recent dispatch decision."""
    return tuple(asdict(receipt) for receipt in _last_dispatch_receipts)


_legacy.dispatch_event = dispatch_event
_legacy.last_dispatch_receipts = last_dispatch_receipts


def main() -> None:
    _legacy.main()


if __name__ == "__main__":
    main()
