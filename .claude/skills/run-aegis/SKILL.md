---
name: run-aegis
description: run, start, build, launch, screenshot, smoke test, drive, or interact with AEGIS-Ω — the full-stack bridge + governance dashboard + cockpit system
---

AEGIS-Ω is a three-service stack driven by `driver.cjs` (CommonJS, Node.js). The driver builds both web apps if needed, starts the Python bridge on `:7890`, starts the sovereign-omega governance dashboard on `:5173`, and starts the cockpit AI chat on `:5174`. It then runs curl smoke checks and optionally takes Playwright screenshots.

All paths below are relative to the repo root (`/home/user/AEGIS--`).

---

## Prerequisites

Chromium must be downloaded once per container:

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-browsers /opt/node22/bin/playwright install chromium
```

Python bridge deps (already installed in this container):
```bash
cd sovereign-omega-v2 && pip install flask flask-cors
```

---

## Build

The driver auto-builds if `dist/index.html` is absent. To force a rebuild:

```bash
cd sovereign-omega-v2 && npm run build
cd cockpit && npm run build
```

---

## Run (agent path)

### Smoke test — curl only, ~5–10 s, no browser

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-browsers node .claude/skills/run-aegis/driver.cjs --smoke
```

Verifies: bridge health, `t0_verdict=true`, `corruption_count=0`, `pgcs_passes` value.  
Exit 0 = constitutional invariants hold. Exit 1 = T0 violation (message printed).

### Full run — screenshots + interaction

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-browsers node .claude/skills/run-aegis/driver.cjs
```

Screenshots land in `/tmp/aegis-screenshots/`:
- `sov.png` — sovereign-omega governance dashboard
- `cockpit.png` — cockpit AI chat
- `cockpit-input.png` — cockpit with prompt typed in chat textarea

Typical output when all invariants hold:

```
[aegis-driver] bridge health: {"status":"ok","pgcs_passes":true,...}
[aegis-driver] t0_verdict=true  corruption_count=0  pgcs_passes=true
[aegis-driver] smoke PASS
[aegis-driver] screenshotting sovereign-omega...
[aegis-driver]   title: Sovereign Omega — Governance Runtime
[aegis-driver] screenshotting cockpit...
[aegis-driver]   typed prompt in cockpit chat
[aegis-driver] screenshots saved to /tmp/aegis-screenshots/
[aegis-driver] ALL CHECKS PASS
```

### Screenshot only (skip interaction)

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-browsers node .claude/skills/run-aegis/driver.cjs --ss
```

---

## Run (human path)

Start services manually in three terminals:

```bash
# Terminal 1 — bridge
cd sovereign-omega-v2 && python python/bridge.py

# Terminal 2 — governance dashboard
cd sovereign-omega-v2 && npx vite preview --port 5173

# Terminal 3 — cockpit
cd cockpit && npx vite preview --port 5174
```

This is useless headless; use the driver for programmatic runs.

---

## Ports

| Service | Port | URL |
|---------|------|-----|
| Python bridge | 7890 | `http://localhost:7890/health` |
| sovereign-omega | 5173 | `http://localhost:5173/` |
| cockpit | 5174 | `http://localhost:5174/` |

Bridge endpoints: `/health`, `/telemetry`, `/node`, `/event`, `/gate_signal`, `/claude`

---

## Constitutional Smoke Checks

The driver asserts these three invariants; any failure → exit 1:

```bash
curl -s http://localhost:7890/node | jq '.t0_verdict'          # must be true
curl -s http://localhost:7890/node | jq '.corruption_count'    # must be 0
curl -s http://localhost:7890/telemetry | jq '.pgcs_passes'    # informational
```

---

## Gotchas

- **CommonJS only.** The driver uses `require()`. Do not convert to ESM — Playwright's CJS bundle at `/opt/node22/lib/node_modules/playwright/node_modules/playwright-core` only resolves correctly from CJS context.
- **Chromium path is fixed.** The driver hard-codes `/tmp/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell`. If playwright installs a newer revision, update `CHROMIUM` at line 29 of `driver.cjs`.
- **`waitUntil: 'networkidle'` hangs on cockpit.** Cockpit polls `/telemetry` every 5s — the network never goes idle. Use `domcontentloaded` + `waitForTimeout(3000)`.
- **Vite preview requires a pre-built dist/.** If `dist/index.html` is missing, the driver builds automatically. First run is ~30s longer.
- **Bridge must start before vite previews.** The driver enforces this order. Do not parallelize service startup.

---

## Troubleshooting

**`Chromium not found`** — Run the playwright install command in Prerequisites.

**`T0 ABORT: t0_verdict=false`** — The bridge is reporting a constitutional violation. Check `python/gate.py` hash with `node sovereign-omega-v2/scripts/verify-hashes.mjs`.

**`CORRUPTION: count=N`** — `corruption_count` is non-zero. Inspect `/node` endpoint for details.

**Bridge port 7890 already in use** — `pkill -f bridge.py` then rerun.

**`Cannot find module '…playwright-core'`** — Playwright not installed at `/opt/node22`. Run: `npm install -g playwright` or check `PLAYWRIGHT_CORE` path in driver.cjs line 28.
