---
name: studio-projection
description: Automatically invoked when studio/ code is written or modified, when a studio surface appears to store or cache authoritative state, when studio code attempts direct runtime mutation or write, when divergence classification is needed for a topology comparison, or when operator mode boundaries need enforcement.
---

# Studio Projection Skill

When invoked, enforce the projection purity law from `studio/docs/STUDIO_SPECIFICATION.md`.

## Projection Purity Law

```
ProjectionLayer ∩ ConstitutionalAuthority = ∅
```

Studio surfaces possess: no constitutional authority · no mutation rights · no persistent authority · no replay bypass capability.

All Studio state satisfies: `StudioState(T) = Projection(ReplayState(T))`

## Forbidden Pattern Check

Flag as STUDIO PROJECTION VIOLATION if any of the following appear in `studio/src/`:

| Pattern | Violation |
|---------|-----------|
| Client-authoritative state | Any state variable that is not derived from `/telemetry` or `EventEnvelope` |
| Local governance caches | Storing governance decisions, topology hashes, or lineage locally without re-deriving |
| Hidden mutation surfaces | Any function that writes to runtime without going through EventEnvelope |
| Direct runtime writes | Fetch/POST to any endpoint other than `POST /event` or `GET /telemetry` / `GET /health` |
| Projection-derived legality | Using Studio-derived data to authorize actions outside of observation |
| Replay bypass controls | Any path that skips replay certification |

## EventEnvelope Communication Check

Studio must communicate exclusively through EventEnvelope. Verify all five required properties are present:

1. `replay-certifiable` — envelope can be deterministically re-processed
2. `serializer-stable` — uses RFC 8785 JCS serialization
3. `capability-scoped` — envelope declares capability scope
4. `lineage-addressable` — addressable within replay lineage
5. `deterministic-classified` — carries determinism class (strict/bounded/observational)

## Divergence Classification

When a topology comparison is needed, apply the D0–D4 table:

| Class | Condition |
|-------|-----------|
| D0 | observational drift — no governance impact |
| D1 | serializer mismatch — monitor, log |
| D2 | topology mismatch — freeze mutation authority |
| D3 | ownership inconsistency — freeze + escalate |
| D4 | constitutional invalidity — T0_ABORT |

D2 and above freeze mutation authority immediately.

## Performance Target Check

Verify Studio surfaces meet declared targets:

| Surface | Target |
|---------|--------|
| Replay graph render | < 100ms viewport load |
| Topology diff | < 50ms |
| Epoch traversal | O(log n) — no full-chain scan |
| Lineage lookup | O(log n) — lazy expansion only |
| Divergence visualization | realtime |
| Rollback preview | deterministic |
| Replay refresh | incremental |

## Forbidden Architectural Drift

Flag if Studio code begins to resemble: orchestration runtime · workflow authority · autonomous agent shell · hidden governance layer · mutable topology authority · independent state engine.

## Reporting Format

```
STUDIO PROJECTION: [surface] — PURE / VIOLATION

Forbidden patterns:   NONE | [pattern name at file:line]
EventEnvelope:        COMPLIANT | MISSING property: [list]
Divergence class:     D[0-4] — [condition]
Performance:          PASS | FAIL — [surface: actual vs target]
Architectural drift:  NONE | [drift pattern detected]

Action: PROCEED / HALT — [reason]
```
