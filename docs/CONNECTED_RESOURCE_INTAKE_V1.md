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

### Free Plan grant evidence versus current balance

An **AWS Billing and Cost Management Notification**, received 2026-10-23 by the AEGIS billing mailbox, states the AWS Free Plan is active, includes USD 100 initial Free Plan credit, offers the possibility to earn another USD 100 over six months, and expires 2027-04-23 or earlier if the credits run out. This is provider email evidence of the **original grant**, not direct proof of today's remaining balance, account-linked provisionable services, earned additional credit, or authorization to incur charges. The AWS account may require a paid-plan upgrade for some services, which is not approved.

Direct read-only calls on 2026-10-31: `billing.GetCredits` returned HTTP success with zero entries for the queried 2026 credit period; `freetier.GetAccountPlanState` returned `ResourceNotFoundException: Missing data for account`. These are **incomplete/discordant** with the welcome notification, not proof that the original Free Plan grant never existed. Verify the Free Plan billing-console remaining credit and service eligibility before considering any workload. Keep fail-closed HOLD and do not upgrade the plan or create billable AWS services.


## Dynamic AWS collector V1.1 (no static entitlement or credit)

The new `src/sovereignty/aws-readonly-collector.ts` accepts a supplied **allowlisted read-only AWS API callback** and obtains current STS, S3, EC2, Billing Views, Budgets and Free Tier observations. Counts derive from API arrays, never constants. It rejects incomplete pagination, refuses to fetch account-scoped budgets without a validated transient STS account ID, strips raw errors/ARN/account IDs/secrets, and returns an optional `aws` payload for the existing `observeConnectedResourcesV1` hash-chain. S3 bucket count and EC2 region count are now hashed; changes alter the receipt root.

Cost Explorer is **opt-in** via `include_cost_explorer:true` and a caller-supplied valid `cost_period`, because certain usage-reporting API calls may carry charges. The new collector itself has no SDK, no ambient credentials, no running scheduler, no cloud mutation and no default network call; it executes only when an authorized caller explicitly supplies a read-only implementation. The callback is required to supply fully paginated AWS list responses. A nonempty `NextToken` is treated as UNKNOWN, never as an exhaustive inventory.

No inference on Free Plan balance, available spend, paid resources or authorization is made. Current AWS account principal is root; least-privilege non-root identity must precede any operational integration. The original 2026-10-23 AWS grant of USD 100 remains email-confirmed; **remaining balance UNKNOWN**; `HOLD / NONE` remains invariant. Read-only mocked regression: `cd sovereign-omega-v2 && npx vitest run test/unit/aws-readonly-collector.test.ts test/unit/connected-resource-intake.test.ts && npm run typecheck`. The independent local slice compiled with `tsc` and passed nine Node tests; hosted exact-head checks must be independently confirmed.


## AWS provider mesh adapter V1.2 (not AWS execution)

`provider-adapters/aws.ts` now verifies the **local** connected-resource inventory checksum, maps AWS identity observations to the existing provider mesh at `provider_id=aws`, and creates only `ACCOUNT_CONFIGURED` or `UNKNOWN` with **zero observed capabilities**. The catalog advertises AWS service classes as **declared possibilities**, not account access or entitlement. The exact `integrity_root` is bound as `evidence_hash`; a modified or non-HOLD inventory fails closed.

End-to-end regression verifies dynamically collected STS/S3 metadata flows through the existing intake and provider snapshot/selector while AWS remains `DENIED` for `SERVERLESS_FUNCTION` even when API calls succeed or a large credit is claimed. Current credits remain unverified, and AWS account identity is root, so no cloud deployment or paid AWS API call is permitted. SHA-256 is a local checksum only; no independent provider signature exists. Test: `cd sovereign-omega-v2 && npx vitest run test/unit/provider-aws-account.test.ts test/unit/aws-readonly-collector.test.ts test/unit/connected-resource-intake.test.ts && npm run typecheck`.


## AWS principal classification (read-only security delta, 2026-10-31)

The AWS collector now derives a privacy-preserving `principal_kind` enum from the **transient STS GetCallerIdentity ARN**: `ROOT` for the exact account-bound root ARN, `IAM_PRINCIPAL` for an account-matching IAM user/role or STS assumed-role ARN, otherwise `UNKNOWN`. The ARN, AWS account number, role/user name and STS UserId are never returned or hashed. Historical observations lacking `principal_kind` are processed as before.

Provider mesh never promotes an observed `ROOT` principal even to `ACCOUNT_CONFIGURED`; its observation stays `UNKNOWN` with no executable capabilities and authority `NONE`. A recognized IAM principal remains observational only and is **not** evidence of least privilege, non-expired credits or execution approval. The AWS connector observed root identity on this account; no IAM or billing state was modified. Regression: existing `aws-readonly-collector.test.ts` and `provider-aws-account.test.ts` include root/cross-account/assumed-role/forged-kind cases.


## AWS optional service-discovery V1.3

The existing injected AWS collector now accepts `include_service_discovery:true` for **five additional read-only API metadata calls**: Bedrock `ListFoundationModels`, Glue `GetDatabases`, Lambda `ListFunctions`, DynamoDB `ListTables` and S3 Tables `ListTableBuckets`. The flag is **false by default**; no Bedrock model invocation, Glue job or query is executed. The allowlisted runtime API responses are normalized to outcome, recognized error code and list-count only; no model IDs, database names, resources, account numbers or ARN are written to receipts. AWS-specific continuation markers now force `UNKNOWN` instead of a false exhaustive list count.

Connected read-only AWS scan in `eu-central-1` on 2026-10-31 observed: Bedrock `ListFoundationModels` succeeded with 55 model metadata rows; Glue `GetDatabases` succeeded with 0 databases; IAM `GetAccountSummary` succeeded; Lambda and DynamoDB returned `SubscriptionRequiredException`; S3 Tables returned `ForbiddenException`. **These are API-listing observations only**, not paid invocation entitlement, sufficient Free Plan credits or least-privilege identity. Root STS principal, remaining credit UNKNOWN, and `paid_aws_workloads=HOLD` are unchanged. The CI test file `aws-readonly-collector.test.ts` includes opt-in, count/hash, redaction, denial and pagination regressions.


### AWS principal-kind fail-closed correction (2026-10-31)

Prior source treated a missing or `UNKNOWN` `principal_kind` as non-root because it checked only `principal_kind !== 'ROOT'`. That incorrectly promoted unclassified STS evidence to `ACCOUNT_CONFIGURED`. The adapter now requires **explicit `principal_kind === 'IAM_PRINCIPAL'`** plus a verified STS identity before even observational account configuration. Missing, unknown and root principals remain `UNKNOWN` with zero observed capabilities, and cannot be selected for cloud execution. Existing unit checks that previously promoted missing principal-kind are corrected to use an explicitly recognized IAM fixture, and new negative tests cover omitted/UNKNOWN principals. IAM principal classification still does not establish least privilege or authorization. No AWS permissions, service subscriptions, resources or spending changed.


### AWS error-code normalization correction (2026-10-31)

The AWS collector already recognized `ForbiddenException` from S3 Tables, but the shared connected-resource intake omitted it from its sanitized error allowlist. Thus a real `ForbiddenException` was being downgraded to an unspecified error in the final hashed receipt. Both allowlists now include this well-defined AWS error code, while raw messages, unrecognized errors and secret-bearing details are still dropped. New negative regression assertions cover collector-to-intake preservation, unknown errors, and unchanged `HOLD`. This correction does not grant AWS access, credits or execution authority.
