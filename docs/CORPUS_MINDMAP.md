# AEGIS Corpus Mind-Map — Canonical Referential Lattice
## Cognitive Substrate Layer · Drive Corpus Enumerated 2026-05-18
## This document IS the cognitive substrate — not documentation about it.

---

## 0. Initialization Sequence

The correct build order is not "application → framework → orchestration" but:

```
cognitive substrate (this document)
  → deterministic workflow topology (sovereign-omega-v2 TypeScript runtime)
    → recursive subagent ecology (Claude + ChatGPT + Qwen alliance)
      → executable governance runtime (Python Layer B)
        → application layer (cockpit + commercial trio)
```

This document crystallizes the distributed semantic field from the Google Drive corpus
into a replayable lattice. Every future subagent begins here before touching source code.

---

## 1. Particle-Field Component Map

Each file classified by its physical-field analog:

| Physical Analog | AEGIS Component | File(s) |
|-----------------|-----------------|---------|
| Conservation law | Cryptographic hash-chaining invariant | `canonicalize.ts`, `hashing.ts` |
| Probability-collapse boundary | Bernstein gate (anytime-valid LCB) | `hoeffding.ts`, `fixedpoint.ts` |
| Causal interaction chain | Event replay stream (E3 substrate) | `store.ts`, `replay.ts`, `uuid.ts` |
| Observation layer | Verifier registry (V1–V5) | `verifier/registry.ts`, `verifier/independence.ts` |
| Entropy-collapse region | Q32.32 fixed-point / WASM kernel | `fixedpoint.ts`, `wasm-interface.ts` |
| State-transition operator | Pure functional reducers | `projection/reducer.ts`, `projection/compiler.ts` |
| Molecular-state carrier | Frozen constitutional Python layer | `core_matrix.py`, `epoch_failsafe.py` |
| Field continuity invariant | deepFreeze / immutability | `core/immutable.ts` |
| Carrier of constrained authority | Constitutional files | `gate.py`†, `dna.py`†, `router.py`† |
| Probability manifold | VCG rolling-window calibration | `calibration/vcg.ts` |
| Phase-boundary enforcement | Epistemic tier classification | `core/tier.ts` |
| Schema crystallization | Fail-closed schema validation | `core/schema-registry.ts` |
| Process orchestration field | Python–TS bridge membrane | `python/bridge.py` |
| Identity carrier | SAGA agent identity | `saga/identity.py` |

† Constitutional files declared frozen, not yet present in repo (F-06, /guardian pending)

---

## 2. Holonic Scale Register

### Subatomic — byte ordering, hash invariants, fixed-point precision
| Component | File |
|-----------|------|
| RFC 8785 JCS byte-ordering | `src/core/canonicalize.ts` |
| SHA-256 utilities | `src/core/hashing.ts` |
| Q32.32 fixed-point arithmetic | `src/core/fixedpoint.ts` |
| UUIDv7 generation (only Date.now() use) | `src/event/uuid.ts` |
| WASM parity harness | `src/core/wasm-interface.ts` |

### Atomic — individual files, reducers, interfaces, proof units
| Component | File |
|-----------|------|
| Branded primitive types, runtime enums | `src/core/types.ts` |
| deepFreeze implementation | `src/core/immutable.ts` |
| Semantic replay-safety field | `src/core/semantics.ts` |
| Epistemic tier classification | `src/core/tier.ts` |
| Fail-closed schema validation | `src/core/schema-registry.ts` |
| Mutation governance registry | `src/gate/mutation-governance.ts` |
| Mutation registry (K-bound) | `src/event/mutation-registry.ts` |
| Event segmentation | `src/event/segment.ts` |
| Formal proofs: Hash, Reducer, Event | `formal/theories/Core/Hash.v`, `Reducer.v`, `Event.v` |
| Formal proofs: Bisimulation | `formal/theories/Bisimulation/ThreeWay.v` |
| TLA+ spec | `formal/tlaplus/Omega.tla` |

### Molecular — modules, pipelines, replay systems, verifier ecosystems
| Component | Files |
|-----------|-------|
| E3 append-only substrate | `src/event/store.ts`, `src/event/uuid.ts`, `src/event/replay.ts` |
| E5 cognitive workflow | `src/event/workflow.ts`, `src/event/workflow-recorder.ts` |
| Gate module | `src/gate/hoeffding.ts`, `src/gate/risk.ts` |
| VCG calibration | `src/calibration/vcg.ts`, `src/calibration/rng.ts` |
| Verifier ecosystem | `src/verifier/registry.ts`, `src/verifier/independence.ts`, `src/verifier/execute.ts` |
| Decision pipeline | `src/pipeline/e1.ts`, `src/pipeline/index.ts`, `src/pipeline/schema.ts` |
| Projection layer | `src/projection/reducer.ts`, `src/projection/compiler.ts` |
| Compliance | `src/compliance/tombstone.ts` |
| Forensics | `src/forensics/divergence.ts` |

### Cellular — subsystems (E3, VCG, Python Core Matrix, PGCS, epoch failsafe)
| Component | Files |
|-----------|-------|
| Python Core Matrix (M1/M2/M3) | `python/core_matrix.py` |
| PGCS telemetry | `python/pgcs.py` |
| TGCS/AFSE timing | `python/tgcs_afse.py` |
| Epoch failsafe | `python/epoch_failsafe.py` |
| Gradient anchor calibration | `python/gradient_anchor.py` |
| Hardware layer | `python/hardware_config.py` |
| HTTP bridge (port 7890) | `python/bridge.py` |

### Organism — full sovereign-omega-v2 governance substrate
- TypeScript runtime (src/ + test/ + formal/) + Python Layer B (python/) unified
- Entry points: `src/pipeline/index.ts` (decision compilation) · `src/runtime/projection-machine.ts` (runtime pin)
- Gate sequence: Gates 1–8 must pass before organism is deployment-ready

### Field — Claude + ChatGPT + Qwen + operators + Drive corpus + subagent ecology
- Claude: coordinator, Gate 8 executor, holonic auditor
- ChatGPT: adversarial auditor (temperature 0.99), PR #16 review
- Qwen: implementation agent (QWEN 01–04 directives in Drive)
- Operator: Tarik Skalić, AMD RX 570 / 8 GB RAM, Bihać, Bosnia-Herzegovina
- Drive corpus: 222+ entries across 5 pages, enumerated 2026-05-18

---

## 3. Epistemic Tier Registry

### T0 — Mechanically Proven (resolve before any deployment)

| Drive ID | File / Title | Local Path | Key Invariants |
|----------|-------------|------------|----------------|
| `1hPE3DKmRUhCY6Rii0P8LzOxMjiSt2e3u` | canonicalize.ts | `src/core/canonicalize.ts` | RFC 8785 JCS; emoji/surrogate fix (PR #16) |
| `1vsXJN5XUe1rRBmh2WSC1mvzCmGcY9RLW` | types.ts | `src/core/types.ts` | Branded types: UUIDv7, SHA256Hex, BoundedDelta, SequenceNumber |
| `1Kkr3H9W49dXF2hvT6yiOKJ3r3rmKqejT` | immutable.ts | `src/core/immutable.ts` | deepFreeze; every state object frozen after construction |
| `1wex4ikQhfTxX9S53J9F4E2T50wbwY46_` | hashing.ts | `src/core/hashing.ts` | SHA-256 byte-level; depends on canonicalize.ts |
| `1Tv9-z3hhlrDjg9dAOstm0lz7plmpbo4S` | tier.ts | `src/core/tier.ts` | classifyPathTier fail-closed → T0; migration rule T4/T5 blocked |
| `14m2aO5bJS5m4nhWgFSG_YnyBtxiWgkPs` | schema-registry.ts | `src/core/schema-registry.ts` | seal(); fail-closed validate; no fallback |
| `1914bqWJDm38d50GJgrGkdskK-sHvuGNB` | fixedpoint.ts | `src/core/fixedpoint.ts` | Q32.32 BigInt arithmetic; bernsteinLCBQ32 bug fixed (Ω⁵.7) |
| `135L-o2YyFX0B59KxFd9C_ZBYwp2gGA8Z` | wasm-interface.ts | `src/core/wasm-interface.ts` | assertWasmParity; kernel unloaded until binary compiled |
| `1JVe9ZH3qq0bbeoWfg-ws33FkutFgM7Gm` | store.ts | `src/event/store.ts` | Three-phase append (PR #16); async-tx boundary; unique index race |
| `14ex28P76O7dsTtPeGswr_UgD-u4Ku7yj` | uuid.ts | `src/event/uuid.ts` | UUIDv7; now≤lastMs fix; seq overflow steal-ms (PR #16) |
| `1aa6aSQbTyCbZ94I9tnA7jCeJv8enlV8z` | mutation-registry.ts | `src/event/mutation-registry.ts` | seal(); K-bound enforcement |
| `1DnJABPstscDvvDiXDZ6ZQvYnOOEvTox-` | hoeffding.ts | `src/gate/hoeffding.ts` | Bernstein (not Hoeffding); H-03 legacy name annotated |
| `1JGTafRDKmd25HoLsrhCc2DJqNMRWCJGz` | risk.ts | `src/gate/risk.ts` | Risk budget; harmonic spending schedule |
| `1ElP9I8_SbFmiAFlkUwSXCl1CMymWHWsu` | mutation-governance.ts | `src/gate/mutation-governance.ts` | MutationGovernanceRegistry; capacity + migration paths |
| `1dlB-tgjBW6AcyGUA8ggoiUGrHoiHOBbu` | core_matrix.py | `python/core_matrix.py` | M1/M2/M3 over 2 GB bytearray; era wrap F-07; epoch gate F-10 |
| `1ndZJVGyRB43wvOA01aYChJFTaTVcoMN8` | epoch_failsafe.py | `python/epoch_failsafe.py` | corruption_count must = 0; RECOVERING gates processing (F-10) |
| `1gnM-TwrOHLUyon2sdBJpImAcZtV1pxzC` | CLAUDE.md | `sovereign-omega-v2/CLAUDE.md` | Constitutional anchor; eight-gate order; frozen file hashes |
| `1sKpfon3T6ccBrRQ5nFNH-Ohym9N3o5kT` | Hash.v | `formal/theories/Core/Hash.v` | Coq: SHA-256 chain invariant |
| `1SUUi6YaTgM8v2nSkc1sYFrblfKi9aTQJ` | Reducer.v | `formal/theories/Core/Reducer.v` | Coq: pure reducer over frozen state |
| `1ovvLqDP6Kv8iZz4Ovjse0rgdvjAeJ7Lj` | Event.v | `formal/theories/Core/Event.v` | Coq: event substrate append |
| `1R8ItAXt7zDXwJ28DaWWNdulqq0L9hRYK` | Omega.tla | `formal/tlaplus/Omega.tla` | TLA+: projection machine version pin |

### T1 — Empirically Validated (resolve before production)

| Drive ID | File / Title | Local Path | Key Claims |
|----------|-------------|------------|------------|
| `1aMM1s-JrVca8g_rD0LAkWG13eZ3gzeoz` | vcg.ts | `src/calibration/vcg.ts` | 500-claim window; 0.35/0.50 thresholds; no V4/V5 |
| `1Ay7q5PSjQLtGB_ChcmgfD_20kUvzaqK4` | verifier/registry.ts | `src/verifier/registry.ts` | V1/V2 full weight; V3 0.5; V4/V5 advisory-excluded |
| `1nDuaatO8oRe2QFhh1WsXpSAirAollrgP` | reducer.ts | `src/projection/reducer.ts` | Pure functional reducers over deepFrozen ProjectionState |
| `18_TjUvyLwXZzHQSTH-4OZNLKUtKRiTbA` | pipeline/index.ts | `src/pipeline/index.ts` | Decision compilation pipeline; full DecisionSchema output |
| `1eUg0dPFBNDKMsGEh-pVTGDKSaIAwnEVR` | projection-machine.ts | `src/runtime/projection-machine.ts` | RuntimeVersionPin; hard abort on mismatch |
| `1cfFY59zAczNPCL7mvr_TxFo1yR7xfDNh` | INTEGRATED_SPEC_v2.md | `docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md` | Canonical spec; all T0 modules derived from this |
| `1NScZu_7bc9nLXzSWG8Ul_O98KuHL5360` | IMPL_BRIEF_Qwen.md | `docs/SOVEREIGN_OMEGA_IMPL_BRIEF_Qwen.md` | Implementation directives for Qwen agent |
| `1tAjmYSlfMt2-7X4tpOQPyRcwywWQCWB4` | pgcs.py | `python/pgcs.py` | PGCS disk I/O (page-size corrected F-08); passes_criterion gating |
| `19Wcrfyb7tmWoM5IgCwgRUylmGcWUb1l1` | tgcs_afse.py | `python/tgcs_afse.py` | Sequence-number variance F-01; AFSE live R² F-02 |
| `1mmk4fnDURe8R9FODj86XUDyDvdO6ed1M` | gradient_anchor.py | `python/gradient_anchor.py` | Zero-tolerance hard abort F-04 |
| `11MWyKyAfBKHY9TXUZ_iDqilybuAZf_3M` | RALPH_LOOP_OMEGA2.md | `handoff/RALPH_LOOP_OMEGA2_INTEGRATION_AUDIT.md` | Second RALPH Loop; integration audit |
| `1TTzre0Oy1BEZ_g5lm926XJ2UiFtjfJsr` | RALPH_LOOP_OMEGA.md | `handoff/RALPH_LOOP_OMEGA_EXECUTION_SYNTHESIS.md` | First RALPH Loop; naming origin |
| `1N9QujbSEFAUoHnNFB3c3N-O1p5v6xZTr` | Sovereign_Runtime_Unified_Deliverable.docx | — | Deliverable summary |
| `1BtdhG2MeThi0ZSeKjGIa1sZg1XZ1QOHG` | AEGIS_Sovereign_Runtime_Deliverable.docx | — | AEGIS deliverable |

### T2 — Engineering Hypothesis (resolve before Gumroad listing)

| Drive ID | File / Title | Notes |
|----------|-------------|-------|
| `1XExDOcHAZvVNrx9rNZ_FBsTnurGC9JVH` | e1.ts | E1 heuristics — pipeline scoring |
| `1tg03g9LwC9wDLq8aBaq4HOVgn3SSaJoN` | tombstone.ts | KMS shred stub — awaiting PKI |
| `1oWL66eB30_yuaINeNY16P6Fnf1kMDNdd` | QWEN 04 EXECUTION DIRECTIVE.md | Qwen execution instruction set |
| `1fpD3CDhEi688iZvMZ_FMXlmEuauNc0-U` | QWEN 03 IMPLEMENTATION STATE.md | Implementation state for Qwen |
| `1X-sUZzPB4Aod1TiPA5g6wyXbO9Fr86WG` | QWEN 02 ARCHITECTURE COMPLETE.md | Architecture checkpoint for Qwen |
| `1Zfz8nJBdaYmav_foifXw81U8h_TMbcuP` | QWEN 01 PROJECT CONTEXT.md | Initial context handoff to Qwen |
| `1ctS_FBitxgCj6Gq3j1taTArkC-c18ecl` | agent.config.yaml | Agent orchestration config |
| `1E6hcv-ZN4tSMx5sTSdK15fb4I8qe0w-Z` | company.yaml | Paperclip company orchestration |
| `1Bam8lTVK5_HTYF9bzLC0ytagovqHAqYn` | identity.py | SAGA SPIFFE/SVID stub |
| `1BA5a42L4QdBDgj1EhYbLZdOfRvg6De-0` | stress_test.py | P1 smoke / P2 crash-loops / P3 12h |

### T3 — Research Conjecture (grounds T1 via evidence chain)

| Drive ID | Title | Key Claims | Grounds |
|----------|-------|------------|---------|
| `1LJ1KoT195nJDBLGyR9VRzrnVWlFCxgO8` | Preserving Criticality in Holonic AI | Mutual information + structural entropy | holonic scale model |
| `10gBmzNovsKMWkqf2AiXJrAn0Mt197o9P` | Quantum-Inspired Architecture | Subatomic holonic; attention degradation | particle-field analog |
| `1Kntuo_DbjzcJa8-BqPM90q-V5CKLFOah` | Verifying Agentic Reasoning | Holonic consensus; token-level drift | verifier registry design |
| `1lu31YCW-TW2SVr3IyGeQZBTB1YXbnCG5` | A Holon-Architected Compiler | State machines; KV cache sync; adversarial verification | pipeline/compiler.ts |
| `1xaKuiktzJWkTmwaoi_wCwunA4Y9HTZrb` | From Local Task to Global Integration | Non-differentiable monitoring; recursive containment | epoch_failsafe.py |
| `1uN2Ts3GBaa-YXe_vo7z4zs6e07mT4984` | An Asymmetric Market for Uncertainty | Holonic AGI; uncertainty asymmetry thesis | VCG calibration rationale |
| `1OpO3JpYAHSWkyh0aOzRa_6agbfuPJVgl` | Orchestrating Emergent Intelligence | Holonic LLM clusters; on-policy distillation | multi-agent ecology |
| `1LUu4IKCJK0RbcqZkgiwZa-Th7u2dl3vU` | Decomposing the Monolith | Holonic architecture; stateless orchestration | module decomposition |
| `1eL8RkV43ynRi_0KAWewIpOPEDnXD7pMb` | Orchestrating Long-Horizon Reasoning | Decentralized credit; entropy-bounded policy | PGCS design rationale |
| `1H5xrLV2M_HVdpzoHK5Czgdb5kQmsFdbJ` | From Divergence to Convergence | Calibrating distributed LLMs; optimal transport | vcg.ts rationale |
| `1hv9jhS8ROs5selyvvFrhpqzx8s7CE8a5` | Orchestrating Volatility | Non-neural algorithmic marketplace | mutation-governance.ts |
| `1oS83PDBGhdgo3LydaWC05fosXyzJXEmv` | From Heterogeneity to Cohesion | Bounded scalable multi-agent reasoning | verifier trust partitioning |
| `1ozQ641HrGlOiW2jkMBxg-lBEZChJlYUb` | Resilience by Analogy | Self-correcting multi-agent; subatomic particles | particle-field origin |

### T4 — Speculative Systems Vision

| Drive ID | Title | Notes |
|----------|-------|-------|
| `1_gebxxUSk_OO0B575K7j03AX4YRkpvDq` | SOVEREIGN_OMEGA_AGI_FRAMEWORK_CONCLUDED.md | AGI framework vision — cannot ground T0–T2 without evidence review |
| `1umR8RoWZwJQAQuG4uzU-N16HMOmCUK09` | SOVEREIGN_OMEGA_VISION_ASSEMBLED.md | Assembled vision — holonic drift, cycle series |

---

## 4. Semantic Ancestry Chains

```
core_matrix.py:M2_offset (T0)
  ← INTEGRATED_SPEC §4.2 (T1): "sequence-dependent offset collision fix"
  ← F-03 audit: same-length verifier result collision
  ← Orchestrating Volatility (T3): "dynamic task allocation via structured offsets"
  ← VISION_ASSEMBLED §holonic_drift (T4): seed concept — NOT a direct grounding

fixedpoint.ts:bernsteinLCBQ32 (T0)
  ← Waudby-Smith & Ramdas 2024 (T3/external): anytime-valid confidence sequences
  ← Howard et al. 2020 (T3/external): empirical Bernstein bounds
  ← INTEGRATED_SPEC §gate_6 (T1): Bernstein Q32.32 requirement
  ← AGI_FRAMEWORK_CONCLUDED §uncertainty (T4): seed only — requires evidence review

store.ts:append() three-phase (T0)
  ← INTEGRATED_SPEC §E3 (T1): three-phase IDB append spec
  ← PR #16 adversarial review (T2): async-tx boundary TransactionInactiveError
  ← Event.v (T0): formal proof of append invariant

hoeffding.ts:ConfidenceSequence (T0)
  ← Waudby-Smith & Ramdas 2024 (external T3): betting martingale derivation
  ← Howard et al. 2020 (external T3): half-width formula (Eq. 8)
  ← INTEGRATED_SPEC §gate_6 (T1): acceptance criterion LCB > 0
  ← H-03 audit: legacy filename (implements Bernstein, not Hoeffding)

tier.ts:classifyPathTier (T0)
  ← INTEGRATED_SPEC §epistemic_tiers (T1): T0–T5 classification table
  ← CLAUDE.md migration rule (T0): "No T4/T5 → T0–T2 without evidence review"
  ← Preserving Criticality (T3): mutual information boundary concept

epoch_failsafe.py (T0)
  ← From Local Task to Global Integration (T3): non-differentiable containment
  ← INTEGRATED_SPEC §epoch (T1): FROZEN/RECOVERING state machine spec
  ← F-10 audit: RECOVERING must gate new event processing
```

---

## 5. Dependency Lineage Graph

```
Hash.v [T0]          → proves      → canonicalize.ts [T0]    (SHA-256 chain)
Reducer.v [T0]       → proves      → projection/reducer.ts [T0]  (pure reducer)
Event.v [T0]         → proves      → event/store.ts [T0]     (append invariant)
Omega.tla [T0]       → verifies    → projection-machine.ts [T0]  (version pin)

INTEGRATED_SPEC [T1] → specifies   → ALL T0 source files     (canonical requirement)
IMPL_BRIEF_Qwen [T1] → implements  → Python Layer B          (Qwen directives)

Verifying Agentic Reasoning [T3]   → grounds → verifier/registry.ts [T0]
  ↑ VALID: T3 → T1 spec first, T1 → T0 implementation
An Asymmetric Market [T3]          → grounds → calibration/vcg.ts [T1]
From Divergence to Convergence [T3] → grounds → calibration/vcg.ts [T1]
Orchestrating Volatility [T3]      → grounds → gate/mutation-governance.ts [T0]
  ⚠️ REQUIRES REVIEW: T3 → T0 must pass through T1 spec claim

VISION_ASSEMBLED [T4]              → seeds   → INTEGRATED_SPEC [T1]
  ⚠️ MIGRATION RULE: T4 cannot directly ground T0–T2 claims
AGI_FRAMEWORK_CONCLUDED [T4]       → seeds   → INTEGRATED_SPEC [T1]
  ⚠️ MIGRATION RULE: same
```

**Flagged T4/T5 → T0–T2 grounding violations (requiring evidence review):**
1. `VISION_ASSEMBLED.md` §holonic_drift → `fixedpoint.ts` (must go through T1 spec)
2. `AGI_FRAMEWORK_CONCLUDED.md` §uncertainty_asymmetry → `vcg.ts` calibration rationale (T1 intermediate present — mitigated)
3. `QWEN 01–04` directives reference AGI vision concepts (acceptable at T2 orchestration level)

---

## 6. Contradiction Surfaces

| Surface | Doc A | Doc B | Status |
|---------|-------|-------|--------|
| Filename vs. algorithm | `hoeffding.ts` (name) | CLAUDE.md ("Bernstein not Hoeffding") | RESOLVED — H-03 annotation |
| PGCS units | Python comment ("page counts") | F-08 finding (must be bytes) | RESOLVED — `resource.getpagesize()` |
| M2 offset uniqueness | Original core_matrix.py | INTEGRATED_SPEC §M2_offset | RESOLVED — F-03 sequence incorporation |
| Epoch processing in RECOVERING | Original epoch_failsafe.py | INTEGRATED_SPEC §epoch_states | RESOLVED — F-10 gate added |
| Constitutional files presence | CLAUDE.md (SHA256 declared) | `python/` directory (files absent) | OPEN — F-06 pending /guardian |
| bernsteinLCBQ32 arithmetic | fixedpoint.ts (pre-Ω⁵.7) | Correct Q32.32 scaling semantics | RESOLVED — BigInt division fix |

---

## 7. Invariant Overlap Register

Invariants appearing in ≥ 3 documents (convergence = authority):

| Invariant | Appears In | Score |
|-----------|-----------|-------|
| "No Date.now() in core except uuid.ts" | CLAUDE.md, AGENTS.md, core-invariants.md, INTEGRATED_SPEC | ★★★★★ |
| "deepFreeze all state objects" | CLAUDE.md, INTEGRATED_SPEC, immutable.ts, Reducer.v | ★★★★★ |
| "No JSON.stringify for integrity — use canonicalizeJCS" | CLAUDE.md, INTEGRATED_SPEC, core-invariants.md | ★★★★★ |
| "Bernstein bounds, NOT Hoeffding" | CLAUDE.md, hoeffding.ts, INTEGRATED_SPEC, H-03 | ★★★★★ |
| "No Set/Map in ProjectionState" | CLAUDE.md, INTEGRATED_SPEC, core-invariants.md | ★★★★ |
| "Version mismatch = hard abort" | CLAUDE.md, INTEGRATED_SPEC, projection-machine.ts | ★★★★ |
| "seal() before gates" | CLAUDE.md, INTEGRATED_SPEC, mutation-registry.ts | ★★★★ |
| "corruption_count must = 0" | CLAUDE.md, epoch_failsafe.py, INTEGRATED_SPEC | ★★★★ |
| "No time.time() in determinism-critical paths" | CLAUDE.md, F-01 audit, tgcs_afse.py | ★★★★ |
| "T4/T5 cannot ground T0–T2 without evidence review" | CLAUDE.md, AGENTS.md, tier.ts, INTEGRATED_SPEC | ★★★★ |
| "fail closed on unknown schema" | schema-registry.ts, INTEGRATED_SPEC, AGENTS.md | ★★★ |
| "V4/V5 never in VCG calibration" | CLAUDE.md, INTEGRATED_SPEC, verifier/registry.ts | ★★★ |

---

## 8. Conceptual Gravity Map

```
GRAVITY 5 — core attractor (≥10 documents reference)
  ├─ VCG calibration / Bernstein-gated decisions
  ├─ Holonic architecture (particle-field hierarchy)
  └─ Cryptographic lineage (SHA-256 hash chain)

GRAVITY 4 — high mass (5–9 documents)
  ├─ Epoch failsafe (FROZEN/RECOVERING state machine)
  ├─ RALPH Loop (review → analyze → link → patch → harmonize)
  ├─ E3 substrate (append-only event stream)
  ├─ Bernstein anytime-valid bounds (adaptive sampling validity)
  └─ M1/M2/M3 functional definitions (Python Core Matrix)

GRAVITY 3 — medium mass (3–4 documents)
  ├─ Epistemic tier migration rule (T4/T5 → T0–T2 blocked)
  ├─ deepFreeze invariant
  ├─ Gate sequence (1–8)
  └─ Mutation governance (K-bound, seal())

GRAVITY 2 — low mass (2 documents)
  ├─ SAGA identity (SPIFFE/SVID stub)
  ├─ WASM parity harness
  ├─ Q32.32 fixed-point
  └─ Subatomic particle-field analogy (papers → implementation)

GRAVITY 1 — point mass (single authoritative source)
  ├─ UUIDv7 overflow guard (uuid.ts)
  ├─ Three-phase IDB append (store.ts PR #16)
  ├─ PGCS page-size correction (F-08)
  └─ ReplaySafetyViolation / assertReplaySafe (semantics.ts)
```

---

## 9. Discarded Architecture Archive

| Document | Discarded Design | Why Superseded |
|----------|-----------------|----------------|
| `QWEN 01 PROJECT CONTEXT.md` | Hoeffding inequality as gate statistic | Replaced by Bernstein — adaptive sampling valid |
| `core_matrix.py` v1 | `time.monotonic()` for cycle timing | Non-deterministic; use sequence numbers (F-01) |
| `pgcs.py` (pre-F-08) | Raw page counts as disk I/O | Must multiply by `resource.getpagesize()` |
| `stress_test.py` (pre-F-02) | Hardcoded `afse_r2 = 0.98` | Proved nothing; replaced with live AFSEController |
| `store.ts` (pre-PR #16) | Single-transaction async append | `await` crosses IDB task boundary → TransactionInactiveError |
| `uuid.ts` (pre-PR #16) | `seq & 0xfff` wrap without refresh | Duplicate UUIDs at 4096/ms; fixed with virtual-ms increment |
| `verify-hashes.mjs` (pre-F-06) | Silent SKIP for missing constitutional files | Exit 0 even when absent — constitutional check was no-op |
| `canonicalize.ts` (pre-PR #16) | Surrogate pair via high-surrogate branch | Valid pairs fell through; fixed with `cp > 0xFFFF` check first |
| `fixedpoint.ts` (pre-Ω⁵.7) | `divQ32(sum, BigInt(Number(n)) << 0n)` for mean | Scale error 2^32×; replaced with plain BigInt division |

---

## 10. Unresolved Theoretical Compression Layers

Concepts with no current T0–T2 implementation — latent potential:

| Concept | Source | Tier | Path |
|---------|--------|------|------|
| Optimal transport for LLM calibration | From Divergence to Convergence (T3) | T3→T2 | Could inform VCG window weighting |
| Entropy-bounded policy optimization | Orchestrating Long-Horizon Reasoning (T3) | T3→T2 | Could bound mutation-governance K |
| Token-level drift detection | Verifying Agentic Reasoning (T3) | T3→T1 | hoeffding.ts extension |
| Non-neural algorithmic marketplace | Orchestrating Volatility (T3) | T3→T2 | E5 workflow auction |
| Iris/Coq bisimulation | `formal/theories/Bisimulation/ThreeWay.v` | T0 (stub) | Formally proves store.ts replay safety |
| KMS key shredding | `compliance/tombstone.ts:56` (stub) | T1→T0 | Awaiting production KMS |
| WASM binary compilation | `core/wasm-interface.ts` (kernel unloaded) | T0 (pending) | Q32.32 GPU-accelerated Bernstein |
| gate.py / dna.py / router.py | CLAUDE.md (declared absent) | T0 (blocked) | Requires /guardian APPROVED verdict |

---

## 11. Full Canonical Index

### Research PDFs — T3
| # | Drive ID | Title | Size |
|---|----------|-------|------|
| 1 | `1LJ1KoT195nJDBLGyR9VRzrnVWlFCxgO8` | Preserving Criticality in Holonic AI | 514 KB |
| 2 | `10gBmzNovsKMWkqf2AiXJrAn0Mt197o9P` | Quantum-Inspired Architecture | 511 KB |
| 3 | `1Kntuo_DbjzcJa8-BqPM90q-V5CKLFOah` | Verifying Agentic Reasoning | 508 KB |
| 4 | `1lu31YCW-TW2SVr3IyGeQZBTB1YXbnCG5` | A Holon-Architected Compiler | 506 KB |
| 5 | `1xaKuiktzJWkTmwaoi_wCwunA4Y9HTZrb` | From Local Task to Global Integration | 492 KB |
| 6 | `1uN2Ts3GBaa-YXe_vo7z4zs6e07mT4984` | An Asymmetric Market for Uncertainty | 490 KB |
| 7 | `1OpO3JpYAHSWkyh0aOzRa_6agbfuPJVgl` | Orchestrating Emergent Intelligence | 477 KB |
| 8 | `1LUu4IKCJK0RbcqZkgiwZa-Th7u2dl3vU` | Decomposing the Monolith | 469 KB |
| 9 | `1eL8RkV43ynRi_0KAWewIpOPEDnXD7pMb` | Orchestrating Long-Horizon Reasoning | 455 KB |
| 10 | `1H5xrLV2M_HVdpzoHK5Czgdb5kQmsFdbJ` | From Divergence to Convergence | 443 KB |
| 11 | `1hv9jhS8ROs5selyvvFrhpqzx8s7CE8a5` | Orchestrating Volatility | 419 KB |
| 12 | `1oS83PDBGhdgo3LydaWC05fosXyzJXEmv` | From Heterogeneity to Cohesion | 416 KB |
| 13 | `1ozQ641HrGlOiW2jkMBxg-lBEZChJlYUb` | Resilience by Analogy | 499 KB |

### Spec / Vision / RALPH Docs
| Drive ID | Title | Tier | Size |
|----------|-------|------|------|
| `1cfFY59zAczNPCL7mvr_TxFo1yR7xfDNh` | SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md | T1 | 44 KB |
| `1NScZu_7bc9nLXzSWG8Ul_O98KuHL5360` | SOVEREIGN_OMEGA_IMPL_BRIEF_Qwen.md | T1 | 17 KB |
| `1_gebxxUSk_OO0B575K7j03AX4YRkpvDq` | SOVEREIGN_OMEGA_AGI_FRAMEWORK_CONCLUDED.md | T4 | 13 KB |
| `1umR8RoWZwJQAQuG4uzU-N16HMOmCUK09` | SOVEREIGN_OMEGA_VISION_ASSEMBLED.md | T4 | 12 KB |
| `11MWyKyAfBKHY9TXUZ_iDqilybuAZf_3M` | RALPH_LOOP_OMEGA2_INTEGRATION_AUDIT.md | T2 | 12 KB |
| `1TTzre0Oy1BEZ_g5lm926XJ2UiFtjfJsr` | RALPH_LOOP_OMEGA_EXECUTION_SYNTHESIS.md | T2 | 11 KB |
| `1oWL66eB30_yuaINeNY16P6Fnf1kMDNdd` | QWEN 04 EXECUTION DIRECTIVE.md | T2 | 10 KB |
| `1fpD3CDhEi688iZvMZ_FMXlmEuauNc0-U` | QWEN 03 IMPLEMENTATION STATE.md | T2 | 14 KB |
| `1X-sUZzPB4Aod1TiPA5g6wyXbO9Fr86WG` | QWEN 02 ARCHITECTURE COMPLETE.md | T2 | 14 KB |
| `1Zfz8nJBdaYmav_foifXw81U8h_TMbcuP` | QWEN 01 PROJECT CONTEXT.md | T2 | 7 KB |
| `1N9QujbSEFAUoHnNFB3c3N-O1p5v6xZTr` | Sovereign_Runtime_Unified_Deliverable.docx | T1 | 38 KB |
| `1BtdhG2MeThi0ZSeKjGIa1sZg1XZ1QOHG` | AEGIS_Sovereign_Runtime_Deliverable.docx | T1 | 39 KB |

### Handoff / Protocol Docs
| Drive ID | Title | Tier |
|----------|-------|------|
| `1RwEvyA_nAjh2KYLuemeXseYuUoz5_oRE` | 00_MANIFEST.md | T1 |
| `1CiScoMeBD7p3hjedg0YM8J4YVide3koG` | 05_INVARIANTS.md | T0 |
| `1F6kBOkWOvbHp1_UcvELYca5XYZc5h04c` | 06_TAXONOMY.md | T0 |
| `1_e5serahYTE-PncfotGvYSII3FdEHyJW` | 17_EXPLICITLY_PROHIBITED.md | T0 |
| `15OROnTwfZF2gto9HZ5Kxpo5ceMGs2hz-` | 21_DECISION_LOG.md | T1 |
| `1HqnoRPCvdbBH791ZFg3t7HL_jD7dk9rP` | AGENTS.md | T0 |
| `1gnM-TwrOHLUyon2sdBJpImAcZtV1pxzC` | CLAUDE.md | T0 |
| `1Izrr8mUEXtTJJQ71TI1j6dSst_Uo2mQv` | ARTIFACT_REGISTRY.md | T1 |

### TypeScript Source
| Drive ID | File | Module | Tier |
|----------|------|--------|------|
| `1hPE3DKmRUhCY6Rii0P8LzOxMjiSt2e3u` | canonicalize.ts | core | T0 |
| `1vsXJN5XUe1rRBmh2WSC1mvzCmGcY9RLW` | types.ts | core | T0 |
| `1Kkr3H9W49dXF2hvT6yiOKJ3r3rmKqejT` | immutable.ts | core | T0 |
| `1wex4ikQhfTxX9S53J9F4E2T50wbwY46_` | hashing.ts | core | T0 |
| `1Tv9-z3hhlrDjg9dAOstm0lz7plmpbo4S` | tier.ts | core | T0 |
| `14m2aO5bJS5m4nhWgFSG_YnyBtxiWgkPs` | schema-registry.ts | core | T0 |
| `1914bqWJDm38d50GJgrGkdskK-sHvuGNB` | fixedpoint.ts | core | T0 |
| `135L-o2YyFX0B59KxFd9C_ZBYwp2gGA8Z` | wasm-interface.ts | core | T0 |
| `1pId5tqocB7OC0_mE4GHXOnRlVGUXIE_9` | ordering.ts | core | T0 |
| `1JVe9ZH3qq0bbeoWfg-ws33FkutFgM7Gm` | store.ts | event | T0 |
| `14ex28P76O7dsTtPeGswr_UgD-u4Ku7yj` | uuid.ts | event | T0 |
| `1aa6aSQbTyCbZ94I9tnA7jCeJv8enlV8z` | mutation-registry.ts | event | T0 |
| `1nlonfLoBEX4546W5bsGQqFFfSMXRzBhe` | replay.ts | event | T0 |
| `1Ndxvjz_iDq-mZQDVFgb10KvCwkD8x2zh` | segment.ts | event | T0 |
| `1DnJABPstscDvvDiXDZ6ZQvYnOOEvTox-` | hoeffding.ts | gate | T0 |
| `1JGTafRDKmd25HoLsrhCc2DJqNMRWCJGz` | risk.ts | gate | T0 |
| `1ElP9I8_SbFmiAFlkUwSXCl1CMymWHWsu` | mutation-governance.ts | gate | T0 |
| `1Hs22rvsXvhG1vdsjahdyGjRu2P7jd1pu` | gate/types.ts | gate | T0 |
| `1aMM1s-JrVca8g_rD0LAkWG13eZ3gzeoz` | vcg.ts | calibration | T1 |
| `19_wNYh2yd05pC5xqGbo_mgv_CEWRZn6Q` | rng.ts | calibration | T1 |
| `1YcPP64X1lFRNvfppEi4Q-MNaxWFFSfEY` | calibration/types.ts | calibration | T1 |
| `1Ay7q5PSjQLtGB_ChcmgfD_20kUvzaqK4` | registry.ts | verifier | T1 |
| `1hycYd1amn3Tfe5bdottOLwElcIolTC6y` | independence.ts | verifier | T1 |
| `15j5tnmri5td2AFReMbgQwCo63v0Yt2-i` | execute.ts | verifier | T1 |
| `1aYYJqIRYz4C5DitPnPM_avJSBZGESf3J` | verifier/types.ts | verifier | T1 |
| `1nDuaatO8oRe2QFhh1WsXpSAirAollrgP` | reducer.ts | projection | T1 |
| `1KIm7PYtZxb-zIMQAKJjrHdMn1V8tdCEy` | compiler.ts | projection | T1 |
| `18_TjUvyLwXZzHQSTH-4OZNLKUtKRiTbA` | pipeline/index.ts | pipeline | T1 |
| `1XExDOcHAZvVNrx9rNZ_FBsTnurGC9JVH` | e1.ts | pipeline | T2 |
| `14zHZD8fohpW5J3bJ-P1-1BgBgrtyevva` | schema.ts | pipeline | T1 |
| `1eUg0dPFBNDKMsGEh-pVTGDKSaIAwnEVR` | projection-machine.ts | runtime | T1 |
| `1tg03g9LwC9wDLq8aBaq4HOVgn3SSaJoN` | tombstone.ts | compliance | T1 |
| `1BDZgh9YBL3D4xyYKHKl4B-k04Wa95qip` | divergence.ts | forensics | T1 |
| `1LpuJqGZ4ntp2nmt03mEw9QcEAI-Y0c2N` | gate/migrations/index.ts | migrations | T1 |
| `1UaczxS5Hp7MGpLFh6GqQxOxypdLXylhc` | omega_dynamics/harness.ts | research | T3 |
| `1kVSSc1kmb5-jbqdsJggvAnNrQGL62rfn` | omega_dynamics/types.ts | research | T3 |

### Python Source
| Drive ID | File | Tier | Audit Status |
|----------|------|------|-------------|
| `1dlB-tgjBW6AcyGUA8ggoiUGrHoiHOBbu` | core_matrix.py | T0 | F-03, F-05, F-07, F-09, F-10 resolved |
| `1tAjmYSlfMt2-7X4tpOQPyRcwywWQCWB4` | pgcs.py | T1 | F-08 resolved; H-01 open (stub) |
| `1mmk4fnDURe8R9FODj86XUDyDvdO6ed1M` | gradient_anchor.py | T0 | F-04 resolved |
| `1ndZJVGyRB43wvOA01aYChJFTaTVcoMN8` | epoch_failsafe.py | T0 | F-10 resolved |
| `19Wcrfyb7tmWoM5IgCwgRUylmGcWUb1l1` | tgcs_afse.py | T1 | F-01 resolved |
| `1fPh87XMdrQB1aadSyNbZI9EK9znvncDm` | bridge.py | T1 | F-05 resolved |
| `1BlEgFkEJhd38jpqGfQBpSoglETFnQi2x` | hardware_config.py | T1 | Active |
| `1Bam8lTVK5_HTYF9bzLC0ytagovqHAqYn` | identity.py (saga) | T2 | SPIFFE stub |
| `1BA5a42L4QdBDgj1EhYbLZdOfRvg6De-0` | stress_test.py | T1 | F-02 resolved |

### Formal Proofs
| Drive ID | File | Role |
|----------|------|------|
| `1sKpfon3T6ccBrRQ5nFNH-Ohym9N3o5kT` | Hash.v | Coq: SHA-256 chain |
| `1SUUi6YaTgM8v2nSkc1sYFrblfKi9aTQJ` | Reducer.v | Coq: pure reducer |
| `1ovvLqDP6Kv8iZz4Ovjse0rgdvjAeJ7Lj` | Event.v | Coq: append invariant |
| `1ZTZS8DcP5Vp1Yg_G5Lph-Vi5irepYRUU` | ThreeWay.v | Coq: bisimulation (stub) |
| `1R8ItAXt7zDXwJ28DaWWNdulqq0L9hRYK` | Omega.tla | TLA+: version pin |
| `1jomiD_IqnddsD0dsnjYgp5boKbLUXsn2` | Omega.cfg | TLA+ model config |

### Tests
| Drive ID | File | Gate |
|----------|------|------|
| `1i4xzyhQ1Ta9dQMBXlzUujP4USNlOEyej` | jcs.test.ts | Gate 1 |
| `1ePUAXo5I1ZrH7Shc78eHhXdcpSx5sl6a` | sequence.test.ts | Gate 2 |
| `1OteyjleIM8MS3dhLGvu5wt50UQaALTUJ` | immutable.test.ts | Gate 3 |
| `1aRf5o7wimNnPozQjq6fJSryWJvB5pqlI` | reducer.test.ts | Gate 4 |
| `10fNfuxHB79dcqobrT7nIsCvReh-rHO21` | vcg.test.ts | Gate 5 |
| `1qyNK5d_-oe1LhS-GJdD6otaOLIXG2wrr` | gate.test.ts (integration) | Gate 6 |
| `1OSgMJEAhZXCM2us_E9EyXBGh2mAOwgNe` | gate.test.ts (unit) | Gate 6 |
| `1Ac9sIhW_45A2tx2Sw2iOD4g_49C-TSag` | replay.test.ts | Gate 7 |
| `1RjDUC7bCT2Y53tHfKaN0LxbiJjv3s1a_` | pipeline.test.ts | Gate 7 |
| `1nlWQ6GBexiIknThLtqc0i-VbAfkfApXI` | merkle.test.ts | determinism |
| `1Z6xfgxKHH5gyQfxRK95YzcedsR55N2N5` | cross-engine.test.ts | determinism |
| `1uPDn0rAeuTRrHpV9wx_SCavnb1WoFkiI` | reducer-impurity.test.ts | Gate 4 (adversarial) |

### Configuration & Build
| Drive ID | File | Purpose |
|----------|------|---------|
| `1ctS_FBitxgCj6Gq3j1taTArkC-c18ecl` | agent.config.yaml | Qwen/Claude agent orchestration |
| `1E6hcv-ZN4tSMx5sTSdK15fb4I8qe0w-Z` | company.yaml | Paperclip company config |
| `1sQUtuhGpL0TsvT7GhqR1WpdtXeP1fbME` | .env.example | Environment variable template |
| `1ZifZapDuoPO_okSXk0rObW5F4x-tH39X` | package.json | Node.js project manifest |
| `1tZpjrUvPnKjJlz6EBpqN3EzZBM4fs9Qi` | tsconfig.json | TypeScript strict config |
| `1jAoSzqnX6CyIXuE3t52jpAMdIHWufQwf` | tsconfig.node.json | Node TypeScript config |
| `1-DU0TlsswHZpnaIgTANdh_fNObXKJwK2` | vite.config.ts | Vite build config |
| `13dBcIkdZ85f4bI43RuBQj3kjMlSxLFru` | .mcp.json | MCP server configuration |
| `1YhRWaPwXURMsO4IEteoLmIcW-VK9_p2_` | .gitignore | Git ignore rules |
| `1KdbQTbx4tTxaj7aJB7lua-9Ci0ldYTr8` | ci.yml | GitHub Actions CI |
| `1jFopiD7hZk9RufB9dFVatHXgHhsiaaRJ` | requirements.txt | Python deps |
| `1GUMtQ2-U2j4bDT3iIgbSs97hrMfP-kAx` | Dockerfile.repro | Reproducibility container |
| `16Be1AWO5ItmfmQJE3QNHTbddDDBLxC7u` | settings.json | Claude Code settings |
| `1V2ZELZDpufetL0OqwcV6Ygxh9Lx0zEZt` | transform-manifest.json | Transform manifest |
| `1vnLHzenHOA55vGKpX1fGq_2e7zSX-g1U` | setup.sh | Setup script |

### Scripts & Rules
| Drive ID | File | Purpose |
|----------|------|---------|
| `1UfiPDjUawVlHqXZbuVWvqcpLvxL9oxWR` | verify-hashes.mjs | Constitutional file verification (F-06) |
| `19KsLyMjsNu4CMoomXNz4U5bVpZvMj59s` | hash-transforms.mjs | Hash transform utilities |
| `1GIDx3WcDzEHg0OtR0uduXwqvqf6ilWLS` | verify-canonicalization.ts | JCS verification tool |
| `1s208Od1WuzX-irtoh9qlhHl0WdtqURS9` | guardian.md | Guardian agent spec |
| `136I80y_8WuVeqLPeR2W2wpdTMZlT0yhj` | implementer.md | Implementer agent spec |
| `1TMH1yiWifbIRew1lY0LBgClGna2WHgnJ` | verifier.md | Verifier agent spec |
| `14yVdfU5UNEMWOrAEdZ8ApctAxqLTbXjX` | core-invariants.md | Core invariant rules |
| `1gr8YvGM98p2ZxeyLizL8b0fdfLAYLtVK` | typescript.md | TypeScript rules |
| `1MMPVxYHr1mYniSmEkla8GEu9YfM6-zzy` | gate-protocol.md | Gate protocol rules |
| `1iyIqKVgPfOl7FPOr4ETroH8sqCsXVyHn` | testing.md | Testing rules |
| `1AMoJ_HT4_N1CLKioLWNJfibMS6ANqV17` | build-report.md | Build report command |
| `13q4WuH8Emec5eREOo_IcFrKtLdEANl5p` | run-gates.md | Gate execution command |
| `1vJZyYHn3NbdjdTpBsuHkZEDuKhkgaTcz` | verify-frozen.md | Frozen file verification command |
| `19Ae8j8rBW7cW6LB6X8nUo53N1zMwZhjc` | tier-check.sh | Tier enforcement hook |
| `1dYTQPtaMKJE6s5a7OO1xI9j9UR57V1EF` | block-frozen-writes.sh | Pre-commit frozen file protection |

### Duplicate Copies (informational — do not use for implementation)
The following folders are exact copies of canonical files uploaded for multi-model context delivery:

| Folder | Contents | Session |
|--------|----------|---------|
| `1YidpasL0A7qGhlKCyGjqqpnk6yFEmhNb` | INTEGRATED_SPEC, IMPL_BRIEF, AGI_FRAMEWORK, VISION_ASSEMBLED | Qwen A |
| `1iGNPcjZdiyP6VhztE_Is6Js2M29Sw82b` | Same spec docs | Qwen B |
| `1jYTg53itN3svflR61pG_q8mPrRBVbEOc` | Same spec docs | Qwen C |
| `1M7UE5FdDT9wiB7fCl85pMcXHAwuPD_Pt` | core_matrix.py, pgcs.py, gradient_anchor.py, epoch_failsafe.py | Qwen A |
| `1bG9SV5gOy569C4FPUqFLckYCGAf7klSZ` | Same Python files | Qwen B |
| `1y1gl-3PTO9RbKXEHiy3k7LH_cAnDKBD3` | Same Python files | Qwen C |

---

## In-Repo Corpus Ingestion — Batch 2026-06-25 (RALPH ARBITRATION)

Source: docs already committed to the repo (not Drive), run through the 5-phase RALPH
pipeline per the `corpus-ingestion` skill. ARBITRATION results below. Admitted docs are
candidates for skill extraction — NOT auto-minted; minting is operator-gated to avoid
skill-file sprawl. Quarantined framing routed to `sovereign-omega-v2/docs/FUTURE_PHASES.md`.

| Doc (local path) | Tier | admitted | Notes |
|---|---|---|---|
| `docs/TEMPORAL_SEAM.md` | T2 | true | Seam map: Replay→Temporal, DFA→LangGraph, ledger→PostgreSQL append-only, K8s/EKS, edge WASM. Constraints: replays byte-identical; Redis is observational-only (D0), never authoritative. No T4/T5 framing. |
| `sovereign-omega-v2/docs/FORMAL_VERIFICATION_WASM.md` | T2 / T3 | true | Coq/Iris WASM compacting-allocator schema (Gate 188). T2 = TS impl (bounded generation, exclusive slot map, atomic relocation); T3 = two `Admitted.` lemmas, explicitly NOT grounding T0/T1; Iris library laws cited as T0. |
| `sovereign-omega-v2/docs/SHP_EXECUTION_MODEL.md` | T0 | true | R→A→L→P→H single deterministic loop; LOCK = commitment boundary; SITR (pre-commit) ∩ AOIE (post-commit) = ∅. 8 formal invariants, FNV-1a `commitHash`, no `Date.now()`. Gate 14/15. |
| `docs/PHI_HOLOGRAPHIC_COMPUTE.md` | T2 claim + T3/T4 framing | partial | ADMIT the engineering: branchless WGSL Fibonacci + inline det(Mⁿ)=±1 integrity check; Gates 604/605 at 61%≈φ. QUARANTINE the E₈ / "quantum critical point" / Ising correspondence — T3/T4 framing that must not ground the T2 claim. See FUTURE_PHASES. |

**Skill-extraction candidates (operator-gated):** `temporal-seam`, `formal-verification-wasm`,
`shp-execution-model`. The φ-holographic doc's admitted T2 core fits the existing WebGPU /
`int4-lut-kan` skill family rather than a new file.

**Batch 2 (pending — not yet ARBITRATED):** `AOIE_SPEC.md`, `WORKSPACE_MEMORY_MODEL.md`,
`IDE_RUNTIME_SPEC.md`, `SITR_CONSTITUTION.md`, `HOST_ADAPTATION_SPEC.md`,
`CAPABILITY_GOVERNANCE.md`, `ONTOLOGY.md`, `MYTHOS_COGNITIVE_SUBSTRATE.md` (likely T5 quarantine).

---

*Lattice crystallized 2026-05-18 · Drive corpus: 222+ entries, 5 pages enumerated*
*All T4/T5 → T0–T2 grounding violations flagged · Constitutional files F-06 still pending /guardian*
*Next subagent: begin here, not at CLAUDE.md*
