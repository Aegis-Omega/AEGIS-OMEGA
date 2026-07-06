# AEGIS-Ω — Team Onboarding

Welcome to the AEGIS project. This guide is based on observed usage patterns across the last 30 days of active development. Read it once end-to-end before touching any code.

---

## What You're Working With

AEGIS-Ω is a constitutional AI governance runtime deployed as a Cloud Run service (`aegis-vertex.aegisomega.com`). It runs a 39-department agent swarm, produces hash-chained audit records, and exposes a `/platform/*` API that external clients (Google Sheets, commercial products, direct API consumers) call.

It is **not** an AI model. It is the governance layer that wraps models and makes their outputs auditable, replay-verifiable, and constitutionally bounded.

The monorepo has five active layers:

| Layer | Tech | What it does |
|-------|------|-------------|
| `sovereign-omega-v2/` | TypeScript + Python | Governance runtime — the core product |
| `aegis-cl-psi/` | Rust (422 gates) | Deterministic inference fabric |
| `hub/` | React + Vite | Landing page + pricing + consciousness substrate |
| `platform-picker/`, `hook-generator/`, `content-calendar/` | React + Vite | Commercial AI tools ($19 each) |
| `supabase/functions/` | Deno (Edge Functions) | Payment, key provisioning, webhooks |

---

## First Session Checklist

```bash
# 1. Verify constitutional files are intact (must exit 0 before any work)
cd /home/user/AEGIS-- && cd sovereign-omega-v2 && node scripts/verify-hashes.mjs

# 2. Install deps
cd sovereign-omega-v2 && npm install

# 3. Run Gate 1 — the foundation test
npm run test -- test/unit/jcs.test.ts

# 4. Run full suite (Gate 8) — know the baseline
npm run test && npm run typecheck && npm run build

# 5. Python smoke
python python/tests/stress_test.py --quick
```

If `verify-hashes.mjs` fails, stop. Do not proceed. The constitutional files (`gate.py`, `dna.py`, `router.py`) are frozen — their SHA-256 hashes must match exactly. Any mismatch is a T0 abort condition.

---

## The Gate Protocol — Every Change Follows This

The TypeScript layer has 8 gates that must pass in order. **Gate 8 is the deployment gate — nothing merges without it.**

```bash
# Run the gate you're working on first:
npm run test -- test/unit/jcs.test.ts          # Gate 1 — RFC 8785 canonicalization
npm run test -- test/unit/sequence.test.ts     # Gate 2 — atomic sequences
npm run test -- test/unit/immutable.test.ts    # Gate 3 — immutability
npm run test -- test/unit/reducer.test.ts      # Gate 4 — pure reducers
npm run test -- test/unit/vcg.test.ts          # Gate 5 — calibration
npm run test -- test/unit/gate.test.ts         # Gate 6 — Bernstein bounds
npm run test -- test/integration/replay.test.ts # Gate 7 — replay

# Gate 8 — must pass before every commit:
npm run test && npm run typecheck && npm run build
```

**Key rule:** if a test fails, fix the implementation — never weaken the test.

---

## Python Bridge

The Python bridge (`sovereign-omega-v2/python/bridge.py`) is an HTTP server on port 7890. It is the entry point for all AI calls and exposes the `/platform/*` API.

```bash
# Start the bridge
cd sovereign-omega-v2 && python python/bridge.py

# Smoke test
curl localhost:7890/health
curl localhost:7890/node | jq '.t0_verdict, .corruption_count'
# t0_verdict must be true, corruption_count must be 0

# Test the platform API (no auth required for status)
curl localhost:7890/platform/status

# Test a governed collaboration (requires API key)
curl -X POST localhost:7890/platform/collaborate \
  -H "x-api-key: <key>" \
  -H "Content-Type: application/json" \
  -d '{"objective":"test","mode":"revenue","live":false}'
```

**Never instantiate `anthropic.Anthropic()` directly.** Always go through `python/anth_client.py` — it handles Vertex AI (Cloud Run) vs direct API key (local) automatically.

---

## Adding a New `/platform/*` Endpoint

Pattern from the existing endpoints in `bridge.py`:

1. Add the route with `@app.route('/platform/your-endpoint', methods=['POST'])`.
2. Call `_verify_api_key(request)` at the top — it returns `(email, tier)` or aborts 401.
3. Validate the request body (abort 400 on missing fields).
4. Generate an `execution_id = str(uuid4())`.
5. Wrap the response: `_platform_envelope(execution_id, your_data_dict)`.
6. Add `X-Contract-Version: 1.0.0` to response headers.
7. Add the TypeScript type to `packages/shared/lib/platform-contract.ts`.
8. Add a Python test in `python/tests/test_platform.py`.

The contract file (`platform-contract.ts`) is the single source of truth for all `/platform/*` schemas. Add the TypeScript interface there first, then implement the Python endpoint.

---

## Supabase

The project uses Supabase for:
- `api_key_store` — API key hashes and usage tracking
- `dept_graces` — grace chain token ledger (constitutional token economy)
- `revenue_cycles` — completed collaboration records
- `purchases` — payment records

```bash
# Check which tables exist
# Use the Supabase MCP tools in Claude Code: mcp__71923ddf__list_tables

# Apply a migration
# supabase/migrations/ for new SQL files
# Then: mcp__71923ddf__apply_migration
```

**Never store raw API keys.** Only SHA-256 hashes go in the database. The raw key is returned to the customer once at provisioning time.

**`SUPABASE_SERVICE_ROLE_KEY` is server-side only.** It belongs in Cloud Run secrets and Supabase edge function secrets, never in any frontend `.env`.

---

## Rust (aegis-cl-psi)

```bash
cd aegis-cl-psi

# Run all tests (plain cargo test — NEVER --all-features)
cargo test

# Run a single module
cargo test gossip_broadcast

# Run a single test
cargo test verify_chain_tampered
```

Key rules:
- `BTreeMap` / `BTreeSet` only — never `HashMap` (iteration order must be deterministic)
- Hash field bytes always in big-endian (`to_be_bytes()`)
- Float values hashed as `f64.to_bits().to_be_bytes()`
- Every gate module starts from `*_GENESIS_HASH = [0u8; 32]`

---

## Working with Skills

Skills are the automaton's exocortex — tamper-evident SKILL.md files in `sovereign-omega-v2/.claude/skills/`. Each skill is a constitutional amendment that all future sessions inherit via the `skills:` array in `.claude/settings.json`.

```bash
# Skills live here:
ls sovereign-omega-v2/.claude/skills/

# To invoke a skill in Claude Code:
/skill-name  # e.g. /zoom-out, /morning-audit, /ship
```

Key active skills:
- `metacognition` — the 7-layer cognitive protocol; read before any complex session
- `anthropic-alignment` — strategic context for the partnership thesis
- `deploy` — full deployment workflow (Vercel + Cloud Run)
- `constitutional-audit` — health check before any deploy
- `gate-pair` — protocol for building new Rust gate modules

---

## Commercial Products

The three commercial products (`platform-picker`, `hook-generator`, `content-calendar`) are Vite + React apps that use DashScope (Qwen) as their AI backend. Each requires a buyer's own `VITE_DASHSCOPE_API_KEY`.

```bash
cd platform-picker && npm install && npm run build && vercel --prod
# Same for hook-generator and content-calendar
```

**Payment flow:** Users buy on `aegisomega.com/pricing` (PayPal). After purchase, they receive:
1. An API key (`aegis_...`) for the `/platform/collaborate` API
2. One-click links to all three tools (pre-authenticated via `aegis_token` URL parameter)

The `AccessGate` component in `packages/shared/components/AccessGate.tsx` enforces payment at the product level. It validates the `aegis_token` via HMAC or ECDSA P-256.

---

## Environment Setup

Each product has an `.env.example`. Copy it to `.env` and fill in the values.

Critical vars for local development:

```bash
# sovereign-omega-v2/.env
ANTHROPIC_API_KEY=sk-ant-...        # Direct API (local only; Cloud Run uses Vertex AI)
SUPABASE_URL=https://...supabase.co
SUPABASE_SERVICE_ROLE_KEY=...       # Server-side only — never commit

# hub/.env
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
VITE_PAYPAL_CLIENT_ID=...           # Public — safe to set
```

**Never commit any `.env` file.** They are gitignored. The list in `CLAUDE.md §Never-Commit Files` is exhaustive.

---

## Branch and PR Workflow

Active development branch: `claude/test-coverage-analysis-keTIk`

```bash
git checkout claude/test-coverage-analysis-keTIk
git pull origin claude/test-coverage-analysis-keTIk

# After changes — run Gate 8 first:
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build

# Then commit and push:
git add <specific files>  # never git add -A (avoid accidentally staging .env files)
git commit -m "feat(scope): description"
git push -u origin claude/test-coverage-analysis-keTIk
```

CI runs 6 jobs. The BFT quorum gate requires ≥4/6 passing (≥ 1/φ ≈ 61.8%). If CI fails, fix the underlying job — don't touch the quorum math.

---

## Epistemic Tier System

Every code module declares an epistemic tier. This governs what claims can be made:

| Tier | What it means | Where allowed |
|------|--------------|---------------|
| T0 | Mechanically proven (deterministic, byte-identical) | `src/core`, `src/event`, `src/gate` |
| T1 | Empirically validated (≥3 independent observations) | Most of `src/` |
| T2 | Engineering hypothesis (computable, not yet optimal) | `src/` with evidence |
| T3 | Research conjecture | `src/` with label |
| T4/T5 | Blocked in `src/` | `docs/` only |

When in doubt, label your code T2 and note what evidence would promote it to T1.

---

## What Not to Do

- `--all-features` in cargo (breaks CI — `hip`/`rocblas` need ROCm hardware)
- `Date.now()` anywhere except `src/event/uuid.ts`
- `HashMap` in Rust (use `BTreeMap`)
- `JSON.stringify` for hashing (use `canonicalizeJCS`)
- Modify `gate.py`, `dna.py`, or `router.py` without `/guardian APPROVED`
- Store raw API keys in the database (SHA-256 hash only)
- Client-side payment token minting (server-side only — this was a past critical vulnerability)

---

## Getting Help

- `/zoom-out` — get a full system status overview
- `/morning-audit` — constitutional health check
- `/diagnose` — systematic debugging protocol
- Architecture questions → invoke the `aegis-architecture` skill
- Partnership/enterprise questions → invoke the `anthropic-alignment` skill

The `CLAUDE.md` in the repo root is the authoritative coordination document. When in doubt, read it.
