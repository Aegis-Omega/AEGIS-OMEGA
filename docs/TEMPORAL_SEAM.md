# AEGIS — Temporal / LangGraph / Infrastructure Seam Declaration
## Epistemic Tier: T2 (engineering hypothesis — seam defined, not yet implemented)
## Status: SEAMS DECLARED · Implementation Phase 2+

This document is a constitutional seam declaration, not an implementation guide.
It records where existing AEGIS primitives map to production infrastructure components.
No code is changed by this document. Seams become implementations when Phase 2 begins.

---

## 1. Replay Engine → Temporal Durable Execution

| AEGIS Primitive | Temporal Equivalent | Seam Location |
|-----------------|---------------------|--------------|
| `/replay-engine` — authoritative truth | Temporal `Workflow` — durable, replayable | `src/frame/epoch.ts` → Temporal Activity |
| `/event-log` — append-only event substrate | Temporal `EventHistory` — persistent, exactly-once | `src/ledger/chain.ts` → Temporal Workflow state |
| `executeLoop()` in `RalphExecutor` | Temporal `Activity` with retry policy | `src/agents/executor/loop.ts` |
| `certifyMartingale()` | Temporal `Signal` handler — suspension signal | `src/constitutional/martingale.ts` |
| `AdaptiveLineage.append()` | Temporal `SideEffect` — deterministic-stamped | `src/frame/adaptive-lineage.ts` |
| Fibonacci pacing (FIBONACCI_CAP=89) | Temporal `sleep(fibonacci_interval * base_ms)` | `src/agents/scheduler/fibonacci.ts` |

**Constitutional constraint**: Temporal workflow replays must produce byte-identical hashes.
`hashValue()` determinism is the invariant that makes this possible. No wall-clock in hashes.

---

## 2. DFA Engine → LangGraph Stateful Reasoning

| AEGIS Primitive | LangGraph Equivalent | Seam Location |
|-----------------|---------------------|--------------|
| `/dfa-engine` — phase-locked deterministic execution | LangGraph `StateGraph` with typed state | `src/frame/dfa.ts` |
| `SHPPhase` (READ→ASSESS→LOCK→PROPAGATE→HARMONIZE) | LangGraph `node` per phase | `src/frame/dfa.ts` phases |
| `GovernanceTopology` | LangGraph `GraphState` — typed immutable snapshot | `src/frame/topology.ts` |
| `DivergenceSurface` | LangGraph conditional edge — D2+ freezes graph | `src/frame/divergence.ts` |
| `MirrorStream` observation | LangGraph `interrupt` / `human-in-the-loop` point | `src/frame/mirror.ts` |
| `CapabilityProposal → EvolutionResult` | LangGraph edge weight with constitutional gate | `src/capsule/evolution.ts` |

**Constitutional constraint**: LangGraph state must be serializable as `canonicalizeJCS(state)`.
No `Set`/`Map` in graph state — arrays only. No `Date.now()` in graph nodes.

---

## 3. PostgreSQL Persistence Seam

| AEGIS Primitive | PostgreSQL Mapping | Seam Location |
|-----------------|-------------------|--------------|
| `LedgerChain` — append-only hash chain | `ledger_entries` table (append-only, no UPDATE) | `src/ledger/persistence.ts` |
| `SHA256Hex` — content-addressed records | `BYTEA` or `CHAR(64)` columns | All `_hash` fields |
| `SequenceNumber` (BigInt) | `BIGINT` — monotone counter, NOT `SERIAL` | `src/core/types.ts` |
| `EpochChain` — certified checkpoints | `epochs` table — one row per certified epoch | `src/frame/epoch-chain.ts` |
| `AdaptiveLineage` — evolution trail | `adaptive_lineage_entries` table | `src/frame/adaptive-lineage.ts` |
| `MartingaleCertificate` — suspension proof | `martingale_certificates` table | `src/constitutional/martingale.ts` |

**PostgreSQL invariants:**
- All tables are append-only — no `UPDATE` or `DELETE` on governance records
- `sequence` columns use application-assigned values (NOT `SERIAL`) to preserve replay determinism
- `hash` columns are `CHAR(64)` (hex), indexed for `JOIN` on hash chains
- Foreign keys: `previous_hash` references prior row's hash (not SERIAL ID)

---

## 4. Kubernetes / AWS EKS Production Topology

| Component | K8s/EKS Mapping |
|-----------|----------------|
| sovereign-omega-v2 governance runtime | `Deployment` — 2 replicas min, HPA on CPU |
| Python bridge (`python/bridge.py`) | `Sidecar` container in governance pod |
| WASM kernel (compiled) | `ConfigMap` — mounted as binary artifact |
| Temporal server | Managed Temporal Cloud or self-hosted `StatefulSet` |
| LangGraph reasoning nodes | `Job` or `Deployment` per agent type |
| PostgreSQL | AWS RDS PostgreSQL 16, Multi-AZ, encrypted at rest |
| Redis (session/cache) | AWS ElastiCache — observational layer only, NOT authoritative |

**Constitutional constraint**: Redis MUST NOT be used as a governance source of truth.
All authoritative state derives from PostgreSQL ledger + replay. Redis is `D0 observational`.

---

## 5. Edge Execution (Jetson Orin Nano / WASM)

| Component | Edge Mapping |
|-----------|-------------|
| WASM kernel (`kernel.wasm`) | Runs on Cloudflare Workers / Jetson WASM runtime |
| `hashValue()` | CPU-bound, no GPU — pure WASM SHA-256 |
| `canonicalizeJCS()` | WASM-equivalent proven in Gate 27 (replay-equivalence) |
| Fibonacci scheduler | Pure arithmetic — WASM-safe, no I/O |
| Martingale certifier | Pure computation — WASM-safe |

**Proven**: `H_TS(f_n) = H_WASM(f_n)` for all governance frames (Gate 27 replay-equivalence proof).
WASM nodes can independently verify any `LedgerChain` without a TypeScript runtime.

---

## 6. Phase 2 Implementation Prerequisites

Before any seam becomes live infrastructure, these prerequisites must pass:

1. **Gate 8** on sovereign-omega-v2 — all tests pass (currently: 1964 tests ✓)
2. **WASM equivalence** — Gate 27 proof must cover all new modules (Fibonacci, RALPH, Skill)
3. **PostgreSQL schema migration** — append-only DDL reviewed by operator
4. **Temporal workflow replay test** — Temporal replays must produce identical `epoch_hash` values
5. **LangGraph state serialization test** — `canonicalizeJCS(graph_state)` determinism verified ×3
6. **K8s YAML review** — resource limits, liveness probes, PodDisruptionBudget approved

---

## 7. Law of Silence in Infrastructure

Regardless of infrastructure layer, the Law of Silence holds:

```
No agent communicates with another agent directly.
All inter-agent communication is mediated through EventEnvelope.
Infrastructure (Temporal signals, LangGraph edges, K8s events) must
route through the constitutional EventEnvelope boundary.
```

Implementation: EventEnvelope is the Temporal `Signal` payload. LangGraph edges carry
`EventEnvelope` objects, not raw text. K8s events trigger EventEnvelope ingestion at
`/event` bridge endpoint only.

---

*Seam declaration version: 1.0.0 · Gate 140 · T2 engineering hypothesis*
*Implementation: Phase 2+ (requires federation layer, Gate 145)*
