# Claim Promotion Admission Gate v1 — Design

**Baseline:** `AEGIS_Master_Notebook.md v0.4` digest `457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404`

**Exact source base:** `6eb2ac201bbe60ebaa9cebad714b8696683772e8`

**Goal:** turn the locked v0.4 epistemic policy into a fail-closed CI admission boundary so a verified ledger claim cannot be created or materially mutated without an exact-head, digest-bound promotion tuple and complete verified transition chain.

## Authority invariant

No claim may possess greater epistemic authority than the weakest verified transition required to establish it. Documentation can describe the invariant, but only the CI/admission gate grants enforcement authority.

For v1, any new or changed `Verified` claim in `docs/claims.json` requires a promotion manifest. A manifest with an `OPEN`, `NOT_ESTABLISHED`, missing, stale, or digest-mismatched required transition cannot yield `ADMIT`.

`TARGET_OPEN` and `NOT_ESTABLISHED` may be represented as research state, but their admission decision must remain `DEFER`; they cannot be laundered into a `Verified` ledger mutation.

## Immutable promotion tuple

Every promotion manifest carries these required top-level fields:

- `claim_id`
- `baseline_digest`
- `source_head_sha`
- `claim_statement_digest`
- `red_contract_digest`
- `implementation_digest`
- `negative_control_receipt_digest`
- `ci_run_identity`
- `verification_receipt_digest`
- `admission_policy_digest`
- `final_epistemic_status`
- `admission_decision`

The manifest also contains explicit local bindings identifying the artifacts from which each digest must be recomputed, plus a transition list.

## Digest semantics

1. Claim statement digest: `SHA-256(RFC8785-JCS({claim_id, claim_statement}))`.
2. Red-contract and implementation bundle digests: sort bound repository paths lexicographically, hash each file's exact bytes with SHA-256, build `[{path,sha256}]`, RFC8785-canonicalize that array, then SHA-256 it.
3. JSON receipt and admission-policy digests: parse JSON, reject out-of-domain values, RFC8785-canonicalize, then SHA-256.
4. The baseline digest is an exact constant in the admission policy. A mismatch is a hard denial.

The gate ships its own strict RFC8785 implementation rather than inheriting authority from the current `canonicalize.ts` path. It sorts object names by UTF-16 code units, rejects `bigint`, `undefined`, non-finite numbers, functions, symbols, and sparse/undefined array entries.

## Required transition chain

The v1 policy requires exactly these transition identities for an admitted high-authority promotion:

`RED_CONTRACT -> IMPLEMENTATION -> NEGATIVE_CONTROLS -> EXACT_HEAD_CI -> ATTESTED_RECEIPT`

Each must be `VERIFIED`. Duplicate, missing, or unknown transition IDs fail closed.

## Exact-head rule

`source_head_sha` must be a full 40-hex Git commit that exists locally after `actions/checkout(fetch-depth: 0)` and is an ancestor of the promotion commit being evaluated. A non-existent or non-ancestor head is denied.

The promotion manifest is expected to be created after the implementation/evidence commit, avoiding self-referential commit hashes.

## Claims-ledger integration

The existing claims validator remains authoritative for structural ledger rules. The new gate is additive and specifically prevents promotion bypass.

On pull requests, the gate loads `docs/claims.json` at the base SHA and at HEAD. It requires a promotion manifest for:

- a newly added `Verified` claim;
- any existing claim whose tier changes to `Verified`;
- any material mutation of an already `Verified` claim object.

A promotion manifest is stored as `docs/claim-promotions/<claim_id>.json`.

## Epistemic status versus admission decision

Allowed epistemic statuses are:

- `MACHINE_BOUND`
- `EMPIRICAL`
- `EXTERNAL_ESTABLISHED`
- `TARGET_OPEN`
- `NOT_ESTABLISHED`

`ADMIT` is permitted only for the first three and only when every required transition is `VERIFIED`, every digest recomputes, the source head is valid, the baseline matches, and the policy digest matches. `TARGET_OPEN` and `NOT_ESTABLISHED` require `DEFER`.

## CI behavior

The workflow runs Node's built-in test runner first, then the promotion validator. Any error exits non-zero. No warning can promote a claim. There is no synthetic fallback, default receipt, placeholder digest, or missing-evidence substitution.

## Scope boundary

This build does not prove RH, biological nonclassicality, PQC integration, or any scientific claim. It enforces the provenance and promotion mechanics by which such claims may later become admissible.
