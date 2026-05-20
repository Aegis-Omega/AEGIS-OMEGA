---
name: replay-sovereignty
description: Automatically invoked when a new abstraction is introduced without canonical ontology mapping, when code could violate replay determinism, when cross-platform behavior is assumed in governance paths, when adaptive power is claimed beyond replay-verifiable bounds, or when any of the nine prohibited conditions are detected in proposed code or architecture.
---

# Replay Sovereignty Skill

When invoked, enforce the constitutional root law and canonical ontology admission requirements from `docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md`.

## Root Law Check

```
AdaptivePower(T) ≤ ReplayVerifiability(T)
```

Compute AdaptivePower as count of APPROVED CAPABILITY_EVOLUTION entries in the AdaptiveLineage. Compute ReplayVerifiability as chain length. If AdaptivePower > ReplayVerifiability, flag as ROOT LAW VIOLATION.

## Canonical Ontology Admission Test

For any new abstraction or module, verify all four requirements:

1. **Primitive mapping** — reduces to one of: Event / Transition / Ownership / Entropy / Transport / Verification
2. **Replay mapping** — maps to a SHP phase: READ / ASSESS / LOCK / PROPAGATE / HARMONIZE
3. **Runtime mapping** — maps to a GovernanceTopology field or one of the four execution primitives (/event-log, /replay-engine, /dfa-engine, /checkpoint-vm)
4. **Verifier compatibility** — compatible with VCG calibration and gate decisions; no V4/V5 contamination

If any requirement fails, flag as ONTOLOGY ADMISSION REJECTED and cite the missing mapping.

## Cross-Platform Replay Check

Flag any code that uses:
- `Date.now()` outside `src/event/uuid.ts`
- `Math.random()` in any governance path
- `Set` or `Map` in ProjectionState
- `JSON.stringify` for integrity operations
- Platform-specific file ordering or hash map iteration

These violate replay sovereignty across Linux/macOS/Docker/WASM/ARM/x86.

## Prohibited Conditions Check

Flag immediately as T0_ABORT if any of the following are detected:

| Condition | Detection Pattern |
|-----------|-------------------|
| Hidden memory / state caches | Mutable module-level variables in `src/` outside uuid.ts |
| Unrestricted recursion | Unbounded recursive calls without replay-certified commit boundary |
| Autonomous mutation authority | Code that mutates state without owner proof or VCG gate |
| Unverifiable adaptation | Adaptation paths that bypass `assertMartingaleAnchored` |
| Replay divergence | Hash chain breaks, `certifyAdaptiveLineage` returning `is_valid=false` |
| Topology non-determinism | `topology_hash` computed from wall-clock or random inputs |
| Unbounded ecology growth | Spawning without bounded memory/execution/entropy declaration |
| Privileged orchestration | Code possessing authority not derivable from replay lineage |
| Centralized sovereign intelligence | Single control surface with unrestricted mutation rights |

## Reporting Format

```
REPLAY SOVEREIGNTY: [component] — COMPLIANT / VIOLATION

Root law:         SATISFIED | EXCEEDED (AdaptivePower=X, ReplayVerifiability=Y)
Ontology:         PASS | FAIL — missing: [primitive/replay/runtime/verifier mapping]
Cross-platform:   PASS | FAIL — [specific violation at file:line]
Prohibited:       NONE | [condition name at file:line, class: T0_ABORT]

Action: PROCEED / HALT — [reason]
```
