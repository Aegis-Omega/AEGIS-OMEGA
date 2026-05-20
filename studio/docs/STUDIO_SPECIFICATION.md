# AEGIS Studio — Production Runtime Specification
## Operator Surface Specification · Projection-Purged Edition
## Status: PRODUCTION CONSTITUTIONAL RECORD
## Date: 2026-05-20

```
PROJECTION PURITY ENFORCED       — Studio is read-only, no mutation authority
REPLAY-DERIVED STATE ACTIVE      — all state derives from replay-certified runtime lineage
LINEAGE VISUALIZATION READY      — lazy lineage expansion, epoch collapsing
EPOCH CHAIN SUPPORT ACTIVE       — O(log n) epoch traversal
DIVERGENCE SURFACES DEFINED      — D0–D4 classification, D2+ freezes mutation
CAPSULE OBSERVABILITY ACTIVE     — manifest inspection, entropy budgets
RUNTIME AUTHORITY REMOVED        — Studio cannot mutate runtime directly
CONSTITUTIONAL STRATIFICATION PRESERVED
```

---

## 1. Constitutional Position

```
STRATUM:          III — Projection Layer
Authority:        NONE
Mutation Rights:  NONE
Runtime Role:     Replay-derived operator projection
```

**Fundamental invariant:**
```
StudioState(T) = Projection(ReplayState(T))
```

Studio possesses: no sovereign memory · no hidden state · no mutation authority · no replay bypass capability.

Studio is NOT: orchestration authority · runtime truth · workflow engine · autonomous control layer · mutable governance surface.

Studio IS: replay-derived observability · bounded execution control · constitutional inspection surface · lineage visualization layer · replay-certified operator interface.

---

## 2. Core Runtime Contract

All operator interaction reduces into:

```
OperatorAction
  → EventEnvelope
  → ReplayValidation
  → ConstitutionalCommit
  → ProjectionRefresh
```

Studio never mutates runtime directly. All changes enter through event emission → replay certification → governance validation.

---

## 3. Runtime Surfaces

### 3.1 Replay Graph (Priority 1 — Primary Surface)

**Purpose:** Causal reconstruction, replay traversal, lineage inspection, rollback visualization.

**Capabilities:** event ancestry tracing · topology transition inspection · replay diff visualization · divergence overlays · ownership overlays · capsule execution overlays · epoch transition rendering · lineage traversal · checkpoint visualization

**Requirements:**
- deterministic rendering (byte-identical across renders)
- replay-derived only (no authoritative client state)
- topology-certifiable (hash-verified)
- immutable historical rendering

**Source inputs:** replay-engine · topology-lineage · adaptive-lineage · epoch-chain

### 3.2 Runtime State Surface

**Purpose:** Current certified topology inspection.

**Displays:** topology hash · replay root · epoch state · determinism class · serializer version · governance state · divergence status · entropy budget state

No mutable operator state permitted.

### 3.3 Ownership Surface

**Purpose:** Capability lineage inspection.

**Displays:** capability graph · delegation chain · lease state · revocation ordering · ownership lineage · mutation authority map

**Invariant:** all authority must reconstruct from replay lineage.

### 3.4 Capsule Surface

**Purpose:** Bounded execution observability.

**Displays:** capsule manifests · determinism class · entropy budgets · replay scope · capability scope · rollback status · execution lineage · sandbox state

No direct capsule mutation permitted.

### 3.5 Divergence Surface (Priority 3)

**Purpose:** Replay inconsistency inspection.

**Displays:** divergence class · topology mismatches · serializer mismatches · ownership inconsistencies · runtime fingerprint drift · replay certification failures

| Class | Meaning |
|-------|---------|
| D0 | observational drift |
| D1 | serializer mismatch |
| D2 | topology mismatch |
| D3 | ownership inconsistency |
| D4 | constitutional invalidity |

**Invariant:** D2+ divergence freezes mutation authority.

### 3.6 Replay Diff Surface

**Purpose:** Certified state comparison.

**Displays:** topology delta · lineage delta · capability delta · replay delta · entropy delta · serializer delta

**Comparison types:** event · epoch · chain · topology · rollback

### 3.7 Rollback Surface (Priority 4)

**Purpose:** Checkpoint restoration control.

**Rollback execution path:**
```
RollbackRequest
  → ReplayVerification
  → TopologyCertification
  → GovernanceValidation
  → EpochCommit
```

**Capabilities:** rollback preview · topology verification · lineage verification · replay validation · divergence quarantine preview

### 3.8 Observability Surface

**Purpose:** Replay-centric operational metrics.

**Metrics:** replay throughput · verifier throughput · chain depth · lineage growth · epoch sealing latency · divergence frequency · topology certification latency · replay reconstruction cost · checkpoint density

**Critical distinction:** Logs are non-authoritative. Replay lineage is authoritative.

---

## 4. Studio Architecture

```
studio/
├── src/
│   ├── replay-surface/           Priority 1 — replay graph renderer
│   ├── epoch-surface/            Priority 2 — epoch-chain visualization
│   ├── divergence-surface/       Priority 3 — divergence overlays (D0–D4)
│   ├── rollback-surface/         Priority 4 — rollback certification UI
│   ├── lineage-surface/          Priority 5 — lineage scaling + compaction
│   ├── topology-surface/         topology state inspection
│   ├── ownership-surface/        capability graph, delegation chain
│   ├── capsule-surface/          capsule manifests, entropy budgets
│   ├── observability-surface/    replay throughput, certifier latency
│   └── governance-surface/       GuardianPolicy inspection
├── docs/
│   └── STUDIO_SPECIFICATION.md   (this file)
└── vercel.json                   Deploy as separate Vercel project
```

All surfaces are projection-only. No surface possesses constitutional authority.

---

## 5. Projection Purity Law

```
ProjectionLayer ∩ ConstitutionalAuthority = ∅
```

**Forbidden patterns (all prohibited without exception):**
- client-authoritative state
- local governance caches
- hidden mutation surfaces
- direct runtime writes
- projection-derived legality
- replay bypass controls

---

## 6. Replay Rendering Contract

All Studio rendering reconstructs from:

```
event-log → replay-engine → topology → lineage → epoch → epoch-chain
```

Rendering is replay-derived only. No client-side cached authority.

---

## 7. Runtime Communication Model

Studio communicates exclusively through `EventEnvelope`.

**Envelope requirements (all five mandatory):**
1. replay-certifiable
2. serializer-stable (RFC 8785 JCS)
3. capability-scoped
4. lineage-addressable
5. deterministic-classified

No direct runtime IPC authority permitted.

---

## 8. Determinism Classification

Studio must expose determinism class explicitly on all replay surfaces.

| Class | Meaning |
|-------|---------|
| `strict` | byte-identical replay |
| `bounded` | certified bounded variance |
| `observational` | replay-visible only |

False determinism claims prohibited.

---

## 9. Replay Graph Scaling

**Mandatory scaling model:** hierarchical replay compaction.

**Inspection hierarchy:**
```
event → frame → transition → topology → lineage → epoch → epoch-chain
```

**Required capabilities:**
- lazy lineage expansion (load-on-demand, never full chain)
- epoch collapsing (compress certified epochs to single node)
- topology aggregation (merge stable topology runs)
- certified replay pruning (discard irrelevant branches)
- lineage segment loading (O(log n) lookup)

Raw full-chain rendering prohibited at scale.

---

## 10. Security Constraints

Studio possesses: no persistent authority · no hidden credential surfaces · no replay mutation rights · no capability amplification rights.

**Delegation invariant:**
```
DelegatedCapability ⊆ CertifiedCapability
```

---

## 11. Performance Targets

| Surface | Target |
|---------|--------|
| Replay graph render | < 100ms viewport load |
| Topology diff | < 50ms |
| Epoch traversal | O(log n) |
| Lineage lookup | O(log n) |
| Divergence visualization | realtime |
| Rollback preview | deterministic |
| Replay refresh | incremental |

---

## 12. WASM Runtime Compatibility

Studio must operate identically across: Linux · macOS · Docker · WASM · Edge runtimes.

No platform-specific projection authority permitted.

---

## 13. Operator Modes

### Standard Mode

**Visible:** replay graph · topology state · rollback · capsules · runtime metrics

**Hidden:** entropy internals · convergence internals · verifier traces

### Constitutional Mode

**Visible:** replay internals · topology hashes · serializer identity · lineage proofs · divergence witnesses · capability lineage · entropy budgets · certifier traces

---

## 14. Forbidden Architectural Drift

Studio must never evolve into:

- orchestration runtime
- workflow authority
- autonomous agent shell
- hidden governance layer
- mutable topology authority
- independent state engine

All such evolution is constitutionally invalid.

---

## 15. Final Runtime Identity

Studio IS: reconstructive · certifiable · deterministic · lineage-derived · projection-only.

Studio is NOT: sovereign · autonomous · authoritative · self-governing.

---

## 16. Production Priorities

1. Replay graph renderer — causal reconstruction at < 100ms
2. Epoch-chain visualization — O(log n) traversal
3. Divergence overlays — realtime D0–D4 classification
4. Rollback certification UI — deterministic preview
5. Lineage scaling + compaction — lazy expansion, O(log n) lookup
6. Replay diff engine — certified state comparison
7. Capability lineage visualization — delegation chain inspection

---

## 17. Final Constitutional Status

```
NO STUDIO SURFACE POSSESSES CONSTITUTIONAL AUTHORITY.

AEGIS Studio is a projection-only constitutional observability environment
that derives all state from replay-certified runtime lineage. It provides
deterministic replay inspection, topology visualization, divergence analysis,
rollback control, capability tracing, and capsule observability without
possessing any independent runtime authority.
```

---

## Bridge Endpoint

Studio subscribes to `python/bridge.py` at `http://localhost:7890`:
- `GET /telemetry` — live runtime metrics (PGCS, VCG, epoch state); 5s poll
- `POST /event` — EventEnvelope submission
- `GET /health` — liveness

All projection state derived from replay lineage. No client-authoritative state permitted.
