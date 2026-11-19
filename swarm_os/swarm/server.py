#!/usr/bin/env python3
"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.

S.W.A.R.M. OS v6.0 — Equilibrium Server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FastAPI server with real-time WebSocket protocol.

WebSocket envelopes (typed — never revert to untyped payloads):
  SNAPSHOT        → sent once on WS connect
  EVENT           → broadcast from POST /event
  MANIFOLD_UPDATE → broadcast from POST /ingest and POST /dream

API:
  GET  /          → index.html canvas dashboard
  GET  /state     → full snapshot (events, epiphanies, agents, manifold)
  POST /ingest    → {subject, relation, object, context[]} → {ok, edge_id, total_hyperedges}
  POST /dream     → trigger dream cycle → {ok, dream_cycle, new_epiphanies, ...}
  POST /event     → {agent_id, type, content, cycle} → {ok, id}
  GET  /graph     → hypergraph as D3-compatible JSON
  GET  /spectral  → spectral density (λ₁, stability)
  GET  /health    → system health
  GET  /audit     → ?last_n=N → audit log entries
  WS   /ws        → real-time typed envelopes

Run:
  python swarm/server.py
  python swarm/server.py --port 8001
"""

import argparse
import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# ── Path setup (run from swarm_os/ root) ─────────────────────────────────────
_HERE = Path(__file__).parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_HERE))

from config import PORT, HOST, VERSION, REM_INTERVAL, FORGE_DIR
from swarm_core import QuantumManifold
print("[BOOT] Local imports done.")


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL STATE
# ══════════════════════════════════════════════════════════════════════════════
forge_path  = _ROOT / ".forge"
manifold    = QuantumManifold(forge_path=forge_path)
_ws_clients: Set[WebSocket] = set()
_ws_lock    = asyncio.Lock()

# Boot the identity anchor event
manifold.add_event("SWARM_OS", "BOOT", f"SWARM OS {VERSION} initialized", cycle=0)


# ══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET BROADCAST
# ══════════════════════════════════════════════════════════════════════════════
async def _broadcast(envelope: dict):
    """Send a typed envelope to all connected WebSocket clients."""
    msg = json.dumps(envelope)
    dead: Set[WebSocket] = set()
    async with _ws_lock:
        clients = list(_ws_clients)
    for ws in clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    if dead:
        async with _ws_lock:
            _ws_clients.difference_update(dead)


def _broadcast_sync(envelope: dict):
    """Thread-safe fire-and-forget broadcast from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast(envelope), loop)
    except RuntimeError:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND DREAM THREAD
# ══════════════════════════════════════════════════════════════════════════════
class _DreamThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="SWARM-DreamState")
        self._stop = False

    def run(self):
        time.sleep(5)  # let server boot first
        while not self._stop:
            time.sleep(REM_INTERVAL)
            if len(manifold.hyperedges) < 3:
                continue
            try:
                n_ep = manifold.dream_state_cycle()
                snap = manifold.get_state_snapshot()
                _broadcast_sync({
                    "type":     "MANIFOLD_UPDATE",
                    "manifold": snap,
                })
                _broadcast_sync({
                    "type":  "EVENT",
                    "event": manifold.add_event(
                        "DREAM_STATE", "DREAM_END",
                        f"REM cycle {manifold.dream_cycles} — {n_ep} epiphany/epiphanies",
                        cycle=manifold.dream_cycles,
                    ),
                })
            except Exception as e:
                print(f"[DreamThread] Error: {e}")

    def stop(self):
        self._stop = True


_dream_thread = _DreamThread()


# ══════════════════════════════════════════════════════════════════════════════
# APP
# ══════════════════════════════════════════════════════════════════════════════
app = FastAPI(title="S.W.A.R.M. OS v6.0", version=VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def _startup():
    _dream_thread.start()
    print(f"[SWARM OS] {VERSION} — Dream State thread started.")


@app.on_event("shutdown")
async def _shutdown():
    _dream_thread.stop()


# ══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ══════════════════════════════════════════════════════════════════════════════
class IngestBody(BaseModel):
    subject:  str
    relation: str
    object:   str
    context:  Optional[List[str]] = []


class EventBody(BaseModel):
    agent_id: str
    type:     str
    content:  str
    cycle:    Optional[int] = 0


# ══════════════════════════════════════════════════════════════════════════════
# HTTP ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the WebSocket canvas dashboard."""
    html_path = _HERE / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    # Minimal fallback if index.html not found
    return HTMLResponse(f"""<!DOCTYPE html><html><head>
    <title>SWARM OS {VERSION}</title>
    <style>body{{background:#000;color:#39ff14;font-family:monospace;padding:40px}}</style>
    </head><body>
    <h1>S.W.A.R.M. OS {VERSION}</h1>
    <p>index.html not found. Place it at swarm/index.html.</p>
    <p>API: <a href="/state" style="color:#00ffff">/state</a> &nbsp;
           <a href="/graph" style="color:#00ffff">/graph</a> &nbsp;
           <a href="/health" style="color:#00ffff">/health</a></p>
    </body></html>""")


@app.get("/state")
async def state():
    """Full snapshot: events, epiphanies, agents, manifold."""
    snap = manifold.get_state_snapshot()
    return {
        "events":     manifold.events[-50:],
        "epiphanies": manifold.epiphanies,
        "agents":     list(manifold.agents.values()),
        "manifold":   snap,
    }


@app.post("/ingest")
async def ingest(body: IngestBody):
    edge_id = manifold.ingest(body.subject, body.relation, body.object, body.context)
    snap    = manifold.get_state_snapshot()
    await _broadcast({"type": "MANIFOLD_UPDATE", "manifold": snap})
    return {
        "ok":               True,
        "edge_id":          edge_id,
        "total_hyperedges": len(manifold.hyperedges),
    }


@app.post("/dream")
async def dream():
    """Trigger one Dream State REM cycle immediately."""
    n_ep  = manifold.dream_state_cycle()
    snap  = manifold.get_state_snapshot()
    event = manifold.add_event(
        "DREAM_STATE", "DREAM_END",
        f"REM cycle {manifold.dream_cycles} — {n_ep} epiphany/epiphanies",
        cycle=manifold.dream_cycles,
    )
    await _broadcast({"type": "MANIFOLD_UPDATE", "manifold": snap})
    await _broadcast({"type": "EVENT",           "event":    event})
    return {
        "ok":               True,
        "dream_cycle":      manifold.dream_cycles,
        "new_epiphanies":   n_ep,
        "total_epiphanies": len(manifold.epiphanies),
        "total_hyperedges": len(manifold.hyperedges),
        "manifold":         snap,
    }


@app.post("/event")
async def post_event(body: EventBody):
    """Log a custom event and broadcast to all WS clients."""
    manifold.register_agent(body.agent_id)
    event = manifold.add_event(body.agent_id, body.type, body.content, body.cycle)
    await _broadcast({"type": "EVENT", "event": event})
    return {"ok": True, "id": event["id"]}


@app.get("/graph")
async def graph():
    """Hypergraph as D3-compatible JSON (hyperedges + epiphanies)."""
    snap = manifold.get_state_snapshot()
    return {
        "hyperedges": [
            {"nodes": he["nodes"], "relation": he["relation"],
             "context": he["context"]}
            for he in manifold.hyperedges.values()
        ],
        "epiphanies": [[ep["nodes"][0], ep["nodes"][1]]
                       for ep in manifold.epiphanies if len(ep.get("nodes", [])) >= 2],
        "node_count": len(snap["nodes"]),
        "nodes":      snap["nodes"],
        "edges":      snap["edges"],
    }


@app.get("/spectral")
async def spectral():
    return manifold.spectral_state()


@app.post("/rem")
async def rem():
    """Alias for /dream — kept for backward compat with test_endpoints.py."""
    return await dream()


@app.get("/health")
async def health():
    return {
        "status":            "OPERATIONAL",
        "version":           VERSION,
        "dream_cycles":      manifold.dream_cycles,
        "total_hyperedges":  len(manifold.hyperedges),
        "total_epiphanies":  len(manifold.epiphanies),
        "ws_clients":        len(_ws_clients),
        "dream_state": {
            "cycles":    manifold.dream_cycles,
            "lambda1":   manifold.spectral_state().get("lambda1", 0.0),
        },
        "recent_epiphanies": [[ep["nodes"][0], ep["nodes"][1]]
                               for ep in manifold.epiphanies[-6:]
                               if len(ep.get("nodes", [])) >= 2],
    }


@app.get("/audit")
async def audit(last_n: int = 50):
    entries = manifold.read_audit(last_n=last_n)
    return {"entries": entries, "count": len(entries)}


# ══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET
# ══════════════════════════════════════════════════════════════════════════════
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    async with _ws_lock:
        _ws_clients.add(ws)

    # Send SNAPSHOT on connect
    snap = manifold.get_state_snapshot()
    await ws.send_text(json.dumps({
        "type":       "SNAPSHOT",
        "events":     manifold.events[-50:],
        "epiphanies": manifold.epiphanies,
        "manifold":   snap,
    }))

    try:
        while True:
            # Keep alive — echo PING
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "PING":
                    await ws.send_text(json.dumps({"type": "PONG"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        async with _ws_lock:
            _ws_clients.discard(ws)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"S.W.A.R.M. OS {VERSION}")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--host", type=str, default=HOST)
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   S.W.A.R.M. OS {VERSION:<20}                                   ║
║   Operator: Tarik Skalic — Bihac, Bosnia — 2026                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

  Canvas:    http://{args.host}:{args.port}/
  State:     GET  http://localhost:{args.port}/state
  Ingest:    POST http://localhost:{args.port}/ingest
  Dream:     POST http://localhost:{args.port}/dream
  WebSocket: ws://localhost:{args.port}/ws
  Health:    GET  http://localhost:{args.port}/health
  Audit:     GET  http://localhost:{args.port}/audit?last_n=20
""")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
