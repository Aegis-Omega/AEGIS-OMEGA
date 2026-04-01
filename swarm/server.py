"""server.py — SWARM FastAPI server.

Endpoints:
  GET  /           → serves index.html
  GET  /state      → full current state snapshot (JSON)
  POST /event      → ingest event from forager
  WS   /ws         → real-time broadcast to dashboard clients
"""

import json
import os
import pathlib
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import List, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from config import HOST, MAX_EVENTS, PORT

app = FastAPI(title="SWARM Server")

# ── State ─────────────────────────────────────────────────────────────────────
events: deque = deque(maxlen=MAX_EVENTS)
epiphanies: List[dict] = []
agents: dict = {}          # agent_id → {last_seen, cycle_count}
ws_clients: Set[WebSocket] = set()

# ── Models ────────────────────────────────────────────────────────────────────
class Event(BaseModel):
    id: str = ""
    timestamp: str = ""
    agent_id: str
    type: str          # DREAM_START | THOUGHT | EPIPHANY | PING
    content: str
    cycle: int = 0


# ── Helpers ───────────────────────────────────────────────────────────────────
def _stamp(ev: Event) -> dict:
    d = ev.model_dump()
    if not d["id"]:
        d["id"] = str(uuid.uuid4())
    if not d["timestamp"]:
        d["timestamp"] = datetime.now(timezone.utc).isoformat()
    return d


async def _broadcast(payload: dict):
    dead = set()
    message = json.dumps(payload)
    for ws in ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = pathlib.Path(__file__).parent / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>SWARM — place index.html in the same directory as server.py</h2>")


@app.get("/state")
async def get_state():
    return JSONResponse({
        "events": list(events),
        "epiphanies": epiphanies,
        "agents": agents,
        "event_count": len(events),
        "epiphany_count": len(epiphanies),
        "agent_count": len(agents),
    })


@app.post("/event", status_code=202)
async def ingest_event(ev: Event):
    stamped = _stamp(ev)

    events.append(stamped)

    # Update agent registry
    if ev.agent_id not in agents:
        agents[ev.agent_id] = {"first_seen": stamped["timestamp"], "cycle_count": 0}
    agents[ev.agent_id]["last_seen"] = stamped["timestamp"]
    agents[ev.agent_id]["cycle_count"] += 1

    # Track epiphanies separately
    if ev.type == "EPIPHANY":
        epiphanies.append(stamped)

    await _broadcast(stamped)
    return {"ok": True, "id": stamped["id"]}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    # Send current state snapshot on connect
    await ws.send_text(json.dumps({
        "type": "SNAPSHOT",
        "events": list(events)[-50:],   # last 50 for initial paint
        "epiphanies": epiphanies,
    }))
    try:
        while True:
            await ws.receive_text()     # keep connection alive
    except WebSocketDisconnect:
        ws_clients.discard(ws)


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("server:app", host=HOST, port=PORT, reload=False)
