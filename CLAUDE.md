# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# Behavioral Guidelines — Anti-Slop Protocol (READ FIRST, EVERY SESSION)

These rules take precedence. They exist because the same mistakes kept repeating
across sessions. Follow them before reaching for any of the elaborate framing below.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites
due to overcomplication, and clarifying questions come before implementation rather than
after mistakes.

## 5. Debug Against Reality, Not Docs

**Documentation is a hint, not authority. The running system wins.** This repo's docs
are known to be stale and contradictory — debugging from them wastes hours on code that
never runs.

Authority order when sources disagree (highest first):
1. Live system behavior (probe it)
2. The code paths the runtime/deploy actually use
3. Passing/failing tests + CI logs
4. `HANDOFF.md` (current operational state)
5. `REPO_MAP.md` (what's WIRED vs TESTED-ONLY/DORMANT/BROKEN/DEAD)
6. `CLAUDE.md` (rules, invariants, commands)
7. Older docs/specs — historical context only

The loop:
- Start from the **observed failure** (which command/endpoint/test/page, and *where* —
  local/CI/staging/prod), never from "the docs say X."
- Before editing, check `REPO_MAP.md`: is this path WIRED, or dead/tested-only? Don't fix
  code that never runs.
- Reproduce → locate the live path → smallest surgical fix → narrowest test → required gate.
- A stale doc is a **finding, not a fix target**: note it as doc-debt; don't mass-rewrite
  docs while fixing a bug (rule 3).

## Operating Loop — use what exists, ship to main

Full loop in **`WORKFLOW.md`** (repo root). The index of what's wired vs dormant vs
broken vs contradictory is **`REPO_MAP.md`** (repo root) — read it instead of
re-discovering the tree; when a doc disagrees with the code, the code wins. The two
rules that matter most:

1. **Reach for what exists before building.** Skills (`sovereign-omega-v2/.claude/skills/`),
   the `aegis` CLI + `aegis-omega` SDK (`packages/aegis-py/`), the Drive/Supabase/GitHub
   **MCP servers** (the research corpus lives in Drive — use `corpus-ingestion`), prompt
   caching (already in `python/bridge.py`), and the Rust/Python/TS layers already exist.
   Use them. State which one you checked before writing anything new.
2. **Nothing is "done" until it is on `main`, verified.** Every session opens with
   `scripts/ground-truth.sh` (branch · drift from main · unpushed · membrane · live).
   Stranded on a feature branch = not done.

---

# AEGIS Monorepo — Coordination Document
## Operator: Tarik Skalić · Hardware: AMD RX 570, 8 GB RAM

---

## Repository Layout

```
/sovereign-omega-v2/   Governance runtime (Layer A: TypeScript, Layer B: Python)
/aegis-cl-psi/         CL-Ψ — 422-gate Rust inference crate (T2, EU AI Act-compliant)
/aegis-runtime/        Seven-Pillar distributed agent swarm runtime (T2)
/packages/aegis-py/    Python SDK — AegisClient / AsyncAegisClient / aegis CLI
/packages/shared/      Shared infra (DashScope, useAsyncForm, inference-router, constitutional-ai)
/cockpit/              AI chat UI with sovereign-omega telemetry integration
/platform-picker/      Commercial product — platform recommendation ($19)
/hook-generator/       Commercial product — viral hook generator ($19)
/content-calendar/     Commercial product — content calendar ($19)
/hub/                  Landing page + hash-chained MetacognitiveLoop in browser
/aegisomega-webgpu/    Standalone WebGPU frame graph engine (σ/ρ/λ Φ-field simulation)
/studio/               Constitutional observability (projection only, no authority)
/supabase/functions/   Edge functions: verify-payment, issue-token, ls-webhook
/docs/                 Architecture diagrams, governance specs, partnership brief
```

Key specs: `sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md` (constitutional law) ·
`docs/ANTHROPIC_PARTNERSHIP_BRIEF.md` (Mythos alignment gap + runnable proof)

**CI CEREMONY gate:** `.github/workflows/ci.yml` BFT quorum — 6 jobs, threshold = 1/φ ≈ 0.618. Fewer than 4/6 = CEREMONY fails. Fix the underlying job.

---

## Build & Test Commands

### Proof demo (one command — all six constitutional proofs)
```bash
cd sovereign-omega-v2 && bash scripts/proof-demo.sh
```

### TypeScript — sovereign-omega-v2 (4076 tests)
```bash
cd sovereign-omega-v2
npm run test -- test/unit/jcs.test.ts        # Gate 1 — run first before any change
npm run test -- test/unit/<filename>.test.ts # single file
npm run test                                 # full suite (vitest run)
npm run typecheck                            # tsc --noEmit
npm run build                                # tsc + vite build
npm run test && npm run typecheck && npm run build  # Gate 8 — MUST pass before every commit
```

### Rust — aegis-cl-psi (7178 tests)
```bash
cd aegis-cl-psi
cargo test                   # NEVER --all-features (hip/rocblas require ROCm hardware)
cargo test <module_name>     # single module
```

### Rust — aegis-runtime (133 tests)
```bash
cd aegis-runtime && cargo test
```

### Python Layer B
```bash
cd sovereign-omega-v2
python python/tests/test_platform.py         # platform contract (453 tests)
python python/tests/stress_test.py --quick   # P1 smoke (60s)
python python/tests/stress_test.py --crash-loops  # P2 epoch failsafe (~10 min)
```

### Python SDK
```bash
cd packages/aegis-py && pip install -e .
aegis --help
aegis status                                 # calls /platform/status
aegis collaborate --objective "test" --mode revenue
```

### Hash integrity (run before every session)
```bash
cd sovereign-omega-v2 && node scripts/verify-hashes.mjs   # must exit 0
```

---

## Epistemic Tier System

| Tier | Meaning | Example |
|------|---------|---------|
| **T0** | Mechanically proven — deterministic, byte-identical | RFC 8785 canonicalization, SHA-256 chain |
| **T1** | Empirically validated | Fibonacci scheduler, martingale form |
| **T2** | Engineering hypothesis — computable, not yet proven optimal | BFT quorum, ML routing |
| **T3** | Research conjecture | Phase 6 algebraic topology correspondence |
| **T4/T5** | BLOCKED — confined to `docs/` only | Sovereignty claims |

Promotion is evidence-driven: T2→T1 requires ≥3 independent validations; T1→T0 requires formal proof or byte-identical cross-platform demo. Record promotion as `TIER_PROMOTION` entry in MetacognitiveLoop.

---

## Metacognitive Protocol

**Before every LOCK phase:**
- `node scripts/verify-hashes.mjs` → must exit 0 (L7 self-model valid)
- Classify the action's epistemic tier — T0/T1/T2/T3 (L6)
- Read target file before editing (L3)
- Gate sequence must be respected — never skip gates (L5)

**Non-equivalence invariants (never conflate):**
```
Test pass ≠ Correctness · Auditability ≠ Safety · Replayability ≠ Correctness
Governance ≠ Alignment · Calibration ≠ Truthfulness
```

**Error patterns:** wrong working directory is the #1 source of false failures. Always confirm `pwd` matches the expected repo root before running tests or builds. Read type definitions before writing tests. Run `npm run build` before every `git commit`.

Full protocol: `/metacognition` skill in `sovereign-omega-v2/.claude/skills/`.

---

## Architecture: Layer Stack

```
FIELD    — commercial products (cockpit, studio, platform-picker, …)
ORGANISM — Python bridge (bridge.py, port 7890)
CELLULAR — TypeScript governance runtime (sovereign-omega-v2/src/)
MOLECULAR — Rust gossip + math fabric (aegis-cl-psi/src/, 422 gate modules)
ATOMIC   — Seven-Pillar runtime (aegis-runtime/src/)
```

### Key TypeScript seams

| File | Purpose |
|------|---------|
| `src/core/canonicalize.ts` | RFC 8785 → SHA-256; only permitted hash path |
| `src/constitutional/martingale.ts` | `certifyMartingale()` + `assertMartingaleAnchored()` |
| `src/consensus/swarm.ts` | `tallyVotes()` at 1/φ quorum |
| `src/constitutional/reduction.ts` | `admitAbstraction()` — blocks T4/T5 |
| `src/frame/adaptive-lineage.ts` | Hash-chained capability evolution |
| `src/metacognition/loop.ts` | Tamper-evident self-observation stream |

### Python Bridge endpoints (`python/bridge.py`, port 7890)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Liveness |
| `/node` | GET | `t0_verdict`, `corruption_count`, `c_hash` |
| `/telemetry` | GET | Live PGCS/VCG/epoch metrics |
| `/claude` | POST | Governed Claude call (hash-certified) |
| `/claude/stream` | POST | SSE streaming variant |
| `/platform/status` | GET | Public health + contract version |
| `/platform/collaborate` | POST | 39-dept swarm (API key required) |
| `/platform/executions` | POST | Async initiation → stream URL |
| `/platform/executions/live` | GET | SSE: dag_step / agent_event / completion |
| `/platform/executions/{id}` | GET/DELETE | Fetch / remove stored result |

All `/platform/*` responses: `PlatformEnvelope<T>` + `X-Contract-Version: 1.0.0`.

### Shared infrastructure (`packages/shared/`)

| Module | Purpose |
|--------|---------|
| `@shared/lib/dashscope` | DashScope/Qwen API caller |
| `@shared/lib/inference-router` | DashScope → Ollama → Claude → CL-Ψ fallback |
| `@shared/lib/constitutional-ai` | `callConstitutional<T>()` — audit chain + martingale |
| `@shared/lib/access` | P-256 server-issued payment tokens |

---

## Critical Invariants

### TypeScript (`src/`, `test/`)
- No `Date.now()` except `src/event/uuid.ts`
- No `array.length` for sequences — use `IndexedDBSequenceAllocator`
- No `Set`/`Map` in `ProjectionState` — arrays only (RFC 8785)
- No `JSON.stringify` for integrity — use `canonicalizeJCS`
- `deepFreeze` every state object after construction
- Version mismatch = hard abort. Bernstein bounds, not Hoeffding. `.js` suffix on all imports.

### Rust (`aegis-cl-psi/`, `aegis-runtime/`)
- `BTreeMap`/`BTreeSet` only — never `HashMap`
- `f64` in hash: `value.to_bits().to_be_bytes()` only
- `saturating_add`/`saturating_mul` — no silent overflow
- Always `to_be_bytes()` — never `to_le_bytes()` in hash inputs
- Never `--all-features` in CI

### Python (`python/`)
- No `time.time()` in determinism-critical paths — use sequence numbers
- `corruption_count` must equal 0. PGCS must pass before TGCS is valid.

---

## Constitutional Files (FROZEN — never modify without /guardian APPROVED)

| File | SHA256 |
|------|--------|
| `sovereign-omega-v2/python/gate.py` | `bbe942b819594fd522b421bb9d3aa084735a873d526f35a1e782f31346f3d0fc` |
| `sovereign-omega-v2/python/dna.py` | `cd30ddd5db0403b0e64fb30ce53e0373997fc53cb900a26167eef7d0b69cf8d8` |
| `sovereign-omega-v2/python/router.py` | `8c06ed37a7d95d9de9129c32a426fe5c2b0cd960c2cf5c84c71726b72e6cf941` |

---

## Environment Variables

| Variable | Used by | Purpose |
|----------|---------|---------|
| `VITE_DASHSCOPE_API_KEY` | platform-picker, hook-generator, content-calendar | Qwen API key |
| `VITE_DASHSCOPE_MODEL` | `@shared/lib/inference-router` | Qwen model (default: `qwen3.7-plus`; coder tasks: `qwen3-coder-plus`) |
| `VITE_CLAUDE_API_KEY` | hub, packages/shared | Anthropic API key |
| `VITE_BRIDGE_URL` | hub | Public bridge URL (optional) |
| `AEGIS_USE_VERTEX` | python bridge | `true`=Vertex AI (opt-in ONLY); anything else=direct API key. Never auto-selects Vertex (that caused the GCP bill). |
| `AEGIS_VERTEX_PROJECT` | python bridge | GCP project (default: `aegisomegav1`) |
| `ANTHROPIC_API_KEY` | python bridge | Direct API key — the default inference path |
| `AEGIS_SWARM_MODEL` | python bridge | Swarm model (default: `claude-opus-4-8`) |
| `SUPABASE_URL` | python bridge | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | python bridge | Service role key (server-side only — never frontend) |

---

## Never-Commit Files

```
hub/.env · cockpit/.env · platform-picker/.env · hook-generator/.env
content-calendar/.env · sovereign-omega-v2/.env
~/aegis/server-setup.sh · ~/.hermes/config.yaml · ~/.hermes/.env
~/.hermes/MEMORY.md · ~/.clinerules · /root/.config/gdrive-mcp/credentials.json
```

---

## Deployment

**Commercial products → Vercel:** `vercel --prod` from each product dir after Gate 8 passes.  
Gumroad: $19/product, $29 (any 2), $39 (all 3).

**Core services → Cloud Run (europe-west3):** `git push origin main` triggers GitHub Actions WIF deploy.  
Domain: `aegisomega.com` (Cloudflare DNS). GCP account: `info@aegisomega.com`.

**Payment security:** tokens minted server-side only via Supabase edge functions.  
Never re-introduce client-side token minting (`ls-webhook`: always include `ls_product_id` NOT NULL).

---

## Root Constitutional Law

```
AdaptivePower(T) ≤ ReplayVerifiability(T)
```

**φ-convergence (Gate 79, proven):** `MUTATION_RATE_LIMIT = DEFAULT_QUORUM_THRESHOLD = (√5−1)/2 ≈ 0.6180339887`  
**Martingale:** `E[S_{n+1}|F_n] = S_n` — suspension if `!is_anchored || !drift_bounded || !entropy_bounded`  
**Law of Silence:** agents communicate exclusively through mediated `EventEnvelope`  
**Corpus Sovereignty:** all corpus enters through 5-phase RALPH loop; no raw narrative in agent cognition

**Prohibited (T0_ABORT — no exception paths):**  
hidden memory · unrestricted recursion · autonomous mutation authority · unverifiable adaptation  
replay divergence · topology non-determinism · unbounded ecology · centralized sovereign intelligence

**Open hard problems:** cross-platform deterministic replay · GPU nondeterminism · replay state explosion · verifier scalability · floating-point canonicalization · incremental proof certification · distributed topology hash stability

---

## Orchestration Alliance

Claude (coordinator) · ChatGPT (adversarial audit, temperature 0.99) · Qwen3.7-Plus (implementation, `qwen3.7-plus`) · Qwen3-Coder (BUILDER stage, `qwen3-coder-plus`)

Architecture: FROZEN. No T4/T5 construct may ground a T0–T2 claim without evidence review.

---

## MYTHOS BOOTSTRAP (added 2026-06-14)

**INDEX.md** (`/INDEX.md`) is the machine-readable repository authority graph — ground truth for the MYTHOS pipeline. Every BUILDER modification must cite a path from this file. Files not listed require PLANNER-level approval.

**mythos-bootstrap skill** (`sovereign-omega-v2/.claude/skills/mythos-bootstrap/SKILL.md`) defines the 6-stage execution pipeline: ORCHESTRATE → PLAN → VALIDATE → BUILD → REVIEW → FINALIZE, with SYSTEM STATE VECTOR emitted every cycle and RECONCILIATION MODE on failure.

**mythos-pipeline.ts** (`sovereign-omega-v2/scripts/mythos-pipeline.ts`) — Claude API multi-agent service. Each stage is a separate `claude-opus-4-8` call with role-constrained system prompt. Usage: `npx tsx scripts/mythos-pipeline.ts "task description"`. Exit 0 = FINALIZED · Exit 1 = reconciliation exhausted.

**SessionStart hook** initializes SYSTEM STATE VECTOR with live INDEX.md sha256 on every session.

**Cross-project:** MYTHOS BOOTSTRAP bridges AEGIS-Ω and Sovereign AGI OS. `AdaptivePower(T) ≤ ReplayVerifiability(T)` ↔ `HD = |claimed − actual|` — both measure divergence from ground truth. AEGIS does it cryptographically; Sovereign AGI OS biologically.
