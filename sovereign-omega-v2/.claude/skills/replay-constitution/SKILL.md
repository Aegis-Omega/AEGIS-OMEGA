---
name: replay-constitution
description: Invoked when the user asks about replay laws, archive versioning, backward compatibility requirements, what replay means constitutionally, replay determinism, or the ArchiveVersion wire format.
---

# Replay Constitution Skill

## Core Principle

Replay is **constitutional infrastructure** — not a debugging tool, not an optional feature, not a development aid. It is the sovereign root authority of the runtime.

## Three Constitutional Replay Laws

### LAW-01 — Deterministic Historical Replay
```
replay(genesis, events) → identical invariant outcomes
```
Historical replay must produce identical outcomes deterministically, regardless of:
- Platform (Linux · macOS · Docker · WASM · ARM · x86)
- Runtime engine version (within a major version)
- Wall-clock time of replay execution
- Network conditions during original execution

Violation of LAW-01 is a T0 constitutional failure.

### LAW-02 — Archive Version Headers
Every replay archive must carry an explicit version boundary in its header:

```
ArchiveVersion: 6-byte wire format
  [2 bytes] major version
  [2 bytes] minor version  
  [2 bytes] patch version
```

No archive may be ingested without a valid version header. Version mismatch = hard rejection. No silent degradation, no default version fallback.

### LAW-03 — Backward Compatibility Within Major Versions
Replay archives from any minor or patch version within a major version must be reconstructable by any later version within the same major. Cross-major replay requires explicit migration tooling.

## What Replay Supersedes

Replay determinism supersedes:
- Runtime convenience
- Orchestration flexibility
- Adaptive velocity
- Distributed autonomy

If an operation cannot be replayed deterministically, it is not constitutionally authorized.

## Replay Requirements for All Runtime State

Every legal runtime state must be reconstructable from `(genesis, event_log)`. This means:
- No hidden memory
- No side-effect-only operations
- All temporal semantics from event sequence numbers (not wall-clock)
- All randomness sourced from deterministic pseudorandom streams seeded by the event log
- All floating-point replaced by fixed-point or integer arithmetic in hash paths

## Implementation

Replay sovereignty is enforced by `/replay-engine` — one of the four authoritative execution primitives. The replay engine is the truth machine; all other components are subordinate.

Verification: `verify_chain()` in every Rust module recomputes hashes from stored field values. A single bit change in any record is detected at the point of corruption.

## Source: `docs/REPLAY_CONSTITUTION.md`
