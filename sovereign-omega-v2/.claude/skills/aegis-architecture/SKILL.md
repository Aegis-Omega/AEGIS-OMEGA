---
name: aegis-architecture
description: Invoked when the user asks about AEGIS system layout, product stack, holonic scale hierarchy, how layers connect, shared infrastructure, TypeScript or Rust seams, or the overall monorepo structure.
---

# AEGIS-Ω Architecture Skill

## Holonic Scale Hierarchy

```
FIELD      → commercial products + studio + cockpit (user-facing interfaces)
ORGANISM   → Python bridge (port 7890) — routes TypeScript ↔ hardware inference
CELLULAR   → TypeScript governance runtime (sovereign-omega-v2/src/)
MOLECULAR  → Rust gossip + math fabric (aegis-cl-psi/src/)
ATOMIC     → Seven-Pillar runtime (aegis-runtime/src/)
SUBATOMIC  → Byte invariants (canonicalization, SHA-256, IEE 754 bit patterns)
```

A T0 violation at any scale propagates upward and invalidates everything above it.

## Repository Layout

| Directory | Scale | Language | Purpose |
|-----------|-------|----------|---------|
| `sovereign-omega-v2/` | CELLULAR | TypeScript | Governance runtime — 8 gates, hash-chained event ledger, BFT swarm |
| `aegis-cl-psi/` | MOLECULAR | Rust | 385 gate modules — gossip layer, math substrate, EU AI Act audit chain |
| `aegis-runtime/` | ATOMIC | Rust | Seven-Pillar distributed agent runtime |
| `cockpit/` | FIELD | React/TS | AI chat UI with constitutional telemetry |
| `studio/` | FIELD | React/TS | 10-surface read-only observability dashboard |
| `platform-picker/` | FIELD | React/TS | Creator tool, Qwen-powered, $19 |
| `hook-generator/` | FIELD | React/TS | Creator tool, Qwen-powered, $19 |
| `content-calendar/` | FIELD | React/TS | Creator tool, Qwen-powered, $19 |
| `hub/` | FIELD | React/TS | Products landing page |
| `packages/shared/` | FIELD | TS | Shared infra: DashScope, useAsyncForm, components |
| `sovereign-omega-v2/python/` | ORGANISM | Python | HTTP bridge + PGCS/TGCS/AFSE analytics |

## Key TypeScript Seams (sovereign-omega-v2/src/)

| Seam | File | Purpose |
|------|------|---------|
| Canonical hashing | `src/core/canonicalize.ts` | RFC 8785 → SHA-256; the only permitted hash path |
| Martingale gate | `src/constitutional/martingale.ts` | `certifyMartingale()` + `assertMartingaleAnchored()` |
| BFT consensus | `src/consensus/swarm.ts` | `tallyVotes()` → `SwarmConvergenceRecord` at 1/φ |
| Ontology admission | `src/constitutional/reduction.ts` | `admitAbstraction()` — blocks T4/T5 |
| Adaptive lineage | `src/frame/adaptive-lineage.ts` | Hash-chained capability evolution events |
| Skill catalog | `src/skill-harness/catalog.ts` | Probabilistic competency objects |
| RALPH executor | `src/agents/executor/loop.ts` | Fibonacci-paced R→A→L→P→H loops |

## Key Rust Seams (aegis-cl-psi/src/)

Every public struct has `verify_chain() → (bool, Option<usize>)`. Every record chain starts from `*_GENESIS_HASH = [0u8; 32]`. Hash inputs always use `to_be_bytes()` — never `to_le_bytes()`. `f64` values hashed as `value.to_bits().to_be_bytes()`.

## Seven-Pillar Runtime (aegis-runtime/src/)

| Pillar | Role |
|--------|------|
| StateAnchor | SHA-256 hash-chained append-only ledger |
| DomainFirewall | Domain 0 (immutable) / Domain 1 (mutable) |
| AffineCanvas | Integer affine transforms (no f64) |
| SemanticGraph | BTreeMap DAG, depth-bounded BFS, 5 relation types |
| ValidationDFA | 6-state byte-stream automaton, 36-entry table |
| GossipEmitter | 64-byte UDP frames, AEGIS_PROTOCOL_MAGIC=0xE0E0 |
| HysteresisFilter | Exponential penalty/recovery, quarantine gate |

## Communication Model

- FIELD → ORGANISM: HTTP GET `/telemetry`, POST `/event` (5s poll)
- CELLULAR → ORGANISM: HTTP on port 7890 for governed Claude calls
- MOLECULAR: standalone Rust — invoked by bridge subprocess, not called at runtime
- Agents communicate ONLY through `EventEnvelope` — Law of Silence enforced

## Source: `docs/architecture.md`
