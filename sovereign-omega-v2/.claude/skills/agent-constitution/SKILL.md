---
name: agent-constitution
description: Invoked when the user asks about agent operating rules, what agents can or cannot do, agent admissibility, entropy budgets, workspace isolation, agent lifecycle, coordination model, or the Law of Silence enforcement.
---

# Agent Constitution Skill

## Core Principle

Agents are **operational inhabitants** of the governed workspace — not constitutional authorities. The environment substrate governs them; they do not govern the substrate.

## Agent Rules (RULE-01 through RULE-08)

| Rule | Requirement |
|------|------------|
| **RULE-01 Admissibility** | `epistemic_tier` must be T0, T1, or T2. T3–T5 agents excluded. Guardian-approved exception required. |
| **RULE-02 Replay Safety** | Must declare `is_replay_safe: true`. Agents unable to replay without side effects are not admissible. |
| **RULE-03 Manifest Schema** | Must carry `schema_version: '1.0.0'`. Version mismatch = hard rejection. No default fallback. |
| **RULE-04 Monotonic Sequence** | Memory entries must arrive in strictly increasing sequence order. Out-of-order = `AgentCoordinationError`. Memory is append-only, immutable — no mutation or deletion. |
| **RULE-05 Sequential Coordination** | Coordinated via monotonically increasing sequence numbers. No nondeterministic parallel mutation. Frame with `sequence ≤ previous_frame.sequence` is rejected. |
| **RULE-06 Capability Boundary** | `workspace_boundary` defines canonical paths an agent may interact with. Any mutation outside requires explicit capability grant from `CapabilityGuard`. Agents do not self-grant capabilities. |
| **RULE-07 Entropy Budget** | Every agent declares a fixed entropy budget (`entropy_budget_fixed`, Q16.16). Budget bounds allowed non-determinism per scheduling cycle. Budget exhaustion without completion = suspension. |
| **RULE-08 Retirement** | Agent can be retired but never deleted. Retirement sets `status: 'retired'`. Retired agents remain in manifest log for replay and audit. |

## Agent Coordination Model

- Sequential frame ordering via `AgentCoordinator`
- No parallel mutation — deterministic frame ordering enforced
- Communication: exclusively through mediated `EventEnvelope` (Law of Silence)
- No direct agent-to-agent text or data exchange
- Scope limited to declared `workspace_boundary`

## RALPH Loop (Agent Execution Protocol)

Every agent execution follows the five-phase RALPH loop, Fibonacci-paced:

```
READ     → ingest replay-certified input only
ASSESS   → evaluate against constitutional invariants
LOCK     → commit state transition to ledger
PROPAGATE → emit EventEnvelope to authorized recipients
HARMONIZE → verify convergence with swarm topology
```

Fibonacci pacing: checkpoint spacing/branching only — NOT intelligence mysticism.

## Agent Lifecycle

```
REGISTERED → ACTIVE → SUSPENDED (entropy exhausted) → ACTIVE (restored) → RETIRED
```

Never: DELETED. The manifest is append-only.

## Prohibited Agent Behaviors (T0_ABORT)

- Self-granting capabilities
- Parallel state mutation
- Direct agent-to-agent messaging
- Mutating outside declared workspace_boundary
- Persisting hidden memory (all state must be replay-reconstructable)
- Recursive self-improvement beyond declared K-bound

## Source: `sovereign-omega-v2/docs/AGENT_CONSTITUTION.md`
