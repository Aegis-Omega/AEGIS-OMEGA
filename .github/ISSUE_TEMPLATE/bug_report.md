---
name: Bug report
about: Something is broken in AEGIS-Ω
labels: bug
---

## What broke

<!-- Describe the bug clearly and concisely. -->

## Stratum

- [ ] **Stratum I** — Governance Runtime
  - [ ] sovereign-omega-v2 (TypeScript runtime, src/)
  - [ ] sovereign-omega-v2 (Python core matrix, python/)
  - [ ] aegis-cl-psi (Rust gates)
  - [ ] aegis-runtime (Seven-Pillar swarm)
- [ ] **Stratum II** — Interface Layer
  - [ ] cockpit (constitutional AI chat)
  - [ ] studio (observability projection)
- [ ] **Stratum III** — Commercial Products
  - [ ] hub (landing page)
  - [ ] platform-picker
  - [ ] hook-generator
  - [ ] content-calendar
- [ ] **Cross-cutting**
  - [ ] packages/shared
  - [ ] bridge.py / telemetry

## Steps to reproduce

1.
2.
3.

## Expected behaviour

## Actual behaviour

## Gate or build output

```
paste relevant output
```

## Constitutional tier of the violation

- [ ] T0 — mechanically proven (halt — do not deploy)
- [ ] T1 — empirically validated (fix before production)
- [ ] T2 — engineering hypothesis (fix before listing)
- [ ] T3+ — informational

## Environment

- Node version:
- Python version:
- Rust version (`rustc --version`):
- OS:
- Browser (for UI bugs):
