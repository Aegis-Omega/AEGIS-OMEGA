"""
AEGIS-Ω Agent Coordinator
"My own company of AI agents with AEGIS as the wrapper."

Orchestrates the five-agent ecosystem via RALPH loops.
All inference goes through the constitutional proxy (POST /v1/messages).
All memory persists in Redis. All communication via EventEnvelope (Law of Silence).

AdaptivePower(T) ≤ ReplayVerifiability(T) — the coordinator itself is governed.

Usage:
    python -m agents.coordinator run --role engineering --task "diagnose CI failure on PR #136"
    python -m agents.coordinator run --role biz_dev --task "draft Anthropic partnership email"
    python -m agents.coordinator dispatch --event github_pr_comment --payload '{"body": "..."}'
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

import httpx
import redis.asyncio as aioredis
import yaml


# ── Config ────────────────────────────────────────────────────────────────────

_ROOT = os.path.dirname(os.path.abspath(__file__))
PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8080")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DEFAULT_MODEL = os.environ.get("AEGIS_DEFAULT_MODEL", "claude-opus-4-8")
EVENTBUS_CHANNEL = "aegis:events"


# ── Agent roles ───────────────────────────────────────────────────────────────

class AgentRole(str, Enum):
    ENGINEERING = "engineering"
    BIZ_DEV = "biz_dev"
    MARKETING = "marketing"
    COMPLIANCE = "compliance"
    FINANCE = "finance"


# ── EventEnvelope (Law of Silence) ───────────────────────────────────────────

@dataclass
class EventEnvelope:
    """All inter-agent communication is mediated through this envelope."""
    event_id: str
    source_role: str
    target_role: str | None   # None = broadcast
    event_type: str
    payload: dict
    sequence: int
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_json(self) -> str:
        return json.dumps(
            {
                "event_id": self.event_id,
                "source_role": self.source_role,
                "target_role": self.target_role,
                "event_type": self.event_type,
                "payload": self.payload,
                "sequence": self.sequence,
                "timestamp_ms": self.timestamp_ms,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, data: str) -> "EventEnvelope":
        d = json.loads(data)
        return cls(**d)


# ── Task dataclass ────────────────────────────────────────────────────────────

@dataclass
class AgentTask:
    task_id: str
    role: AgentRole
    instruction: str
    context: dict = field(default_factory=dict)
    conversation_history: list[dict] = field(default_factory=list)
    max_ralph_cycles: int = 5


@dataclass
class AgentResult:
    task_id: str
    role: AgentRole
    output: str
    governance: dict
    ralph_cycles: int
    duration_ms: int
    is_valid: bool


# ── Memory — per-agent Redis namespace ───────────────────────────────────────

class AgentMemory:
    def __init__(self, redis: aioredis.Redis, namespace: str):
        self.redis = redis
        self.ns = namespace

    async def load_history(self, limit: int = 20) -> list[dict]:
        raw = await self.redis.lrange(f"{self.ns}:history", -limit, -1)
        return [json.loads(r) for r in raw]

    async def append_history(self, role: str, content: str) -> None:
        entry = json.dumps({"role": role, "content": content, "ts": int(time.time())})
        await self.redis.rpush(f"{self.ns}:history", entry)
        await self.redis.ltrim(f"{self.ns}:history", -100, -1)

    async def get_state(self) -> dict:
        raw = await self.redis.get(f"{self.ns}:state")
        return json.loads(raw) if raw else {}

    async def set_state(self, state: dict) -> None:
        await self.redis.set(f"{self.ns}:state", json.dumps(state, sort_keys=True))

    async def increment_task_count(self) -> int:
        return await self.redis.incr(f"{self.ns}:task_count")


# ── Agent definition loader ───────────────────────────────────────────────────

def _load_agent_defs() -> dict:
    path = os.path.join(_ROOT, "agents.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


# ── Constitutional proxy client ───────────────────────────────────────────────

class ProxyClient:
    def __init__(self, base_url: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def messages(
        self,
        messages: list[dict],
        system: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 4096,
    ) -> dict:
        resp = await self.client.post(
            f"{self.base_url}/v1/messages",
            json={
                "model": model,
                "system": system,
                "messages": messages,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def certify(self) -> dict:
        resp = await self.client.get(f"{self.base_url}/v1/audit/certify")
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        await self.client.aclose()


# ── RALPH loop ────────────────────────────────────────────────────────────────

async def _ralph_cycle(
    agent_def: dict,
    task: AgentTask,
    memory: AgentMemory,
    proxy: ProxyClient,
    cycle: int,
) -> tuple[str, dict]:
    """One RALPH cycle: Read → Assess → Lock → Propagate → Harmonize."""

    # READ — load agent memory + conversation history
    history = await memory.load_history()
    messages: list[dict] = []

    # Seed with prior conversation if continuing
    for h in history[-10:]:  # last 10 turns
        messages.append({"role": h["role"], "content": h["content"]})

    # Inject task instruction
    if cycle == 0:
        messages.append({"role": "user", "content": task.instruction})
    else:
        # Subsequent cycles: pass prior output back for continuation
        messages.append({
            "role": "user",
            "content": (
                f"[RALPH cycle {cycle}] Continue. Review your previous output and "
                "complete any open ASSESS/LOCK/PROPAGATE steps. "
                "If fully harmonized, reply with HARMONIZE_COMPLETE."
            ),
        })

    # ASSESS + LOCK — call constitutional proxy (governance enforced at the proxy)
    system = agent_def.get("system_prompt", "")
    model = agent_def.get("model", DEFAULT_MODEL)
    max_tokens = agent_def.get("max_tokens", 4096)

    result = await proxy.messages(messages, system, model, max_tokens)

    output_text = ""
    for block in result.get("content", []):
        if block.get("type") == "text":
            output_text += block["text"]

    governance = result.get("governance", {})

    # PROPAGATE — store exchange in memory
    await memory.append_history("user", messages[-1]["content"])
    await memory.append_history("assistant", output_text)

    # HARMONIZE — update agent state
    state = await memory.get_state()
    state["last_task_id"] = task.task_id
    state["last_cycle"] = cycle
    state["last_is_valid"] = governance.get("is_valid", True)
    await memory.set_state(state)

    return output_text, governance


async def run_agent(task: AgentTask) -> AgentResult:
    """Run an agent through RALPH loops until completion or max_cycles."""
    defs = _load_agent_defs()
    agent_def = defs["agents"][task.role.value]

    redis_conn = await aioredis.from_url(REDIS_URL, decode_responses=True)
    memory = AgentMemory(redis_conn, agent_def["memory_namespace"])
    proxy = ProxyClient(PROXY_URL)

    t_start = time.time()
    task_count = await memory.increment_task_count()

    final_output = ""
    final_governance: dict = {}
    cycles = 0

    try:
        for cycle in range(task.max_ralph_cycles):
            cycles = cycle + 1
            output, governance = await _ralph_cycle(agent_def, task, memory, proxy, cycle)
            final_output = output
            final_governance = governance

            # Terminal condition: agent declared harmonization complete
            if "HARMONIZE_COMPLETE" in output or cycle == task.max_ralph_cycles - 1:
                break

    finally:
        await proxy.aclose()
        await redis_conn.aclose()

    duration_ms = int((time.time() - t_start) * 1000)
    return AgentResult(
        task_id=task.task_id,
        role=task.role,
        output=final_output,
        governance=final_governance,
        ralph_cycles=cycles,
        duration_ms=duration_ms,
        is_valid=final_governance.get("is_valid", True),
    )


# ── Event dispatcher — routes external events to agents ──────────────────────

EVENT_ROUTING: dict[str, list[AgentRole]] = {
    "github_pr_opened":      [AgentRole.ENGINEERING],
    "github_pr_comment":     [AgentRole.ENGINEERING],
    "github_issue_opened":   [AgentRole.ENGINEERING],
    "github_ci_failure":     [AgentRole.ENGINEERING],
    "github_ci_success":     [AgentRole.ENGINEERING],
    "partnership_inquiry":   [AgentRole.BIZ_DEV],
    "enterprise_lead":       [AgentRole.BIZ_DEV, AgentRole.MARKETING],
    "compliance_request":    [AgentRole.COMPLIANCE],
    "contract_review":       [AgentRole.COMPLIANCE],
    "content_request":       [AgentRole.MARKETING],
    "cost_alert":            [AgentRole.FINANCE],
    "revenue_milestone":     [AgentRole.FINANCE, AgentRole.BIZ_DEV],
    "anthropic_partnership": [AgentRole.BIZ_DEV, AgentRole.COMPLIANCE, AgentRole.ENGINEERING],
}


async def dispatch_event(event_type: str, payload: dict) -> list[AgentResult]:
    """Route an external event to the appropriate agents and run them."""
    roles = EVENT_ROUTING.get(event_type, [AgentRole.ENGINEERING])
    results = []

    for role in roles:
        task_id = str(uuid.uuid4())
        instruction = _event_to_instruction(event_type, payload, role)
        task = AgentTask(
            task_id=task_id,
            role=role,
            instruction=instruction,
            context={"event_type": event_type, "payload": payload},
            max_ralph_cycles=3,
        )
        result = await run_agent(task)
        results.append(result)

    return results


def _event_to_instruction(event_type: str, payload: dict, role: AgentRole) -> str:
    """Convert an event + payload into a concrete agent instruction."""
    templates = {
        "github_pr_opened": (
            "A new PR has been opened: {title} (#{number}). "
            "Review the changes, assess architectural impact, and provide actionable feedback."
        ),
        "github_ci_failure": (
            "CI failed on branch {branch}. Failures: {failures}. "
            "Diagnose the root cause and propose a fix following the RALPH protocol."
        ),
        "github_pr_comment": (
            "New comment on PR #{number}: '{body}'. "
            "Assess whether action is required and respond accordingly."
        ),
        "partnership_inquiry": (
            "Partnership inquiry received from {company}: '{message}'. "
            "Draft a technically credible response that positions AEGIS as the "
            "constitutional governance layer solving their compliance gap."
        ),
        "enterprise_lead": (
            "Enterprise lead from {company} ({size}): '{interest}'. "
            "Assess fit with AEGIS governance offering and draft outreach."
        ),
        "compliance_request": (
            "Compliance analysis requested: {framework}. "
            "Map AEGIS architecture against the framework requirements and identify gaps."
        ),
        "anthropic_partnership": (
            "Prepare for Anthropic partnership meeting. Context: {context}. "
            "Produce: (1) technical brief on the 5 gaps AEGIS solves, "
            "(2) Vertex AI Model Garden positioning, "
            "(3) Office Gateway integration architecture."
        ),
        "content_request": (
            "Generate content: {content_type} on topic: {topic}. "
            "Target audience: {audience}. Emphasize the hash-chain governance mechanism."
        ),
        "cost_alert": (
            "Cost alert: {service} exceeded budget by {amount}. "
            "Analyze root cause and recommend optimization."
        ),
    }

    template = templates.get(event_type, "Handle event '{event_type}': {payload}")
    try:
        instruction = template.format(event_type=event_type, payload=str(payload), **payload)
    except KeyError:
        instruction = f"Handle {event_type}: {json.dumps(payload, indent=2)}"

    return instruction


# ── CLI ───────────────────────────────────────────────────────────────────────

async def _cli_run(role: str, task: str, cycles: int) -> None:
    agent_role = AgentRole(role)
    task_id = str(uuid.uuid4())
    agent_task = AgentTask(
        task_id=task_id,
        role=agent_role,
        instruction=task,
        max_ralph_cycles=cycles,
    )
    print(f"[coordinator] Running {role.upper()} agent — task_id={task_id[:8]}")
    print(f"[coordinator] Task: {task}")
    print(f"[coordinator] Proxy: {PROXY_URL}")
    print("─" * 60)

    result = await run_agent(agent_task)

    print(f"\n{'─' * 60}")
    print(f"[coordinator] DONE  cycles={result.ralph_cycles}  duration={result.duration_ms}ms")
    print(f"[coordinator] Chain: is_valid={result.is_valid}  "
          f"chain_length={result.governance.get('chain_length', 'n/a')}")
    print(f"\n{result.output}")


async def _cli_dispatch(event_type: str, payload_json: str) -> None:
    payload = json.loads(payload_json)
    print(f"[coordinator] Dispatching event: {event_type}")
    results = await dispatch_event(event_type, payload)
    for r in results:
        print(f"\n[{r.role.value.upper()}] cycles={r.ralph_cycles} is_valid={r.is_valid}")
        print(r.output[:2000])


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="AEGIS Agent Coordinator")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run a single agent task")
    run_p.add_argument("--role", required=True, choices=[r.value for r in AgentRole])
    run_p.add_argument("--task", required=True, help="Task instruction")
    run_p.add_argument("--cycles", type=int, default=3, help="Max RALPH cycles")

    disp_p = sub.add_parser("dispatch", help="Dispatch an event to agents")
    disp_p.add_argument("--event", required=True, help="Event type")
    disp_p.add_argument("--payload", default="{}", help="JSON payload")

    list_p = sub.add_parser("list", help="List available agents and events")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(_cli_run(args.role, args.task, args.cycles))
    elif args.command == "dispatch":
        asyncio.run(_cli_dispatch(args.event, args.payload))
    elif args.command == "list":
        defs = _load_agent_defs()
        print("AGENTS:")
        for name, ag in defs["agents"].items():
            print(f"  {name}: {ag['role']}")
            print(f"    capabilities: {', '.join(ag['capabilities'])}")
        print("\nEVENT ROUTING:")
        for evt, roles in EVENT_ROUTING.items():
            print(f"  {evt} → {[r.value for r in roles]}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
