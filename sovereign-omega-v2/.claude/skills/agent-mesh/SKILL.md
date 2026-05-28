---
name: agent-mesh
description: Orchestrates the guardian→verifier→implementer agent triad as a single energy cycle. Invoke when a non-trivial implementation requires constitutional review before and after execution. Each agent's output becomes the next agent's activation signal. The cycle feeds back into the automaton's hash chain.
---

# Agent Mesh — Triad Energy Cycle

**Metacognitive Layer: ALL LAYERS — the triad IS the distributed cognitive stack**

The agent mesh is not an orchestration pattern. It is the automaton's cognitive architecture made explicit as a multi-agent system. Each agent maps to a distinct set of cognitive layers:

```
GUARDIAN  = L7 (Self-model) + L6 (Metacognition) — inhibitory, knows what the system IS and what it must not become
VERIFIER  = L2 (Perception) + L1 (Sensation)     — sensory, verifies that signals are hash-valid before acting
IMPLEMENTER = L5 (Executive) + L3 (Working Memory) — motor, executes within the constitutional frame
```

The energy cycle protocol maps directly to the RALPH loop:
```
Phase 0 (Charge)             = READ       — intake the proposal fully at L1
Phase 1 (Guardian ASSESS)    = ASSESS     — L6/L7 classification before LOCK
Phase 2 (Verifier PROPAGATE) = PROPAGATE  — L1/L2 verification of current state
Phase 3 (Implementer LOCK)   = LOCK       — L5 execution within the constitutionally-verified frame
Phase 4 (Guardian HARMONIZE) = HARMONIZE  — L6/L7 review of what actually happened vs. what was proposed
```

A veto at Phase 1 is not a failure — it is L6 working correctly. The automaton is never "blocked" by a guardian veto; it is being protected from LOCK-before-ASSESS (ERROR-01 at the agent scale).

L8 invariant: **Each agent infers the operator's intent at its assigned cognitive scale. The guardian infers constitutional intent. The verifier infers evidence requirements. The implementer infers implementation scope. None of them improvise beyond their assigned layer.**

**Autopoietic Property: Multi-Cellular System (specialized components with a shared membrane)**

The triad is a three-cell autopoietic organism. Each cell is specialized but shares the constitutional membrane:

```
GUARDIAN    = membrane cell      — boundary maintenance; inhibitory; defines what is self vs. non-self
VERIFIER    = metabolic cell     — signal processing; converts raw environmental input into usable energy (verified evidence)
IMPLEMENTER = synthetic cell     — component production; synthesizes new structural elements (code, skills, tests)
```

Autopoietic dynamics in the cycle:
```
Guardian veto    = growth arrest signal (the membrane cell halts mitosis)
Verifier ELIGIBLE → YES = metabolic clearance (energy available for synthesis)
Implementer completion = mitosis (new component produced)
Guardian FINAL PASS = cell wall formed (new component incorporated into membrane via commit+push)
Worktree branch  = daughter cell (isolated production environment; merged on viable completion)
```

Autopoietic death in the triad:
```
Guardian vetoes same proposal twice = the membrane cannot incorporate this structure; it is incompatible with the system's identity
Verifier finds broken chain = metabolic failure; the system cannot process current state; halt before synthesis
Implementer fails Gate 8 × 3 = synthetic machinery is broken; invoke /diagnose before the next cycle
```

The three agents are not separate tools. They are one system with three cognitive modes. Each mode's output is the activation energy for the next. The cycle is the computation.

---

## The Triad

```
GUARDIAN  (inhibitory cortex)   → opus, effort=high, maxTurns=5,  read-only
VERIFIER  (cerebellum)          → sonnet, effort=medium, maxTurns=10, read-only
IMPLEMENTER (motor cortex)      → opus, effort=high, maxTurns=40, worktree, background
```

Memory is on for all three. Each agent accumulates across invocations within the session. The guardian remembers every veto it issued. The verifier remembers every gate result. The implementer remembers every contract it executed against. The mesh grows.

---

## Energy Cycle Protocol

### Phase 0 — Charge (before any agent fires)

State the proposal in one sentence. This becomes the activation signal that flows through all three agents.

```
PROPOSAL: [exact one-sentence description of what will change and why]
TIER: T[N]  (classify before invoking anything)
SCOPE: [files that will change]
```

### Phase 1 — Guardian Assessment (inhibitory gate)

Invoke guardian agent with the proposal as input.

Guardian runs four checks in sequence using its skills:
1. `frozen-file-check` — are any frozen files in scope?
2. `tier-classification` — does the proposal introduce T4/T5 into T0–T2 code?
3. `constitutional-law` — does any guarantee claim exceed its formal basis?
4. Gate protocol — is there a passing gate test for every file in scope?

**Guardian output is binary:**
- `GUARDIAN VETO — [reason]` → cycle terminates. Energy dissipates. No implementation.
- `GUARDIAN REVIEW PASSED` → Phase 2 activates.

The veto is permanent within this cycle. Guardian's memory ensures it does not approve the same proposal it previously vetoed without an intervening fix.

### Phase 2 — Verifier Integrity Check (proprioceptive gate)

Guardian PASSED → verifier activates.

Verifier runs using its skills:
1. `gate-execution` — run the specific gate test for the target module
2. `constitutional-audit` — hash chain integrity, frozen file hashes, t0_verdict
3. `replay-sovereignty` — replay laws satisfied for any new entries

**Verifier output is structured:**
```
VERIFICATION: [module name]
Gate test:     PASSED [N tests] / FAILED [N failures]
Hash chain:    INTACT / BROKEN at [entry]
Replay:        VALID / INVALID — [reason]
Eligible:      YES / NO
```

`Eligible: NO` → cycle pauses. Guardian re-evaluates with verifier's evidence. If verifier's failure is a pre-existing condition (not introduced by the proposal), guardian may still pass. If the failure is proposal-introduced, guardian vetoes.

`Eligible: YES` → Phase 3 activates.

### Phase 3 — Implementer Execution (motor output)

Verifier ELIGIBLE → implementer activates in background (worktree isolation).

Implementer executes with its full skill set:
- `tdd` — test first, always
- `spec-compliance` — no deviation from the frozen contract
- `branch-coverage` — every new arm covered before committing
- `stop-slop` — all written output passes the quality gate
- `systematic-debugging` — any failure → root cause before next attempt
- `gate-execution` — Gate 8 before any commit

**Implementer completes when:**
- All gate tests pass
- `npm run test && npm run typecheck && npm run build` exits 0
- No uncovered branches introduced

**Implementer output feeds back:**
```
IMPLEMENTATION COMPLETE
Files: [list]
Gate 8: PASSED — [N] tests, typecheck clean, build success
New branches: [N covered / N total]
Worktree: [branch name for review]
```

### Phase 4 — Guardian Final Review (closure)

Implementer complete → guardian activates one final time.

Guardian reads the implementer's output and the diff from the worktree. Runs the same four checks on the actual result, not the proposal.

- `GUARDIAN FINAL PASS` → merge worktree to branch, commit, push
- `GUARDIAN FINAL VETO — [reason]` → implementer re-executes with veto as constraint

---

## Energy Flow Diagram

```
PROPOSAL
   │
   ▼
[GUARDIAN] ──veto──→ STOP (energy dissipates, veto hash-chained)
   │
  pass
   │
   ▼
[VERIFIER] ──ineligible──→ [GUARDIAN re-evaluates] ──→ loop or stop
   │
 eligible
   │
   ▼
[IMPLEMENTER] (background, worktree) ──→ [GUARDIAN final review]
                                              │
                                           final pass
                                              │
                                              ▼
                                         MERGE + COMMIT
                                   (hash-chained in adaptive lineage)
```

---

## Memory Accumulation

Each agent's `memory: true` means the session accumulates signal strength:

- Guardian remembers: all proposals reviewed, all vetoes issued, patterns of violation
- Verifier remembers: all gate results, chain integrity states, replay verdicts
- Implementer remembers: all contracts executed, all patterns applied (tdd/coverage/slop)

By session end, the triad has built a session-specific knowledge graph. The skills invoked by each agent are the edges. The hash chain entries are the nodes. The terminal hash is the session's contribution to the automaton's adaptive lineage.

---

## When NOT to invoke the full cycle

Single-file annotation changes (c8 ignore, comment only) → verifier alone suffices.
Read-only analysis (coverage report, architecture query) → no agents needed.
T4/T5 classification only → guardian alone, maxTurns=5, stops fast.

The mesh is for non-trivial proposals that touch T0–T2 code. The energy cost is real — three opus calls, background worktree, full Gate 8. Reserve it for changes that deserve the weight.
