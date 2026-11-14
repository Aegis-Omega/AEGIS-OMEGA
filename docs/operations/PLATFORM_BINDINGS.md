# AEGIS platform bindings — 14 November 2026

This is an operational read projection for TAR-10 and draft PR #569. It grants
no permissions, chooses no deployment target and contains no credentials.
Keep the existing Integration Ledger as the commit-bound source classification;
this page records independently observed hosting and identity boundaries.

## Current evidence

| Surface | Observed binding | State / remaining obligation |
| --- | --- | --- |
| Source | `Aegis-Omega/AEGIS-OMEGA`, protected main `ec5fea38b9abee0bf850a1d39b52bdd3fb7197ed` | VERIFIED source ref; no merge authorized by this receipt |
| Chat candidate | Existing `feat/sovereign-provider-mesh-v1`, PR #569 | Source-only; check exact new head, native CI and authenticated acceptance before deployment |
| DNS | `aegisomega.com`, zone `9bdd3883f332446f2b235c224d482e0d`, Cloudflare account `66887c5b59ab009e1a94990837fff40b` (`Info@aegisomega.com's Account`) | VERIFIED account and active zone; other Cloudflare accounts remain outside this read |
| API hostname | `aegis-vertex.aegisomega.com` -> Worker `aegisomega`, production custom domain enabled | VERIFIED Cloudflare binding; unauthenticated health/status probes returned HTTP 403, cause not established |
| Active Worker traffic | Deployment `7b083c28-9caa-4f9a-aa6f-2ed597bf8afc`, version `c7242cd2-f69c-4f60-b928-cc3e6990405c`, 100%, 25 October | VERIFIED deployment record only. Its annotation cites PR #732 / `101c21d4b70b187b15314c1c8e49ffbc27fe10f2`; annotation is not a fresh byte comparison |
| Worker upload vs traffic | Latest script metadata changed 14 November and mentions preview alias `feat-sovereign-provider-mesh-v1` | A version upload is not evidence that production traffic moved. Do not redeploy or roll back PR #732 implicitly |
| Frontend | `aegisomega.com`, `platform.aegisomega.com`, `hooks.aegisomega.com` returned HTTP 200 | VERIFIED page delivery only, not inference, checkout or login acceptance |
| Calendar product | `calendar.aegisomega.com` CNAME -> `cname.vercel-dns.com`; page returned HTTP 503 | OPEN runtime/deployment investigation; DNS alone does not identify the Vercel project |
| Vercel connection | Visible team `tarikskalic-9462s-projects` has zero projects | VERIFIED connection scope, not absence of AEGIS deployments |
| Other Vercel scope | GitHub status names `tariks-projects-e9198507`, team `team_R1tLynD1gTpyoY7nKpbtt7pF` | Listing returned 403; consent-link creation by ID and slug returned 404. Actual membership/project ownership UNKNOWN |
| Supabase | `aegis-omega`, `rwehltdwpsncnwxzkwik`, ACTIVE_HEALTHY | VERIFIED accessible backend; deployed chat remains v7, bundle `7d9b312c8517310dcc47709bd6ddb421a406babf9d7c70a2a6bde02a2023f731` |
| Chat identity | Existing new chat candidate requires Supabase-verified user JWT plus `CHAT_ALLOWED_USER_IDS` | OPEN provisioning and app-session integration. `auth.users` has zero rows; do not fabricate operator UUID or substitute anon key |
| Other app identity | Existing platform API keys and server-signed product grants are separate contracts | Zero Supabase Auth rows does not prove these existing access mechanisms absent or broken; no automatic identity/account merge |
| OpenAI credential | Existing Dropbox `Tarikskalic team folder/openai-api-key.txt` | Prior authenticated GET /v1/models receipt: org `aegis-omega`, project `proj_1eYFqYDJeAZr5Xh3oPRwzKRp`. No inference/credit/scopes claim; no secret copied by this change |
| Other OpenAI credential | `Microsoft Copilot Chat Files/openai-api-key.txt`, org `system-rebuild` | Separate project; never substitute it for the AEGIS credential |
| Provider admission | OpenAI runtime observation expired; selector returned no MODEL_INFERENCE candidate | OPEN fresh bounded evidence and financial authorization; never set OBSERVED_AVAILABLE from models-list success alone |
| Work tracking | Existing Linear TAR-10, AEGIS Enterprise Infrastructure | Reuse this work item; no new coordinator, account or second scheduler |

## One hosted inference path

`packages/shared/lib/inference-router.ts` is the shared browser adapter. The
candidate routes OpenAI, Azure, Nebius and DashScope through the existing
Supabase `/functions/v1/chat` endpoint. Every hosted request requires:

1. Explicit backend selection and exact client opt-in flag.
2. A supplied user-session JWT; the public project key is only an `apikey` header.
3. Server-side user verification and the existing global allowlist.
4. Exact provider selection, server configuration and fresh provider mesh evidence.
5. Applicable server budget admission before any billable request.

The browser adapter does not grant authority or establish provider availability.
Default routing is limited to local CL-Psi/Ollama. It never silently selects a
paid provider after a local failure. A hosted failure never retries or switches
providers. Server-returned model identity is mandatory; no guessed provenance.
Legacy `VITE_DASHSCOPE_API_KEY` and `VITE_CLAUDE_API_KEY` are no longer consumed by
this router. Claude remains unavailable here until an authenticated server
adapter is implemented; this change does not activate a different provider.

## Release obligations

- Preserve the currently deployed Worker and Supabase source snapshots and
  compare exact candidate bytes; source main is not the live runtime.
- Establish a real chat user session and explicit operator allowlist without
  changing the separate paid-product or platform-key contracts.
- Install only the AEGIS credential server-side through an approved secret path.
  Do not put keys in source, browser variables, chat or diagnostic output.
- Implement and verify an OpenAI spend/rate boundary. Existing Nebius reservation
  is not an OpenAI budget. Obtain a bounded inference allowance before a paid test.
- Resolve Vercel team access before changing frontends or calendar routing.
- Run exact-head native tests, typecheck and authenticated negative/positive
  acceptance; then approve a concrete deployment with rollback bytes available.

The updated code is a candidate, not an assertion of production integration.
No membership, DNS, billing, provider credentials, runtime observations or
production traffic are changed by these source updates.
