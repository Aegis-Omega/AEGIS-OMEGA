---
name: substrate-ecology
description: Invoked when the user asks about substrate evolution, ecological evolution model, holonic governance, GCCE architecture, the Khatt Loop Protocol, or how the system adapts at scale over time.
---

# Substrate & Ecology Skill

## Substrate Evolution Principle

The substrate evolves through constitutional phase transitions — not arbitrary upgrades. Each evolution must:
1. Preserve all existing invariants (no T0 violation)
2. Pass through governance gate validation
3. Be replay-reconstructable from genesis

Archive format version `ARCHIVE_V1_0_0` (6-byte wire header) governs serialization across evolution phases.

## Ecological Evolution Model

AEGIS-Ω operates as a **bounded ecology** — adaptive and recursive, but never sovereign:

```
Ecology bounded: adaptive / recursive / bounded / replay-governed — NOT sovereign AI
```

**Ecological constraints:**
- `AdaptivePower(T) ≤ ReplayVerifiability(T)` — always
- Adaptive events consume entropy budget; budget is finite per epoch
- Specialization emerges from repeated execution clusters — it is never assigned
- Ecology cannot self-expand beyond declared K-bound

## Holonic Governance at Scale

Each scale monitors and preserves the invariants of all scales below it:

```
FIELD       (commercial) — reads telemetry, writes through EventEnvelope only
ORGANISM    (Python bridge) — routes between governance and hardware inference
CELLULAR    (TypeScript) — hash-chained event ledger, BFT, martingale gating
MOLECULAR   (Rust gossip) — deterministic state-coherence routing, EU AI Act chain
ATOMIC      (Seven-Pillar) — StateAnchor, DomainFirewall, ValidationDFA
SUBATOMIC   (byte invariants) — RFC 8785, SHA-256, IEEE 754 bit patterns
```

A violation at SUBATOMIC invalidates ATOMIC, MOLECULAR, CELLULAR, ORGANISM, FIELD — in that order. No exception.

## GCCE Architecture (Gate 202)

The Geometric Calligraphic Cognition Engine models cognition as N-dimensional manifold traversal:

**Khatt Loop Protocol phases:**
1. Nuqta (dot) — identify the causal point
2. Alif (stroke) — establish the vertical invariant axis
3. Rasm (skeleton) — trace the causal flow path
4. Tashkeel (diacritics) — annotate epistemic uncertainty gradients
5. Tanasub (proportion) — apply dimensional scaling ratio

Output: geometric projection integrating causal flow, vertical constraints, and uncertainty gradients.

## EU AI Act Compliance (Article 12)

The audit chain in `aegis-cl-psi` captures events for Article 12 audit export. The gossip layer produces tamper-evident hash chains that satisfy traceability requirements for high-risk AI systems. Export endpoint pending (see Known Limitations in README).

## Ecological Prohibited Modes

| Prohibited Mode | Why |
|----------------|-----|
| Hidden memory | Violates replay sovereignty |
| Unrestricted recursion | Unbounded entropy consumption |
| Autonomous mutation authority | Violates AdaptivePower ≤ ReplayVerifiability |
| Unbounded ecology | Violates K-bound |
| Centralized sovereign intelligence | Violates Law of Silence + distributed governance |

## Source: `docs/SUBSTRATE_EVOLUTION.md`, `docs/ECOLOGICAL_EVOLUTION_MODEL.md`, `docs/GCCE_ARCHITECTURE.md`
