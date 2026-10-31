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

## Capacity provenance binding V1.1

The separate `planFreeResourceV1` planning gate now requires each **independently approved** capacity witness to carry **both** `snapshot_root` (exact provider-mesh snapshot) and `observation_evidence_hash` (the precise provider observation). It fails closed on missing or mismatched hashes, including witnesses with a matching provider and generation from a different snapshot or observation. The fields are optional in the legacy interface only to parse older inventory; they are mandatory for `PLANNING_ELIGIBLE`. An approved digest **is not a signed provider attestation** unless independently sourced, verified and anchored by the trusted caller.

This binding does **not** authenticate caller-supplied `approved_roots`, reserve capacity, prove provider-side no-overage guarantees or authorize any execution. Missing independent billing/quota proof remains `HOLD`.


## AWS account read-only expansion: 2026-10-31

AWS STS identity succeeded on two connector links, both selecting the same AWS account. Sanitized reads for that account: S3 ListBuckets `NotSignedUp`; EC2 DescribeRegions `OptInRequired`; Cost Explorer GetCostAndUsage `SubscriptionRequiredException`; Billing ListBillingViews succeeded with 1 view; Budgets DescribeBudgets succeeded with 0 budgets; Free Tier GetFreeTierUsage returned 0 entries.

The operator reported **USD 100 of AWS credits**, but the *remaining credit balance, expiration and restrictions remain UNKNOWN*. A billing view is not a credit receipt, an empty usage list is not entitlement proof, and a budget alarm is not a spending hard stop. The AWS extension preserves `zero_spend_admission=HOLD`, `authority_effect=NONE`, `paid_aws_workloads=HOLD` regardless of claimed credit, and outputs no AWS account ID, ARN or credentials. Its content hash is only a local checksum, not AWS attestation.

The code is pure and network-free. It adds an optional AWS snapshot to the existing Cloudflare/Hugging Face adapter; snapshots without AWS remain backwards compatible. Run `cd sovereign-omega-v2 && npx vitest run test/unit/connected-resource-intake.test.ts && npm run typecheck`. Before any AWS resource creation: independently confirm credit from Billing, effective limits, least-privilege non-root identity, regional service eligibility and explicit operator workload approval. No cloud writes or costs authorized by this extension.
