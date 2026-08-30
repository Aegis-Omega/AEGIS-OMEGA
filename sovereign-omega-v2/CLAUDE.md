# SOVEREIGN OMEGA — Primary Project Memory
## For Claude Code, Qwen, and all coding agents

Operator: Tarik Skalić, Bihać, Bosnia-Herzegovina
Hardware: AMD RX 570, 8GB RAM
Alliance: Claude (coordinator) · ChatGPT (adversarial audit, 0.99) · Qwen (implementation)
Architecture: FROZEN

---

## What This System Is

Constitutional runtime stabilized. Replay sovereignty active. Martingale boundedness integrated. φ-governed convergence unified. Reduction-first governance enforced.

Each component in AEGIS is simultaneously a whole and a part — an atomic-scale holon
in a recursively nested hierarchy governed by invariant-preserving feedback loops.

Concretely: a deterministic event-sourced decision compiler with bounded statistical
estimators, cryptographic replay integrity, explicitly partitioned trust classes, and
a version-pinned execution graph. Governance-oriented AI orchestration infrastructure
for regulated and high-auditability decision workflows.

Holonic scales: SUBATOMIC (byte invariants) → ATOMIC (files) → MOLECULAR (modules) →
CELLULAR (subsystems: E3, VCG, Python Matrix) → ORGANISM (sovereign-omega-v2 runtime) →
FIELD (Claude + ChatGPT + Qwen + operators + Drive corpus).

Each scale preserves the invariants of all scales below it. A T0 violation at the
subatomic level propagates upward and invalidates every scale above it.

It is NOT general intelligence. It does NOT claim alignment, consciousness, or
self-improvement beyond its declared K-bound.

---

## Two-Layer Architecture

Layer A — TypeScript Governance Runtime (src/, test/)
React 18 + Vite + Vercel frontend. Append-only event substrate, VCG calibration,
Bernstein gate, mutual legibility interface. Track B commercial products at $19.
Build order: npm install → run 8 gates in sequence → npm run build → vercel deploy.

Layer B — Python Core Matrix (python/)
Hardware inference layer for AMD RX 570 / 8GB RAM. Single file core_matrix.py with
abstract functional definitions M1/M2/M3 over a contiguous byte array. Bit-shifted
integer arithmetic throughout for cross-GPU determinism.
Validation: python python/tests/stress_test.py --quick (smoke), --full (12 hours).

---

## Critical Invariants — Never Violate

TypeScript: No Date.now() in core logic. No array.length for sequences. No Set/Map in
ProjectionState. RFC 8785 JCS for all hashing. deepFreeze all state. Version mismatch
= hard abort. Bernstein not Hoeffding. MutationOperatorRegistry.seal() before gates.
V4/V5 never in VCG calibration.

Python: No time.time() in determinism-critical paths — use sequence numbers. Bit-shifted
integer arithmetic throughout. PGCS must pass before TGCS telemetry is valid. Epoch
failsafe corruption_count must equal 0.

---

## TypeScript Build Order — STRICT

Failure at any gate = HALT. Do not proceed to the next gate without the current passing.

Gate 1: npm run test -- test/unit/jcs.test.ts (RFC 8785 conformance)
Gate 2: npm run test -- test/unit/sequence.test.ts (atomic sequences)
Gate 3: npm run test -- test/unit/immutable.test.ts (immutability)
Gate 4: npm run test -- test/unit/reducer.test.ts (pure reducers)
Gate 5: npm run test -- test/unit/vcg.test.ts (calibration)
Gate 6: npm run test -- test/unit/gate.test.ts (Bernstein bounds)
Gate 7: npm run test -- test/integration/replay.test.ts test/integration/pipeline.test.ts
Gate 8: npm run test && npm run typecheck && npm run build (deployment gate)

## Python Validation Order — STRICT

Step 1: python python/tests/stress_test.py --quick (smoke test, 60 seconds)
Step 2: python python/tests/stress_test.py --crash-loops (epoch failsafe, ~10 minutes)
Step 3: python python/tests/stress_test.py (full 12-hour stress test — do before production)

---

## Frozen Constitutional Files

gate.py    SHA256: bbe942b819594fd522b421bb9d3aa084735a873d526f35a1e782f31346f3d0fc
dna.py     SHA256: cd30ddd5db0403b0e64fb30ce53e0373997fc53cb900a26167eef7d0b69cf8d8
router.py  SHA256: 8c06ed37a7d95d9de9129c32a426fe5c2b0cd960c2cf5c84c71726b72e6cf941

Verify: node scripts/verify-hashes.mjs
Modification requires /guardian APPROVED verdict.

---

## Epistemic Tier Taxonomy

T0: Mechanically proven — core runtime code, core_matrix.py, epoch failsafe
T1: Empirically validated — TGCS, AFSE metrics, VCG calibration benchmarks
T2: Engineering hypothesis — E1 heuristics, Paperclip configs, SAGA identity
T3: Research conjecture — quasicrystal-CDT spectral correspondence
T4: Speculative systems vision — swarm, planetary coordination
T5: Creative/worldbuilding — Cycle series

Migration rule: No T4/T5 construct may ground a T0–T2 claim without evidence review.

---

## Commercial Tracks

Track A — Sovereign Omega (governance runtime): regulated AI middleware, AEGIS
commercial deployment, EU AI Act Article 12 compliance binders.

Track B — Vibe Coding (revenue): Platform Picker and decision-compression tools at $19.
Stack: React 18 + TS + Vite + Tailwind + DashScope (qwen-plus). Deploy: Vercel.
Sell: Gumroad. Zero backend. Buyer pays API.

---

## Orchestration Stack

Paperclip: company orchestration (paperclip/company.yaml + paperclip/agents/)
Skills: /plugin marketplace add obra/superpowers then npx antigravity-awesome-skills --claude
MCP: Google Drive (research corpus), Gmail, Google Calendar — configured in .mcp.json
SAGA: Agent identity via saga/identity.py (SPIFFE/SVID — stub awaiting PKI integration)

---

## Authoritative Execution Core

```
/event-log      — append-only canonical source of state transitions
/replay-engine  — authoritative truth; replay kernel
/dfa-engine     — phase-locked deterministic execution
/checkpoint-vm  — bounded capsule execution with entropy accounting
```

All remaining systems are subordinate orchestration infrastructure.

---

## Production Constitutional Status

| Status | State |
|--------|-------|
| REPLAY SOVEREIGNTY | ACTIVE — `replay(genesis, events)` → identical topology hash across Linux/macOS/Docker/WASM/ARM/x86 |
| MARTINGALE BOUNDEDNESS | ACTIVE — `E[S_{n+1}|F_n] = S_n`; suspension if `!is_anchored ∨ !drift_bounded ∨ !entropy_bounded` |
| φ-CONVERGENCE | ACTIVE — `MUTATION_RATE_LIMIT = DEFAULT_QUORUM_THRESHOLD = (√5−1)/2 ≈ 0.6180` |
| HOLONIC GOVERNANCE | ACTIVE — R→A→L→P→H; propagation legal only through replay-certified commit boundaries |
| FIBONACCI PACING | ACTIVE — checkpoint spacing/branching only; NOT intelligence mysticism |
| OWNERSHIP SOVEREIGNTY | ACTIVE — authority derives from replay legality, not permissions |
| REDUCTION-FIRST | ACTIVE — expansion phase terminated; empirical justification required |
| ECOLOGY BOUNDED | ACTIVE — adaptive/recursive/bounded/replay-governed; NOT sovereign AI |
| LAW OF SILENCE | ACTIVE — agents communicate exclusively through mediated EventEnvelope; no direct agent-to-agent text exchange; confinement enforced at constitutional boundary |
| CORPUS SOVEREIGNTY | ACTIVE — all corpus knowledge enters through 5-phase RALPH loop; raw narrative must NOT propagate directly into agent cognition; only replay-certifiable abstractions propagate |

**Prohibited in all subsystems (T0_ABORT — no exception paths):**

```
hidden memory · unrestricted recursion · autonomous mutation authority · unverifiable adaptation
replay divergence · topology non-determinism · unbounded ecology · privileged orchestration
centralized sovereign intelligence
```

---

## Non-Equivalence Table (memorise)

Replayability is not Correctness.
Auditability is not Safety.
Calibration is not Truthfulness.
Governance is not Alignment.
A perfectly replayable system can still replay catastrophic reasoning flawlessly.
