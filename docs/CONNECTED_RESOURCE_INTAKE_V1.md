# AEGIS connected-resource intake V1

**Source-bound checkpoint date:** 2026-10-31. **Authority:** NONE. **Cost:** no paid calls.

This adapter converts four **read-only** Cloudflare account observations and Hugging Face Jobs metadata into a minimal, content-hashed inventory. Its `integrity_root` is only an integrity checksum of the normalized output, **not a Cloudflare or Hugging Face signature** and not independent evidence that the original source is genuine.

## Observed at connected endpoints (not arbitrary tier assumptions)

| Source | Read-only observation | Interpretation |
| --- | --- | --- |
| Cloudflare `GET /accounts/{account_id}/ai-gateway/billing/credit-balance` | HTTP 200, `balance=0` | AI Gateway prepaid balance zero; this does **not** measure Workers AI's free-neuron allowance. |
| Cloudflare `GET /accounts/{account_id}/ai-gateway/billing/topup/config` | HTTP 200, `threshold=0, amount=0` | AI Gateway auto-topup appears off, not a global Cloudflare billing guarantee. |
| Cloudflare `GET /accounts/{account_id}/workers/account-settings` | HTTP 200, `default_usage_model=standard` | Workers tier and no-overage contract **not proven**. |
| Cloudflare `GET /accounts/{account_id}/workers/scripts` | HTTP 200, 1 script `aegisomega` | Worker existence, not callable quota or free inferencing. |
| Hugging Face `Jobs ps(all=true)` | 0 jobs listed for connected Free account | No job in listing; GPU entitlement and remaining quota **not known**. |

The first API read is NOT evidence for the Workers AI paid/free allowance, which is separately metered. Billing credits and account billing-usage APIs responded 403 due to missing OAuth scopes; the account's overall billable usage remains UNKNOWN.

## Contract

`observeConnectedResourcesV1(reads)` is pure, network-free and does **not** obtain credentials, reserve quota or infer free availability. It strips unexpected provider fields and yields `zero_spend_admission=HOLD`, `authority_effect=NONE` until independent, authenticated and provider-enforced hard-stop free-quota proof can enter the separate `planFreeResourceV1` gate.

Run: `cd sovereign-omega-v2 && npx vitest run test/unit/connected-resource-intake.test.ts && npm run typecheck`.

**Boundary:** PR draft; no merge, no deploy, no new paid resource, no new secret access.
