# Plugin Habitat Constitution
## Epistemic Tier: T1
## Status: Constitutional Law — immutable without /guardian APPROVED verdict

Plugins are constitutionally governed ecological inhabitants of the runtime environment.
They are NOT constitutional authorities.

---

## Constitutional Definition

A plugin is:
- An operational extension with bounded capability access
- Subject to sandbox isolation and entropy budgeting
- Required to declare replay safety before admission
- Subject to eviction if it violates constitutional constraints

A plugin is NOT:
- A governance authority
- An ontology primitive
- A source of constitutional truth
- An admissible ground for T0–T2 claims

---

## Seven Constitutional Rules

### RULE-01 — Plugins Are Environment Inhabitants, Not Constitutional Authorities
No plugin may invoke governance functions directly. Governance is performed by the
Ralph Loop, invariant-checker, and constitutional substrate — not by plugins.

### RULE-02 — Plugins May Evolve Operational Behavior But May Not Redefine Ontology Primitives
A plugin may add new operational capabilities within its bounded scope.
A plugin may NOT add terms to `docs/ONTOLOGY.md`, modify `src/core/types.ts`, or
alter any T0 constitutional document.

### RULE-03 — All Plugin Mutations Require Replay Persistence
Every mutation a plugin performs must be recorded as a `MutationReceipt`.
A plugin mutation without a receipt is a RULE-01 + ENVIRONMENT_CONSTITUTION.md RULE-01
joint violation.

### RULE-04 — Plugin Telemetry Must Bind to Constitutional Invariants
Plugin telemetry (`ExtensionTelemetry`) must include:
- `entropy_used_fixed` — quantifying the plugin's entropy contribution
- `replay_safe_ratio` — fraction of mutations that are replay-reconstructable
- `sandbox_isolation_intact` — boolean confirming no sandbox escape

### RULE-05 — Plugin Capability Access Is Least-Privilege by Default
All `CapabilityContract.is_least_privilege` values are `true` by construction.
Plugins may only request capabilities declared in their `PluginManifest`.
Plugin capabilities are a strict subset of the registered `HostCapability` set.

### RULE-06 — Plugin State Must Remain Replay-Reconstructable
`PluginManifest.is_replay_safe` must be `true` for admission.
A plugin that introduces nondeterministic state is constitutionally inadmissible.

### RULE-07 — Plugin Entropy Contribution Must Remain Measurable
Every `MutationReceipt` carries `entropy_contribution_fixed` (Q16.16).
The `SandboxBoundary` enforces the plugin's entropy budget:
when `entropy_used >= entropy_budget`, further mutations are rejected.

---

## Plugin Lifecycle

```
manifest declared
  → ExtensionRegistry.admit(manifest, sequence)
    → validate: schema_version, epistemic_tier (T0-T2 only), is_replay_safe
    → status: 'admitted'
  → CapabilityContract created per requested capability
    → SandboxBoundary created from contracts
  → plugin executes mutations
    → SandboxBoundary.checkSandboxAllows() called before each mutation
    → MutationReceipt issued after each mutation
    → SandboxBoundary.recordMutation() updates entropy accounting
  → ExtensionRegistry.telemetryFor() produces ExtensionTelemetry
  → if violation: ExtensionRegistry.evict(plugin_id, sequence)
    → status: 'evicted'
    → all contracts expire
```

---

## Admission Requirements (PluginManifest)

| Field | Requirement |
|-------|-------------|
| `schema_version` | Must equal `PLUGIN_MANIFEST_SCHEMA_VERSION = '1.0.0'` |
| `epistemic_tier` | T0, T1, or T2 only (T3–T5 are inadmissible) |
| `is_replay_safe` | Must be `true` |
| `capability_requests` | All requested capabilities must be already registered in CapabilityGuard |
| `ontology_terms_used` | All terms must be registered in `docs/ONTOLOGY.md` |
| `entropy_budget_fixed` | Must be a positive Q16.16 value |

---

## Sandbox Enforcement

The `SandboxBoundary` is the runtime enforcement layer for plugin isolation.

Every plugin operation is checked against:
1. `allowed_capability_ids` — the plugin may only use listed capabilities
2. `allowed_paths` — the plugin may only access paths with matching prefix
3. `max_mutation_count` — exceeded → `SandboxViolationError`
4. `entropy_budget_fixed` — exceeded → `SandboxViolationError`
5. `is_isolated: true` — if false, all operations are rejected

---

## Plugin Registry Budget

| Metric | Limit | Rationale |
|--------|-------|-----------|
| Admitted plugins | ≤ 16 | Beyond 16, governance review required |
| Capabilities per plugin | ≤ 2 | Least-privilege principle |
| Ontology terms per plugin | ≤ 4 | Prevents ontology inflation |
| Mutation count per plugin | Declared at admission | Enforced by SandboxBoundary |

---

## Amendment Process

Changes to this document require:
1. `/guardian APPROVED` verdict from the constitutional authority
2. Simultaneous update to `src/extensions/` affected modules
3. All tests in `test/unit/extensions.test.ts` still passing
4. Full Gate 8 (215 TypeScript tests) still passing

## Evolution History

| Rule | Date | Amendment | Authority |
|------|------|-----------|-----------|
| RULE-01..07 | 2026-05-19 | Initial constitutional codification | Gate 10 CONFIDENCE 0.99 |
