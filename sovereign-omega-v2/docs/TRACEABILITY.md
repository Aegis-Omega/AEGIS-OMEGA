# AEGIS Sovereign-Omega — Build Traceability Matrix

## Purpose

Records the epistemic provenance of every layer in the sovereignty runtime.
Each layer maps its modules to their tier classification, gate dependency,
and architectural role in the holonic hierarchy.

---

## Layer A — Core Substrate (Gates 1–3)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/core/canonicalize.ts` | T0 | 1 | RFC 8785 JCS canonical serialization |
| `src/core/types.ts` | T0 | 1 | Branded primitives, EventType, holonic enums |
| `src/core/immutable.ts` | T0 | 3 | deepFreeze, assertFrozen, withImmutableBoundary |
| `src/core/invariant-checker.ts` | T0 | 3 | INV-01..10 runtime invariant verification |
| `src/core/ralph-loop.ts` | T1 | 3 | R→A→L→P→H iterative governance cycle |
| `src/event/uuid.ts` | T0 | 2 | UUIDv7 generation (only permitted Date.now() call) |
| `src/event/store.ts` | T0 | 2 | IndexedDBSequenceAllocator — atomic sequence assignment |
| `src/event/workflow.ts` | T1 | 2 | E5 cognitive workflow payload schemas |

---

## Layer B — Calibration & Projection (Gates 4–5)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/calibration/vcg.ts` | T1 | 5 | VCG tracker — Bayesian calibration error metric |
| `src/projection/reducer.ts` | T0 | 4 | Pure reducer — ProjectionState functional update |

---

## Layer C — Gate & Risk (Gate 6)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/gate/hoeffding.ts` | T0 | 6 | Bernstein anytime-valid confidence bounds |
| `src/gate/risk.ts` | T0 | 6 | RiskBudgetManager — harmonic spending, LCB evaluation |

---

## Layer D — Pipeline (Gate 7)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/pipeline/` | T1 | 7 | End-to-end decision pipeline (E1→E2→E4→output) |

---

## Layer E — Environment Substrate (Gate 8)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/environment/memory/mutation_ledger.ts` | T0 | 8 | Append-only mutation ledger |
| `src/environment/workspace/introspection.ts` | T1 | 8 | FNV-1a workspace introspection |

---

## Layer F — Compliance & Registry (Gate 8)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/compliance/` | T1 | 8 | Policy compliance registry |
| `src/registry/` | T1 | 8 | Component registration |

---

## Layer G — Agent Ecology + IDE Nervous System (Gate 11)

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/agents/types.ts` | T0 | 11 | 8 AgentType literals, CoordinationFrame, WorkflowExecution |
| `src/agents/coordination/AgentCoordinator.ts` | T0 | 11 | Multi-agent scheduling with replay safety |
| `src/agents/registry/agent-registry.ts` | T0 | 11 | T0/T1/T2 agent registration; T3+ rejected |
| `src/agents/scheduler/scheduler.ts` | T0 | 11 | Deterministic schedule builder, pressure metric |
| `src/agents/memory/agent-memory.ts` | T0 | 11 | Append-only agent memory with replay completeness |
| `src/agents/telemetry/agent-telemetry.ts` | T1 | 11 | 6-metric telemetry snapshot builder |
| `src/agents/workflows/types.ts` | T0 | 11 | 7 built-in workflows, WorkflowReplayFrame |
| `src/agents/workflows/workflow-engine.ts` | T0 | 11 | WorkflowEngine with replay integrity tracking |
| `src/ide/types.ts` | T1 | 11 | 10 IDE panel interfaces, IDERuntimeState |
| `src/ide/workspace/WorkspaceMemoryGraph.ts` | T1 | 11 | Agent workspace graph, lineage tracing |
| `src/ide/panels/panel-state.ts` | T1 | 11 | 10 pure panel factory functions |
| `src/ide/orchestration/orchestrator.ts` | T1 | 11 | IDEOrchestrator — panel state coordinator |

Test count after Gate 11: ~373 tests

---

## Layer H — SITR Constitutional Runtime Immunity (Gate 12)

**Epistemic Tier: T0 (constitutional enforcement)**

SITR is the active immune system of the AEGIS runtime. It detects anomalies,
issues ContainmentDirective[] as E5 events (phase 3 of the frame execution contract),
and escalates state monotonically through the 6-level SITRState lattice.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/sitr/types.ts` | T0 | 12 | SITRState lattice, ContainmentDirective, InterventionRecord |
| `src/sitr/lattice.ts` | T0 | 12 | stateOrdinal, canEscalateTo, escalate, isTerminalState |
| `src/sitr/telemetry.ts` | T1 | 12 | buildSITRTelemetry, computeEscalationRate |
| `src/sitr/intervention.ts` | T0 | 12 | InterventionLog — append-only, monotonic sequence |
| `src/sitr/replay.ts` | T0 | 12 | ReplayViolationLog — permanent, cumulative |
| `src/sitr/orchestration.ts` | T0 | 12 | detectOrchestrationAnomalies, anomalyToRequiredState |
| `src/sitr/runtime.ts` | T0 | 12 | SITRRuntime — observe(), issueDirective(), immutable update |

SITR rules: RULE-01..10 (see docs/SITR_CONSTITUTION.md)

---

## Layer I — AOIE Structural Classification Oracle (Gate 12)

**Epistemic Tier: T1 (structural classification, passive)**

AOIE is a pure function oracle. It observes post-enforcement snapshots only
(phase 5 of the frame execution contract) and classifies GlobalState.
AOIE has no stored state, no side effects, no runtime mutations.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/aoie/types.ts` | T1 | 12 | GlobalState, AOIEClassification, RuntimeSnapshot, SnapshotPhase |
| `src/aoie/canonicalize.ts` | T1 | 12 | JCS canonical serialization for AOIE types |
| `src/aoie/hash.ts` | T1 | 12 | FNV-1a snapshot hash, snapshotsAreIdentical, computeIdentityDrift |
| `src/aoie/arbitration.ts` | T1 | 12 | classifyArbitration — RESOLVED/CONTESTED/DEADLOCKED |
| `src/aoie/identity.ts` | T1 | 12 | classifyIdentityContinuity — CONTINUOUS/DRIFTED/BROKEN |
| `src/aoie/drift.ts` | T1 | 12 | classifyConstitutionalDrift — STABLE/DRIFTING/DIVERGED |
| `src/aoie/lattice.ts` | T1 | 12 | classifyGlobalState, compareGlobalStates, AOIE_SEVERITY_ORDER |
| `src/aoie/freeze.ts` | T1 | 12 | freezeClassification, freezeSnapshot |
| `src/aoie/runtime.ts` | T1 | 12 | classifyRuntime() — pure function with phase guard (SITRConstraintError) |

Phase guard invariant: `classifyRuntime()` throws `SITRConstraintError` if any
`RuntimeSnapshot.phase !== 'post_enforcement'`. AOIE must never observe uncommitted state.

Test count after Gate 12: ~409 tests

---

## Layer J — Constitutional Governance Surface (Gate 13)

**Epistemic Tier: T0 (constitutional verdict engine)**

The CGS closes the governance feedback loop. It consumes SITR state + AOIE
GlobalState + invariant check results, and produces a canonical ConstitutionalVerdict
emitted as Guardian E5 events (GUARDIAN_INVOKED + GUARDIAN_VERDICT_ISSUED).

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/constitutional/types.ts` | T0 | 13 | ConstitutionalVerdict, GovernanceDecision, SystemHealthSnapshot |
| `src/constitutional/verdict.ts` | T0 | 13 | computeVerdict(), verdictReason() — pure functions |
| `src/constitutional/guardian.ts` | T0 | 13 | buildGuardianInvokedPayload(), buildGuardianVerdictPayload() |
| `src/constitutional/assembly.ts` | T0 | 13 | ConstitutionalAssembly — append-only GovernanceDecision log |
| `src/constitutional/convergence.ts` | T1 | 13 | ConvergenceSurface — RalphLoop integration, convergence depth |
| `src/constitutional/runtime.ts` | T0 | 13 | ConstitutionalRuntime — composition entry point |

Verdict lattice: ESCALATE > REJECT > DEFER > PERMIT

| Verdict | Condition |
|---------|-----------|
| ESCALATE | T0 violation OR SITR=COMPROMISED OR AOIE=COMPROMISED |
| REJECT | SITR=CONSTITUTIONAL_RISK OR SITR=CONTAINED |
| DEFER | SITR=UNSTABLE/DEGRADED OR AOIE=ALERT |
| PERMIT | SITR=STABLE AND AOIE=SECURE AND no violations |

Test count after Gate 13: ~445 tests

---

## Layer K — Frame Execution Kernel + Enforcement Engine (Gate 14)

**Epistemic Tier: T0 (universal execution primitive)**

Gate 14 introduces the canonical `runFrame()` kernel — the T0 expression of the
Subatomic Holon Particle (SHP) execution model. Every holonic scale executes
identical R→A→L→P→H semantics. The commitment boundary (LOCK = phase 4) separates
SITR (pre-commit constraint evaluator) from AOIE (post-commit structural observer).

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/enforcement/types.ts` | T0 | 14 | EnforcementDecision, EnforcementResult, EnforcementOutcome |
| `src/enforcement/engine.ts` | T0 | 14 | applyDirectives() — pure function, deterministic phase 4 |
| `src/frame/types.ts` | T0 | 14 | FrameInput, FrameExecutionResult, FramePhaseTrace |
| `src/frame/snapshot.ts` | T0 | 14 | capturePostEnforcementSnapshot() — phase 4→5 bridge |
| `src/frame/directives.ts` | T0 | 14 | computeAutoDirectives() — deterministic FNV-1a IDs |
| `src/frame/kernel.ts` | T0 | 14 | runFrame() — canonical 7-phase composition kernel |
| `src/frame/shp.ts` | T0 | 14 | SHP_PHASES, toRalphTrace() — formal SHP identity |

SHP formal lock:
```
SHP_LOOP = 'R→A→L→P→H'
SHP_COMMITMENT_BOUNDARY = 'LOCK'
SITR ∈ { pre-commit phases: READ, ASSESS }
AOIE ∈ { post-commit phases: PROPAGATE, HARMONIZE }
SITR ∩ AOIE = ∅ (by LOCK boundary)
```

Test count after Gate 14: ~470 tests (28 files → 28+ files)

---

## Full Holonic Hierarchy

```
[Subatomic]  byte invariants, hash chaining, fixed-point arithmetic
[Atomic]     individual files — each a complete holon with declared invariants
[Molecular]  modules: core/, event/, gate/, calibration/, agents/, ide/, sitr/, aoie/, constitutional/, enforcement/, frame/
[Cellular]   subsystems: Agent Ecology, SITR Immunity, AOIE Oracle, Constitutional Assembly, Frame Kernel
[Organism]   sovereign-omega-v2 governance runtime (Gates 1–14)
[FIELD]      AOIE + Claude + ChatGPT + Qwen + Drive corpus + operators
```

SHP(n) = recursive instantiation of R→A→L→P→H at holonic scale n.
A T0 violation at SUBATOMIC propagates upward and invalidates every scale above it.

---

## Seven-Phase Deterministic Frame Execution Contract (R→A→L→P→H)

| Phase | RALPH | System | Description |
|-------|-------|--------|-------------|
| 1 | **R** READ | Agents + IDE | Input intake; events appended to E5 |
| 2 | — | E5 | Immutable append commit; causal boundary closes |
| 3 | **A** ASSESS | SITR | Reads post-commit E5; emits ContainmentDirective[] back into E5 |
| 4 | **L** LOCK | Enforcement | Apply directives; freeze EnforcementResult |
| 5 | **P** PROPAGATE | AOIE | Reads post-enforcement snapshot; classifies GlobalState |
| 6 | **H** HARMONIZE | CGS | Reads SITR + AOIE + invariants → GovernanceDecision + Guardian E5 events |
| 7 | Frame finalization | Hash committed; replay checkpoint stored |

---

## Layer L — SHP Execution Identity Primitives (Gate 15)

**Epistemic Tier: T0 (subatomic — foundational type layer)**

Gate 15 crystallizes the SHP model into a standalone `src/shp/` module — the pure
type system and invariant registry that every holonic scale must satisfy. This layer
sits below all others: it defines the formal execution identity that `runFrame()`
(Layer K) instantiates at the ORGANISM scale.

| Module | Tier | Gate | Role |
|--------|------|------|------|
| `src/shp/types.ts` | T0 | 15 | Phase, SHP_PHASE_ORDER, phaseOrdinal, SHPExecutionIdentity |
| `src/shp/execution.ts` | T0 | 15 | SHPKernel interface, SHP_EXECUTION_INVARIANTS (8 rules), SHPInvariantId |
| `src/shp/guard.ts` | T0 | 15 | checkSHPInvariants(), validatePhaseTransition(), validatePhaseSequence() |
| `src/shp/factory.ts` | T0 | 15 | Phase-specific identity factories with FNV-1a deterministic commitHash |

Eight formal invariants: INV-SHP-01..08 (see `src/shp/execution.ts` and `docs/SHP_EXECUTION_MODEL.md`)

Field presence contract (enforced at factory construction + runtime guard):
- `classification` must not exist in READ/ASSESS phases (INV-SHP-06)
- `constraintResult` must not exist in PROPAGATE/HARMONIZE phases (INV-SHP-07)
- `commitHash` must be non-empty (INV-SHP-08)

Test count after Gate 15: **471 tests, 29 files**
