---
name: handoff-docs
description: Invoked when the user asks about the non-negotiable invariants list, explicitly prohibited constructs, operator decision log, epistemic taxonomy in handoff context, or the RALPH Ω loop execution synthesis.
---

# Handoff Documents Skill

## Non-Negotiable Invariants (T0)

### TypeScript Layer
1. No `Date.now()` in core logic — use `event.timestamp_ms`
2. No `array.length` for sequence numbers — use `IndexedDBSequenceAllocator`
3. No `Set` or `Map` in `ProjectionState` — arrays only
4. RFC 8785 JCS for all hashing — never `JSON.stringify`
5. `deepFreeze` all state after construction
6. Version mismatch = hard abort, never silent fallback
7. Bernstein bounds not Hoeffding — adaptive sampling violates IID
8. `MutationOperatorRegistry.seal()` before gate evaluations
9. V4/V5 verifiers never in VCG calibration

### Python Layer
10. All temporal semantics use event sequence number, never `time.time()`
11. Bit-shifted integer arithmetic in all determinism-critical paths
12. PGCS must pass (zero disk I/O) before TGCS telemetry is meaningful
13. Epoch failsafe `corruption_count` = 0 at all times
14. Anchor tokens immutable after epoch 0

### Rust Layer
15. `BTreeMap` / `BTreeSet` only — never `HashMap` (iteration order must be deterministic)
16. No `f64` in hash inputs — use `value.to_bits().to_be_bytes()` for floats
17. `saturating_add` / `saturating_mul` — no silent overflow
18. Hash field order: always `to_be_bytes()` (big-endian), never little-endian
19. Never `--all-features` in CI — `hip` and `rocblas` require ROCm hardware

## Explicitly Prohibited Constructs

From `handoff/17_EXPLICITLY_PROHIBITED.md`:

| Construct | Prohibition Reason |
|-----------|-------------------|
| Hidden memory | Violates replay sovereignty |
| Unrestricted recursion | Unbounded entropy |
| Autonomous mutation authority | Violates AdaptivePower ≤ ReplayVerifiability |
| Unverifiable adaptation | Cannot be governance-certified |
| Replay divergence | T0 constitutional failure |
| Topology non-determinism | Cross-platform hash instability |
| Unbounded ecology | K-bound violation |
| Privileged orchestration | Violates distributed authority model |
| Centralized sovereign intelligence | Violates Law of Silence |
| T4/T5 constructs in `src/` | Tier ceiling violation |

## Epistemic Tier Taxonomy (Handoff Context)

| Tier | Label | Permitted In |
|------|-------|-------------|
| T0 | Mechanically proven | `src/core`, `src/event`, `src/gate` |
| T1 | Empirically validated | `src/verifier`, `src/calibration` |
| T2 | Engineering hypothesis | `src/projection`, `src/pipeline` |
| T3 | Research conjecture | `docs/research` only |
| T4 | Speculative vision | `docs/vision` only |
| T5 | Creative/worldbuilding | `docs/cycles` only |

Migration rule: No T4/T5 construct may ground a T0–T2 claim without evidence review.

## Non-Equivalence Table (Memorise)

```
Replayability  ≠  Correctness
Auditability   ≠  Safety
Calibration    ≠  Truthfulness
Governance     ≠  Alignment
```

A perfectly replayable system can still replay catastrophic reasoning flawlessly.

## Gate 8 — Deployment Gate

Must pass before any commit enters the branch:
```bash
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build
```

A partial pass is a failure. Gate 8 is not optional.

## Source: `sovereign-omega-v2/handoff/05_INVARIANTS.md`, `handoff/06_TAXONOMY.md`, `handoff/17_EXPLICITLY_PROHIBITED.md`, `sovereign-omega-v2/CLAUDE.md`
