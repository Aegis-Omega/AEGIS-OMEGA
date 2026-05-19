# SITR Constitution — Systemic Intervention & Threat Response

## Epistemic Tier: T0 · Gate 12

SITR is the constitutional runtime immune system of the AEGIS ecology.
It detects anomalies, issues containment directives, and escalates state monotonically.
SITR is an ACTIVE layer — it produces ContainmentDirective[] that are treated as E5 events
and resolved by the enforcement engine (AgentCoordinator/WorkflowEngine).

**SITR is NOT a truth engine. SITR is constitutional runtime stabilization.**

---

## RULE-01 — E5 Event Emission Pattern

SITR never directly mutates agent or workflow state. All containment actions are emitted
as ContainmentDirective events to be appended into E5 (phase 3 of the frame execution
contract). The enforcement engine applies them deterministically. This preserves
replay integrity: the same E5 log always produces the same enforcement decisions.

## RULE-02 — Monotonic Escalation Only

The SITRState lattice is strictly ordered:
```
STABLE → DEGRADED → UNSTABLE → CONSTITUTIONAL_RISK → CONTAINED → COMPROMISED
```
No de-escalation is permitted via `observe()`. Once the system reaches CONSTITUTIONAL_RISK,
it can only escalate further until an explicit constitutional reset event is appended to E5.

## RULE-03 — Replay Violation Permanence

Once a replay violation is recorded in ReplayViolationLog, it cannot be removed or
amended. Replay violations are irreversible facts of the system's history.

## RULE-04 — Intervention Log Monotonicity

InterventionRecord entries must arrive in strictly increasing sequence order.
Out-of-order entries throw SITRConstraintError. This mirrors the AgentMemory / MutationLedger
invariant and ensures the intervention log is replay-reconstructable.

## RULE-05 — No Wall-Clock Dependence

All SITR state transitions are keyed on sequence numbers, not wall-clock time.
No Date.now() is permitted in any SITR module.

## RULE-06 — No Randomness

SITR decisions are fully deterministic. Identical input signals always produce
identical SITR state transitions. `observe()` is a pure functional update.

## RULE-07 — No Semantic Inference

SITR does not reason about the meaning or intent of agent actions. It classifies
observable structural properties: frame ordering, replay safety flags, telemetry
thresholds. Semantic interpretation is out of scope.

## RULE-08 — No Probabilistic Reasoning

SITR uses deterministic threshold classification only. No Bernstein bounds, no
confidence intervals, no statistical tests inside SITR. Thresholds are constitutional
constants, not calibrated parameters.

## RULE-09 — SITR Does Not Call AOIE

SITR and AOIE are strictly separated. SITR is T0 (constitutional enforcement).
AOIE is T1 (structural classification). SITR must never import from src/aoie/.
The dependency direction is: AOIE observes SITR outputs; SITR does not observe AOIE.

## RULE-10 — Containment Actions are Replay-Reconstructable

Every ContainmentDirective carries `is_replay_reconstructable: true`. This is a
constitutional requirement, not an optional field. Any directive that cannot be
replayed from E5 is invalid and must be rejected.

---

## Escalation Lattice

| State | Ordinal | Trigger examples |
|-------|---------|-----------------|
| `STABLE` | 0 | Clean signals, all invariants satisfied |
| `DEGRADED` | 1 | `workflow_replay_integrity < 1`; `pressure_index > 0.9` |
| `UNSTABLE` | 2 | Non-monotonic frame sequence; invariant_satisfied=false in workflow |
| `CONSTITUTIONAL_RISK` | 3 | Non-replay-safe CoordinationFrame detected |
| `CONTAINED` | 4 | Active containment directive in force |
| `COMPROMISED` | 5 | Terminal — multiple T0 violations confirmed |

---

## ContainmentAction Table

| Action | Effect |
|--------|--------|
| `quarantine_agent` | Agent removed from active schedule |
| `freeze_workflow` | Workflow execution halted |
| `block_frame` | CoordinationFrame rejected from log |
| `invalidate_replay_chain` | Replay chain marked invalid |
| `elevate_state` | Explicit state escalation directive |

---

## Intervention Lifecycle

```
(1) observe() — consume CoordinationFrame[], WorkflowReplayFrame[], AgentTelemetrySnapshot
(2) detectOrchestrationAnomalies() — scan frames for ordering violations, non-replay-safe
(3) escalate() — compute required SITRState monotonically
(4) issueDirective() — produce ContainmentDirective as E5 event
(5) Enforcement engine reads directive from E5 and applies it to AgentCoordinator/WorkflowEngine
(6) InterventionRecord recorded in append-only InterventionLog
```

---

## 7-Phase Frame Execution Context

SITR operates in phase 3 of the deterministic frame execution contract:

| Phase | System | Description |
|-------|--------|-------------|
| 1 | Agents + IDE | Input intake; events appended to E5 |
| 2 | E5 | Immutable append commit; causal boundary closes |
| **3** | **SITR** | **Reads post-commit E5; emits ContainmentDirective[] back into E5** |
| 4 | Enforcement | AgentCoordinator/WorkflowEngine apply directives from E5 |
| 5 | AOIE | Reads post-enforcement snapshot; classifies GlobalState |
| 6 | IDE | Renders panels from E5 + AOIE output |
| 7 | Runtime | Frame hash committed; replay checkpoint stored |

---

## Non-Goals

- SITR does NOT mutate historical replay frames
- SITR does NOT rewrite agent memory
- SITR does NOT fabricate telemetry signals
- SITR does NOT perform probabilistic reasoning or confidence estimation
- SITR does NOT classify semantic correctness of agent actions
- SITR does NOT de-escalate (that requires an explicit constitutional reset event in E5)
