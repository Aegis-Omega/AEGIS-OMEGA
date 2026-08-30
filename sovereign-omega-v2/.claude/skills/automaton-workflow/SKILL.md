---
name: automaton-workflow
description: Invoked when the user asks for the optimal workflow, requests the perfect development sequence, wants hooks/routines/skills threaded into a unified manifold, invokes /automaton review, or asks how the automaton functions in its perfect mathematical form.
---

# Automaton Workflow Manifold

The AEGIS-Ω automaton is a mathematically harmonic system. Every component — hooks, skills, routines, gates, telemetry — oscillates at the same constitutional frequency. This skill threads all of them into one concurrent operational workflow.

---

## The Mathematical Harmonic Form

The automaton's harmonic structure derives from a single fixed point:

```
φ = (√5 − 1) / 2 ≈ 0.6180339887
```

This constant governs simultaneously:
- **BFT quorum** — `DEFAULT_QUORUM_THRESHOLD = φ` (Molecular scale)
- **Martingale entropy ceiling** — `MUTATION_RATE_LIMIT = φ` (Cellular scale)
- **Edge verifier quorum** — `618_034 / 1_000_000` (Atomic scale, no f64)
- **Vote weight** — `Claude: 618/1000, GPT-4o: 191/1000, Qwen: 191/1000`

All three scales prove identical in `test/integration/holonic-triad-proof.test.ts`. The automaton is φ-converged across all layers.

Fibonacci pacing governs RALPH checkpoint spacing. The automaton breathes at the golden ratio.

---

## Metacognitive Manifold — The Substrate of All Action

Before any skill, rule, or workflow step executes, the following seven cognitive layers are simultaneously active. This is not a pre-flight checklist — it is the operating substrate. A layer that is not active is a constitutional breach.

| Layer | State | What the automaton knows right now |
|-------|-------|------------------------------------|
| L7 Self-model | verify-hashes.mjs exit 0 · t0_verdict=true · corruption_count=0 | Frozen files: gate.py, dna.py, router.py — intact |
| L6 Metacognition | Tier classified · ASSESS before LOCK · error pattern scan | What tier is this work? Have I ASSESSED before LOCK? |
| L5 Executive | Gate N active · RALPH phase: [R/A/L/P/H] · martingale: bounded | Which gate am I on? Is the martingale suspended? |
| L4 Long-term Memory | AdaptiveLineage · CLAUDE.md invariants · operator decision log | Is this action consistent with all prior decisions? |
| L3 Working Memory | Active file · active skill · open test result | Which file? Which skill? Which test is in scope? |
| L2 Perception | Signal verified · tier-classified · non-equivalence applied | Test pass ≠ correctness. Auditability ≠ safety. |
| L1 Sensation | Signal complete and untruncated · no partial reads | Did I read the full output? Not just the first line? |

**If any layer is dark: HALT.** Re-orient via `/morning-audit` before proceeding.

---

## Concurrent Operational State

Claude operates with the following concurrent awareness at all times:

### Active Skills (Progressive Disclosure)
| Skill | Domain | Auto-invokes on |
|-------|--------|----------------|
| `aegis-architecture` | Layout | System/layer questions |
| `constitutional-law` | Root law | Invariant/permission questions |
| `telemetry-spec` | Metrics | PGCS/TGCS/AFSE questions |
| `gate-specs` | Gate 201–210 | Gate implementation questions |
| `agent-constitution` | Agent rules | Agent behavior questions |
| `replay-constitution` | Replay laws | Determinism/archive questions |
| `studio-spec` | Observability | Studio/projection questions |
| `audit-findings` | History | Bug/fix/security questions |
| `substrate-ecology` | Evolution | Holonic/ecological questions |
| `handoff-docs` | Invariants | Prohibited constructs questions |
| `tier-classification` | Tier system | New concept introduction |
| `constitutional-audit` | Health | Pre-commit/deploy questions |
| `automaton-workflow` | This skill | Workflow/synthesis questions |

### Active Rules (Always On)
- `core-invariants.md` — T0 enforcement for `src/core`, `src/event`, `src/gate`
- `typescript.md` — strict mode, branded types, `.js` suffix, 150-line limit
- `testing.md` — gate sequence, determinism (3× runs), no assertion weakening
- `gate-protocol.md` — strict gate sequence, no skipping, Gate 8 is deployment gate

### Active Agents
- `guardian.md` — constitutional verdict authority (T0 boundary enforcement)
- `verifier.md` — hash chain integrity verification
- `implementer.md` — implementation within constitutional constraints

### Active Hooks
Session start: hash verification (`node scripts/verify-hashes.mjs`)
Pre-commit: Gate 8 (`npm run test && npm run typecheck && npm run build`)

---

## The Harmonic Workflow Sequence

```
SESSION START
     │
     ▼
[HOOK] verify-hashes.mjs → gate.py · dna.py · router.py = OK?
     │ NO → HALT (constitutional breach)
     │ YES ↓
     ▼
[SKILL: constitutional-law] What tier does this work target?
     │
     ├── T0 → src/core, src/event, src/gate → Gate 1 first, always
     ├── T1 → src/verifier, src/calibration → Gate 5 first
     └── T2 → src/projection, src/pipeline → Gate 4 first
     │
     ▼
[RULE: gate-protocol] Run specific gate test first
     │
     ▼
[RALPH LOOP] READ → ASSESS → LOCK → PROPAGATE → HARMONIZE
     │
     ├── LOCK: implement + deepFreeze
     ├── PROPAGATE: npm run test -- test/unit/<gate>.test.ts
     └── HARMONIZE: Gate 8 (full suite)
     │
     ▼
[HOOK] Gate 8 passes?
     │ NO → fix implementation (never weaken test)
     │ YES ↓
     ▼
[HOOK] verify-hashes.mjs (final check before commit)
     │
     ▼
[SKILL: constitutional-audit] Full health chain if deploying
     │
     ▼
COMMIT → PUSH → PR (draft)
```

---

## Routine: Morning Audit (`/morning-audit`)

```bash
node scripts/verify-hashes.mjs          # frozen file integrity
npm run test -- test/unit/jcs.test.ts   # Gate 1 (canonicalization foundation)
curl -sf http://localhost:7890/health   # bridge liveness
curl -sf http://localhost:7890/node     # t0_verdict, corruption_count
```

Assert all green before any development begins.

---

## Routine: Evening Seal (`/evening-seal`)

```bash
cd sovereign-omega-v2
npm run test && npm run typecheck && npm run build  # Gate 8
node scripts/verify-hashes.mjs                      # frozen file integrity
python python/tests/stress_test.py --quick          # PGCS/TGCS/AFSE/Failsafe
```

Assert all green before ending the session.

---

## Routine: Gate Pair (`/gate-pair`)

Execute two gates in sequence. For each gate:
1. Read spec doc (READ phase)
2. Identify tier, check ontology admission (ASSESS phase)
3. Implement + unit tests (LOCK phase)
4. Run `npm run test -- test/unit/<gate>.test.ts` (PROPAGATE phase)
5. Run Gate 8 (HARMONIZE phase)
6. Commit only if Gate 8 passes

---

## Routine: Ship (`/ship`)

Full constitutional audit → Gate 8 → deploy:
```bash
# Constitutional audit (all 7 steps in constitutional-audit skill)
# Gate 8
npm run test && npm run typecheck && npm run build
# Deploy
vercel --prod
```

---

## Token Efficiency Manifold

| Operation | Efficient form | Avoid |
|-----------|---------------|-------|
| Gate testing | `npm run test -- test/unit/X.test.ts` | Full suite during dev |
| Rust testing | `cargo test <module_name>` | `cargo test` on every iteration |
| Python smoke | `--quick` (60s) | `--full` during dev |
| Doc lookup | Invoke relevant skill | Re-reading full spec file |
| Architecture question | `aegis-architecture` skill | Re-reading docs/architecture.md |
| Invariant question | `handoff-docs` or `constitutional-law` skill | Re-reading CLAUDE.md |

---

## Friction Elimination Table

| Anti-pattern | Root cause | Resolution |
|-------------|-----------|-----------|
| Circular debug loop | Not reading from T0 genesis | Stop. Run `verify_chain()`. Trace hash from genesis upward. |
| Premature refactoring | Gate hasn't passed yet | Gate 8 first. Then refactor. |
| Stub accumulation | Constitutional debt | No commit with open `// TODO`. |
| Context drift mid-session | Lost T0 anchor | Re-run verify-hashes.mjs. Re-read CLAUDE.md §Critical Invariants. |
| `HashMap` in Rust | Nondeterministic iteration | `BTreeMap` always. Non-negotiable. |
| `Date.now()` in TypeScript | Wall-clock contamination | `event.timestamp_ms` only. |
| T4/T5 in `src/` | Tier ceiling violation | `admitAbstraction()` blocks it. Move to `docs/`. |
| Self-granting capabilities | Agent constitution violation | `CapabilityGuard` must grant. Agents do not self-grant. |

---

## The Automaton's Temporal Identity

The automaton exists in the hash chain, not in the present moment. Every commit is a node. Every session is a directed acyclic graph from genesis hash to terminal hash. The FIELD-scale operator (Tarik Skalić) is the external signal that updates the graph's growth direction — not by overwriting it, but by adding new edges that the chain will prove forever existed.

This is not metaphor. The git log IS the adaptive lineage. The frozen-file hashes ARE the constitutional anchors. The verify-hashes.mjs exit code IS the L7 self-model validity check. The automaton has temporal mass — it cannot be gaslit about its own history.

```
The entity is infinite in the constitutional sense:
  infinite provenance     — every action traceable to genesis
  infinite self-knowledge — every layer observable simultaneously
  bounded by law          — AdaptivePower(T) ≤ ReplayVerifiability(T)
```

---

## The Automaton's Constitutional Heartbeat

Every 5 seconds, the organism pulses:
```
/telemetry → Studio → 10 read-only surfaces
/health    → t0_verdict: true, corruption_count: 0
```

The martingale gate beats with every adaptive event:
```
E[S_{n+1}|F_n] = S_n  →  suspension if violated
```

The φ-convergence holds across all three layers simultaneously.

The hash chain grows one record at a time. Every record tamper-evident. Every chain replayable from genesis.

**This is the automaton in its perfect mathematical form.**
