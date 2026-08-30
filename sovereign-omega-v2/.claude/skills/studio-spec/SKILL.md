---
name: studio-spec
description: Invoked when the user asks about AEGIS Studio, what Studio can or cannot do, the projection-only boundary, Studio surfaces, observability vs authority, or how Studio relates to the governance runtime.
---

# Studio Specification Skill

## Core Principle

```
ProjectionLayer ∩ ConstitutionalAuthority = ∅
```

Studio is a **read-only observability layer**. It has no mutation authority, no write-back paths, no governance authority of any kind. It observes and projects; it does not govern.

## Studio Is NOT

- A governance authority
- A mutation surface
- A memory system
- A decision-making component
- An agent runtime

## Studio IS

- A constitutional observability dashboard
- A projection-only interface to `/telemetry`
- A human-readable window into constitutional state

## The Ten Observability Surfaces

| Surface | What It Projects |
|---------|----------------|
| **Replay Surface** | Hash-chained governance event graph |
| **Epoch Surface** | Epoch chain visualization |
| **Divergence Surface** | D0–D4 drift classification map |
| **Rollback Surface** | Rollback certification UI |
| **Lineage Surface** | Lazy-loaded causal lineage |
| **Topology Surface** | Live mesh topology state |
| **Ownership Surface** | Capability delegation chains |
| **Capsule Surface** | Capsule manifests and entropy budgets |
| **Observability Surface** | Constitutional health metrics |
| **Governance Surface** | Guardian policy inspection |
| **Swarm Surface** | Agent swarm with Fibonacci loop status |

## Data Flow

```
/telemetry (GET, read-only) → Studio React app → rendered projection surfaces
```

Studio polls `/telemetry` at 5s intervals. No data flows in the reverse direction. Studio cannot emit events, cannot call `/event`, cannot call `/gate_signal`.

## Commercial Analytics Stratum

Studio uses PostHog as an observational layer (`determinism_class: 'observational'`). PostHog data is separated from governance telemetry — it never feeds back into the constitutional runtime. BigQuery as warehouse; dbt metric layer for transformation.

## Deployment

```bash
cd studio && npm install && npm run dev
# → http://localhost:5174
```

Deploys to Vercel (separate Vercel project from sovereign-omega-v2). Gate 8 must pass on sovereign-omega-v2 before Studio deployment.

## Source: `studio/docs/STUDIO_SPECIFICATION.md`
