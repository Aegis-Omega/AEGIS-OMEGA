# Environment Adaptation Constitution
## Epistemic Tier: T0
## Status: Constitutional Law — immutable without /guardian APPROVED verdict

The runtime may adapt to its host environment, but no adaptation may violate replay
determinism, ontology integrity, provenance continuity, or constitutional invariants.

The environment adaptation layer is constitutionally typed. No environment binding,
workspace, or host capability may exist outside the governed interface.

---

## Architectural Separation

### Constitutional Core (immutable or governance-constrained)
- Ontology enforcement (`docs/ONTOLOGY.md`)
- Replay law (`docs/REPLAY_CONSTITUTION.md`)
- Invariant enforcement (`src/core/invariant-checker.ts`)
- Provenance continuity (`docs/TRACEABILITY.md`)
- Entropy boundaries (`crates/constitutional-substrate/src/entropy.rs`)

### Environment Adaptation Layer (host-specific, governed)
- Filesystem bindings (`src/environment/bindings/`)
- Workspace discovery (`src/environment/workspace/`)
- Host capability registry (`src/environment/kernel/capability_guard.ts`)
- Capability mapping (`src/environment/kernel/`)
- Process observation

### Operational Extensions (replaceable)
- Plugins (`src/extensions/`)
- Workflows
- Agents (`src/environment/agents/`)
- Toolchains (`src/environment/tools/`)

### Replay Memory Layer (persistent)
- Replay archives (`src/environment/memory/`)
- Environment snapshots (`src/environment/snapshots/`)
- Mutation history
- Provenance graph edges

---

## Constitutional Rules

### RULE-01 — No Environment Mutation Without Replay Persistence
Every environment mutation must be appended to the `MutationLedger` before it takes
effect. A mutation that does not appear in the ledger is constitutionally inadmissible.

**Implementation:** `src/environment/memory/mutation_ledger.ts:MutationLedger.append()`
**Violation consequence:** T0_ABORT — the append-only invariant is constitutional bedrock.

---

### RULE-02 — Every Host Capability Must Have Provenance, Ontology, and Admissibility
Every `HostCapability` registered with the `CapabilityGuard` must declare:
- `provenance_tier`: T0, T1, or T2 (T3–T5 are constitutionally excluded)
- `ontology_term`: a term registered in `docs/ONTOLOGY.md`
- `admissibility_reason`: explicit justification for why this capability is needed
- `entropy_impact_bounded: true` (unbounded entropy impact is disqualifying)

**Implementation:** `src/environment/kernel/capability_guard.ts:CapabilityGuard.register()`
**Violation consequence:** `CapabilityAdmissionError` thrown at registration time.

---

### RULE-03 — Environment Adaptation Must Be Replay-Reconstructable
All environment state transitions must be expressible as a sequence of `EnvironmentMutation`
records. Given the mutation ledger, the environment state at any prior sequence must be
reconstructable without access to external state.

Exception: physical observables (thermal state, hardware IDs) are annotated as
non-reconstructable per `docs/REPLAY_CONSTITUTION.md LAW-04`.

**Implementation:** `src/environment/memory/mutation_ledger.ts:MutationLedger.verifyStructural()`

---

### RULE-04 — Host-Derived Nondeterminism Must Be Isolated Behind Canonicalization Boundaries
Any nondeterministic host value (filesystem ordering, process IDs, timestamps) must be
canonicalized before entering the governed environment. The canonicalization function must
be a pure function — identical input produces identical output.

**Implementation:** `src/environment/workspace/introspection.ts:canonicalizePath()`
                   `src/environment/workspace/introspection.ts:deterministicWorkspaceId()`

---

### RULE-05 — Plugins May Not Mutate Constitutional Primitives Directly
All plugin mutations must pass through `CapabilityGuard` and `SandboxBoundary`.
No plugin may directly modify types in `src/core/`, `crates/constitutional-substrate/`,
or the constitutional documents in `docs/`.

**Implementation:** `src/extensions/sandbox/sandbox.ts:checkSandboxAllows()`

---

### RULE-06 — Environment Snapshots Must Be Schema-Versioned Constitutional Artifacts
Every `WorkspaceSnapshot` must declare its `schema_version` as the first field.
Deserializers must read the version before any other field.
Version-blind deserialization is a constitutional violation.

**Implementation:** `src/environment/snapshots/snapshot.ts:deserializeSnapshot()`
                   `WORKSPACE_SNAPSHOT_SCHEMA_VERSION = '1.0.0'`

---

### RULE-07 — Replay Archives Must Reconstruct Environment, Capability, Mutation, and Invariant State
A complete replay reconstruction requires:
1. Environment state hash at each sequence
2. Active capability grants at each sequence
3. Full mutation lineage
4. Invariant outcome at each governance cycle

An environment whose state cannot be reconstructed from its mutation ledger is in
constitutional violation.

**Implementation:** `src/environment/memory/mutation_ledger.ts:ReplayFrame`

---

## Security Boundary

All environment bindings must pass through:
```
environment/kernel/capability_guard.ts
```

No direct host mutations are permitted outside governed interfaces.
A mutation that bypasses the `CapabilityGuard` is a RULE-01 + RULE-05 joint violation.

---

## Amendment Process

Changes to this document require:
1. `/guardian APPROVED` verdict from the constitutional authority
2. New entry in the Evolution History table below
3. All downstream implementations updated in the same commit
4. All 265 tests (215 TypeScript + 50 Rust) still passing

## Evolution History

| Rule | Date | Amendment | Authority |
|------|------|-----------|-----------|
| RULE-01..07 | 2026-05-19 | Initial constitutional codification | Gate 10 CONFIDENCE 0.99 |
