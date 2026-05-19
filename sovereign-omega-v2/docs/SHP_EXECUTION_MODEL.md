# Subatomic Holon Particle (SHP) Execution Model

## Epistemic Tier: T0 · Gate 14 Lock

## Core Claim

SHP is not a new layer. SHP is the execution identity of `runFrame()` across all scales.

Every component in AEGIS — Agent, Workflow, IDE panel, SITR runtime, AOIE oracle,
Constitutional Assembly — is a projection of a single deterministic loop primitive
executing at a different holonic scale.

---

## The Loop: R → A → L → P → H

```
runFrame(frames, telemetry, ...) → FrameExecutionResult
```

| Phase | Label | System | Pre/Post-Commit | Description |
|-------|-------|--------|-----------------|-------------|
| 1 | **R** READ | Agents + IDE | pre | Deterministic event intake; no inference |
| 3 | **A** ASSESS | SITR | pre | Constraint evaluation; compute ΔS, detect violations |
| 4 | **L** LOCK | Enforcement | boundary | Apply directives; freeze EnforcementResult |
| 5 | **P** PROPAGATE | AOIE | post | Classify post-lock reality; no influence over L |
| 6 | **H** HARMONIZE | Constitutional + Guardian | post | Verdict → E5 events |

---

## The Commitment Boundary

`LOCK` is the causal commitment point. Everything before it is pre-commit; everything after it is post-commit.

```
pre-commit  [READ → ASSESS]
                   ↓
           [LOCK] ← commitment boundary
                   ↓
post-commit [PROPAGATE → HARMONIZE]
```

This boundary is not an architectural convention. It is a proof invariant:

```
pre-commit safety ≠ post-commit observation
```

Collapsing SITR + AOIE across this boundary destroys:
- Replay determinism (AOIE would see uncommitted state)
- Causal ordering proof (SITR would see AOIE's classification mid-frame)
- Enforcement verifiability (immune response would be coupled to its own observer)
- Auditability (violations would be self-referential)

---

## SITR and AOIE as Temporal Projections

SITR and AOIE are not separate systems. They are temporal projections of the same loop, separated by the LOCK phase:

**SITR (ASSESS phase)**
- Evaluates: *what must not happen*
- Produces: enforcement constraints (ContainmentDirective[])
- Operates: BEFORE commitment boundary
- Property: contrafactual safety domain

**AOIE (PROPAGATE phase)**
- Evaluates: *what did happen*
- Produces: structural classification (AOIEClassification)
- Operates: AFTER commitment boundary
- Property: observational state domain

The separation is what makes each verifiable. SITR's monotonic escalation is provable
because it cannot see AOIE's verdict and de-escalate based on it. AOIE's classification
is deterministic because it sees only finalized, post-enforcement state.

---

## Fractal Rule: SHP(n) = Recursive Instantiation at Scale n

The loop executes identically at every holonic scale:

| Scale | SHP Instantiation |
|-------|-------------------|
| `SUBATOMIC` | byte-level hash invariants per event |
| `ATOMIC` | per-file module invariants |
| `MOLECULAR` | per-module interface contracts |
| `CELLULAR` | per-subsystem (Agent Ecology, SITR, AOIE, Constitutional) |
| `ORGANISM` | `runFrame()` — the complete system loop |
| `FIELD` | Claude + operators + Drive corpus governance cycle |

Only the grain of the frame changes, not the structure of the loop.

---

## Code Expression

```typescript
// src/frame/shp.ts
export const SHP_LOOP = 'R→A→L→P→H' as const
export const SHP_COMMITMENT_BOUNDARY = 'LOCK' as const

export const SHP_PHASES = {
  READ:       { phase_number: 1, pre_commit: true,  post_commit: false, system: 'agents+ide' },
  ASSESS:     { phase_number: 3, pre_commit: true,  post_commit: false, system: 'sitr' },
  LOCK:       { phase_number: 4, pre_commit: false, post_commit: false, system: 'enforcement' },
  PROPAGATE:  { phase_number: 5, pre_commit: false, post_commit: true,  system: 'aoie' },
  HARMONIZE:  { phase_number: 6, pre_commit: false, post_commit: true,  system: 'constitutional+guardian' },
}

// Observable RALPH trace from any FrameExecutionResult
export function toRalphTrace(result: FrameExecutionResult): RalphLoopTrace
```

---

## Failure Modes (Formal Premortem)

| Failure | Mechanism | Guard |
|---------|-----------|-------|
| SITR calls AOIE | Couples pre-commit to post-commit | `RULE-09` in SITR_CONSTITUTION.md |
| AOIE reads pre-commit snapshot | Sees uncommitted state | Phase guard in `classifyRuntime()` → `SITRConstraintError` |
| Enforcement reads AOIE verdict | Creates feedback loop | Enforcement engine is purely directive-driven, no AOIE import |
| Cross-holon feedback explosion | Propagation fanout | `computeAutoDirectives()` produces bounded directive set |
| Graph cycles in Σ | Non-DAG propagation | E5 append-only substrate enforces causal order |

---

## Final Statement

The system is not unified by architecture. It is unified by the temporal structure of execution.

**Boundaries are not separations of systems — they are phase transitions inside a single recursive deterministic loop.**

`runFrame()` is that loop. The separation between SITR and AOIE is not an illusion to be collapsed — it is the proof that the loop is correct.

---

## Formal Lock

```
SHP_LOOP = 'R→A→L→P→H'
SHP_COMMITMENT_BOUNDARY = 'LOCK'
SITR ∈ { pre-commit phases }
AOIE ∈ { post-commit phases }
SITR ∩ AOIE = ∅ (by LOCK boundary)
```

This is the T0 constitutional statement of the AEGIS frame execution model.
It cannot be modified without a `/guardian APPROVED` verdict.

---

## Gate 15 Extension — `src/shp/` Type Primitives

**Epistemic Tier: T0 · Gate 15**

Gate 15 crystallizes the SHP model into a standalone type-level module (`src/shp/`)
that any holonic scale can import independently of the ORGANISM-scale `runFrame()`.

### Eight Formal Invariants

| ID | Rule | Runtime Guard |
|----|------|---------------|
| INV-SHP-01 | ASSESS must occur before LOCK | `phaseOrdinal` ordering |
| INV-SHP-02 | LOCK is a single immutable commit point | `validatePhaseTransition` |
| INV-SHP-03 | PROPAGATE may only use commitHash + frozen state | `SHPKernel.propagate()` contract |
| INV-SHP-04 | HARMONIZE is purely observational feedback | `SHPKernel.harmonize()` contract |
| INV-SHP-05 | No phase may be reordered or skipped | `validatePhaseSequence` |
| INV-SHP-06 | `classification` must not exist before LOCK | `checkSHPInvariants` |
| INV-SHP-07 | `constraintResult` must not exist after LOCK | `checkSHPInvariants` |
| INV-SHP-08 | `commitHash` is the only cross-phase identifier | `checkSHPInvariants` |

### Field Presence Contract

```
READ / ASSESS:          constraintResult permitted | classification FORBIDDEN
LOCK:                   neither field present
PROPAGATE / HARMONIZE:  classification permitted | constraintResult FORBIDDEN
```

### Deterministic `commitHash`

All factory functions compute `commitHash` via FNV-1a 32-bit hash of
`(holonId:sequence:stateKey)`. No `Date.now()`, no UUIDv7. Same inputs always
produce the same hash — enabling replay verification and cross-phase identity tracking.

### Module Map

| File | Role |
|------|------|
| `src/shp/types.ts` | Phase, SHP_PHASE_ORDER, phaseOrdinal, SHPExecutionIdentity |
| `src/shp/execution.ts` | SHPKernel interface, SHP_EXECUTION_INVARIANTS (8 entries) |
| `src/shp/guard.ts` | checkSHPInvariants(), validatePhaseTransition(), validatePhaseSequence() |
| `src/shp/factory.ts` | createReadIdentity() … createHarmonizeIdentity() |

Test coverage: 24 tests in `test/unit/shp.test.ts`
