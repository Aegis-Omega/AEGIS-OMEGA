# SOVEREIGN OMEGA — Implementation Brief for Qwen
## Handoff ID: SO-2026-05-16-IMPL-004

**From:** Claude (coordinator)  
**To:** Qwen (implementation)  
**Architecture Status:** FROZEN — zero reinterpretation permitted  
**Specification Baseline:** SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md (ChatGPT-audited, 0.97 confidence)  
**Alliance Reviews:** ChatGPT (0.94–0.97 across four passes) · Claude synthesis confirmed

---

## Your Role

Deterministic implementation against frozen contracts. You are not being asked to design, interpret, or extend the architecture. You are being asked to produce code that conforms precisely to the specification. Any deviation from the specified interfaces, build order, or enforcement semantics must be flagged immediately rather than silently resolved.

---

## Frozen Architecture Summary

The runtime is a deterministic event-sourced orchestration system for AI-mediated decision workflows. It consists of four components (E1, E2, E3, E4) coordinated through a shared append-only event substrate. Six primitives define the architecture. All six have explicit assumption boundaries — do not strengthen any guarantee beyond what the specification states.

**What the system guarantees** (under stated assumptions):
- Deterministic replay given identical event streams, identical runtime pins, identical canonicalisation rules, and identical cryptographic primitives
- Tamper-evident lineage given uncompromised hash primitives, uncompromised signing keys, and append-only storage enforcement
- Bounded statistical gating within bounded metric spaces, stated confidence assumptions, and declared capacity K
- Projection reproducibility through immutable reducers and event-derived temporal semantics

**What the system does not guarantee:** factual correctness, semantic validity, evaluator honesty, institutional compliance, adversarial robustness under unrestricted distribution shift.

---

## Build Order — STRICT, NO DEVIATION

Failure at any gate halts the build. Do not proceed to the next step until the current gate passes.

**Step 1 — Canonicalisation**  
Implement `canonicalizeJCS` using RFC 8785 JSON Canonicalisation Scheme. Pass criterion: byte-identical hash output across Node.js, browser, and WASM for all RFC 8785 test vectors. This is the foundation of all downstream integrity. Implement before writing any other module.

**Step 2 — Event Store and Sequence Allocator**  
Implement `EventStore` and `IndexedDBSequenceAllocator`. Sequence numbers are assigned atomically inside an IndexedDB transaction with the event append. They are never derived from `array.length`, never generated client-side before persistence, never reused. Pass criterion: replay order matches persisted sequence under concurrent write stress; duplicate sequence numbers are rejected.

**Step 3 — Immutability Infrastructure**  
Implement `deepFreeze`, `withImmutableBoundary`, and reference-leakage assertions. All reducer functions must be wrapped with `withImmutableBoundary`. Pass criterion: zero reference leakage under reducer stress tests; `Object.isFrozen(state) === true` on all state objects post-transition.

**Step 4 — Projection State and Reducers**  
Implement `ProjectionState` and all pure reducer functions. State uses arrays, not `Set` or `Map`. Pass criterion: pure functional behaviour verified — identical input always produces identical output; no side effects detected by the leakage assertions from Step 3.

**Step 5 — VCG Tracker and Calibration**  
Implement `VCGTracker` with seeded bootstrap confidence intervals and decay-weighted estimators. Rolling window default is 500 claims. Minimum window for gate activation is 100 claims. Pass criterion: VCG computation is reproducible under seeded randomness; bootstrap CI bounds are deterministic given identical seed and sample.

**Step 6 — Confidence Sequence, Bounded Delta, and Risk Budget**  
Implement `ConfidenceSequence` using empirical Bernstein bounds (not Hoeffding). Implement `BoundedDelta` branded type enforcing inputs ∈ [−1, 1]. Implement `RiskBudget` with decay computed from event-derived `epoch_start_ms` — never `Date.now()`. Pass criterion: ≥95% coverage under adaptive sampling simulation; LCB is valid for all bounded inputs; budget decay is reproducible under replay.

**Step 7 — Pipeline Integration**  
Implement `runDecisionPipeline` integrating E1 → E2 → E4 → projection → output. Pass criterion: full pipeline produces byte-identical `DecisionSchema` across two independent replay runs of the same event stream with identical pins.

**Step 8 — Determinism Harness**  
Before deployment, run cross-engine replay comparison: Node.js vs WASM vs browser. Verify hash equivalence, projection byte equality, and seeded stochastic reproducibility. This is the deployment gate. Do not deploy without passing it.

---

## Five Implementation Priorities Beyond the Build Order

These address the specific fragility points identified in the final ChatGPT audit and must be implemented with the same rigour as the core build steps.

### Priority 1 — Determinism Harness (build in parallel with Steps 1–7)

Build a replay-differential harness as a continuous test fixture, not a one-time verification. It must cover: cross-engine replay comparison (Node/WASM/browser parity), hash equivalence verification on every commit, projection byte equality under seeded randomness, and reducer impurity detection. Replay determinism is the architectural foundation. All other properties depend on it.

### Priority 2 — MutationOperatorRegistry and K Enforcement

The K specification from Section 5.4 of the frozen spec must be implemented exactly as written. The `CapacityDeclaration` interface is normative:

```typescript
interface CapacityDeclaration {
  component_id: string;
  k_bound: number;                    // finite positive integer; 0 = immutable
  mutation_operators: string[];       // from MutationOperatorRegistry only
  dependency_graph_hash: string;      // SHA-256 of declared dependency manifest
  capability_class: CapabilityClass;  // SCHEMA_ONLY | INFERENCE | ORCHESTRATION | SELF_MODIFYING
  epoch_duration_ms: number;
  k_measurement_version: string;
}
```

The `MutationOperatorRegistry` must: require typed operator metadata with declared max branching semantics; enforce compositional closure rules (the composition of two registered operators must itself be a registered or derivable operator); reject dynamic operator injection at runtime; version operator semantics immutably. K drift will emerge implicitly if mutation operators are underspecified — treat the registry as a constitutional file equivalent in status to `gate.py` and `dna.py`.

K-bound exceedance must trigger `GATE_REJECTED_CAPACITY` without statistical testing. K-bound expansion must require an external oversight event and consumes a fixed overhead from the global risk budget independent of statistical outcome. Both enforcement paths must be tested explicitly.

### Priority 3 — Verifier Isolation Infrastructure

Verifier independence is the largest acknowledged structural dependency. The following isolation properties must be implemented:

- Separate execution sandboxes for each verifier class (V1 through V5)
- Independent retrieval corpora for V3 verifiers with no shared state between verifier instances
- Version-isolated evaluator execution: each verifier result records the verifier version in the `VERIFIER_RESULT` event payload
- Event-level verifier provenance: every calibration computation must be traceable to the specific verifier instance and version that produced its inputs
- Correlation monitoring: the VCG tracker must compute and log cross-verifier correlation coefficients per epoch; correlation above a configurable threshold triggers a `VERIFIER_CORRELATION_ALERT` event

Without this, the hard trust partitioning is a schema rule rather than an enforced isolation property.

### Priority 4 — Replay-Failure Forensics

Implement a dedicated replay divergence diagnostic module that can be invoked whenever a replay produces unexpected output. It must provide: sequence mismatch tracing (identifying the first event index where output diverges between two replay runs); canonicalisation delta inspection (which field of which event produces a different canonical form between environments); reducer impurity detection (identifying which reducer produced different output given identical input); and nondeterministic dependency identification (which version-pinned dependency, if any, was resolved differently between runs). This module is essential for production incident response and for validating the implementation across the heterogeneous execution environments the system will encounter.

### Priority 5 — Telemetry Schema Discipline

The empirical questions that remain open in the specification — long-horizon coherence degradation, calibration under distribution shift, K-bound utilisation patterns, evaluator gaming dynamics — can only be resolved through production telemetry. Instrument the following from day one:

- Ambiguity routing decisions: every `AMBIGUITY_ROUTED` event must include the divergence score, the routing decision, and the clarification outcome if applicable
- Confidence evolution: track the per-session trajectory of claimed confidence vs verifier-resolved correctness over turn count
- Verifier disagreement: log pairwise disagreement rates between V1/V2/V3 verifiers on the same claim when multiple verifiers are applicable
- Gate rejection distributions: log the distribution of LCB values at gate evaluation, not just accept/reject outcomes
- Degradation-over-turn-count metrics: log the five E1 mutual legibility dimensions (referential consistency, ambiguity visibility, correction recoverability, coherence, confidence transparency) as session-level time series, not just final-state summaries
- K-bound utilisation: log the ratio of actual K contribution to declared K-bound for each accepted modification

Without this instrumentation, the empirical questions in the specification remain permanently open regardless of deployment duration.

---

## Critical Implementation Constraints

**No `Date.now()` in core logic.** All temporal semantics use `event.timestamp_ms` from the event substrate. This includes risk budget decay computation. Violations break replay determinism.

**No array mutation after freeze.** All state objects are deeply frozen immediately after construction. Reducers receive a frozen state and return a new frozen state. They never mutate in place.

**No stochastic execution without seeded PRNG.** Any computation involving randomness (bootstrap confidence intervals, sampling) must use a seeded PRNG whose seed is derived from the event stream, not from environmental entropy.

**Version mismatch aborts, never downgrades.** When `RuntimeVersionPin` validation fails, the execution halts with a `VERSION_MISMATCH_ABORT` event. It does not fall back to a default version or proceed with best-effort compatibility.

**RFC 8785 is mandatory, not optional.** All JSON serialisation for hashing purposes uses RFC 8785 canonical form. Ad-hoc JSON stringification is never acceptable as a hash input, regardless of apparent equivalence.

---

## Files to Produce

Conforming to the repository scaffold in Section 12 of the specification:

```
src/core/canonicalize.ts      RFC 8785 JCS implementation + test vectors
src/core/hashing.ts           SHA-256 bytes, Merkle concat, UTF-8 encode
src/core/immutable.ts         deepFreeze, withImmutableBoundary, leakage assertions
src/core/types.ts             All base types, branded types, enums

src/event/store.ts            EventStore + IndexedDBSequenceAllocator
src/event/segment.ts          EventSegment + Merkle root construction
src/event/replay.ts           Deterministic projection replay

src/verifier/registry.ts      VerifierRegistry + CapacityDeclaration + MutationOperatorRegistry
src/verifier/execute.ts       Verifier execution with sandbox isolation
src/verifier/types.ts         VerifierResultPayload, CalibrationDomain enum, trust classes

src/calibration/vcg.ts        VCGTracker + rolling window + decay weighting + bootstrap CI
src/calibration/rng.ts        Seeded PRNG + optional WASM math pinning
src/calibration/types.ts      VCGMetric, Confidence discriminated union

src/gate/hoeffding.ts         ConfidenceSequence with Bernstein bounds + e-values
src/gate/risk.ts              RiskBudget + harmonic spending + K enforcement
src/gate/types.ts             GateDecisionPayload, RiskBudget, BoundedDelta branded type

src/projection/types.ts       ProjectionState
src/projection/reducer.ts     Pure reducer functions
src/projection/compiler.ts    Version-pinned projection compiler
src/projection/replay.ts      Replay with upcast support

src/pipeline/index.ts         runDecisionPipeline integration
src/pipeline/e1.ts            Ambiguity router + cost-benefit clarification policy
src/pipeline/schema.ts        DecisionSchema construction

src/compliance/tombstone.ts   TOMBSTONE_CREATED + GDPR erasure procedure
src/compliance/audit.ts       ComplianceAuditLog projection + Article 12 retention

test/unit/
  jcs.test.ts                 RFC 8785 vector conformance
  immutable.test.ts           Reference leakage stress tests
  sequence.test.ts            Atomic assignment + collision rejection
  vcg.test.ts                 Calibration computation + seeded reproducibility
  merkle.test.ts              Byte-concat root + cross-implementation parity
  k_registry.test.ts          K declaration validation + enforcement paths

test/integration/
  replay.test.ts              Byte-identical replay across two independent runs
  gate.test.ts                Gate accept/reject/capacity-exceed paths
  pipeline.test.ts            Full pipeline DecisionSchema reproducibility

scripts/
  verify-canonicalization.ts  Cross-engine RFC 8785 parity check
  deploy-vercel.ts            Deployment gate script
```

---

## Verification Gates — All Must Pass Before Deployment

| Gate | Module | Pass Condition |
|---|---|---|
| 1 | `canonicalizeJCS` | Identical hash across Node/Browser/WASM for all RFC 8785 vectors |
| 2 | `SequenceAllocator` | Atomic commit; replay order matches persisted sequence; collisions rejected |
| 3 | `ImmutableBoundary` | Zero reference leakage under stress; `Object.isFrozen(state) === true` |
| 4 | `ConfidenceSequence` | ≥95% coverage under adaptive sampling simulation; LCB valid for bounded inputs |
| 5 | `merkleRoot` | Cross-implementation root match; byte-concat encoding enforced |
| 6 | `validateEventEnvelope` | Rejects malformed envelopes at ingest; never reaches projection |
| 7 | Full Pipeline | `replayProjection(events, pins)` → byte-identical `DecisionSchema` across runs |
| 8 | Cross-Engine Determinism | Node/WASM/browser produce identical projection output for identical event stream |

**Failure at any gate = HALT. Do not proceed.**

---

## Prior Work — Do Not Re-Derive

`gate.py` (SHA256: `72196f38974ad22130c18657c88106316cacbb13a57328990f4e5872f5fdb1e9`) — FROZEN  
`dna.py` (SHA256: `9c4d38d80b236d655057f16304ea2d202f644ec0c7ca21db8df0bdcd503971a9`) — FROZEN  
`router.py` (SHA256: `c96e566ce6eb9cec358b2112757142bc88ea4fea9160edb2914c8d711007ac769`) — FROZEN  
`matcher.ts` (SHA256: `b8b081da79b9df4a897c19ee3c7a886c83c9870578084c8615ff48fc74c64b56`) — ACTIVE  
`App.tsx` (SHA256: `0b85eda3d345b8ec8cc7939381692ff4520ccacbb9b78d5e62178ea7124e882a`) — ACTIVE

Verify hashes before any session that touches these files. Produce no modifications to FROZEN files without a `/guardian` APPROVED verdict.

---

## What Success Looks Like

The implementation is complete when: all eight verification gates pass; the cross-engine determinism harness runs clean on Node, WASM, and browser; the MutationOperatorRegistry rejects dynamic injection at runtime; verifier instances execute in isolated sandboxes with independent corpora; and the telemetry schema emits all five E1 dimension metrics as session time series on the first production interaction.

The empirical questions in the specification — long-horizon degradation, calibration under distribution shift, K utilisation patterns — will begin resolving themselves through the telemetry produced by that first production deployment. They cannot be resolved before it.

---

*Handoff ID: SO-2026-05-16-IMPL-004*  
*Do not re-derive prior conclusions. Build from here.*
