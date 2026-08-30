# Constitutional Governance Surface — Gate 13

## Epistemic Tier: T0 · Gate 13

The Constitutional Governance Surface (CGS) closes the AEGIS governance feedback loop.
It consumes convergent signals from SITR (constitutional enforcement) and AOIE (structural
classification), applies invariant checks, and produces a canonical ConstitutionalVerdict
that is emitted as a Guardian E5 event pair (GUARDIAN_INVOKED + GUARDIAN_VERDICT_ISSUED).

---

## Architecture Position

```
Environment Substrate
  → Agent Ecology (Gate 11: src/agents/)
    → IDE Nervous System (Gate 11: src/ide/)
      → SITR Constitutional Immunity (Gate 12: src/sitr/)
      → AOIE Structural Oracle (Gate 12: src/aoie/)
        → Constitutional Governance Surface (Gate 13: src/constitutional/)
          → E5 Guardian Events → [back to agents via enforcement]
```

The CGS is the closing arc of the governance loop. Every evaluation cycle terminates in
a GovernanceDecision that is replay-reconstructable and E5-appendable.

---

## Verdict Lattice

```
ESCALATE > REJECT > DEFER > PERMIT
```

| Verdict | Condition |
|---------|-----------|
| `ESCALATE` | T0 invariant violation OR SITR=COMPROMISED OR AOIE=COMPROMISED |
| `REJECT` | SITR=CONSTITUTIONAL_RISK OR SITR=CONTAINED |
| `DEFER` | SITR=UNSTABLE/DEGRADED OR AOIE=ALERT |
| `PERMIT` | SITR=STABLE AND AOIE=SECURE AND all invariants passed |

ESCALATE takes priority over all other verdicts. A single T0 violation
immediately escalates regardless of SITR or AOIE state.

---

## Module Map (`src/constitutional/`, 6 files)

| Module | Role | Lines |
|--------|------|-------|
| `types.ts` | ConstitutionalVerdict, GovernanceDecision, ConstAssemblyState, SystemHealthSnapshot | ~75 |
| `verdict.ts` | `computeVerdict()`, `verdictReason()` — pure functions, no state | ~65 |
| `guardian.ts` | `buildGuardianInvokedPayload()`, `buildGuardianVerdictPayload()` — E5 event factories | ~55 |
| `assembly.ts` | `ConstitutionalAssembly` — append-only decision log, immutable functional update | ~100 |
| `convergence.ts` | `ConvergenceSurface` — RalphLoop integration, convergence depth, system health | ~110 |
| `runtime.ts` | `ConstitutionalRuntime` — top-level composition entry point | ~130 |

---

## Seven-Phase Frame Execution (complete circuit)

| Phase | System | Description |
|-------|--------|-------------|
| 1 | Agents + IDE | Input intake; events appended to E5 |
| 2 | E5 | Immutable append commit; causal boundary closes |
| 3 | SITR | Reads post-commit E5; emits ContainmentDirective[] back into E5 |
| 4 | Enforcement | AgentCoordinator/WorkflowEngine apply SITR directives |
| 5 | AOIE | Reads post-enforcement snapshot; classifies GlobalState |
| **6** | **CGS** | **Reads SITR state + AOIE classification + invariant check → GovernanceDecision + Guardian E5 events** |
| 7 | Frame finalization | Hash committed; replay checkpoint stored |

---

## ConstitutionalRuntime API

```typescript
const runtime = ConstitutionalRuntime.empty()

const updated = runtime.evaluate({
  sitr,          // SITRRuntime — provides currentState()
  aoie,          // AOIEClassification — provides global_state
  invariantSnapshot,  // RuntimeSnapshot (invariant-checker schema)
  sequence,      // current frame sequence number
  decision_id,   // unique ID for this governance decision
})

updated.currentVerdict()          // 'PERMIT' | 'DEFER' | 'REJECT' | 'ESCALATE'
updated.decisions()               // readonly GovernanceDecision[]
updated.convergenceDepth()        // consecutive PERMIT cycles
updated.telemetry(currentSeq)     // ConstitutionalTelemetry snapshot
updated.guardianInvokedPayload()  // for E5 GUARDIAN_INVOKED event
updated.guardianVerdictPayload()  // for E5 GUARDIAN_VERDICT_ISSUED event
```

---

## Invariants

- **No Date.now()**: All temporal semantics from sequence numbers
- **No Set/Map**: Arrays only in all state structures
- **deepFreeze**: All GovernanceDecision objects frozen immediately
- **Replay-reconstructable**: `is_replay_reconstructable: true` on every decision
- **Pure verdict**: `computeVerdict()` is a pure function — same inputs, same output
- **Functional assembly**: `ConstitutionalAssembly.observe()` returns new instance; source unchanged
- **Guardian mapping**: PERMIT|DEFER → APPROVED; REJECT|ESCALATE → VETOED

---

## Guardian Event Flow (E5)

```
CGS evaluation
  → buildGuardianInvokedPayload({ invoked_by, check_reason, files_under_review })
     → appended to E5 as GUARDIAN_INVOKED event

  → buildGuardianVerdictPayload({ verdict, location, reason, invocation_event_id })
     → appended to E5 as GUARDIAN_VERDICT_ISSUED event
```

The `invocation_event_id` links the verdict back to its invocation event —
creating a causal chain in E5 that is fully replay-auditable.

---

## ConvergenceSurface

The `ConvergenceSurface` wraps the `RalphLoop` at the ORGANISM holonic scale.
It tracks consecutive PASS cycles (`convergenceDepth()`) and provides a
`systemHealth()` snapshot with SITR/AOIE/verdict/coherence fields.

```
convergenceDepth() > 0  →  system is in sustained governance convergence
convergenceDepth() = 0  →  last cycle was not a clean PERMIT
is_coherent = true      →  SITR=STABLE ∧ AOIE=SECURE ∧ no T0 violations
```

---

## Non-Goals

- CGS does NOT mutate agent or workflow state
- CGS does NOT replace SITR enforcement (SITR is still the active immune system)
- CGS does NOT replace AOIE classification (AOIE remains the structural oracle)
- CGS does NOT perform probabilistic reasoning — verdicts are deterministic threshold classification
- CGS does NOT store wall-clock time — sequence numbers only
