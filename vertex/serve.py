"""
AEGIS-Ω Constitutional Governance Proxy
Vertex AI Custom Prediction Endpoint + Anthropic-compatible gateway

Deployment: Cloud Run (aegisomegav1, us-central1)
Port: 8080
Routes:
  GET  /health                      — Vertex AI health probe
  POST /predict                     — Vertex AI native prediction format
  POST /v1/messages                 — Anthropic-compatible gateway (drop-in replacement)
  GET  /v1/audit/chain              — Full audit chain export
  GET  /v1/audit/certify            — Chain integrity verification
  GET  /v1/audit/{seq}              — Single entry lookup

Every inference call is hash-chained:
  entry_hash = SHA-256(prev_hash ‖ seq.to_be_bytes() ‖ canonical(observation))
  certify() re-walks chain → is_valid flips false if any entry tampered
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any

import anthropic
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

# Robust import path — works in dev (serve.py in vertex/, agents at ../agents)
# and in the flattened container (serve.py at /app, agents at /app/agents).
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (_SELF_DIR, os.path.join(_SELF_DIR, "..")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Config ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DEFAULT_MODEL = os.environ.get("AEGIS_DEFAULT_MODEL", "claude-opus-4-8")
CHAIN_KEY = "aegis:chain"
GENESIS_HASH = "0" * 64
MAX_CHAIN_ENTRIES = 50_000  # Redis list cap


# ── Hash chain (mirrors sovereign-omega-v2/src/metacognition/loop.ts) ─────────

def _canonical(obj: Any) -> bytes:
    """RFC 8785 (JCS) canonical JSON — deterministic across platforms."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_entry_hash(prev_hash: str, seq: int, observation: dict) -> str:
    payload = prev_hash.encode() + seq.to_bytes(8, "big") + _canonical(observation)
    return _sha256(payload)


# ── Application state ─────────────────────────────────────────────────────────

class ChainState:
    def __init__(self):
        self.redis: aioredis.Redis | None = None
        self.anthropic: anthropic.AsyncAnthropic | None = None
        self._seq = 0

    async def init(self):
        self.redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        if ANTHROPIC_API_KEY:
            self.anthropic = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        # restore sequence from Redis
        length = await self.redis.llen(CHAIN_KEY)
        self._seq = length

    async def append(self, observation: dict, tier: str = "T1") -> dict:
        seq = self._seq
        # get last hash
        if seq == 0:
            prev_hash = GENESIS_HASH
        else:
            last_raw = await self.redis.lindex(CHAIN_KEY, -1)
            last = json.loads(last_raw)
            prev_hash = last["entry_hash"]

        entry_hash = compute_entry_hash(prev_hash, seq, observation)
        entry = {
            "sequence": seq,
            "previous_entry_hash": prev_hash,
            "entry_hash": entry_hash,
            "observation": observation,
            "tier": tier,
            "timestamp_ms": int(time.time() * 1000),
        }
        raw = json.dumps(entry, separators=(",", ":"))
        await self.redis.rpush(CHAIN_KEY, raw)
        if seq % 1000 == 0 and seq > MAX_CHAIN_ENTRIES:
            await self.redis.ltrim(CHAIN_KEY, -MAX_CHAIN_ENTRIES, -1)
        self._seq = seq + 1
        return entry

    async def certify(self) -> dict:
        all_raw = await self.redis.lrange(CHAIN_KEY, 0, -1)
        entries = [json.loads(r) for r in all_raw]
        if not entries:
            return {"is_valid": True, "entry_count": 0, "terminal_hash": GENESIS_HASH}

        prev = GENESIS_HASH
        for e in entries:
            expected = compute_entry_hash(prev, e["sequence"], e["observation"])
            if expected != e["entry_hash"]:
                return {
                    "is_valid": False,
                    "entry_count": len(entries),
                    "terminal_hash": e["entry_hash"],
                    "tampered_at_sequence": e["sequence"],
                }
            prev = e["entry_hash"]

        return {"is_valid": True, "entry_count": len(entries), "terminal_hash": prev}

    async def get_entry(self, seq: int) -> dict | None:
        raw = await self.redis.lindex(CHAIN_KEY, seq)
        return json.loads(raw) if raw else None

    async def full_chain(self, limit: int = 200) -> list[dict]:
        all_raw = await self.redis.lrange(CHAIN_KEY, -limit, -1)
        return [json.loads(r) for r in all_raw]


state = ChainState()

# Supabase persistence config (optional — graceful no-op if unset)
_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


async def _persist_cycle_result(result: dict) -> None:
    """
    Persist a collaboration cycle result to Supabase for permanent storage.
    Fire-and-forget — never raises; caller is not blocked.
    Stores: cycle_id, objective, projection, departments_collaborated, chain_valid, timestamp.
    """
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        return
    try:
        row = {
            "cycle_id": result.get("cycle_id"),
            "objective": result.get("objective", "")[:500],
            "mode": result.get("mode", "revenue"),
            "departments_collaborated": result.get("departments_collaborated", 0),
            "chain_valid": result.get("chain_valid", True),
            "projection_arr_usd": (
                result.get("projection", {}) or {}
            ).get("first_year_arr_usd"),
            "projection_tier": (result.get("projection", {}) or {}).get("tier"),
            "constitutional_verdict": (
                (result.get("constitutional_audit") or {}).get("verdict", "APPROVED")
            ),
            "live": result.get("live", False),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        url = f"{_SUPABASE_URL}/rest/v1/revenue_cycles"
        headers = {
            "apikey": _SUPABASE_KEY,
            "Authorization": f"Bearer {_SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=row, headers=headers)
    except Exception:  # noqa: BLE001 — persistence is best-effort
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await state.init()
    yield


app = FastAPI(
    title="AEGIS-Ω Agent Platform",
    version="1.1.0",
    lifespan=lifespan,
)


# ── Production hardening: observability, auth, rate limiting ───────────────────
# Honors the deploy caveat — public Cloud Run exposure requires auth on the
# cost-incurring routes, error handling, and observability before going live.

PLATFORM_API_KEY = os.environ.get("PLATFORM_API_KEY", "")  # if set, gates cost routes
RATE_LIMIT_PER_MIN = int(os.environ.get("RATE_LIMIT_PER_MIN", "60"))

# Routes that spend compute/money — require the API key when one is configured.
_GATED_PREFIXES = ("/platform/collaborate", "/agents/run", "/agents/dispatch", "/v1/messages", "/predict")

# In-memory metrics (per-process; Cloud Run logs aggregate across instances).
METRICS: dict[str, Any] = {
    "requests_total": 0,
    "errors_total": 0,
    "by_path": defaultdict(lambda: {"count": 0, "errors": 0, "latency_ms_sum": 0}),
}
# Per-client sliding-window request timestamps for rate limiting.
_RL_WINDOW: dict[str, deque] = defaultdict(deque)


def _client_id(request: Request) -> str:
    return request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()


def _rate_limited(client: str) -> bool:
    now = time.time()
    win = _RL_WINDOW[client]
    while win and now - win[0] > 60.0:
        win.popleft()
    if len(win) >= RATE_LIMIT_PER_MIN:
        return True
    win.append(now)
    return False


@app.middleware("http")
async def observability_and_guard(request: Request, call_next):
    path = request.url.path
    client = _client_id(request)
    t0 = time.time()

    # Rate limit (skip health/metrics so probes never trip it).
    if path not in ("/health", "/metrics") and _rate_limited(client):
        METRICS["requests_total"] += 1
        return JSONResponse(
            {"error": "rate_limited", "limit_per_min": RATE_LIMIT_PER_MIN}, status_code=429
        )

    # Auth gate on cost-incurring routes when a key is configured.
    if PLATFORM_API_KEY and any(path.startswith(p) for p in _GATED_PREFIXES):
        provided = request.headers.get("x-api-key", "")
        if provided != PLATFORM_API_KEY:
            METRICS["requests_total"] += 1
            return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001 — turn any unhandled error into JSON
        latency_ms = int((time.time() - t0) * 1000)
        METRICS["requests_total"] += 1
        METRICS["errors_total"] += 1
        m = METRICS["by_path"][path]
        m["count"] += 1; m["errors"] += 1; m["latency_ms_sum"] += latency_ms
        print(json.dumps({"level": "error", "path": path, "client": client,
                          "latency_ms": latency_ms, "error": str(exc)}))
        return JSONResponse(
            {"error": "internal_error", "detail": "An internal error has occurred."},
            status_code=500,
        )

    latency_ms = int((time.time() - t0) * 1000)
    METRICS["requests_total"] += 1
    m = METRICS["by_path"][path]
    m["count"] += 1; m["latency_ms_sum"] += latency_ms
    if response.status_code >= 500:
        METRICS["errors_total"] += 1; m["errors"] += 1
    # Structured access log → Cloud Logging picks this up as JSON.
    print(json.dumps({"level": "info", "path": path, "method": request.method,
                      "status": response.status_code, "latency_ms": latency_ms, "client": client}))
    return response


@app.get("/metrics")
async def metrics():
    """Request/latency/error metrics for this instance (Cloud Run aggregates logs)."""
    by_path = {
        p: {
            "count": v["count"],
            "errors": v["errors"],
            "avg_latency_ms": (v["latency_ms_sum"] // v["count"]) if v["count"] else 0,
        }
        for p, v in METRICS["by_path"].items()
    }
    return {
        "requests_total": METRICS["requests_total"],
        "errors_total": METRICS["errors_total"],
        "rate_limit_per_min": RATE_LIMIT_PER_MIN,
        "auth_enabled": bool(PLATFORM_API_KEY),
        "by_path": by_path,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _classify_tier(messages: list[dict]) -> str:
    """Simple epistemic tier from message content — real impl would use CCIL-Ψ."""
    total = sum(len(m.get("content", "")) for m in messages)
    if total < 200:
        return "T0"
    if total < 2000:
        return "T1"
    return "T2"


async def _call_claude(messages: list[dict], model: str, system: str | None, max_tokens: int, **kwargs) -> dict:
    if not state.anthropic:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")

    req_kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if system:
        req_kwargs["system"] = system
    req_kwargs.update(kwargs)

    response = await state.anthropic.messages.create(**req_kwargs)
    return response.model_dump()


async def _governed_inference(messages: list[dict], model: str, system: str | None, max_tokens: int, **kwargs) -> dict:
    """Run Claude inference wrapped in constitutional governance."""
    request_id = str(uuid.uuid4())
    tier = _classify_tier(messages)

    # Pre-inference audit entry (pre-submission hook)
    pre_entry = await state.append(
        observation={
            "layer": "EXECUTIVE",
            "signal": f"inference_request:{request_id} model:{model} messages:{len(messages)}",
            "tier": tier,
            "request_id": request_id,
        },
        tier=tier,
    )

    # Call Claude
    t0 = time.time()
    try:
        response = await _call_claude(messages, model, system, max_tokens, **kwargs)
    except Exception as exc:
        # Log failure in chain
        await state.append(
            observation={
                "layer": "METACOGNITIVE",
                "signal": f"inference_error:{request_id} error:{type(exc).__name__}",
                "tier": "T0",
                "request_id": request_id,
            }
        )
        raise

    latency_ms = int((time.time() - t0) * 1000)

    # Post-inference audit entry
    output_tokens = response.get("usage", {}).get("output_tokens", 0)
    post_entry = await state.append(
        observation={
            "layer": "PERCEPTION",
            "signal": f"inference_complete:{request_id} tokens:{output_tokens} latency_ms:{latency_ms}",
            "tier": tier,
            "request_id": request_id,
            "output_tokens": output_tokens,
        },
        tier=tier,
    )

    cert = await state.certify()

    return {
        **response,
        "governance": {
            "request_id": request_id,
            "pre_entry_hash": pre_entry["entry_hash"],
            "post_entry_hash": post_entry["entry_hash"],
            "pre_sequence": pre_entry["sequence"],
            "post_sequence": post_entry["sequence"],
            "chain_length": post_entry["sequence"] + 1,
            "is_valid": cert["is_valid"],
            "terminal_hash": cert["terminal_hash"],
            "tier": tier,
            "latency_ms": latency_ms,
        },
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "chain_length": state._seq}


@app.post("/predict")
async def vertex_predict(request: Request):
    """Vertex AI native prediction format.

    Request:  {"instances": [{"messages": [...], "system": "...", "model": "..."}]}
    Response: {"predictions": [{...response, "governance": {...}}]}
    """
    body = await request.json()
    instances = body.get("instances", [])
    predictions = []

    for inst in instances:
        messages = inst.get("messages", [])
        model = inst.get("model", DEFAULT_MODEL)
        system = inst.get("system")
        max_tokens = inst.get("max_tokens", 4096)
        result = await _governed_inference(messages, model, system, max_tokens)
        predictions.append(result)

    return {"predictions": predictions}


@app.post("/v1/messages")
async def anthropic_messages(request: Request):
    """Anthropic-compatible endpoint — drop-in gateway replacement.

    Accepts the same request body as api.anthropic.com/v1/messages.
    Returns the same response schema PLUS a 'governance' envelope.
    """
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", DEFAULT_MODEL)
    system = body.get("system")
    max_tokens = body.get("max_tokens", 4096)

    extra = {k: v for k, v in body.items() if k not in ("messages", "model", "system", "max_tokens")}

    result = await _governed_inference(messages, model, system, max_tokens, **extra)
    return JSONResponse(result)


@app.get("/v1/audit/chain")
async def audit_chain(limit: int = 100):
    entries = await state.full_chain(limit=min(limit, 500))
    cert = await state.certify()
    return {"entries": entries, "certify": cert}


@app.get("/v1/audit/certify")
async def audit_certify():
    return await state.certify()


@app.get("/v1/audit/{seq}")
async def audit_entry(seq: int):
    entry = await state.get_entry(seq)
    if not entry:
        raise HTTPException(404, f"Entry {seq} not found")
    return entry


# ── Agent ecosystem endpoints ─────────────────────────────────────────────────

@app.post("/agents/run")
async def agent_run(request: Request):
    """Run a single agent task through the coordinator.

    Request:  {"role": "engineering", "task": "...", "cycles": 3}
    Response: {"task_id": "...", "role": "...", "output": "...", "governance": {...}, ...}
    """
    body = await request.json()
    role = body.get("role", "engineering")
    task_instruction = body.get("task", "")
    cycles = int(body.get("cycles", 3))

    if not task_instruction:
        raise HTTPException(400, "task is required")

    # Inline import to keep coordinator dependencies optional
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from agents.coordinator import AgentTask, AgentRole, run_agent
    except ImportError as exc:
        raise HTTPException(503, f"Agent coordinator not available: {exc}")

    try:
        agent_role = AgentRole(role)
    except ValueError:
        raise HTTPException(400, f"Unknown role: {role}. Valid: {[r.value for r in AgentRole]}")

    task_obj = AgentTask(
        task_id=str(uuid.uuid4()),
        role=agent_role,
        instruction=task_instruction,
        max_ralph_cycles=cycles,
    )
    result = await run_agent(task_obj)
    return {
        "task_id": result.task_id,
        "role": result.role.value,
        "output": result.output,
        "governance": result.governance,
        "ralph_cycles": result.ralph_cycles,
        "duration_ms": result.duration_ms,
        "is_valid": result.is_valid,
    }


@app.post("/agents/dispatch")
async def agent_dispatch(request: Request):
    """Dispatch an external event to the appropriate agents.

    Request:  {"event_type": "github_ci_failure", "payload": {...}}
    Response: {"results": [{...}, ...]}
    """
    body = await request.json()
    event_type = body.get("event_type", "")
    payload = body.get("payload", {})

    if not event_type:
        raise HTTPException(400, "event_type is required")

    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from agents.coordinator import dispatch_event
    except ImportError as exc:
        raise HTTPException(503, f"Agent coordinator not available: {exc}")

    results = await dispatch_event(event_type, payload)
    return {
        "results": [
            {
                "task_id": r.task_id,
                "role": r.role.value,
                "output": r.output,
                "governance": r.governance,
                "ralph_cycles": r.ralph_cycles,
                "duration_ms": r.duration_ms,
                "is_valid": r.is_valid,
            }
            for r in results
        ]
    }


@app.get("/agents/roles")
async def agent_roles():
    """List available agent roles and event routing."""
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from agents.coordinator import EVENT_ROUTING, _load_agent_defs
        defs = _load_agent_defs()
        return {
            "agents": {
                name: {
                    "name": ag.get("name", name),
                    "capabilities": ag.get("capabilities", []),
                }
                for name, ag in defs["agents"].items()
            },
            "event_routing": {
                evt: [r.value for r in roles]
                for evt, roles in EVENT_ROUTING.items()
            },
        }
    except ImportError as exc:
        raise HTTPException(503, f"Agent coordinator not available: {exc}")


# ── Platform layer — the consumer-facing ultra-premium product surface ─────────
# Every one of the 39 departments is a tier-0 (Mythos-level) agent. The platform
# exposes them three ways: as a catalog (browse the swarm), as single governed
# runs (one agent), and as collaborations (the swarm works together toward an
# outcome — revenue plans, research pipelines). Every response is governed and
# replay-certifiable: the audit chain records the work.

PLATFORM_TIERS = {
    "explorer": {
        "price_usd_mo": 0,
        "runs_per_mo": 10,
        "collaboration": False,
        "blurb": "Try any single Mythos agent. Governed, audited, replayable.",
    },
    "operator": {
        "price_usd_mo": 49,
        "runs_per_mo": 500,
        "collaboration": True,
        "blurb": "Full swarm collaboration. Revenue + research pipelines. Audit export.",
    },
    "sovereign": {
        "price_usd_mo": 499,
        "runs_per_mo": -1,  # unlimited
        "collaboration": True,
        "blurb": "Unlimited. Self-hosted substrate, guardian review, SLA, custom orchestration.",
    },
}


@app.get("/platform/catalog")
async def platform_catalog():
    """The premium agent catalog: every Mythos department, its capabilities, tiers."""
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from agents.coordinator import _load_agent_defs
        defs = _load_agent_defs()
    except ImportError as exc:
        raise HTTPException(503, f"Agent coordinator not available: {exc}")

    agents = {
        name: {
            "name": ag.get("name", name),
            "tier": ag.get("tier", 0),
            "mythos": ag.get("tier", 0) == 0,
            "autonomous": bool(ag.get("autonomous", False)),
            "evolving": bool(ag.get("evolving", False)),
            "capabilities": ag.get("capabilities", []),
            "max_tokens": ag.get("max_tokens", 4096),
        }
        for name, ag in defs["agents"].items()
    }
    mythos_count = sum(1 for a in agents.values() if a["mythos"])
    return {
        "platform": "AEGIS-Ω Agent Platform",
        "tagline": "39 Mythos-level autonomous agents. Governed. Replay-certifiable.",
        "agent_count": len(agents),
        "mythos_count": mythos_count,
        "pricing_tiers": PLATFORM_TIERS,
        "agents": agents,
    }


@app.post("/platform/collaborate")
async def platform_collaborate(request: Request):
    """Run a multi-agent collaboration — the swarm working together.

    Request:  {"mode": "revenue" | "cognitive", "objective": "...", "live": false}
    Response: the collaboration result, governed and recorded in the audit chain.

    'revenue'   → the commercial departments produce an executable go-to-market
                  with a governed (tier-tagged, never-T0) revenue projection.
    'cognitive' → the four cognitive-substrate agents run the research →
                  ARBITRATION → batch → chronology knowledge pipeline.
    """
    body = await request.json()
    mode = body.get("mode", "revenue")
    objective = body.get("objective") or body.get("topic") or ""
    live = bool(body.get("live", False))

    if not objective:
        raise HTTPException(400, "objective (or topic) is required")

    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    if mode == "revenue":
        try:
            from agents.revenue_engine import run_revenue_cycle
        except ImportError as exc:
            raise HTTPException(503, f"Revenue engine not available: {exc}")
        r = await run_revenue_cycle(objective, live=live)

        # Red team verdict (attached by revenue_engine post-cycle)
        rt = r.red_team
        red_team_data = rt.to_dict() if rt and hasattr(rt, "to_dict") else None

        # If quarantined, block and return safety report instead
        if rt and getattr(rt, "quarantine", False):
            return JSONResponse({
                "mode": "revenue",
                "blocked": True,
                "reason": "Constitutional red team quarantine",
                "concerns": rt.concerns,
                "cycle_id": r.cycle_id,
            }, status_code=422)

        result = {
            "mode": "revenue",
            "cycle_id": r.cycle_id,
            "objective": r.objective,
            "live": r.live,
            "stages": [
                {"sequence": a.sequence, "role": a.role, "output": a.output,
                 "envelope_id": a.envelope_id, "source_envelope": a.source_envelope}
                for a in r.artifacts
            ],
            "projection": (
                {
                    "first_year_arr_usd": r.projection.first_year_arr_usd,
                    "tier": r.projection.tier,
                    "kan_score": r.projection.kan_score,
                    "assumptions": r.projection.assumptions,
                    "governed_note": r.projection.governed_note,
                } if r.projection else None
            ),
            "lineage_terminal_hash": r.lineage_terminal_hash,
            "chain_valid": r.chain_valid,
            "departments_collaborated": len(r.artifacts),
            "constitutional_audit": red_team_data,
        }

        # Persist to Supabase (fire-and-forget — non-blocking)
        asyncio.create_task(_persist_cycle_result(result))
    elif mode == "cognitive":
        try:
            from agents.cognitive_pipeline import run_pipeline
        except ImportError as exc:
            raise HTTPException(503, f"Cognitive pipeline not available: {exc}")
        r = await run_pipeline(objective, live=live)
        result = {
            "mode": "cognitive",
            "pipeline_id": r.pipeline_id,
            "topic": r.topic,
            "arbitration": r.arbitration,
            "admitted": len(r.admitted),
            "quarantined": len(r.quarantined),
            "kan_terminal_hash": r.kan_terminal_hash,
            "chain_valid": r.chain_valid,
            "stage_results": r.stage_results,
        }
    else:
        raise HTTPException(400, f"Unknown mode: {mode}. Use 'revenue' or 'cognitive'.")

    # Record the collaboration in the platform audit chain (governed, replayable).
    try:
        await state.append(
            {"layer": "PLATFORM_COLLABORATION", "mode": mode,
             "objective": objective[:120], "chain_valid": result.get("chain_valid", True)},
            tier="T2",
        )
    except Exception:  # noqa: BLE001 — audit is best-effort, never blocks the response
        pass

    return result


# ── Batch agent endpoint ──────────────────────────────────────────────────────

@app.post("/agents/batch")
async def agent_batch(request: Request):
    """
    Run multiple agent tasks in parallel and return all results.

    Request:
      {"tasks": [{"role": "strategy", "task": "...", "cycles": 3}, ...]}
      max 10 tasks per batch; all run concurrently via asyncio.gather.

    Response:
      {"results": [{task_id, role, output, duration_ms, is_valid}, ...],
       "batch_id": "...", "duration_ms": N}

    Ideal for: running several departments simultaneously, comparing outputs,
    or preparing a briefing from multiple specialist agents at once.
    """
    body = await request.json()
    tasks_raw = body.get("tasks", [])
    if not tasks_raw:
        raise HTTPException(400, "tasks list is required")
    if len(tasks_raw) > 10:
        raise HTTPException(400, "max 10 tasks per batch")

    batch_id = str(uuid.uuid4())
    t_batch_start = time.time()

    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from agents.coordinator import AgentTask, AgentRole, run_agent
    except ImportError as exc:
        raise HTTPException(503, f"Agent coordinator not available: {exc}")

    async def _run_one(task_dict: dict) -> dict:
        role_str = task_dict.get("role", "engineering")
        task_text = task_dict.get("task", "")
        cycles = int(task_dict.get("cycles", 3))
        if not task_text:
            return {"error": "task is required", "role": role_str}
        try:
            agent_role = AgentRole(role_str)
        except ValueError:
            return {"error": f"unknown role: {role_str}", "role": role_str}
        task_obj = AgentTask(
            task_id=str(uuid.uuid4()),
            role=agent_role,
            instruction=task_text,
            max_ralph_cycles=cycles,
        )
        t0 = time.time()
        result = await run_agent(task_obj)
        return {
            "task_id": result.task_id,
            "role": result.role.value,
            "output": result.output,
            "ralph_cycles": result.ralph_cycles,
            "duration_ms": result.duration_ms,
            "is_valid": result.is_valid,
        }

    results = await asyncio.gather(*[_run_one(t) for t in tasks_raw], return_exceptions=False)

    total_ms = int((time.time() - t_batch_start) * 1000)
    try:
        await state.append(
            {"layer": "BATCH_EXECUTION", "batch_id": batch_id,
             "task_count": len(tasks_raw), "duration_ms": total_ms},
            tier="T2",
        )
    except Exception:
        pass

    return {"batch_id": batch_id, "results": list(results), "duration_ms": total_ms}


# ── Multi-objective comparison ─────────────────────────────────────────────────

@app.post("/platform/compare")
async def platform_compare(request: Request):
    """
    Run revenue cycles for multiple objectives in parallel and rank them.

    Request:
      {"objectives": ["obj1", "obj2", "obj3"], "live": false}
      max 5 objectives; all run concurrently; ranked by KAN-scored ARR projection.

    Response:
      {"ranked": [{objective, cycle_id, arr_usd, kan_score, tier, rank}, ...],
       "best": {objective, arr_usd}, "analysis": "..."}

    The constitutional governance engine scores each projected ARR via the
    INT4 LUT-KAN gate — the same gate that scores all other claims. The ranking
    is itself tier-tagged (T2 engineering hypothesis — the best-scoring projection
    may not be the best real business opportunity).
    """
    body = await request.json()
    objectives = body.get("objectives", [])
    live = bool(body.get("live", False))

    if not objectives:
        raise HTTPException(400, "objectives list is required")
    if len(objectives) > 5:
        raise HTTPException(400, "max 5 objectives per comparison")

    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from agents.revenue_engine import run_revenue_cycle

    # Run all cycles in parallel
    t_start = time.time()
    cycle_results = await asyncio.gather(
        *[run_revenue_cycle(obj, live=live) for obj in objectives],
        return_exceptions=True,
    )

    # Rank by KAN score * ARR
    ranked: list[dict] = []
    for obj, r in zip(objectives, cycle_results):
        if isinstance(r, Exception):
            ranked.append({"objective": obj, "error": str(r), "rank": 99})
            continue
        proj = r.projection
        arr = proj.first_year_arr_usd if proj else 0
        kan = proj.kan_score if proj else 0
        # Composite score: KAN quality × ARR magnitude (log-normalized)
        import math
        composite = kan * (math.log10(max(arr, 1)) if arr > 0 else 0)
        ranked.append({
            "objective": obj,
            "cycle_id": r.cycle_id,
            "arr_usd": arr,
            "kan_score": kan,
            "tier": proj.tier if proj else "unknown",
            "composite_score": round(composite, 2),
            "chain_valid": r.chain_valid,
            "constitutional_verdict": (
                r.red_team.verdict if r.red_team and hasattr(r.red_team, "verdict") else "APPROVED"
            ),
        })

    ranked.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    best = ranked[0] if ranked else {}
    total_ms = int((time.time() - t_start) * 1000)

    # Audit the comparison
    try:
        await state.append(
            {"layer": "PLATFORM_COMPARISON", "objective_count": len(objectives),
             "best_objective": best.get("objective", "")[:80],
             "best_arr": best.get("arr_usd", 0)},
            tier="T2",
        )
    except Exception:
        pass

    return {
        "ranked": ranked,
        "best": best,
        "objective_count": len(objectives),
        "duration_ms": total_ms,
        "note": (
            "T2 governed comparison — ranking by KAN-score × log(ARR). "
            "Composite score is an engineering hypothesis, not a proven ROI forecast. "
            "Human judgment required before committing resources."
        ),
    }


# ── Streaming collaboration endpoint (SSE) ────────────────────────────────────

@app.post("/platform/stream")
async def platform_stream(request: Request):
    """
    Server-Sent Events stream for a revenue collaboration.
    Each stage emits an event as it completes so clients can watch the swarm work.

    Request:  {"objective": "...", "live": false}
    Response: text/event-stream — one SSE event per stage + a final 'done' event.

    Event format:
      data: {"stage": N, "role": "strategy", "output": "...", "envelope_id": "..."}
      data: {"done": true, "projection": {...}, "chain_valid": true}
    """
    body = await request.json()
    objective = body.get("objective", "").strip()
    live = bool(body.get("live", False))
    if not objective:
        raise HTTPException(400, "objective is required")

    async def _generate():
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from agents.revenue_engine import REVENUE_STAGES, StageArtifact, RevenueCycleResult, _demo_output, _govern_projection, _record_revenue_cycle
        import uuid

        cycle_id = str(uuid.uuid4())
        result = RevenueCycleResult(cycle_id=cycle_id, objective=objective, live=live)

        # Attempt real tool runner in live mode
        _api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        use_tools = live and bool(_api_key)

        prior_output: str | None = None
        prior_envelope: str | None = None

        for seq, (role, mandate) in enumerate(REVENUE_STAGES):
            envelope_id = f"{cycle_id}:{seq}:{role}"
            if use_tools:
                try:
                    from agents.tool_runner import run_collaborative_stage
                    output = await run_collaborative_stage(
                        role=role, mandate=mandate, objective=objective,
                        prior_context=prior_output, api_key=_api_key,
                        namespace=f"revenue:{role}",
                    )
                    output = output[:2000]
                except Exception:
                    output = _demo_output(role, objective, prior_output) + " [fallback: internal error]"
            else:
                output = _demo_output(role, objective, prior_output)

            artifact = StageArtifact(
                sequence=seq, role=role, mandate=mandate,
                envelope_id=envelope_id, output=output, source_envelope=prior_envelope,
            )
            result.artifacts.append(artifact)
            prior_output, prior_envelope = output, envelope_id

            # Emit stage event immediately
            event_data = json.dumps({
                "stage": seq, "role": role, "output": output,
                "envelope_id": envelope_id, "source_envelope": prior_envelope,
            })
            yield f"data: {event_data}\n\n"

        # Govern projection
        finance_output = result.artifacts[-1].output if result.artifacts else ""
        result.projection = _govern_projection(objective, finance_output)

        # Record in lineage
        result.lineage_terminal_hash, result.chain_valid = _record_revenue_cycle(result)

        # Emit done event
        done_data = json.dumps({
            "done": True,
            "cycle_id": cycle_id,
            "chain_valid": result.chain_valid,
            "departments_collaborated": len(result.artifacts),
            "projection": (
                {
                    "first_year_arr_usd": result.projection.first_year_arr_usd,
                    "tier": result.projection.tier,
                    "kan_score": result.projection.kan_score,
                    "governed_note": result.projection.governed_note,
                } if result.projection else None
            ),
        })
        yield f"data: {done_data}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ── Autonomous scheduling endpoint (Cloud Scheduler target) ───────────────────

@app.post("/platform/schedule/revenue")
async def schedule_revenue(request: Request):
    """
    Cloud Scheduler target — runs a revenue cycle and persists results.
    Cloud Scheduler POSTs to this endpoint on a cron schedule.

    Request body (JSON from scheduler):
      {"objective": "...", "live": true}  — or empty (uses env SCHEDULE_OBJECTIVE)

    Response: 200 immediately with cycle summary (Cloud Scheduler reads this).
    Auth: requires PLATFORM_API_KEY (gated by observability_and_guard middleware).
    """
    body: dict = {}
    try:
        body = await request.json()
    except Exception:
        pass

    default_objective = os.environ.get(
        "SCHEDULE_OBJECTIVE",
        "Run the weekly autonomous revenue cycle: identify highest-value opportunities, "
        "research real prospects, produce an executable GTM plan for AEGIS constitutional governance.",
    )
    objective = (body.get("objective") or default_objective).strip()
    live = bool(body.get("live", bool(os.environ.get("ANTHROPIC_API_KEY"))))

    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from agents.revenue_engine import run_revenue_cycle

    r = await run_revenue_cycle(objective, live=live)

    summary = {
        "scheduled": True,
        "cycle_id": r.cycle_id,
        "objective": r.objective,
        "live": r.live,
        "departments_collaborated": len(r.artifacts),
        "chain_valid": r.chain_valid,
        "projection": (
            {
                "first_year_arr_usd": r.projection.first_year_arr_usd,
                "tier": r.projection.tier,
                "governed_note": r.projection.governed_note,
            } if r.projection else None
        ),
    }

    # Audit the scheduled run
    try:
        await state.append(
            {"layer": "SCHEDULED_EXECUTION", "objective": objective[:100],
             "cycle_id": r.cycle_id, "chain_valid": r.chain_valid},
            tier="T2",
        )
    except Exception:
        pass

    return summary


# ── Platform status ───────────────────────────────────────────────────────────

@app.get("/platform/analytics")
async def platform_analytics():
    """
    Platform usage analytics — what agents have done, how often, how well.
    Pulls from the hash-chained audit log and in-memory metrics.
    Public for discovery; no sensitive data exposed.
    """
    # Pull from audit chain for governed events
    try:
        chain_entries = await state.full_chain(limit=500)
    except Exception:
        chain_entries = []

    # Count by layer / event type
    layer_counts: dict[str, int] = {}
    platform_collaborations = 0
    scheduled_runs = 0
    webhook_events = 0

    for e in chain_entries:
        obs = e.get("observation", {})
        layer = obs.get("layer", "UNKNOWN")
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
        if layer == "PLATFORM_COLLABORATION":
            platform_collaborations += 1
        elif layer == "SCHEDULED_EXECUTION":
            scheduled_runs += 1
        elif layer == "WEBHOOK":
            webhook_events += 1

    # In-process metrics
    top_paths = sorted(
        [(p, v["count"], v.get("errors", 0)) for p, v in METRICS["by_path"].items()],
        key=lambda x: x[1], reverse=True,
    )[:10]

    return {
        "platform": "AEGIS-Ω Agent Platform v1.2.0",
        "audit_chain": {
            "total_entries": state._seq,
            "layer_breakdown": layer_counts,
            "platform_collaborations": platform_collaborations,
            "scheduled_runs": scheduled_runs,
            "webhook_events": webhook_events,
        },
        "request_metrics": {
            "requests_total": METRICS["requests_total"],
            "errors_total": METRICS["errors_total"],
            "error_rate": (
                round(METRICS["errors_total"] / METRICS["requests_total"], 4)
                if METRICS["requests_total"] else 0.0
            ),
            "top_paths": [
                {"path": p, "count": c, "errors": e} for p, c, e in top_paths
            ],
        },
        "capabilities": {
            "tool_execution": True,
            "web_search": True,
            "url_fetch": True,
            "github_search": True,
            "code_execution": True,
            "persistent_memory": True,
            "agent_self_learning": True,
            "streaming_sse": True,
            "scheduled_execution": True,
            "parallel_dag_pipeline": True,
            "collaboration_modes": ["revenue", "cognitive"],
        },
    }


@app.get("/platform/status")
async def platform_status():
    """Full platform status: chain health, agent count, rate limits, capabilities."""
    cert = {"is_valid": True, "entry_count": state._seq}
    try:
        cert = await state.certify()
    except Exception:
        pass
    return {
        "platform": "AEGIS-Ω Agent Platform",
        "version": "1.2.0",
        "constitutional_chain": {
            "length": state._seq,
            "is_valid": cert.get("is_valid", True),
            "terminal_hash": cert.get("terminal_hash", ""),
        },
        "capabilities": {
            "tool_execution": True,
            "web_search": True,
            "url_fetch": True,
            "github_search": True,
            "code_execution": True,
            "persistent_memory": True,
            "agent_self_learning": True,
            "streaming_sse": True,
            "scheduled_execution": True,
            "parallel_dag_pipeline": True,
            "python_sdk": "pip install aegis-omega",
            "collaboration_modes": ["revenue", "cognitive"],
            "role_specialized_tools": True,
        },
        "pricing_tiers": PLATFORM_TIERS,
        "rate_limit_per_min": RATE_LIMIT_PER_MIN,
        "auth_enabled": bool(PLATFORM_API_KEY),
        "live_agents_enabled": bool(ANTHROPIC_API_KEY),
    }


# ── Webhook receiver (GitHub) ─────────────────────────────────────────────────

@app.post("/platform/webhooks/github")
async def github_webhook(request: Request):
    """
    Receive GitHub webhook events and dispatch them to the appropriate agents.
    Handles: push, pull_request, issues, pull_request_review, check_run.

    Verify GITHUB_WEBHOOK_SECRET if set (HMAC-SHA256).
    """
    import hmac, hashlib as _hl

    # Signature verification
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if secret:
        sig_header = request.headers.get("x-hub-signature-256", "")
        body_raw = await request.body()
        expected = "sha256=" + hmac.new(secret.encode(), body_raw, _hl.sha256).hexdigest()
        if not hmac.compare_digest(sig_header, expected):
            return JSONResponse({"error": "invalid_signature"}, status_code=401)
        body = json.loads(body_raw)
    else:
        body = await request.json()

    event_type = request.headers.get("x-github-event", "unknown")

    # Map GitHub events to agent dispatch
    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from agents.coordinator import dispatch_event
        results = await dispatch_event(event_type, body)
        dispatched = len(results)
    except Exception as exc:
        dispatched = 0
        event_type = f"{event_type}:dispatch_failed:{exc}"

    # Audit in chain
    try:
        await state.append(
            {"layer": "WEBHOOK", "event_type": event_type,
             "repo": body.get("repository", {}).get("full_name", ""),
             "dispatched_to_agents": dispatched},
            tier="T2",
        )
    except Exception:
        pass

    return {"received": event_type, "dispatched_to_agents": dispatched}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
