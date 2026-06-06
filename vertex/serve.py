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

import hashlib
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import anthropic
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
import httpx


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await state.init()
    yield


app = FastAPI(
    title="AEGIS-Ω Constitutional Governance Proxy",
    version="1.0.0",
    lifespan=lifespan,
)


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
        from agents.coordinator import EVENT_ROUTING, AgentRole
        import yaml
        with open(os.path.join(os.path.dirname(__file__), "..", "agents", "agents.yaml")) as f:
            defs = yaml.safe_load(f)
        return {
            "agents": {
                name: {"role": ag["role"], "capabilities": ag["capabilities"]}
                for name, ag in defs["agents"].items()
            },
            "event_routing": {
                evt: [r.value for r in roles]
                for evt, roles in EVENT_ROUTING.items()
            },
        }
    except ImportError as exc:
        raise HTTPException(503, f"Agent coordinator not available: {exc}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
