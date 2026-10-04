# Automaton-3 PostgreSQL Durability v1

Status: **SOURCE_IMPLEMENTED / HOSTED_POSTGRES_REPLAY_PENDING**  
Authority effect: **NONE**  
Runtime default: unchanged; the in-memory Automaton-3 implementation remains the admitted reference.

## Why this exists

`WriterLeaseManager` and `DurableExecutionRegistry` already define the required Automaton-3 safety semantics, but their state is process-local. A multi-host executor needs the serialization boundary in a transactional store or two hosts can each believe they own the same authority domain.

This slice moves only that concurrency boundary into PostgreSQL. It does **not** replace AEGIS canonical hashing, receipts, authority evaluation, EventEnvelope, or operator approval semantics.

## Source artifacts

- `harness/sdk/sql/automaton3_postgres_durability_v1.sql`
- `harness/sdk/postgres_durable_execution.py`
- `sovereign-omega-v2/python/tests/test_automaton3_postgres_durability.py`
- `scripts/run-automaton3-tests.py`
- `scripts/validate-automaton3.py`

## Preserved invariants

### Writer authority

PostgreSQL serializes each `authority_domain` through a generation row locked with `SELECT ... FOR UPDATE`.

A writer lease is valid only when the caller's holder identity root, fencing token, lease generation, expected parent state, and action digest satisfy the reference contract.

Authoritative action claims have a unique primary key over `(authority_domain, lease_generation, action_digest)`, so a successful claim cannot be admitted twice by two concurrent database sessions.

The database stores the fencing token but does **not** independently recreate AEGIS canonical hashing. `PostgresWriterLeaseManager` derives the token with the same `canonical_hash("AEGIS_WRITER_FENCE_V1", ...)` implementation used by the reference model. This deliberately avoids creating a second canonicalization implementation.

### Durable execution

Every state-changing durable operation locks the execution row before validating and mutating it.

The backend preserves exact transition sequence, monotone heartbeat generation, terminal-state rejection, idempotent external-action claim uniqueness, cancellation state, orphan threshold, atomic clearing of current authority, and same-transaction revocation of leases actually held by the execution identity.

External action claims are unique on `(execution_id, idempotency_key)`. This prevents two database sessions from both *claiming* the same effect. It does not prove that an external provider performs a side effect exactly once.

## Failure model

Database/driver exceptions map to `POSTGRES_DURABILITY_UNAVAILABLE`. The adapter rolls back and does **not** retry a write automatically. A network failure after dispatch can have an ambiguous commit outcome, so blind retries would weaken idempotency/fencing semantics.

Domain denials remain deterministic AEGIS codes such as `WRITER_ALREADY_ACTIVE`, `STALE_FENCING_TOKEN`, `REPLAYED_AUTHORITATIVE_ACTION`, `DURABLE_SEQUENCE_INVALID`, `HEARTBEAT_NOT_MONOTONE`, `DUPLICATE_EXTERNAL_ACTION`, and `ORPHAN_THRESHOLD_NOT_REACHED`.

## Database security boundary

The SQL contract uses only `aegis_private`, contains no `SECURITY DEFINER` function, grants no runtime privilege, and explicitly revokes `PUBLIC` schema/table/function access.

A deployment must create or select a dedicated runtime database role and grant only the functions/tables that the deployment actually needs. Supabase `anon` and `authenticated` access is neither required nor granted by this source contract.

## Admission tests

The Automaton-3 deterministic suite is expanded from 41 to 53 tests. Twelve PostgreSQL durability tests check private-schema confinement, no `SECURITY DEFINER` widening, row locks, action/idempotency uniqueness, atomic cancel/orphan lease revocation, PUBLIC revocation, fencing-token/receipt parity, durable-root parity, fail-closed connection handling, and—critically—that the SQL contract, adapter, durability tests, and this specification are themselves hash-bound into the Automaton-3 exact-candidate manifest. The summary also states `distributed_exact_once_claimed=false` and the admission validator rejects an overclaim.

## What is not yet admitted

A source PASS is not a multi-host production PASS.

Before changing the runtime default, execute an exact-source PostgreSQL contention replay that demonstrates at minimum:

- N concurrent acquisition attempts on one authority domain -> exactly one admitted lease;
- stale fencing token rejected after revoke/reacquire;
- duplicate action digest -> one admitted claim;
- concurrent transition sequence -> one transition for each sequence number;
- concurrent identical external idempotency key -> one claim;
- cancellation/orphan mutation atomically clears held authority and matching leases;
- process crash/restart can reconstruct the same durable execution root.

Then run database security/performance advisors and bind the database engine/version, schema digest, source commit, test transcript, and resulting root into an admission receipt.

Until that evidence exists, status remains `SOURCE_IMPLEMENTED / HOSTED_POSTGRES_REPLAY_PENDING`.
