"""Governed AEGIS coordinator boundary using the single Automaton-3 evaluator.

The historical implementation remains in :mod:`agents.coordinator_legacy`. This
module re-exports its API, but no agent dispatch receives operational authority
from documentation priors or local scoring. The final decision is made only by
``harness.sdk.authority_client.authorize_from_environment``.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agents import coordinator_legacy as _legacy
from harness.sdk.authority_client import authorize_from_environment
from harness.sdk.skill_routing import ADMITTED, DENIED, SkillRoutingReceipt, record_skill_observation

for _name in dir(_legacy):
    if not _name.startswith("__") and _name not in globals():
        globals()[_name] = getattr(_legacy, _name)

ROLE_RECEIPT_KIND = "AEGIS_COORDINATOR_ROLE_ROUTING_RECEIPT_V2"


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
    """Compatibility facade; operational authority comes only from Automaton-3."""

    def __init__(self, *, skill_tree_path: str | Path = _legacy.SKILL_TREE_PATH, repo_root: str | Path = _legacy._REPO_ROOT, capability_map: dict[str, str] | None = None) -> None:
        self._tree: dict[str, Any] | None = None
        self._skill_tree_path = Path(skill_tree_path)
        self._repo_root = Path(repo_root).resolve()
        self._capability_map = dict(capability_map or _legacy.CAPABILITY_SKILL_MAP)
        self._last_mutation_error: str | None = None

    def _central_decision(self, *, role: str, task_instruction: str) -> dict[str, Any]:
        action = {"operation": "agent-dispatch", "role": role, "instruction_digest": __import__("hashlib").sha256(task_instruction.encode("utf-8")).hexdigest()}
        return authorize_from_environment(
            action_class="D1",
            authority_domain="agent:dispatch",
            requested_capability="coordinator.dispatch",
            tool="agents.coordinator:dispatch",
            target=role,
            action=action,
        )

    def competency_decision(self, skill_id: str, *, capability: str | None = None) -> SkillRoutingReceipt:
        decision = self._central_decision(role=skill_id, task_instruction=capability or skill_id)
        score = float(decision.get("authority_score", "0")) if decision.get("outcome") == ADMITTED else 0.0
        body = {
            "schema_version": "2.0.0", "receipt_kind": "AEGIS_COORDINATOR_ROUTING_RECEIPT_V2",
            "capability": capability or skill_id, "skill_id": skill_id,
            "outcome": decision.get("outcome", DENIED), "authority_score": score,
            "observation_state": "CENTRAL_AUTHORITY", "validated_runs": 0,
            "registry_root": None, "registry_receipt_hash": None,
            "reason_codes": tuple(decision.get("denial_codes", [])),
        }
        return SkillRoutingReceipt(**body, receipt_hash=str(decision.get("decision_root")))

    def competency_score(self, skill_id: str) -> float:
        return self.competency_decision(skill_id).authority_score

    def capability_decision(self, capability: str) -> SkillRoutingReceipt:
        return self.competency_decision(self._capability_map.get(capability, capability), capability=capability)

    def capability_score(self, capability: str) -> float:
        return self.capability_decision(capability).authority_score

    def role_routing_receipt(self, role: "AgentRole", task_instruction: str, agent_defs: dict[str, Any]) -> RoleRoutingReceipt:
        decision = self._central_decision(role=role.value, task_instruction=task_instruction)
        outcome = decision.get("outcome", DENIED)
        score = float(decision.get("authority_score", "0")) if outcome == ADMITTED else 0.0
        reasons = tuple(sorted(set(decision.get("denial_codes", []))))
        root = str(decision.get("decision_root"))
        return RoleRoutingReceipt("2.0.0", ROLE_RECEIPT_KIND, role.value, outcome, score, (root,), reasons, root)

    def score_role_for_task(self, role: "AgentRole", task_instruction: str, agent_defs: dict[str, Any]) -> float:
        return self.role_routing_receipt(role, task_instruction, agent_defs).authority_score

    def emit_skill_event(self, capability: str, success: bool) -> None:
        """Record telemetry only; an observation never grants authority by itself."""
        skill_id = self._capability_map.get(capability)
        try:
            tree = json.loads(self._skill_tree_path.read_text(encoding="utf-8"))
            if skill_id is None:
                raise ValueError("unmapped capability")
            observed_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
            updated = record_skill_observation(tree, skill_id=skill_id, success=success, observed_at=observed_at, repo_root=self._repo_root)
            temporary = self._skill_tree_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, self._skill_tree_path)
            self._last_mutation_error = None
        except (OSError, TypeError, ValueError) as exc:
            self._last_mutation_error = type(exc).__name__


_legacy.SkillRouter = SkillRouter
_skill_router = SkillRouter()
_legacy._skill_router = _skill_router
_last_dispatch_receipts: tuple[RoleRoutingReceipt, ...] = ()


async def dispatch_event(event_type: str, payload: dict) -> list["AgentResult"]:
    global _last_dispatch_receipts
    candidate_roles = _legacy.EVENT_ROUTING.get(event_type, [_legacy.AgentRole.ENGINEERING])
    definitions = _legacy._load_agent_defs(); agent_defs = definitions.get("agents", {})
    instruction_sample = _legacy._event_to_instruction(event_type, payload, candidate_roles[0])
    indexed = [(index, role, _skill_router.role_routing_receipt(role, instruction_sample, agent_defs)) for index, role in enumerate(candidate_roles)]
    _last_dispatch_receipts = tuple(item[2] for item in indexed)
    admitted = [item for item in indexed if item[2].outcome == ADMITTED]
    admitted.sort(key=lambda item: (-item[2].authority_score, item[0]))
    results: list[AgentResult] = []
    for _, role, _receipt in admitted:
        task = _legacy.AgentTask(task_id=str(_legacy.uuid.uuid4()), role=role, instruction=_legacy._event_to_instruction(event_type, payload, role), context={"event_type": event_type, "payload": payload}, max_ralph_cycles=3)
        results.append(await _legacy.run_agent(task))
    return results


def last_dispatch_receipts() -> tuple[dict[str, Any], ...]:
    return tuple(asdict(receipt) for receipt in _last_dispatch_receipts)


_legacy.dispatch_event = dispatch_event
_legacy.last_dispatch_receipts = last_dispatch_receipts


def main() -> None:
    _legacy.main()


if __name__ == "__main__":
    main()
