# SOVEREIGN OMEGA — Artifact Registry v2.0

## Tags: [FROZEN] = no modifications without /guardian APPROVED
##        [ACTIVE] = current working version
##        [EXPERIMENTAL] = under development

---

## FROZEN — Constitutional Layer

| File | SHA256 | Status |
|---|---|---|
| `gate.py` | `72196f38974ad22130c18657c88106316cacbb13a57328990f4e5872f5fdb1e9` | FROZEN |
| `dna.py` | `9c4d38d80b236d655057f16304ea2d202f644ec0c7ca21db8df0bdcd503971a9` | FROZEN |
| `router.py` | `c96e566ce6eb9cec358b2112757142bc88ea4fea9160edb2914c8d711007ac769` | FROZEN |
| `docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md` | Architecture FROZEN (ChatGPT 0.99) | FROZEN |

**Verification:**
```bash
sha256sum gate.py dna.py router.py
```

---

## ACTIVE — TypeScript Runtime Package

| File | Description |
|---|---|
| `CLAUDE.md` | Primary project memory for Claude Code |
| `src/core/types.ts` | All base types, branded types, enums |
| `src/core/canonicalize.ts` | RFC 8785 JCS implementation |
| `src/core/hashing.ts` | SHA-256, Merkle, UTF-8 encoding |
| `src/core/immutable.ts` | deepFreeze, withImmutableBoundary |
| `src/event/store.ts` | EventStore + IndexedDB sequence allocator |
| `src/event/uuid.ts` | UUIDv7 generation |
| `src/event/replay.ts` | Deterministic projection replay |
| `src/event/segment.ts` | Merkle segment construction |
| `src/verifier/types.ts` | Verifier interface contracts |
| `src/verifier/registry.ts` | VerifierRegistry + MutationOperatorRegistry + CapacityDeclarationRegistry |
| `src/verifier/execute.ts` | Verifier execution with isolation |
| `src/calibration/rng.ts` | Seeded PRNG (xoshiro128**) |
| `src/calibration/vcg.ts` | VCG tracker + bootstrap CI |
| `src/gate/hoeffding.ts` | Bernstein anytime-valid confidence sequences |
| `src/gate/risk.ts` | Risk budget + harmonic spending |
| `src/projection/reducer.ts` | ProjectionState + pure reducers |
| `src/pipeline/e1.ts` | Ambiguity routing interface |
| `src/pipeline/schema.ts` | DecisionSchema construction |
| `src/pipeline/index.ts` | Main pipeline orchestration |
| `src/compliance/tombstone.ts` | GDPR tombstoning + Article 12 audit |
| `src/registry/types.ts` | Semantic particle types: HolonicScale, MutationAuthority, ProofCoverage, SemanticNode |
| `src/registry/entries.ts` | T0/T1 artifact registry entries — 18 classified nodes |
| `src/registry/index.ts` | Registry access: lookupNode, queryByGate, queryByTier, queryByMutationAuthority |
| `src/event/workflow.ts` | E5 cognitive workflow event payloads — AI-mediated development substrate |

---

## EPISTEMIC TIER TAXONOMY

| Tier | Standard | Domain Ceiling |
|---|---|---|
| T0 | Mechanically proven / deterministic | Core runtime code |
| T1 | Empirically validated | Calibration research |
| T2 | Engineering hypothesis | E1 ambiguity heuristics |
| T3 | Research conjecture | Quasicrystal-CDT correspondence |
| T4 | Speculative systems vision | Swarm, AEGIS civilisational |
| T5 | Creative / worldbuilding | Cycle series documents |

**Migration rule:** No T4/T5 construct may ground a T0–T2 claim without explicit evidence review.

---

## HANDOFF LOG

| ID | Date | From → To | Task | Status |
|---|---|---|---|---|
| SO-2026-05-13-ARCH-001 | May 13 | Claude → ChatGPT | Council architecture review | APPROVED 0.97 |
| SO-2026-05-13-IMPL-001 | May 13 | Claude → Qwen | gate.py + dna.py | Delivered |
| SO-2026-05-13-IMPL-002 | May 13 | Qwen → Claude | Master handoff synthesis | Delivered |
| SO-2026-05-16-SPEC-001 | May 16 | Full alliance | Spec v2.0 + verification sweep | FROZEN 0.99 |
| SO-2026-05-16-IMPL-004 | May 16 | Claude → Qwen | Full TypeScript runtime package | This package |

---

## BUILD ORDER (STRICT)

1. `canonicalizeJCS` + RFC 8785 test vectors → Gate 1
2. `EventStore` + `IndexedDBSequenceAllocator` → Gate 2
3. `deepFreeze` + `withImmutableBoundary` → Gate 3
4. `ProjectionState` + pure reducers → Gate 4
5. `VCGTracker` + seeded bootstrap → Gate 5 (vcg.test.ts)
6. `ConfidenceSequence` + `BoundedDelta` + risk budget → Gate 6
7. `runDecisionPipeline` integration → Gate 7
8. Cross-engine determinism harness → Gate 8 (DEPLOYMENT GATE)

**Failure at any gate = HALT.**
