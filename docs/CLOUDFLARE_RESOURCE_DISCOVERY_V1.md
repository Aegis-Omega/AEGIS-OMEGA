# Cloudflare resource discovery, V1 (account inventory, no authority)

This module inventories **existing** resources only, using seven fixed authenticated `GET` requests and a caller-supplied read-only credential or connector-compatible read callback. It does **not** provision services, enable R2, run AI models, create billable resources, or prove a free allowance.

- Surfaces: Workers, D1, Pages, Queues, Vectorize v2, AI Gateway gateways, R2.
- Every surface has `PRESENT`, `EMPTY`, `SETUP_REQUIRED`, or `UNKNOWN` and a first-page count. `EMPTY` is observed empty at one trusted API page; `UNKNOWN` is emitted for malformed, contradictory, incomplete, denied and failed reads.
- R2 `403 / 10042` is precisely **setup required**, *not* evidence of zero R2 buckets.
- No returned payload contains an account identifier, token, script names, errors, or user supplied URL.
- Receipt SHA-256 is an **integrity checksum only**, not source authentication. `free_quota_verified=false`, `cost_authority=NONE`, `routing_authority=NONE`.
- Hosted CI: `npx vitest run test/unit/cloudflare-resource-discovery.test.ts && npm run typecheck`, existing Sovereignty Contracts workflow.

### Read-only connected-source checkpoint, 2026-10-31

Directly inspected the already connected Cloudflare account. Workers 1 (`aegisomega`), D1 0, Pages 0, Queues 0, Vectorize v2 0, AI Gateway 0. R2 returned 403 / 10042: setup required. No paid resource enabled, no deployment and no increase in provider permissions. This status is time-scoped; the new module's fixture only checks parsing, not live connected OAuth.
