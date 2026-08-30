# Host Adaptation Specification
## Epistemic Tier: T1
## Status: Active

This document specifies how the constitutionally governed adaptive runtime embeds
itself within a host environment while preserving all constitutional invariants.

The runtime is a constitutionally governed adaptive runtime environment.
It is NOT described as AGI, autonomous consciousness, universal intelligence, or self-aware.

---

## Adaptation Model

The runtime co-evolves with the host environment in three directions:

```
Host environment shapes runtime behavior (environmental pressure)
Runtime shapes local operational structure (governed adaptation)
Constitutional invariants preserve continuity across all adaptation (identity preservation)
```

This is not self-modification. It is governed embedding:
- The runtime discovers host capabilities.
- The runtime registers them with explicit provenance.
- The runtime adapts its operational behavior to the available capability set.
- All adaptation is logged as `EnvironmentMutation` records.
- No adaptation violates replay determinism.

---

## Workspace Introspection

### Detection Sequence
1. Receive `canonicalRoot` (caller-supplied — not inferred from `process.cwd()` to preserve determinism)
2. Canonicalize via `canonicalizePath()` — pure function, deterministic
3. Detect installation context from root contents (pure function)
4. Enumerate governed directories — apply `buildGovernedPath()` to each
5. Generate `workspace_id` via `deterministicWorkspaceId()` — FNV-1a hash, no crypto dep
6. Construct `GovernedWorkspace` via `buildGovernedWorkspace()` — immutable

### Canonical Path Rules
- All backslashes converted to forward slashes
- Repeated slashes collapsed
- Trailing slashes removed
- Paths are case-preserved (no lowercasing — case-insensitive FS detection is out of scope)
- Relative paths (`./`, `../`) are NOT resolved — callers must supply absolute paths

### Installation Context Detection (pure function, ordered precedence)
| Signal | Context |
|--------|---------|
| `package.json` + `packages/` directory | `monorepo` |
| `.github/` or `CI` directory | `ci-environment` |
| `Dockerfile` or `.dockerenv` | `container` |
| `package.json` only | `standalone` |
| none of the above | `development` |

---

## Capability Governance

### Capability Classes
| Class | Description | Entropy impact |
|-------|-------------|----------------|
| `filesystem` | Read/write to governed paths | Bounded (scoped to registered paths) |
| `process` | Spawn/observe child processes | Bounded (no recursive escalation) |
| `network` | HTTP/WebSocket to registered endpoints | Bounded (no arbitrary egress) |
| `telemetry` | Read/emit telemetry metrics | Bounded (observational only) |

### Capability Admission Checklist
Every `HostCapability` must satisfy all conditions before registration:
- [ ] `provenance_tier` ∈ {T0, T1, T2}
- [ ] `ontology_term` registered in `docs/ONTOLOGY.md`
- [ ] `admissibility_reason` non-empty string
- [ ] `entropy_impact_bounded = true`

Violation of any condition: `CapabilityAdmissionError` thrown at `CapabilityGuard.register()`.

### Capability Grant Lifecycle
```
register(capability) → guard_v2
grant(capability_id, granted_to, scope, sequence) → { guard_v3, grant }
[... use grant ...]
revoke(grant_id, sequence_revoked) → guard_v4
```

Every guard is immutable. Mutation produces a new guard instance (functional update pattern).

### Capability Surface Area Budget
The number of registered capabilities must remain within the substrate size budget:
- Soft limit: 8 capabilities (review required above this)
- Hard limit: 16 capabilities (SUBSTRATE_EVOLUTION.md RULE-02 applies by analogy)

---

## Environment Snapshotting

### Snapshot Format (WORKSPACE_SNAPSHOT_SCHEMA_VERSION = '1.0.0')
| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | `'1.0.0'` | Must be first field; read before all others |
| `snapshot_id` | `string` | FNV-1a hash of canonical state string |
| `captured_at_sequence` | `number` | Event substrate sequence at snapshot time |
| `canonical_root` | `string` | Canonicalized workspace root |
| `governed_paths` | `string[]` | Sorted list of canonical governed paths |
| `active_capability_ids` | `string[]` | Active capability IDs at snapshot time |
| `environment_hash` | `SHA256Hex` | Hash of full environment state (caller-computed) |
| `total_mutations` | `number` | Total mutations since workspace creation |

### Attestation
A snapshot is attested when:
1. `schema_version === WORKSPACE_SNAPSHOT_SCHEMA_VERSION`
2. `snapshot_id.startsWith('snap_')`
3. `captured_at_sequence >= 0`

---

## Replayable Mutation Layer

### Mutation Record Structure
Every `EnvironmentMutation` contains:
- `mutation_id` — unique identifier
- `sequence` — monotonically increasing, from event substrate
- `mutation_type` — one of 8 defined types (RULE-01 ensures completeness)
- `target_path` — canonical path that is being modified
- `prev_state_hash` / `next_state_hash` — before/after state hashes
- `provenance_source` — Drive ID or local reference (RULE-02 compliance)
- `admitted_by` — capability_id that authorized this mutation
- `is_replay_reconstructable` — explicit declaration

### Mutation Sequence Invariant
The `MutationLedger` enforces monotonic sequence ordering. A mutation with
`sequence ≤ last_sequence` is rejected with `MutationRejectedError`.
This is the environment-layer analog of the Rust `ReplayLedger` chain contiguity invariant.

---

## Constitutional Telemetry Extensions

### New Metrics (admissible under TELEMETRY_SPEC.md)

| Metric | Definition | Invariant | Status |
|--------|-----------|-----------|--------|
| `environment_entropy` | Normalized entropy from mutation count | T1 provisional | T2 hypothesis |
| `capability_surface_area` | Count of registered host capabilities | None (informational) | T2 hypothesis |
| `mutation_velocity` | Mutations per sequence span | Backpressure trigger if > 100/span | T2 hypothesis |
| `replay_reconstruction_integrity` | Fraction of replay-reconstructable mutations | Should be 1.0 | T2 hypothesis |
| `adaptation_pressure_index` | Composite: entropy + surface + velocity | Alert threshold > 0.8 | T2 hypothesis |
| `constitutional_stability_score` | 1 - adaptation_pressure_index | Alert threshold < 0.2 | T2 hypothesis |
| `environmental_drift_rate` | Unique env hashes per sequence span | Alert if > 0.1/span | T2 hypothesis |
| `replay_identity_integrity` | Fraction of valid replay frames | Should be 1.0 | T2 hypothesis |

All metrics are T2 provisional pending P3 empirical validation for T1 elevation.
No dedicated INV-* until empirical data establishes thresholds.
