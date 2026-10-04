# Governed External Ingress V1

Status: **source candidate / authority effect NONE**.

This slice closes the boundary between provider-native identities/events and the
existing Automaton-3 authority model. It adds no new authority store and no
provider secret storage.

## Invariants

1. External verification is an observation, never an AEGIS grant.
2. Provider input must bind to the exact verified bytes or normalized claims.
3. Resend `email.received` enters only a `quarantine:*` routing domain.
4. Inbound email bodies and attachment bytes do not enter the event envelope.
5. WorkOS `permissions` are only an upper bound. A permission must map to an
   already-known AEGIS capability; it does not satisfy policy, capability
   evidence, writer-lease, idempotency, or explicit-approval requirements.
6. WorkOS-derived execution identities hard-code `observed_authority=0.000000`.
7. A WorkOS delegated user claim is not an AEGIS operator approval.
8. Consequential work remains exclusively decided by `AuthorityEvaluator`.

## Resend inbound contract

Resend currently delivers inbound mail through `email.received` webhooks and
provides webhook verification over the exact raw request body.

AEGIS consumes that boundary in two phases:

1. the host verifies the raw webhook with Resend's webhook verifier;
2. `build_resend_email_received_event` binds the same body digest to an
   `ExternalVerificationReceipt`, removes prompt-bearing content, and emits a
   quarantine `EventEnvelope`.

The event retains hashes/counts for message, sender, recipients, subject, and
attachment metadata. Fetching email body or attachment bytes is a separate
capability.

Provider references:
- https://resend.com/features/inbound
- https://resend.com/changelog/managing-webhooks-via-api

## WorkOS Agent Auth contract

WorkOS Agent Auth currently gives first-party agents blueprint-bounded identities
and short-lived scoped tokens. Agent tokens identify the agent
(`sub_profile=ai_agent`), session, blueprint, organization, effective permissions,
and, for delegated sessions, the user in `act`.

AEGIS accepts only already-verified claims. The host verifier must validate JWT
signature, issuer, audience, and expiry before binding normalized claims into the
verification receipt. The adapter rejects user tokens, issuer/audience mismatch,
claim substitution, and capability widening.

A WorkOS permission such as `email:send` can map to an internal capability such
as `external.email.send`, but the resulting `ExecutionIdentityEnvelope` still
has zero observed authority. External identity can request; it cannot authorize.

Provider reference:
- https://workos.com/docs/authkit/agent-blueprints

## Evidence-bound files

- `harness/sdk/external_ingress.py`
- `schemas/external-verification-receipt.v1.schema.json`
- `sovereign-omega-v2/python/tests/test_external_ingress.py`
- `scripts/run-automaton3-tests.py`
- `scripts/validate-automaton3.py`

## Explicit non-claims

This source does not prove that a Resend webhook was received, that WorkOS Agent
Auth is enabled for an AEGIS environment, that a live provider token was minted,
or that any external action was authorized. Those require separate exact-runtime
evidence.
