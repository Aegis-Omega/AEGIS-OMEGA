# INDEX.md — AEGIS Repository Authority Graph

> Ground truth for the MYTHOS BOOTSTRAP pipeline. Every BUILDER modification must
> reference a path in this graph. Files not listed here require PLANNER-level approval
> before a BUILDER stage may touch them.

**Epistemic Tier: T0 (machine-readable authority)**
**Updated:** 2026-06-19

---

## Constitutional Files (FROZEN — never modify without /guardian APPROVED)

| Path | Role | SHA256 |
|------|------|--------|
| `sovereign-omega-v2/python/gate.py` | Mutation authority — sliding-window gate signal tracker | `bbe942b819594fd522b421bb9d3aa084735a873d526f35a1e782f31346f3d0fc` |
| `sovereign-omega-v2/python/dna.py` | Canonical type definitions — EventClass, GateSignal, SCHEMAS | `cd30ddd5db0403b0e64fb30ce53e0373997fc53cb900a26167eef7d0b69cf8d8` |
| `sovereign-omega-v2/python/router.py` | Deterministic verifier-byte dispatch — fail-closed | `8c06ed37a7d95d9de9129c32a426fe5c2b0cd960c2cf5c84c71726b72e6cf941` |

---

## Core TypeScript Source (`sovereign-omega-v2/src/`)

| Path | Role | Tier |
|------|------|------|
| `src/core/canonicalize.ts` | RFC 8785 JCS → SHA-256 — only permitted hash path | T0 |
| `src/core/types.ts` | Branded types: UUIDv7, SHA256Hex, BoundedDelta, SequenceNumber | T0 |
| `src/constitutional/martingale.ts` | `certifyMartingale()` + `assertMartingaleAnchored()` | T0 |
| `src/constitutional/reduction.ts` | `admitAbstraction()` — blocks T4/T5 constructs | T0 |
| `src/consensus/swarm.ts` | `tallyVotes()` at 1/φ quorum threshold | T0 |
| `src/frame/adaptive-lineage.ts` | Hash-chained TOPOLOGY_TRANSITION + CAPABILITY_EVOLUTION | T0 |
| `src/metacognition/loop.ts` | `MetacognitiveLoop` — tamper-evident self-observation stream | T0 |
| `src/event/uuid.ts` | Only file permitted to call `Date.now()` | T0 |
| `src/gate/bernstein.ts` | Bernstein bounds — never Hoeffding | T1 |
| `src/verifier/calibration.ts` | VCG calibration — V4/V5 excluded | T1 |

---

## Python Layer B (`sovereign-omega-v2/python/`)

| Path | Role | Tier |
|------|------|------|
| `python/bridge.py` | Flask HTTP bridge — port 7890, all `/platform/*` endpoints | T1 |
| `python/core_matrix.py` | M1/M2/M3 over contiguous byte array, bit-shifted integer arithmetic | T1 |
| `python/tgcs_afse.py` | TGCS + AFSE controllers — sequence-number regularity, no wall-clock | T1 |
| `python/gradient_anchor.py` | Drift anchor — zero tolerance raises RuntimeError | T1 |
| `python/tests/test_platform.py` | Platform contract — 557 tests | T0 |

---

## Test Files (`sovereign-omega-v2/test/`)

| Path | Gates Covered | Test Count |
|------|--------------|------------|
| `test/unit/jcs.test.ts` | Gate 1 — RFC 8785 conformance | ~20 |
| `test/unit/sequence.test.ts` | Gate 2 — atomic sequences | ~15 |
| `test/unit/immutable.test.ts` | Gate 3 — immutability | ~12 |
| `test/unit/reducer.test.ts` | Gate 4 — pure reducers | ~18 |
| `test/unit/vcg.test.ts` | Gate 5 — VCG calibration | ~24 |
| `test/unit/gate.test.ts` | Gate 6 — Bernstein bounds | ~20 |
| `test/integration/replay.test.ts` | Gate 7 — replay sovereignty | ~30 |
| `test/integration/pipeline.test.ts` | Gate 7 — pipeline integrity | ~25 |
| `test/unit/martingale.test.ts` | Constitutional law enforcement | 24 |
| `test/unit/metacognition.test.ts` | MetacognitiveLoop tamper detection | 27 |
| `test/unit/adaptive-lineage.test.ts` | Hash-chained lineage | 28 |
| `test/unit/autopoietic-admission.test.ts` | T4/T5 blocking via admitAbstraction() | 10 |
| `test/integration/holonic-triad-proof.test.ts` | Gate 79 — φ-convergence | ~18 |
| `test/integration/phi-holonic-triad-extension.test.ts` | Gate 80 — φ extension | ~20 |
| `test/integration/replay-topology-stability.test.ts` | Gate 81 — 3-run determinism | 14 |

---

## Scripts

| Path | Purpose |
|------|---------|
| `sovereign-omega-v2/scripts/verify-hashes.mjs` | Frozen file SHA-256 verification — must exit 0 |
| `sovereign-omega-v2/scripts/proof-demo.sh` | 6-proof constitutional demo — all must PASS |
| `sovereign-omega-v2/scripts/mythos-pipeline.ts` | Claude API 6-stage MYTHOS pipeline |

---

## Commercial Products

| Path | Product | Deploy |
|------|---------|--------|
| `hub/` | Landing page + live MetacognitiveLoop | Vercel → aegisomega.com |
| `platform-picker/` | Platform recommendation ($19) | Vercel |
| `hook-generator/` | Viral hook generator ($19) | Vercel |
| `content-calendar/` | Content calendar ($19) | Vercel |
| `cockpit/` | AI chat with telemetry | Vercel |

---

## Python SDK

| Path | Purpose |
|------|---------|
| `packages/aegis-py/` | `AegisClient` / `AsyncAegisClient` / `aegis` CLI |
| `packages/shared/` | `@shared/lib/dashscope`, `inference-router`, `constitutional-ai` |

---

## Gemma Holon Client (`clients/gemma-holon/`)

| Path | Purpose |
|------|---------|
| `clients/gemma-holon/skills/ogemma-gate.md` | Agent Skills for Google AI Edge Gallery (Gemma-4E4B iOS) |
| `clients/gemma-holon/skills/ogemma-gate.json` | JSON skill definition for iOS AI Chat |
| `clients/gemma-holon/state.json` | Biological state: `{ stress, attention, rir, atp }` — holon gate input |

---

## Hooks & Configuration

| Path | Purpose |
|------|---------|
| `.claude/settings.json` | Root hooks: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop |
| `.claude/hooks/session-start.sh` | npm deps + verify-hashes + manifold load |
| `.claude/hooks/pre-commit-gate.sh` | Gate 8 enforcement before every git commit |
| `.claude/hooks/pre-write-tier.sh` | L6 ASSESS tier classification before every write |
| `.claude/hooks/post-write.sh` | Viability ring assertion after write |
| `.claude/hooks/stop-constitutional-seal.sh` | Evening seal on session end |

---

## Skills (key entries — full list: 58 skills in sovereign-omega-v2/.claude/skills/)

| Skill | Invocation trigger |
|-------|--------------------|
| `automaton-workflow` | Workflow, hooks, routines, automaton review |
| `autopoiesis` | Self-organization, consciousness, autopoietic properties |
| `brainstorming` | New feature design — hard gate before implementation |
| `constitutional-law` | Root law, replay sovereignty, ontology admission |
| `constitutional-audit` | Pre-commit/deploy health check |
| `deploy` | Vercel, Cloud Run, production deployment |
| `diagnose` | Test failures, build errors, runtime assertions |
| `gate-pair` | Executing two gates in sequence |
| `metacognition` | 7-layer cognitive protocol |
| `morning-audit` | Session start verification |
| `mythos-bootstrap` | 6-stage MYTHOS pipeline enforcement |
| `replay-sovereignty` | Cross-platform determinism proof |
| `stop-slop` | Prose quality gate — invoke before writing any artifact |
| `zoom-out` | Status overview, gate progress, next steps |

---

## Sovereign AGI OS (cross-project reference)

| Concept | Description | Relation to AEGIS |
|---------|-------------|-------------------|
| `HD = |claimed − actual|` | Hallucination delta metric | Maps to `AdaptivePower(T) ≤ ReplayVerifiability(T)` — both measure divergence from ground truth |
| `state.json` | Biological state: stress, attention, RIR, ATP | Analogous to AEGIS SYSTEM STATE VECTOR |
| Swarm / hypergraph | N persona-diverse agents, inverse-HD weighting | Analogous to AEGIS 39-dept swarm at 1/φ quorum |

---

## Forbidden Modifications

| File/Pattern | Reason |
|---|---|
| `sovereign-omega-v2/python/gate.py` | FROZEN constitutional file |
| `sovereign-omega-v2/python/dna.py` | FROZEN constitutional file |
| `sovereign-omega-v2/python/router.py` | FROZEN constitutional file |
| `hub/.env`, `cockpit/.env`, `platform-picker/.env` | API keys — never commit |
| `sovereign-omega-v2/.env` | API keys — never commit |
| `benchmark/multi_model_runner.py` | READ ONLY (Sovereign AGI OS) |
| `docs/outputs/kaggle_writeup_FINAL.md` | LOCKED (Sovereign AGI OS) |

---

## Build Commands (strict gate sequence)

```bash
# Gate 1 (always first):
cd sovereign-omega-v2 && npm run test -- test/unit/jcs.test.ts

# Gate 8 (before every commit):
npm run test && npm run typecheck && npm run build

# Constitutional membrane:
node scripts/verify-hashes.mjs   # must exit 0

# Platform contract:
python python/tests/test_platform.py   # must show 453 PASS
```
