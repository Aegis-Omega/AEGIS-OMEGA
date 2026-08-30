# Queued Control-Plane Enforcement — 2026-07-19

**Baseline:** `main@a58fd426c11a908e49f2da11781d816d4c2c3e65`  
**Operator decision:** all queued control-plane tasks approved  
**Execution posture:** fail closed; exact-head evidence required

## 1. Grace-cycle control flow

The queued alert was stale against the current baseline.

`award_graces_for_cycle` already:

- returns without mutation for `QUARANTINE` and unknown verdicts;
- requires both Supabase endpoint and service-role configuration;
- excludes blank artifacts while preserving role order;
- invokes `award_grace` once per active role;
- preserves the previous role as `p_from_dept`;
- bounds failures per request so one unavailable award does not suppress later attempts.

`query_fitness_trend` is a separate read-only wrapper and contains no grace mutation loop.

The five-test regression suite at
`sovereign-omega-v2/python/tests/test_grace_chain_repair.py` is now executed by the named
`aegis / scale-os-controls` check.

## 2. OSV workflow startup

The queued startup-failure alert was also stale against the current baseline.

The current workflow:

- starts successfully on pull requests;
- uses exact reusable workflow version `v2.3.8`;
- declares the required Actions, contents, and security-event permissions;
- has separate pull-request and scheduled/push jobs.

The named Scale OS check statically parses the workflow and denies changes that remove
required triggers, permissions, recursive scan arguments, or exact semantic-version pins.
This complements the actual OSV reusable-workflow execution; it is not a substitute for a
vulnerability result.

## 3. Explicit public-table RLS posture

The operator selected a service-only posture for:

- `public.access_grants`;
- `public.analytics_events`;
- `public.purchases`;
- `public.swarm_memory`.

Migration `explicit_service_only_rls_policies` was applied to Supabase project
`rwehltdwpsncnwxzkwik`. Each table now has a restrictive `FOR ALL` policy for
`anon, authenticated` with `USING (false)` and `WITH CHECK (false)`.

`service_role` access remains available through PostgreSQL `BYPASSRLS` semantics.
The post-migration Supabase security-advisor result contains zero lints. The source-equivalent
migration is committed at
`supabase/migrations/20260719090000_explicit_service_only_rls_policies.sql`.

## 4. Cognitive manifest mainline migration

The prior generator, schema, and workflow existed only on a stale non-mainline branch.
The migrated implementation:

- hashes every repository `SKILL.md` by raw bytes;
- emits deterministic `.claude.json` and `skill-hashes.sha256` anchors;
- binds each branch manifest to the current mainline parent-state hash;
- excludes wall-clock input;
- records `GITHUB_OIDC_ATTESTATION` as the only admitted signature mode;
- refreshes branch anchors after repository changes.

## 5. Automaton-2 enforcement

The `aegis / automaton-2` check denies:

- parent-state mismatch;
- skill digest or size mismatch;
- missing or repository-escaping skill evidence;
- JSON-schema violations;
- state-hash mismatch;
- deterministic replay divergence;
- stale `skill-hashes.sha256` output;
- execution without the GitHub Actions OIDC authority environment.

An admitted run emits a deterministic Automaton-2 receipt, uploads it as a retained artifact,
and attests the receipt and both cognitive anchors through `actions/attest@v4`.

The implementation includes negative and determinism tests for all five originally queued
failure classes.

## 6. Required-check boundary

The repository now exposes a stable check context named `aegis / automaton-2` suitable for
branch rules and merge queues. This change set does not claim that a GitHub branch ruleset was
modified unless the repository administration API records that separate configuration change.

## 7. PR #216 posture

PR #216 is currently mergeable and no longer a draft. Its claims-ledger additions correctly
separate verified primitive parity from proposed full tri-language structure parity. Its five
MCP resources are read-only and key-free.

It remains subject to current-main admission, Automaton-2 validation, MCP build and resource
regression tests, and exact-head repository gates before merge. External Vercel build-rate
limits are capacity failures and are not evidence of a repository code failure.
