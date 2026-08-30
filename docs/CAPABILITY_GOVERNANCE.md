# Capability Governance Specification
## Epistemic Tier: T1
## Status: Active

Capability governance is the mechanism by which the constitutionally governed adaptive
runtime controls host resource access. No capability may be exercised without explicit
registration, provenance linkage, and least-privilege grant.

---

## Governance Principle

The capability model implements a least-privilege security architecture:
1. All host capabilities are enumerated in the capability registry.
2. No code may access host resources except through a registered and granted capability.
3. Every capability has a bounded entropy impact.
4. Every grant is scoped to the minimum necessary paths.
5. All grants are revocable and append-only in the grant ledger.

---

## Capability Registry (CapabilityGuard)

The `CapabilityGuard` is the single authority for all environment bindings.

### State Model
`CapabilityGuard` is an immutable value type. Every mutating operation (register, grant,
revoke) produces a new `CapabilityGuard` instance. The previous instance remains valid
for replay purposes.

This follows the same functional update pattern as `MutationLedger` and the Rust `ReplayLedger`.

### Registration Requirements (ENVIRONMENT_CONSTITUTION.md RULE-02)
```
HostCapability {
  capability_id: string        // unique; kebab-case by convention
  class: HostCapabilityClass   // 'filesystem' | 'process' | 'network' | 'telemetry'
  name: string                 // human-readable
  provenance_tier: T0|T1|T2    // must NOT be T3–T5
  ontology_term: string        // must be registered in ONTOLOGY.md
  admissibility_reason: string // must be non-empty
  entropy_impact_bounded: true // false = registration rejected
}
```

### Grant Lifecycle

```
Initial state: guard_0 (empty registry)
  → register(filesystem_capability) → guard_1
  → register(telemetry_capability)  → guard_2
  → grant(filesystem_cap, agent_id, ['/workspace'], seq=10) → { guard_3, grant_A }
  → agent uses filesystem_cap for mutations with admitted_by=grant_A.capability_id
  → revoke(grant_A.grant_id, seq=50) → guard_4
```

All state transitions are recorded as `EnvironmentMutation` records in the `MutationLedger`.

---

## Plugin Capability Contracts

Plugins receive capabilities through `CapabilityContract`, not through `CapabilityGrant`.
This is a constitutionally enforced distinction:

| Mechanism | Used by | Authority | Scope |
|-----------|---------|-----------|-------|
| `CapabilityGrant` | Core runtime agents | `CapabilityGuard` | Any registered capability |
| `CapabilityContract` | Plugins only | `ExtensionRegistry` + `SandboxBoundary` | Subset of granted capabilities |

A plugin may only request capabilities that are already registered in `CapabilityGuard`.
A plugin may never receive a capability that is not declared in its `PluginManifest.capability_requests`.

### Least-Privilege Enforcement
All `CapabilityContract.is_least_privilege` values are `true` (constitutional invariant).
There is no mechanism to set `is_least_privilege = false` — it is hardcoded at construction.

---

## Entropy Impact Budgeting

Every capability registration declares `entropy_impact_bounded`.
Only `true` is constitutionally admissible.

The entropy budget is tracked at the sandbox level:
```
SandboxBoundary {
  entropy_budget_fixed: number  // max Q16.16 entropy units the plugin may contribute
  entropy_used_fixed: number    // accumulated from MutationReceipt.entropy_contribution_fixed
}
```

When `entropy_used_fixed >= entropy_budget_fixed`, further mutations are rejected with
`SandboxViolationError`.

---

## Capability Audit Trail

Every `EnvironmentMutation` records:
- `admitted_by`: the `capability_id` that authorized this mutation
- `provenance_source`: the Drive ID or local reference grounding this capability

The `CapabilityGuard.isAuthorized(mutation)` check verifies that an active grant exists
for `mutation.admitted_by` at the mutation's sequence number.

An audit of the mutation ledger can reconstruct the full capability usage history:
which capabilities were used, by whom, in what scope, for which mutations.

---

## Capability Size Budget

Analogous to `docs/SUBSTRATE_EVOLUTION.md` size budget:

| Metric | Limit | Rationale |
|--------|-------|-----------|
| Registered capabilities | ≤ 8 | Beyond 8, review for ontology inflation |
| Active grants per agent | ≤ 4 | Least-privilege principle |
| Plugin capability requests | ≤ 2 per plugin | Minimal surface area |
| Capability classes | 4 (fixed) | filesystem, process, network, telemetry |

---

## Amendment Process

Changes to this document require `/guardian APPROVED` verdict and simultaneous updates to:
- `src/environment/kernel/capability_guard.ts`
- `docs/ENVIRONMENT_CONSTITUTION.md` RULE-02
- `docs/ONTOLOGY.md` (if new capability classes are added)
- All tests in `test/unit/environment.test.ts`
