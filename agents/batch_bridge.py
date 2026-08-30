#!/usr/bin/env python3
"""
AEGIS-Ω — Batch bridge (cost-safe agent dispatch)  ·  EPISTEMIC TIER: T2
=======================================================================
Why this exists: the previous path ran the 39 managed agents as LIVE streaming
sessions (coordinator.py: beta.sessions.create -> stream), fanned across many
roles x RALPH cycles, several with the computer_use tool and 16k-32k max_tokens.
One dispatch could drain the whole budget. It also needed Redis for memory and a
fully-populated env; with neither present the sync between this session and the
agents degraded into repeated uncontrolled live calls.

This module replaces that with the safe shape the batch attempt was reaching for:

  1. ENV, explicit and documented (agents/.env.example). Nothing implicit.
  2. MEMORY STORE with no external services — a file-backed JSON store, so a
     missing Redis can never silently break synchronization again.
  3. Message BATCHES API (50% cheaper, async) instead of live session fan-out,
     behind a HARD USD cap and a dry-run default. It is structurally impossible
     for this to runaway-spend: it estimates worst-case cost, refuses above the
     cap, and submits NOTHING unless AEGIS_BATCH_LIVE=1 is set explicitly.

Dry-run (default, $0):   python3 -m agents.batch_bridge
Live (guarded):          AEGIS_BATCH_LIVE=1 AEGIS_BATCH_MAX_USD=0.50 python3 -m agents.batch_bridge
"""
from __future__ import annotations

import json
import os
import pathlib
from dataclasses import dataclass, field

# ── Config (env, explicit) ──────────────────────────────────────────────────
MODEL = os.environ.get("AEGIS_SWARM_MODEL", "claude-opus-4-8")
MAX_TOKENS = int(os.environ.get("AEGIS_BATCH_MAX_TOKENS", "2048"))
MAX_USD = float(os.environ.get("AEGIS_BATCH_MAX_USD", "1.00"))
LIVE = os.environ.get("AEGIS_BATCH_LIVE") == "1"
STORE_DIR = pathlib.Path(os.environ.get(
    "AEGIS_BATCH_STORE", str(pathlib.Path(__file__).parent / ".batch_state")))

# Per-1M-token USD (Opus 4.8); Batches API applies a 50% discount to both.
_PRICE = {"claude-opus-4-8": (5.0, 25.0), "claude-sonnet-4-6": (3.0, 15.0),
          "claude-haiku-4-5": (1.0, 5.0)}
_BATCH_DISCOUNT = 0.5


# ── Memory store (file-backed, no Redis) ────────────────────────────────────
class FileStore:
    """Minimal JSON state store. Replaces the Redis-only AgentMemory so a missing
    service can't break session<->agent synchronization. Deterministic on disk."""

    def __init__(self, directory: pathlib.Path):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, value: dict) -> None:
        path = self.dir / f"{key}.json"
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")

    def get(self, key: str) -> dict | None:
        path = self.dir / f"{key}.json"
        return json.loads(path.read_text()) if path.exists() else None


@dataclass
class AgentTask:
    custom_id: str          # stable id → lets results sync back to the right agent
    system: str
    prompt: str
    max_tokens: int = MAX_TOKENS


@dataclass
class BatchPlan:
    model: str
    n: int
    est_usd: float
    over_cap: bool
    requests: list = field(default_factory=list)


def _tok(text: str) -> int:
    return max(1, len(text) // 4)  # ~4 chars/token, worst-case-friendly


def estimate(tasks: list[AgentTask], model: str) -> float:
    """Worst-case USD: every task emits its full max_tokens. Batch = 50% off."""
    in_price, out_price = _PRICE.get(model, _PRICE["claude-opus-4-8"])
    total = 0.0
    for t in tasks:
        tin = _tok(t.system) + _tok(t.prompt)
        total += (tin / 1e6) * in_price + (t.max_tokens / 1e6) * out_price
    return round(total * _BATCH_DISCOUNT, 4)


def plan(tasks: list[AgentTask], model: str = MODEL, cap: float = MAX_USD) -> BatchPlan:
    est = estimate(tasks, model)
    requests = [{
        "custom_id": t.custom_id,
        "params": {
            "model": model,
            "max_tokens": t.max_tokens,
            "system": t.system,
            "messages": [{"role": "user", "content": t.prompt}],
        },
    } for t in tasks]
    return BatchPlan(model=model, n=len(tasks), est_usd=est,
                     over_cap=est > cap, requests=requests)


def submit(tasks: list[AgentTask], *, live: bool = LIVE, cap: float = MAX_USD,
           store: FileStore | None = None) -> dict:
    """Plan the batch, enforce the cap, and only submit when explicitly live and
    under cap. Returns a record persisted to the store for session synchronization.
    NEVER spends money in dry-run or when over cap."""
    store = store or FileStore(STORE_DIR)
    p = plan(tasks, cap=cap)
    record = {"model": p.model, "n_requests": p.n, "est_usd": p.est_usd,
              "cap_usd": cap, "live": bool(live), "status": "dry_run",
              "batch_id": None, "custom_ids": [t.custom_id for t in tasks]}

    if not live:
        record["status"] = "dry_run"
    elif p.over_cap:
        record["status"] = "refused_over_cap"
    else:
        # LIVE, under cap → Anthropic Message Batches API (50% cheaper, async).
        from anthropic import Anthropic  # imported only on the live path
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        batch = client.messages.batches.create(requests=p.requests)
        record["status"] = "submitted"
        record["batch_id"] = batch.id

    store.put("last_batch", record)
    return record


# ── Demonstration: dry-run over the registered agents, $0 ───────────────────
def _sample_tasks() -> list[AgentTask]:
    reg_path = pathlib.Path(__file__).parent / "agent_registry.json"
    reg = json.loads(reg_path.read_text()) if reg_path.exists() else {}
    ids = list(reg.keys()) or ["engineering", "strategy", "compliance"]
    return [AgentTask(custom_id=dept,
                      system=f"You are the AEGIS {dept} function. Be concise.",
                      prompt="Summarize your single highest-leverage action this week.")
            for dept in ids]


if __name__ == "__main__":
    tasks = _sample_tasks()
    rec = submit(tasks)  # dry-run by default
    print("AEGIS Batch Bridge — plan")
    print("=" * 56)
    print(f"  model         : {rec['model']}")
    print(f"  requests      : {rec['n_requests']} agents")
    print(f"  est max cost  : ${rec['est_usd']:.4f}  (Batches API, 50% off, worst case)")
    print(f"  cap           : ${rec['cap_usd']:.2f}")
    print(f"  live          : {rec['live']}   status: {rec['status']}")
    print("=" * 56)
    if rec["status"] == "dry_run":
        print("No API call made ($0). Set AEGIS_BATCH_LIVE=1 to submit (still capped).")
    elif rec["status"] == "refused_over_cap":
        print(f"REFUSED: estimate ${rec['est_usd']:.4f} exceeds cap ${rec['cap_usd']:.2f}. "
              f"Raise AEGIS_BATCH_MAX_USD deliberately or lower AEGIS_BATCH_MAX_TOKENS.")
    else:
        print(f"Submitted batch {rec['batch_id']} — results retrievable via the Batches API.")
