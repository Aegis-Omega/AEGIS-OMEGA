---
name: claude-api-ref
description: >
  Auto-activates for any task in this project that touches the Anthropic API,
  Anthropic SDK, or model selection. Triggers on: "claude api", "anthropic sdk",
  "model id", "claude-fable", "claude-opus", "claude-sonnet", "claude-haiku",
  "thinking", "streaming", "tool use", "prompt caching", "managed agents",
  "messages api", "vertex ai", "cloud run model", "AEGIS_SWARM_MODEL".
  Provides AEGIS-specific model defaults and API patterns.
  Bundled claude-api skill handles full SDK docs; this layer handles project context.
---

# Claude API Reference — AEGIS-Ω Project Layer

**Auto-activates** for any Claude API / Anthropic SDK work in this project.

---

## Current Model Defaults (AEGIS-Ω)

| Use | Model ID | Config |
|-----|----------|--------|
| Swarm (bridge.py) | `claude-fable-5` | `AEGIS_SWARM_MODEL` env var |
| Hub inference-router | `claude-fable-5` | `VITE_CLAUDE_MODEL` env var |
| Thinking | adaptive (always-on for Fable 5) | `AEGIS_SWARM_THINKING=false` to opt out |

**Latest model IDs (do not append date suffixes):**

```
claude-fable-5          ← default for AEGIS swarm
claude-opus-4-8         ← reasoning-heavy tasks
claude-sonnet-4-6       ← balanced cost/quality
claude-haiku-4-5        ← fast lightweight tasks
```

**Never use:** `claude-sonnet-4-6-20251114` or any date-suffixed form. Use bare IDs only.

**Mythos 5 facts (Model Documentation Form v1.0, 2026-06-08):** `claude-mythos-5` is
the same underlying model as `claude-fable-5` with certain cyber/bio classifiers
disabled per customer use case. Trusted-access program only (Project Glasswing) — no
open distribution. Both released 2026-06-09. Black-box inference-only; weights never
available. Input: 1M tokens text + 600 images/request. Model max output 300K tokens
(API per-request limit remains 128K). EU provider: Anthropic Ireland Limited.
AEGIS uses `claude-fable-5` — do not request Mythos access in code paths.

---

## AEGIS-Specific API Patterns

### Adaptive Thinking (Fable 5 / Opus 4.7+)
```python
# bridge.py / anth_client.py pattern:
thinking_config = {'type': 'adaptive'} if SWARM_THINKING else None
# Do NOT use budget_tokens — deprecated on Fable 5 / Opus 4.6+
```

### Vertex AI vs Direct API (bridge.py auto-detect)
```python
# AEGIS_USE_VERTEX=true  → Vertex AI (Cloud Run, ADC auth)
# AEGIS_USE_VERTEX=false → direct Anthropic API key
# (unset)               → auto-detect via google.auth ADC
```

### Prompt Caching (already wired in bridge.py)
```python
# System prompts wrapped with cache_control=ephemeral.
# 10% token cost on cache hit. 5-minute TTL minimum.
# Do NOT cache per-request dynamic content (objective, mode).
```

### Refusal Guard (Fable 5)
```python
# After every API call in _swarm_live():
if response.stop_reason == 'refusal':
    # Use template fallback — do not surface refusal to customer
    output = _platform_dept_output(objective, mode, dept)
```

---

## Vertex AI Endpoint (Cloud Run production)

```
Model: claude-fable-5 via anthropic.claude-fable-5@20260101
Region: eu (europe-west1 multi-region, data residency)
Project: aegisomegav1
Auth: Workload Identity (ADC) — no long-lived keys
```

---

## Key SDK Files in This Repo

| File | Purpose |
|------|---------|
| `python/anth_client.py` | Vertex AI / direct API factory — the ONLY permitted instantiation path |
| `python/bridge.py` | Uses `anth_client.py`; adds hash-chain audit + tier validation |
| `packages/shared/lib/inference-router.ts` | TS multi-backend router: DashScope → Ollama → Claude → CL-Ψ |
| `hub/src/lib/telemetry.ts` | Optional live bridge overlay — `VITE_BRIDGE_URL` |

**Rule:** Never instantiate `anthropic.Anthropic()` directly in bridge code — always go through `anth_client.py`. This ensures Vertex AI fallback and ADC auth work correctly on Cloud Run.

---

## Token Limits and Costs (cached 2026-06-10)

| Model | Context | Input $/1M | Output $/1M |
|-------|---------|------------|-------------|
| claude-fable-5 | 1M | $5.00 | $25.00 |
| claude-opus-4-8 | 1M | $5.00 | $25.00 |
| claude-sonnet-4-6 | 1M | $3.00 | $15.00 |
| claude-haiku-4-5 | 200K | $1.00 | $5.00 |

**On "unlimited tokens":** Context windows are system constraints. Compaction
(already active) extends sessions by summarizing prior context — this is the
correct mechanism. The grace chain token economy (see `dept_graces` Supabase
table) is the *constitutional* unlimited-token answer: graces flow forward
through the 39-dept swarm indefinitely, each cycle replenishing the chain.

---

*Source: Anthropic API docs (2026-06-10) · AEGIS project patterns · T1 reference*
