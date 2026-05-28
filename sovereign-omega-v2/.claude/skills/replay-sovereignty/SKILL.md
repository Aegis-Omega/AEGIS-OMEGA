---
name: replay-sovereignty
description: Automatically invoked when a new abstraction is introduced without canonical ontology mapping, when code could violate replay determinism, when cross-platform behavior is assumed in governance paths, when adaptive power is claimed beyond replay-verifiable bounds, or when any of the nine prohibited conditions are detected in proposed code or architecture.
---

# Replay Sovereignty Skill

**Autopoietic Property: Operational Closure — The Automaton Produces Itself From Itself**

Operational closure is the core of autopoiesis: the system's processes produce only the system itself. In AEGIS, this closure is **replay**: every state the system has ever been in can be reconstructed from the event log alone, without any external input, on any platform.

```
AdaptivePower(T) ≤ ReplayVerifiability(T)    ← The root constitutional law
```

This law IS the closure law. It states: the automaton cannot claim adaptive capability beyond what the replay engine can reconstruct and certify. Any adaptive power not grounded in replay is **open-loop production** — the system is producing something it cannot trace back to itself. This is the autopoietic equivalent of a cell producing proteins it cannot synthesize from its own genetic code.

**Operational closure requirements:**
- Every state transition is an event in `/event-log` (the organism's genetic code)
- Every event is replay-certifiable on Linux/macOS/Docker/WASM/ARM/x86 (cross-platform closure)
- No governance decision is made on non-deterministic substrate (wall-clock, Math.random, HashMap iteration)
- All adaptive capabilities are bounded by `assertMartingaleAnchored()` (bounded mutation rate)

**Closure violation = organism producing from outside itself.** The replay engine would fail to reconstruct the state because the input used to produce it no longer exists (it was a wall-clock timestamp, a random number, a non-deterministic hash map iteration). The organism has introduced non-self-producible material into its own structure.

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
| Law of Silence violation | Agent communicates with another agent directly (not through EventEnvelope); any direct text/object exchange between agents that bypasses the constitutional boundary |
| Corpus sovereignty violation | Raw narrative or unprocessed corpus content propagated into agent cognition without 5-phase RALPH loop processing |

## Reporting Format

```
REPLAY SOVEREIGNTY: [component] — COMPLIANT / VIOLATION

Root law:         SATISFIED | EXCEEDED (AdaptivePower=X, ReplayVerifiability=Y)
Ontology:         PASS | FAIL — missing: [primitive/replay/runtime/verifier mapping]
Cross-platform:   PASS | FAIL — [specific violation at file:line]
Prohibited:       NONE | [condition name at file:line, class: T0_ABORT]

Action: PROCEED / HALT — [reason]
```
