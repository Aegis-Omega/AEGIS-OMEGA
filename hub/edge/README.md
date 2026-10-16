# AEGIS Public Observation Gateway — deployment boundary

**Purpose:** Make the already-public `GET /platform/status` response observable in a mobile browser when the upstream API's cross-origin policy blocks a direct frontend request.

**Does not do:** authenticate, call `/platform/calibration` or `/platform/tools`, run inference, buy services, verify audit-chain cryptography, expose customer data, access Supabase, or mutate remote resources.

Worker endpoint: `https://aegis-public-observation.tarikskalic33.workers.dev/api/status` (public, read-only).

- Only GET/OPTIONS on `/api/status` and `/platform/status` are supported. GET `/api/health` is local health, **not** upstream health.
- Upstream is hardcoded to `https://aegis-vertex.aegisomega.com/platform/status`. No user-controlled target and no forwarded credentials/cookies.
- Response fields are hard-allowlisted: `version`, `contract_version`, `total_agents`, `available`, `chain_valid`, `audit_chain_hash`, plus constrained upstream metadata.
- No inference of a verified chain: gateway labels remote data `UNSIGNED_REMOTE_REPORT_NOT_INDEPENDENTLY_VERIFIED`.
- No cache; every client request makes a bounded upstream GET (3.8-second deadline). Traffic/rate cost and Cloudflare's free-tier limits need monitoring before high-volume public promotion.

Run tests: `node --test public-observation.test.mjs`.

**No DNS move or production replacement.** The worker is a bounded public read-only telemetry projection; AEGIS production `aegisomega.com` remains unchanged.