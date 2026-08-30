# Agent Constitution — Constitutional Operating Rules for AEGIS Agents

## Epistemic Tier: T1 · Gate 11

Agents are operational inhabitants of the governed workspace — not constitutional
authorities. The environment substrate governs them; they do not govern the substrate.

---

## RULE-01 — Admissibility Gate

An agent may only be registered if its `epistemic_tier` is T0, T1, or T2.
T3–T5 agents are constitutionally excluded. No exception is permitted without
a Guardian-approved justification that includes evidence review.

## RULE-02 — Replay Safety Requirement

Every registered agent must declare `is_replay_safe: true`. Agents that cannot
replay their execution trace without side effects are not admissible. Replay safety
is a constitutional invariant, not a quality attribute.

## RULE-03 — Manifest Schema Version

All agent manifests must carry `schema_version: '1.0.0'`. A version mismatch
triggers a hard rejection. There is no fallback to a default version.

## RULE-04 — Monotonic Sequence Memory

Agent memory entries must arrive in strictly increasing sequence order.
Out-of-order entries throw `AgentCoordinationError`. Memory is append-only
and immutable — there is no mutation or deletion path.

## RULE-05 — Sequential Coordination

Agents are coordinated sequentially via monotonically increasing sequence numbers.
No nondeterministic parallel mutation is permitted. The `AgentCoordinator` enforces
deterministic frame ordering; a frame whose sequence ≤ the previous frame's sequence
is rejected.

## RULE-06 — Capability Boundary

An agent's `workspace_boundary` defines the canonical paths it may interact with.
Any mutation outside this boundary requires an explicit capability grant from the
`CapabilityGuard`. Agents do not self-grant capabilities.

## RULE-07 — Entropy Budget

Every agent declares a fixed entropy budget (`entropy_budget_fixed`, Q16.16).
This budget bounds the agent's allowed non-determinism per scheduling cycle.
Agents that exhaust their entropy budget without completing their cycle are suspended.

## RULE-08 — Retirement

An agent can be retired but never deleted. Retirement sets `status: 'retired'` and
removes the agent from the active schedule. Retired agents remain in the manifest
log for replay and audit purposes.

---

## Agent Lifecycle Table

| Status | Transitions | Description |
|--------|-------------|-------------|
| `registered` | → `active`, → `retired` | Admitted and awaiting scheduling |
| `active` | → `suspended`, → `retired` | Currently executing in a workflow |
| `suspended` | → `active`, → `retired` | Paused due to entropy budget or error |
| `retired` | (terminal) | Permanently decommissioned |

---

## Admissibility Requirements

| Requirement | Value | Rule |
|-------------|-------|------|
| Epistemic tier | T0, T1, or T2 only | RULE-01 |
| Replay safe | `true` (hard requirement) | RULE-02 |
| Schema version | `'1.0.0'` exact match | RULE-03 |
| Unique agent_id | No duplicates allowed | RULE-05 |

---

## Non-Goals

- Agents do NOT govern constitutional files (gate.py, dna.py, router.py are frozen)
- Agents do NOT have write access to the event substrate (read-only access only)
- Agents do NOT modify the CapabilityGuard or ExtensionRegistry
- Agents do NOT generate UUIDs using Date.now() — only `uuid.ts` may do so
- Agents do NOT implement the Ralph Loop cycle management — that is `ralph-loop.ts`
