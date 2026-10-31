# AEGIS Ω signed free-resource approval boundary (candidate V1)

`createTrustedFreeResourcePlannerV1(authenticated_bootstrap_policy, read_authenticated_generation)` is the **server-trusted** planning entrypoint. It uses the existing project's Ed25519 verification and RFC 8785 canonicalization. Its untrusted `plan(snapshot,request,evidence,untrusted_approvals)` method cannot nominate trusted signer keys or replace the revocation snapshot.

## Trust separation

- The caller can submit signed approval envelopes, but **cannot supply trusted signer public keys or revocation policy at request time**. Only the trusted runtime bootstrap may construct the planner. The bootstrap policy is copied into private Sets.
- Each Ed25519 signature signs the *domain-separated* canonical approval payload. The approval is bound to one policy ID, audience, provider ID, capacity evidence SHA-256 root, exact Provider Mesh snapshot root, exact observation evidence hash, issued generation, expiry generation and unique approval ID.
- Missing/invalid signature, unrecognized signer, revoked signer or approval ID, policy mismatch, stale or future revocation snapshot, expired signature, mismatching provider observation/snapshot, and absent quota evidence all fail closed to `HOLD`.
- **No trust keys, signer tokens, private keys or actual operator approvals are configured here.** The unit-test keys are deterministic, explicitly synthetic, and exist only in the isolated test fixture. Real trusted bootstrapping and independent source acknowledgement are OPEN.
- A signature proves endorsement by an authorized **configured key**. It does **not** prove the provider actually has remaining quota, the account has a free-only plan, or that a hard billable-overage stop exists. Those obligations must be verified independently at the provider and reflected in the evidence. An untrusted external service must not be allowed to choose `authenticated_bootstrap_policy`.

## Not an execution gate

Existing `planFreeResourceV1` accepts raw approved roots as a low-level *non-authorizing planning primitive*. It MUST NOT be exposed directly to untrusted callers. Use the trusted wrapper for an authenticated planning decision. Both retain `authority_effect: NONE`. Neither reserves a quota, grants consent, approves billing, signs a provider statement or permits model execution.

Verification: `cd sovereign-omega-v2 && npx vitest run test/unit/trusted-free-resource-planner.test.ts && npm run typecheck` in the existing Sovereignty Contracts workflow. Candidate stays DRAFT, NO_MERGE, NO_DEPLOY, NO_NEW_SPEND.

## Anti-replay bound on the runtime clock

The trusted runtime MUST inject a monotonic and authenticated `read_authenticated_generation` callback during initialization. The signer policy also sets `max_observation_age_generations`. Both are host-controlled. An untrusted request cannot backdate `current_generation`, expand observation age or supply the clock itself to make an expired signed approval eligible. A missing, throwing, or malformed trusted clock returns `HOLD`. An unchanged snapshot and signed witness are not enough to evade the runtime's advanced generation.

Production must still authenticate the source of the clock/revocation/policy and ensure these values are not sourced from a request, model output or mutable provider response. This module remains a planning-only contract.

## Task-specific signed request binding

A capacity witness cannot authorize arbitrary tasks, even when the same provider,
snapshot and measured free capacity remain unchanged. The signed approval
payload now includes `request_root`, computed using SHA-256 over the canonical
**entire** `FreeResourceRequestV1` object with domain
`AEGIS_FREE_RESOURCE_REQUEST_V1`.

The digest commits to the requested unit, worst-case units, required capabilities,
allowed providers, provider preference and generation/freshness constraints.
Any change requires a new approval signed by a trusted signer. Older signed
approvals lacking `request_root` fail closed.

This is still **planning only**: no provider-side reserve, live free allowance,
no-overage verification, independently authenticated trust bootstrap, consumption
or deployment is established. No credentials or production admission are added.
