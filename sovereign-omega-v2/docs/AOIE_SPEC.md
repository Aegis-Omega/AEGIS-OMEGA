# AOIE Specification — Arbitration & Ontological Identity Engine

## Epistemic Tier: T1 · Gate 12

AOIE is the structural epistemic classification oracle of the AEGIS runtime.
It observes a post-enforcement snapshot of the system and classifies its structural
consistency, contradiction, drift, and identity continuity.

**AOIE is PASSIVE. AOIE is OBSERVATIONAL. AOIE cannot mutate any runtime state.**

---

## Pure Function Design Rationale

AOIE has no class, no stored state, no side effects. Its primary entry point is:

```typescript
classifyRuntime(params): AOIEClassification
```

This is a pure function: same inputs always produce the same AOIEClassification.
This property is required by the replay determinism invariant: given an identical
E5 log, the system must produce identical AOIE outputs.

Pure function design also makes AOIE trivially testable (no mocks needed) and
trivially parallelisable (no shared state to coordinate).

---

## GlobalState Classification Rules

| GlobalState | Condition |
|-------------|-----------|
| `SECURE` | arbitration=RESOLVED AND identity=CONTINUOUS AND drift=STABLE |
| `ALERT` | arbitration=CONTESTED OR identity=DRIFTED OR drift=DRIFTING |
| `COMPROMISED` | arbitration=DEADLOCKED OR identity=BROKEN OR drift=DIVERGED |

COMPROMISED takes priority over ALERT. ALERT takes priority over SECURE.
A single broken signal elevates the entire GlobalState.

---

## AOIEClassification Schema

```typescript
interface AOIEClassification {
  global_state: GlobalState              // 'SECURE' | 'ALERT' | 'COMPROMISED'
  arbitration: ArbitrationState          // 'RESOLVED' | 'CONTESTED' | 'DEADLOCKED'
  identity_continuity: IdentityContinuityState  // 'CONTINUOUS' | 'DRIFTED' | 'BROKEN'
  constitutional_drift: ConstitutionalDriftState // 'STABLE' | 'DRIFTING' | 'DIVERGED'
  classified_at_sequence: number
  is_replay_reconstructable: true
  schema_version: '1.0.0'
}
```

Every output is deep-frozen immediately by `freezeClassification()`.

---

## Snapshot Phase Requirement

`classifyRuntime()` enforces a phase guard:

```
All input RuntimeSnapshot objects must have phase = 'post_enforcement'
```

This is the AOIE-SITR separation invariant: AOIE must never observe uncommitted state
or pre-enforcement state. Snapshots from phases 1-3 of the frame execution contract
are forbidden as AOIE input. Violation throws SITRConstraintError.

The three snapshot phases:

| Phase | Who creates it | AOIE access |
|-------|---------------|-------------|
| `pre_commit` | Before E5 append | ❌ FORBIDDEN |
| `post_commit` | After E5 append, before enforcement | ❌ FORBIDDEN (SITR input only) |
| `post_enforcement` | After enforcement engine runs | ✅ ONLY valid AOIE input |

---

## Arbitration Subsystem

**RESOLVED**: No conflicting policy mutations; all epistemic assertions have verified
evidence hashes (non-zero).

**CONTESTED**: At least one EpistemicAssertion has a zero evidence hash — the claim is
unverified. The system cannot determine whether the tier classification is legitimate.

**DEADLOCKED**: Two or more PolicyMutations target the same `policy_type` at different
sequence numbers — a constitutional contradiction. The system cannot determine which
mutation is authoritative.

---

## Identity Continuity Subsystem

Identity drift is computed as the fraction of adjacent snapshot pairs with differing
`state_hash` values. RFC-8785 JCS canonicalization ensures deterministic hashing.

| State | Drift threshold |
|-------|----------------|
| `CONTINUOUS` | drift = 0 (all snapshots identical) |
| `DRIFTED` | 0 < drift ≤ 0.3 |
| `BROKEN` | drift > 0.3 |

---

## Constitutional Drift Subsystem

Drift rate = `PolicyMutation.length / max(1, RuntimeSnapshot.length)`.

| State | Rate threshold |
|-------|---------------|
| `STABLE` | 0 mutations, or rate ≤ 0.1 |
| `DRIFTING` | 0.1 < rate ≤ 0.5 |
| `DIVERGED` | rate > 0.5 |

---

## AOIE vs SITR Authority Boundary

| Property | SITR | AOIE |
|----------|------|------|
| Authority | Constitutional enforcement | Structural classification |
| Mutation | Can issue ContainmentDirective (via E5) | Never |
| State | Stateful (SITRRuntime) | Stateless (pure function) |
| Inputs | Post-commit E5 signals | Post-enforcement snapshots only |
| Outputs | Directives, interventions, violations | AOIEClassification (read-only) |
| Tier | T0 | T1 |
| Frame phase | 3 (evaluation) | 5 (projection) |

**AOIE must never directly influence orchestration runtime. AOIE output is read-only
classification data for governance dashboards and telemetry analytics.**

---

## Ralph Loop Holonic Placement

AOIE is the FIELD-scale observer in the AEGIS holonic hierarchy:

```
[Subatomic] byte invariants, hash chaining
[Atomic]    individual files
[Molecular] modules (agents/, ide/, sitr/, aoie/)
[Cellular]  subsystems (Agent Ecology, SITR Immunity)
[Organism]  sovereign-omega-v2 runtime
[FIELD]     AOIE + Claude + ChatGPT + Qwen + Drive corpus + operators
```

AOIE operates at the FIELD scale — it observes the entire organism and classifies
its structural state. This is why AOIE is stateless: a field observer does not
accumulate state; it observes the organism at a point in time and returns a classification.
