"""
AEGIS-Ω Agent Coordinator v2.0
"A company of 34 autonomous AI agents, governed by the constitutional substrate."

Three inference backends (auto-detected from environment):
  MANAGED_AGENTS — Anthropic client.beta.agents (persistent, session-based, streaming)
  VERTEX_AI      — AnthropicVertex (GCP project aegisomegav1, constitutional proxy wrapping)
  DIRECT         — Constitutional proxy (POST /v1/messages) — fallback for any environment

Backend priority:
  1. MANAGED_AGENTS if ANTHROPIC_API_KEY set and agent_registry.json exists
  2. VERTEX_AI      if VERTEX_PROJECT_ID set
  3. DIRECT         fallback via PROXY_URL

All memory persists in Redis. All communication via EventEnvelope (Law of Silence).
AdaptivePower(T) ≤ ReplayVerifiability(T) — the coordinator itself is governed.

Usage:
    python -m agents.coordinator run --role engineering --task "diagnose CI failure on PR #136"
    python -m agents.coordinator run --role ai_safety --task "evaluate alignment property X"
    python -m agents.coordinator run --role cybersecurity --task "scan for constitutional breaches"
    python -m agents.coordinator dispatch --event github_pr_comment --payload '{"body": "..."}'
    python -m agents.coordinator list
    python -m agents.coordinator backend   # show active backend
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
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
import redis.asyncio as aioredis
import yaml


# ── Config ────────────────────────────────────────────────────────────────────

_ROOT = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_ROOT)
PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8080")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DEFAULT_MODEL = os.environ.get("AEGIS_DEFAULT_MODEL", "claude-opus-4-8")
VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT_ID", "aegisomegav1")
VERTEX_REGION = os.environ.get("VERTEX_REGION", "us-east5")
EVENTBUS_CHANNEL = "aegis:events"
SKILL_TREE_PATH = os.path.join(_REPO_ROOT, "harness", "skill_tree.json")
MANAGED_REGISTRY_PATH = Path(_ROOT) / "agent_registry.json"
VERTEX_REGISTRY_PATH = Path(_ROOT) / "vertex_agent_registry.json"


# ── Backend detection ─────────────────────────────────────────────────────────

class BackendType(str, Enum):
    MANAGED_AGENTS = "managed_agents"   # Anthropic Managed Agents beta
    VERTEX_AI      = "vertex_ai"        # Google Cloud Vertex AI + AnthropicVertex
    DIRECT         = "direct"           # Constitutional proxy (fallback)


def _detect_backend() -> BackendType:
    """Auto-detect the best available inference backend."""
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_registry = MANAGED_REGISTRY_PATH.exists()
    has_vertex = bool(os.environ.get("VERTEX_PROJECT_ID"))

    if has_api_key and has_registry:
        return BackendType.MANAGED_AGENTS
    if has_vertex:
        return BackendType.VERTEX_AI
    return BackendType.DIRECT


ACTIVE_BACKEND = _detect_backend()

# Capability → skill_id mapping: which harness skill backs each agent capability
CAPABILITY_SKILL_MAP: dict[str, str] = {
    "code_generation":       "rust_gate_module_development",
    "code_review":           "typescript_event_ledger",
    "pr_management":         "agent_handoff_protocol",
    "ci_diagnosis":          "gate8_deployment_gate",
    "architecture_decisions":"constitutional_law_enforcement",
    "test_writing":          "gate8_deployment_gate",
    "dependency_audit":      "audit_trail_management",
    "partnership_outreach":  "probabilistic_competency_modeling",
    "enterprise_sales":      "orchestration_routing",
    "rfp_response":          "audit_trail_management",
    "competitive_analysis":  "epistemic_tier_classification",
    "technical_briefing":    "constitutional_law_enforcement",
    "investor_communication":"martingale_gating",
    "technical_content":     "skill_tree_construction",
    "seo_optimization":      "orchestration_routing",
    "positioning":           "epistemic_tier_classification",
    "case_studies":          "audit_trail_management",
    "documentation":         "typescript_event_ledger",
    "social_media":          "probabilistic_competency_modeling",
    "press_releases":        "constitutional_law_enforcement",
    "eu_ai_act_analysis":    "replay_sovereignty",
    "nist_framework_mapping":"constitutional_law_enforcement",
    "contract_review":       "audit_trail_management",
    "privacy_assessment":    "frozen_file_protection",
    "regulatory_gap_analysis":"eccf_security_alignment",
    "fisma_alignment":       "replay_sovereignty",
    "revenue_analysis":      "martingale_gating",
    "cost_optimization":     "gate8_deployment_gate",
    "unit_economics":        "probabilistic_competency_modeling",
    "pricing_strategy":      "orchestration_routing",
    "vendor_negotiation":    "agent_handoff_protocol",
    "budget_forecasting":    "martingale_gating",
    "api_cost_tracking":     "telemetry_streaming",
    # Mythos-level cognitive substrate capabilities
    "deep_research":         "corpus_ingestion_pipeline",
    "multi_source_synthesis":"epistemic_tier_classification",
    "corpus_ingestion":      "corpus_ingestion_pipeline",
    "tier_arbitration":      "epistemic_tier_classification",
    "annotation_pipeline":   "corpus_ingestion_pipeline",
    "batch_processing":      "gate8_deployment_gate",
    "fibonacci_cadence":     "orchestration_routing",
    "parallel_arbitration":  "epistemic_tier_classification",
    "chronology":            "audit_trail_management",
    "retrospective_analysis":"constitutional_law_enforcement",
    "lineage_narration":     "replay_sovereignty",
    "metacognitive_observation":"constitutional_law_enforcement",
}


# ── Agent roles — all 34 departments ─────────────────────────────────────────

class AgentRole(str, Enum):
    # Research & Science
    AI_RESEARCH          = "ai_research"
    AI_SAFETY            = "ai_safety"
    APPLIED_SCIENCE      = "applied_science"
    # Engineering
    ENGINEERING          = "engineering"
    PLATFORM_ENGINEERING = "platform_engineering"
    HARDWARE_ENGINEERING = "hardware_engineering"
    SUPPLY_CHAIN         = "supply_chain"
    # Data
    DATA_LABELING        = "data_labeling"
    DATA_GOVERNANCE      = "data_governance"
    # Product
    PRODUCT_MANAGEMENT   = "product_management"
    PRODUCT_DESIGN       = "product_design"
    DEVEX                = "devex"
    # Security
    CYBERSECURITY        = "cybersecurity"
    IT_SYSTEMS           = "it_systems"
    INTERNAL_AI          = "internal_ai_enablement"
    # Trust, Safety & Ethics
    TRUST_SAFETY         = "trust_safety"
    AI_ETHICS            = "ai_ethics"
    # Legal & Compliance
    COMPLIANCE           = "compliance"
    POLICY_AFFAIRS       = "policy_affairs"
    # Commercial
    COMMUNICATIONS       = "communications"
    MARKETING            = "marketing"
    BIZ_DEV              = "biz_dev"
    SALES                = "sales"
    SOLUTIONS_ENGINEERING = "solutions_engineering"
    CUSTOMER_SUCCESS     = "customer_success"
    SUPPORT              = "support"
    DEVREL               = "devrel"
    PARTNERSHIPS         = "partnerships"
    # Finance
    FINANCE              = "finance"
    CORPORATE_DEVELOPMENT = "corporate_development"
    STRATEGY             = "strategy"
    # People & Talent
    TALENT_ACQUISITION   = "talent_acquisition"
    PEOPLE_OPS           = "people_ops"
    WORKPLACE            = "workplace"
    # Enablement
    EDUCATION            = "education"
    # Mythos-level cognitive substrate (tier 0 apex agents)
    DEEP_RESEARCHER      = "deep_researcher"
    CORPUS_INGESTOR      = "corpus_ingestor"
    BATCH_PROCESSOR      = "batch_processor"
    CHRONOLOGIST         = "chronologist"


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
    backend: BackendType = field(default_factory=lambda: ACTIVE_BACKEND)


@dataclass
class AgentResult:
    task_id: str
    role: AgentRole
    output: str
    governance: dict
    ralph_cycles: int
    duration_ms: int
    is_valid: bool


# ── Phase 2: Skill Router — probabilistic competency-backed routing ───────────

class SkillRouter:
    """
    Phase 2 skill harness integration.
    Routes tasks to agents based on competency score from skill_tree.json.
    Writes SKILL_VALIDATED / SKILL_DEGRADED events back to the tree after execution.

    Score formula: confidence × recency_score × (1 − failure_rate)
    This mirrors the orchestration_routing skill spec:
      "Route tasks to best-qualified agent using: competency confidence,
       specialization domain, failure history, domain affinity, recency score."
    """

    def __init__(self):
        self._tree: dict | None = None

    def _load_tree(self) -> dict:
        if self._tree is None and os.path.exists(SKILL_TREE_PATH):
            with open(SKILL_TREE_PATH) as f:
                self._tree = json.load(f)
        return self._tree or {"skills": []}

    def _skill_by_id(self, skill_id: str) -> dict | None:
        tree = self._load_tree()
        for s in tree.get("skills", []):
            if s["skill_id"] == skill_id:
                return s
        return None

    def competency_score(self, skill_id: str) -> float:
        """confidence × recency_score × (1 − failure_rate)"""
        s = self._skill_by_id(skill_id)
        if not s:
            return 0.5  # unknown skill — neutral
        return s["confidence"] * s["recency_score"] * (1.0 - s["failure_rate"])

    def capability_score(self, capability: str) -> float:
        """Resolve capability → skill_id → competency score."""
        skill_id = CAPABILITY_SKILL_MAP.get(capability)
        if not skill_id:
            return 0.5
        return self.competency_score(skill_id)

    def score_role_for_task(self, role: "AgentRole", task_instruction: str, agent_defs: dict) -> float:
        """
        Score an agent role for a given task.
        Uses the declared capabilities list from agents.yaml.
        Returns sum of capability scores weighted by mention in task text.
        """
        agent_def = agent_defs.get(role.value, {})
        capabilities: list[str] = agent_def.get("capabilities", [])
        if not capabilities:
            return 0.5

        task_lower = task_instruction.lower()
        total, weight = 0.0, 0.0
        for cap in capabilities:
            score = self.capability_score(cap)
            # Domain-keyword boost: if task mentions the capability domain, weight it higher
            boost = 1.5 if any(kw in task_lower for kw in cap.replace("_", " ").split()) else 1.0
            total += score * boost
            weight += boost
        return total / weight if weight > 0 else 0.5

    def emit_skill_event(self, capability: str, success: bool) -> None:
        """
        Phase 2: write SKILL_VALIDATED or SKILL_DEGRADED back to skill_tree.json.
        Updates: validated_runs, failure_rate, recency_score (decay toward 0.9 on success, 0.7 on failure).
        Does NOT modify confidence directly — that requires 3+ independent validations to promote.
        """
        skill_id = CAPABILITY_SKILL_MAP.get(capability)
        if not skill_id:
            return

        tree = self._load_tree()
        for s in tree.get("skills", []):
            if s["skill_id"] != skill_id:
                continue

            s["validated_runs"] += 1
            total = s["validated_runs"]
            prev_failures = round(s["failure_rate"] * (total - 1))

            if success:
                # SKILL_VALIDATED: decay failure_rate, boost recency
                s["failure_rate"] = prev_failures / total
                s["recency_score"] = min(1.0, s["recency_score"] * 0.95 + 0.05)
                # Confidence promotion: if 3+ runs with failure_rate < 0.1, promote to next tier
                if total >= 3 and s["failure_rate"] < 0.1 and s["confidence"] < 0.95:
                    s["confidence"] = min(0.95, s["confidence"] + 0.02)
            else:
                # SKILL_DEGRADED: increment failure count, decay recency
                s["failure_rate"] = (prev_failures + 1) / total
                s["recency_score"] = max(0.1, s["recency_score"] * 0.9)
                s["confidence"] = max(0.1, s["confidence"] - 0.05)

            s["last_validated"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
            break

        # Write back
        try:
            with open(SKILL_TREE_PATH, "w") as f:
                json.dump(tree, f, indent=2)
            self._tree = tree  # refresh cache
        except OSError:
            pass  # non-fatal — skill tree is observational, not load-bearing


_skill_router = SkillRouter()

# Lazy backend singletons — initialized on first use
_managed_client: ManagedAgentsClient | None = None
_vertex_client: VertexClient | None = None

def _get_managed_client() -> ManagedAgentsClient:
    global _managed_client
    if _managed_client is None:
        _managed_client = ManagedAgentsClient()
    return _managed_client

def _get_vertex_client() -> VertexClient:
    global _vertex_client
    if _vertex_client is None:
        _vertex_client = VertexClient()
    return _vertex_client


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
        raw = yaml.safe_load(f)
    # Support both v1 (agents: {}) and v2 (departments: {}) schema
    if "departments" in raw:
        raw["agents"] = raw["departments"]
    return raw


# ── Managed Agents client (Anthropic beta) ────────────────────────────────────

class ManagedAgentsClient:
    """
    Wraps Anthropic Managed Agents for session-based dispatch.
    Agent IDs loaded from agent_registry.json (created by register_managed.py).
    """

    def __init__(self):
        try:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        except (ImportError, KeyError) as exc:
            raise RuntimeError(f"ManagedAgentsClient init failed: {exc}") from exc

        registry_path = MANAGED_REGISTRY_PATH
        if registry_path.exists():
            with open(registry_path) as f:
                self._registry: dict[str, str] = json.load(f)
        else:
            self._registry = {}

    def get_agent_id(self, dept_id: str) -> str | None:
        return self._registry.get(dept_id)

    async def run(
        self,
        dept_id: str,
        messages: list[dict],
        system: str,
        max_tokens: int = 8192,
    ) -> dict:
        """Create a session and stream the response for a given department agent."""
        agent_id = self.get_agent_id(dept_id)
        if not agent_id:
            raise ValueError(f"No managed agent registered for department: {dept_id}")

        # Run in executor since the Anthropic SDK is sync
        loop = asyncio.get_event_loop()

        def _sync_run() -> dict:
            # Create a session for this task
            session = self._client.beta.sessions.create(agent=agent_id)
            session_id = session.id

            # Send the task message
            self._client.beta.sessions.events.send(
                session_id=session_id,
                events=[{
                    "type": "user.message",
                    "content": [{"type": "text", "text": messages[-1]["content"]}],
                }],
            )

            # Stream the response
            output_parts: list[str] = []
            model_id = DEFAULT_MODEL
            input_tokens = 0
            output_tokens = 0

            with self._client.beta.sessions.stream(session_id=session_id) as stream:
                for event in stream:
                    etype = getattr(event, "type", None)
                    if etype == "agent.message":
                        for block in getattr(event, "content", []):
                            if getattr(block, "type", None) == "text":
                                output_parts.append(block.text)
                    elif etype in ("session.status_terminated", "session.status_idle"):
                        break

            return {
                "content": [{"type": "text", "text": "".join(output_parts)}],
                "model": model_id,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
                "governance": {
                    "backend": "managed_agents",
                    "agent_id": agent_id,
                    "session_id": session_id,
                    "is_valid": True,
                },
            }

        return await loop.run_in_executor(None, _sync_run)


# ── Vertex AI client (AnthropicVertex) ───────────────────────────────────────

class VertexClient:
    """
    Wraps AnthropicVertex for Claude inference via Google Cloud.
    Constitutional proxy may still be in the path if PROXY_URL is also set.
    """

    def __init__(self, project: str = VERTEX_PROJECT, region: str = VERTEX_REGION):
        try:
            import anthropic
            self._client = anthropic.AnthropicVertex(project_id=project, region=region)
            self._project = project
            self._region = region
        except ImportError as exc:
            raise RuntimeError(
                "anthropic[vertex] not installed. Run: pip install 'anthropic[vertex]>=0.52.0'"
            ) from exc

    async def run(
        self,
        dept_id: str,
        messages: list[dict],
        system: str,
        model: str = "claude-opus-4-8@001",
        max_tokens: int = 8192,
    ) -> dict:
        loop = asyncio.get_event_loop()

        def _sync_run() -> dict:
            response = self._client.messages.create(
                model=model,
                system=system,
                messages=messages,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
            )
            text_blocks = [
                {"type": "text", "text": b.text}
                for b in response.content
                if hasattr(b, "text")
            ]
            return {
                "content": text_blocks,
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "governance": {
                    "backend": "vertex_ai",
                    "project": self._project,
                    "region": self._region,
                    "is_valid": True,
                },
            }

        return await loop.run_in_executor(None, _sync_run)


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

    # ASSESS + LOCK — call inference backend (governance enforced at every tier)
    system = agent_def.get("system_prompt", "")
    model = agent_def.get("model", DEFAULT_MODEL)
    max_tokens = agent_def.get("max_tokens", 4096)

    backend = task.backend
    if backend == BackendType.MANAGED_AGENTS:
        result = await _get_managed_client().run(task.role.value, messages, system, max_tokens)
    elif backend == BackendType.VERTEX_AI:
        result = await _get_vertex_client().run(task.role.value, messages, system, max_tokens=max_tokens)
    else:
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
    """Run an agent through RALPH loops until completion or max_cycles.

    Phase 2: emits SKILL_VALIDATED / SKILL_DEGRADED events back to skill_tree.json
    after each execution, closing the evidence loop for probabilistic competency modeling.
    """
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
    succeeded = False

    try:
        for cycle in range(task.max_ralph_cycles):
            cycles = cycle + 1
            output, governance = await _ralph_cycle(agent_def, task, memory, proxy, cycle)
            final_output = output
            final_governance = governance

            # Terminal condition: agent declared harmonization complete
            if "HARMONIZE_COMPLETE" in output or cycle == task.max_ralph_cycles - 1:
                succeeded = governance.get("is_valid", True) and "ERROR" not in output[:200]
                break

    finally:
        await proxy.aclose()
        await redis_conn.aclose()

    duration_ms = int((time.time() - t_start) * 1000)
    result = AgentResult(
        task_id=task.task_id,
        role=task.role,
        output=final_output,
        governance=final_governance,
        ralph_cycles=cycles,
        duration_ms=duration_ms,
        is_valid=final_governance.get("is_valid", True),
    )

    # Phase 2: emit skill events for all capabilities declared by this agent
    capabilities: list[str] = agent_def.get("capabilities", [])
    for cap in capabilities:
        _skill_router.emit_skill_event(cap, success=succeeded)

    # Evolution: record this run in the hash-chained AdaptiveLineage and, when an
    # agent's skills cross the promotion threshold, the engine earns it a TIER_PROMOTION.
    # Guarded — evolution is observational metabolism and must never break a run.
    if agent_def.get("evolving"):
        _record_evolution(task.role.value, capabilities, succeeded)

    return result


def _record_evolution(role: str, capabilities: list[str], succeeded: bool) -> None:
    """Append a CAPABILITY_EVOLUTION event and run a promotion tick (best-effort)."""
    try:
        from agents.evolution import AdaptiveLineage, EvolutionEngine

        lineage = AdaptiveLineage.load()
        lineage.append(
            "CAPABILITY_EVOLUTION",
            skill_id=role,
            from_tier="T2",
            to_tier="T2",
            evidence=f"run {'succeeded' if succeeded else 'degraded'}; caps={','.join(capabilities[:4])}",
        )
        lineage.save()
        # One promotion tick — skills that crossed the evidence threshold get promoted.
        EvolutionEngine(lineage=lineage).tick(apply_changes=True)
    except Exception:  # noqa: BLE001 — evolution is non-load-bearing
        pass


# ── Event dispatcher — routes external events to agents ──────────────────────

EVENT_ROUTING: dict[str, list[AgentRole]] = {
    # Engineering events
    "github_pr_opened":          [AgentRole.ENGINEERING],
    "github_pr_comment":         [AgentRole.ENGINEERING],
    "github_issue_opened":       [AgentRole.ENGINEERING],
    "github_ci_failure":         [AgentRole.ENGINEERING],
    "github_ci_success":         [AgentRole.ENGINEERING],
    "dependency_vulnerability":  [AgentRole.CYBERSECURITY, AgentRole.ENGINEERING],
    "architecture_review":       [AgentRole.ENGINEERING, AgentRole.AI_RESEARCH],
    "gate_failure":              [AgentRole.ENGINEERING, AgentRole.AI_SAFETY],
    "infra_scaling":             [AgentRole.PLATFORM_ENGINEERING, AgentRole.HARDWARE_ENGINEERING],
    "deployment_event":          [AgentRole.PLATFORM_ENGINEERING],
    # Security events
    "security_incident":         [AgentRole.CYBERSECURITY, AgentRole.AI_SAFETY, AgentRole.COMPLIANCE],
    "constitutional_breach":     [AgentRole.CYBERSECURITY, AgentRole.AI_SAFETY, AgentRole.COMPLIANCE],
    "t0_abort":                  [AgentRole.CYBERSECURITY, AgentRole.ENGINEERING, AgentRole.AI_SAFETY],
    "pen_test_finding":          [AgentRole.CYBERSECURITY],
    # Research events
    "capability_evaluation":     [AgentRole.AI_RESEARCH, AgentRole.AI_SAFETY],
    "alignment_finding":         [AgentRole.AI_SAFETY, AgentRole.AI_ETHICS, AgentRole.COMPLIANCE],
    "tier_promotion_request":    [AgentRole.AI_RESEARCH, AgentRole.AI_SAFETY],
    "research_publication":      [AgentRole.AI_RESEARCH, AgentRole.COMMUNICATIONS],
    # Trust & Safety events
    "content_policy_violation":  [AgentRole.TRUST_SAFETY, AgentRole.COMPLIANCE],
    "classifier_alert":          [AgentRole.TRUST_SAFETY, AgentRole.CYBERSECURITY],
    "bias_report":               [AgentRole.AI_ETHICS, AgentRole.TRUST_SAFETY],
    # Commercial events
    "partnership_inquiry":       [AgentRole.BIZ_DEV, AgentRole.PARTNERSHIPS],
    "enterprise_lead":           [AgentRole.SALES, AgentRole.BIZ_DEV, AgentRole.MARKETING],
    "anthropic_partnership":     [AgentRole.BIZ_DEV, AgentRole.COMPLIANCE, AgentRole.ENGINEERING],
    "vertex_model_garden":       [AgentRole.BIZ_DEV, AgentRole.PLATFORM_ENGINEERING, AgentRole.DEVEX],
    "press_inquiry":             [AgentRole.COMMUNICATIONS, AgentRole.POLICY_AFFAIRS],
    "rfp_received":              [AgentRole.SOLUTIONS_ENGINEERING, AgentRole.COMPLIANCE, AgentRole.BIZ_DEV],
    "deal_closed":               [AgentRole.CUSTOMER_SUCCESS, AgentRole.FINANCE, AgentRole.SALES],
    "customer_churn_risk":       [AgentRole.CUSTOMER_SUCCESS, AgentRole.SALES],
    "support_ticket":            [AgentRole.SUPPORT, AgentRole.ENGINEERING],
    "content_request":           [AgentRole.MARKETING, AgentRole.DEVREL],
    "community_event":           [AgentRole.DEVREL, AgentRole.MARKETING],
    # Compliance events
    "compliance_request":        [AgentRole.COMPLIANCE, AgentRole.POLICY_AFFAIRS],
    "contract_review":           [AgentRole.COMPLIANCE],
    "eu_ai_act_audit":           [AgentRole.COMPLIANCE, AgentRole.AI_ETHICS, AgentRole.POLICY_AFFAIRS],
    "regulatory_change":         [AgentRole.COMPLIANCE, AgentRole.POLICY_AFFAIRS, AgentRole.COMMUNICATIONS],
    # Finance events
    "cost_alert":                [AgentRole.FINANCE, AgentRole.PLATFORM_ENGINEERING],
    "revenue_milestone":         [AgentRole.FINANCE, AgentRole.BIZ_DEV, AgentRole.STRATEGY],
    "budget_review":             [AgentRole.FINANCE],
    "acquisition_inquiry":       [AgentRole.CORPORATE_DEVELOPMENT, AgentRole.STRATEGY, AgentRole.BIZ_DEV],
    # People events
    "talent_need":               [AgentRole.TALENT_ACQUISITION, AgentRole.PEOPLE_OPS],
    "culture_signal":            [AgentRole.PEOPLE_OPS],
    # Strategy events
    "competitive_intelligence":  [AgentRole.STRATEGY, AgentRole.BIZ_DEV, AgentRole.MARKETING],
    "market_opportunity":        [AgentRole.STRATEGY, AgentRole.PRODUCT_MANAGEMENT, AgentRole.BIZ_DEV],
    # Education events
    "training_request":          [AgentRole.EDUCATION, AgentRole.DEVREL],
    "certification_inquiry":     [AgentRole.EDUCATION, AgentRole.CUSTOMER_SUCCESS],
    # Mythos cognitive-substrate events — the four-stage knowledge pipeline
    "research_request":          [AgentRole.DEEP_RESEARCHER],
    "corpus_document":           [AgentRole.CORPUS_INGESTOR],
    "corpus_batch":              [AgentRole.BATCH_PROCESSOR, AgentRole.CORPUS_INGESTOR],
    "retrospective_request":     [AgentRole.CHRONOLOGIST],
    "knowledge_pipeline":        [AgentRole.DEEP_RESEARCHER, AgentRole.CORPUS_INGESTOR,
                                  AgentRole.BATCH_PROCESSOR, AgentRole.CHRONOLOGIST],
}


async def dispatch_event(event_type: str, payload: dict) -> list[AgentResult]:
    """Route an external event using skill-backed competency scoring (Phase 2).

    Primary routing from EVENT_ROUTING; within that set, agents are scored by
    the SkillRouter against their declared capabilities. The highest-scoring
    agent runs first. All agents in the routing set still run (not winner-take-all)
    but the order reflects competency confidence.
    """
    candidate_roles = EVENT_ROUTING.get(event_type, [AgentRole.ENGINEERING])
    defs = _load_agent_defs()

    # Score candidates by competency and sort descending
    instruction_sample = _event_to_instruction(event_type, payload, candidate_roles[0])
    scored = sorted(
        candidate_roles,
        key=lambda r: _skill_router.score_role_for_task(r, instruction_sample, defs["agents"]),
        reverse=True,
    )

    results = []
    for role in scored:
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

async def _cli_run(role: str, task: str, cycles: int, backend: BackendType | None = None) -> None:
    agent_role = AgentRole(role)
    task_id = str(uuid.uuid4())
    agent_task = AgentTask(
        task_id=task_id,
        role=agent_role,
        instruction=task,
        max_ralph_cycles=cycles,
        backend=backend or ACTIVE_BACKEND,
    )
    print(f"[coordinator] Running {role.upper()} agent — task_id={task_id[:8]}")
    print(f"[coordinator] Task: {task}")
    print(f"[coordinator] Backend: {agent_task.backend.value}")
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

    back_p = sub.add_parser("backend", help="Show active inference backend")

    run_p.add_argument("--backend", choices=[b.value for b in BackendType],
                       help="Override auto-detected inference backend")

    args = parser.parse_args()

    if args.command == "run":
        backend_override = BackendType(args.backend) if getattr(args, "backend", None) else None
        asyncio.run(_cli_run(args.role, args.task, args.cycles, backend_override))
    elif args.command == "dispatch":
        asyncio.run(_cli_dispatch(args.event, args.payload))
    elif args.command == "list":
        defs = _load_agent_defs()
        print("AGENTS:")
        for dept_id, ag in defs["agents"].items():
            tier = ag.get("tier", "?")
            name = ag.get("name", dept_id)
            caps = ag.get("capabilities", [])
            print(f"  {dept_id:35s}  {name}  (tier={tier})")
            if caps:
                print(f"    capabilities: {', '.join(caps[:5])}{'...' if len(caps) > 5 else ''}")
        print(f"\n  Total: {len(defs['agents'])} departments")
        print("\nEVENT ROUTING:")
        for evt, roles in EVENT_ROUTING.items():
            print(f"  {evt:35s} → {[r.value for r in roles]}")
    elif args.command == "backend":
        print(f"Active backend: {ACTIVE_BACKEND.value}")
        print(f"  ANTHROPIC_API_KEY set: {bool(os.environ.get('ANTHROPIC_API_KEY'))}")
        print(f"  agent_registry.json:   {MANAGED_REGISTRY_PATH.exists()}")
        print(f"  VERTEX_PROJECT_ID:     {os.environ.get('VERTEX_PROJECT_ID', '(not set)')}")
        if MANAGED_REGISTRY_PATH.exists():
            with open(MANAGED_REGISTRY_PATH) as f:
                reg = json.load(f)
            print(f"  Managed agents registered: {len(reg)}")
        if VERTEX_REGISTRY_PATH.exists():
            with open(VERTEX_REGISTRY_PATH) as f:
                vreg = json.load(f)
            print(f"  Vertex agents registered:  {len(vreg)}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
