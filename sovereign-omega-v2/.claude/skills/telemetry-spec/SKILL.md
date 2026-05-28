---
name: telemetry-spec
description: Invoked when the user asks about telemetry metrics, PGCS/TGCS/AFSE, constitutionalized telemetry admissibility, bridge endpoints, metric determinism requirements, or what makes a metric constitutionally valid.
---

# Telemetry Specification Skill

## Core Principle

Telemetry is constitutionally typed **epistemic state** — not observational output. Telemetry semantics may not drift independently from constitutional interpretation.

## Admissibility Rule (all five required)

A metric is constitutionally admissible only when:

1. **Ontology registration** — term appears in `docs/ONTOLOGY.md`
2. **Provenance linkage** — grounded in `docs/TRACEABILITY.md` at T0–T2
3. **Deterministic computation path** — no floating-point, no wall-clock time, no random sources
4. **Invariant binding** — mapped to an existing `INV-*` or accompanied by a new one
5. **Replay declarability** — metric can be reconstructed from the replay archive

## Key Metrics

### `pgcs_passes` (T0)
Probabilistic Governance Coherence Score. Must pass before TGCS telemetry is meaningful. Implementation: `python/pgcs.py`.

### `afse_r2` (T1)
AFSE correlation coefficient — R² between local AMD RX 570 throughput and distributed topology baseline. Constitutional floor: `afse_r2 ≥ 0.98 when pgcs_passes` (INV-09). Stored as Q16.16 fixed-point integer in archives (`afse_r2_fixed`). Float in telemetry JSON is display-only.

### `tgcs_variance` (T1)
TGCS run-to-run cycle timing variance σ². Constitutional success: σ² = 0.

### `corruption_count` (T0)
CoreMatrix corruption counter. Must equal 0 at all times. Non-zero = T0 violation. Check via `GET /health` or `/telemetry`.

### `drift_index` (T1)
Drift classification D0–D4. D0 = constitutional baseline. D4 = divergence detected. Only D0 satisfies `drift_bounded`.

## Bridge Endpoints (port 7890)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/telemetry` | GET | Live runtime metrics (PGCS, VCG, epoch state) |
| `/telemetry/stream` | GET | SSE stream (5s interval) |
| `/event` | POST | Ingest governance events |
| `/gate_signal` | POST | Gate pass/fail signals |
| `/health` | GET | Liveness check — asserts `corruption_count == 0` |
| `/metrics` | GET | Prometheus-format metrics |
| `/snapshot` | GET | Point-in-time state snapshot |
| `/claude` | POST | Governed Claude call (hash-certified, tier-stamped) |
| `/node` | GET | Constitutional autonode descriptor (t0_verdict, c_hash) |

## Validation Order

```
PGCS must pass (zero disk I/O) → TGCS telemetry becomes meaningful
TGCS variance = 0 → AFSE R² computation valid
AFSE R² ≥ 0.98 → Epoch failsafe corruption_count check valid
corruption_count = 0 → T0_verdict: true → telemetry certified
```

## Replay Requirements

All telemetry values must be reconstructable from the replay archive. Metrics that cannot be replayed from the event log are not constitutionally admissible — they may only appear in the observational (PostHog) stratum.

## Source: `docs/TELEMETRY_SPEC.md`
