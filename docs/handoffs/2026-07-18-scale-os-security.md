# Scale OS Security Appendix — 2026-07-18

This appendix records security findings and boundaries discovered while initializing the Scale OS control plane. It is not authorization to change production behavior.

## Scale OS schema posture

The new `scale_os` schema uses:

- RLS on all five tables.
- Revoked direct access for `anon` and `authenticated`.
- Explicit client-deny policies.
- Server-side operational access only.
- Indexed foreign-key references from approvals/events to tasks.

The current event records are not cryptographically signed. Until the existing Ed25519 signing and verification path is integrated, use the terms **audit record** or **control-plane event**, not tamper-proof ledger.

## Existing Supabase findings outside Scale OS

The Supabase advisor identified two public `SECURITY DEFINER` functions callable by unauthenticated and authenticated API roles:

```text
public.award_grace(...)
public.verify_and_increment_api_key(...)
```

Do not revoke execution blindly. First locate every caller and test the grace, payment, and API-key paths. Remediation requires a separate operator decision because it can break live clients.

The advisor also identified these public tables with RLS enabled but no explicit policies:

```text
public.access_grants
public.analytics_events
public.purchases
public.swarm_memory
```

RLS with no policy may intentionally mean deny-all. Classify each table against actual runtime calls before adding policies or changing grants.

Other advisor findings include pre-existing unindexed foreign keys, RLS initialization-plan inefficiencies, multiple permissive policies, and unused indexes. Do not remove indexes solely because a low-volume environment reports no usage.

## Required security implementation

The next Scale OS security PR should add:

1. A canonical event-envelope schema.
2. Deterministic canonicalization.
3. An adapter to the repository's existing Ed25519 signer.
4. Signature verification before event acceptance.
5. Idempotency keys and source-object hashes.
6. Separate identities for request, approval, execution, and verification.
7. Replay and negative tests.
8. Explicit terminal approval states.

## Prohibited shortcuts

- No new independent crypto implementation.
- No service-role key in browser code.
- No secret values in repository files, logs, issues, or chat.
- No blanket authenticated RLS policies.
- No fail-open approval path.
- No production IAM or database permission change without live caller analysis and operator approval.
