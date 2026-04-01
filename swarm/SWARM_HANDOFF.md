# SWARM Handoff Document

## Project Identity
- **Name:** SWARM — Synthetic Wandering Agent Reflection Machine
- **GCP Project:** `lifequestplatinum`
- **Cloud Run Service:** `swarm-server` (second service alongside Sovereign OS dashboard)
- **Local Port:** `8000`
- **Branch:** `claude/swarm-handoff-package-YDdyV`

---

## What This Is

SWARM is a real-time multi-agent thought simulation. A `forager.py` process uses the Gemini API to generate autonomous, wandering reflections. It posts structured events to a local FastAPI server (`server.py`). A browser dashboard (`index.html`) renders the live stream via WebSocket.

Two special event types are the core signal:
- **`DREAM_START`** — the agent begins a new associative chain of thought
- **`EPIPHANY`** — the agent surfaces a synthesized insight from prior wandering

The server maintains rolling state (last 200 events, active agents, epiphany log) queryable at `GET /state`.

---

## File Map

```
swarm/
├── SWARM_HANDOFF.md   ← you are here
├── requirements.txt   ← pip install this first
├── config.py          ← ports, limits, model name
├── server.py          ← FastAPI: /state, /event, /ws, serves index.html
├── forager.py         ← Gemini agent loop, posts events to server
├── index.html         ← live WebSocket dashboard (open in Chrome)
├── Dockerfile         ← for Cloud Run deployment
└── deploy.sh          ← builds + deploys to Cloud Run (lifequestplatinum)
```

---

## Startup Sequence

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Gemini API key
export GEMINI_API_KEY=your_key_here          # Linux/Mac
# set GEMINI_API_KEY=your_key_here           # Windows CMD

# 3. Start the server (leave this terminal open)
python server.py

# 4. Open the dashboard in Chrome
#    Navigate to: http://localhost:8000

# 5. In a NEW terminal, start the forager
python forager.py

# 6. Watch for DREAM_START and EPIPHANY events in the forager terminal

# 7. Verify state via curl
curl http://localhost:8000/state
```

---

## Verification Checklist

- [ ] `server.py` starts without error on port 8000
- [ ] `http://localhost:8000` loads the dashboard in Chrome
- [ ] `forager.py` connects and begins posting events
- [ ] Dashboard shows live events updating in real time
- [ ] At least one `DREAM_START` event appears within 30s
- [ ] At least one `EPIPHANY` event appears within 2 minutes
- [ ] `curl http://localhost:8000/state` returns valid JSON with `events`, `agents`, `epiphanies` keys

---

## Cloud Run Deployment

Run `deploy.sh` after local test passes. It will:
1. Build the Docker image
2. Push to Artifact Registry under `lifequestplatinum`
3. Deploy as `swarm-server` service
4. Set `GEMINI_API_KEY` as a Cloud Run secret
5. Print the live service URL

```bash
bash deploy.sh
```

The `index.html` is served by the server at `/` — no separate static hosting needed.

---

## Architecture Notes

- Server is stateless between restarts (in-memory only). For persistence, add Firestore or Redis.
- Forager runs one Gemini call per cycle (~5–15s). Rate limits are handled with exponential backoff in `forager.py`.
- Multiple forager instances can run simultaneously — each registers as a distinct agent.
- WebSocket broadcasts every event to all connected browser clients in real time.
- `/state` is the canonical proof endpoint: it returns the full current snapshot.

---

## Known Gotchas

1. **`GEMINI_API_KEY` not set** → forager exits immediately with a clear error message
2. **Port 8000 in use** → change `PORT` in `config.py` and update the curl/browser URL
3. **Chrome WebSocket** → must open `http://localhost:8000` (not file://) for WS to connect
4. **Cloud Run cold start** → first request after idle may take 3–5s; not a bug
5. **Windows paths** → the directory `D:\03_WORK_PROJECTS\swarm\` works fine; all scripts use relative paths internally

---

## Event Schema

```json
{
  "id": "uuid4",
  "timestamp": "ISO-8601",
  "agent_id": "forager-<uuid4-prefix>",
  "type": "DREAM_START | THOUGHT | EPIPHANY | PING",
  "content": "string",
  "cycle": 12
}
```

---

## Contact / Continuity

This package was generated as a self-contained handoff. The next Claude Code session should:
1. Read this file first
2. Create `D:\03_WORK_PROJECTS\swarm\` and place all 8 files
3. Follow the Startup Sequence above exactly
4. Not run anything until file placement is confirmed
