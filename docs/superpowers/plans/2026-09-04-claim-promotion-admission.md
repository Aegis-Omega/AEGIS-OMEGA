# Claim Promotion Admission Gate v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce fail-closed claim promotion for any new or materially changed `Verified` ledger claim using the locked v0.4 baseline, exact-head provenance, digest recomputation, negative controls, CI identity, and attested receipts.

**Architecture:** Add an independent claim-promotion validator beside the existing claims-ledger validator. The validator owns strict RFC8785 canonicalization for its receipt domain, recomputes all bound digests, validates exact-head ancestry, enforces transition completeness, and compares PR base versus HEAD to detect verified-claim promotions or mutations that require a manifest.

**Tech Stack:** Node.js 20, `node:test`, built-in `crypto`, `fs`, `path`, `child_process`; GitHub Actions; zero new npm dependencies.

**Spec:** `docs/superpowers/specs/2026-09-04-claim-promotion-admission-design.md`

## Global Constraints

- Baseline digest is exactly `457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404`.
- Exact source base is `6eb2ac201bbe60ebaa9cebad714b8696683772e8`.
- No production implementation before a hosted RED failure is observed.
- `ADMIT` requires every required transition to be `VERIFIED`.
- `TARGET_OPEN` and `NOT_ESTABLISHED` require `DEFER`.
- No mock/synthetic evidence may fill a missing artifact binding.
- No external runtime dependency may be added.

---

### Task 1: Hosted RED contract

**Files:**
- Create: `test/claim-promotion-admission.test.mjs`
- Create: `.github/workflows/claim-promotion-admission.yml`

**Interfaces:**
- Consumes: future module `scripts/lib/claim-promotion.mjs`.
- Produces: failing behavioral contract for strict JCS, authority leakage, digest binding, exact-head validation, and verified-claim mutation detection.

- [ ] **Step 1: Write failing tests**

Tests must import these future exports:

```js
canonicalizeJCSStrict(value)
sha256JCS(value)
computeBundleDigest(repoRoot, paths)
validatePromotionManifest({ repoRoot, manifest, policy, currentHead, isAncestor })
findVerifiedClaimMutations(baseClaims, currentClaims)
```

The suite must cover:

```text
UTF-16 ordering differs from Unicode code-point ordering
bigint rejected
undefined object field rejected
valid fully VERIFIED tuple -> ADMIT
OPEN required transition + MACHINE_BOUND/ADMIT -> reject
baseline digest mismatch -> reject
bound artifact digest mismatch -> reject
source head not ancestor -> reject
TARGET_OPEN + ADMIT -> reject
new Verified claim -> promotion required
mutated Verified claim -> promotion required
unchanged Verified claim -> no new promotion required
```

- [ ] **Step 2: Add PR workflow**

Run:

```bash
node --test test/claim-promotion-admission.test.mjs
```

The workflow intentionally references code that does not yet exist.

- [ ] **Step 3: Open draft PR and verify RED**

Expected hosted failure: `ERR_MODULE_NOT_FOUND` for `scripts/lib/claim-promotion.mjs` or equivalent missing-production-module failure.

- [ ] **Step 4: Record exact RED run ID in PR body**

Do not reinterpret unrelated infrastructure errors as a valid RED receipt.

---

### Task 2: Baseline and policy artifacts

**Files:**
- Create: `docs/research-control-baseline.v0.4.json`
- Create: `docs/claim-admission-policy.v1.json`
- Create: `docs/claim-promotion.schema.json`
- Create directory marker: `docs/claim-promotions/.gitkeep`

**Interfaces:**
- Produces policy constants consumed by the validator.

- [ ] **Step 1: Add immutable baseline descriptor**

It must contain the v0.4 digest, RH status `NOT_PROVEN_AT_CURRENT_CLOSURE`, and enforcement state `POLICY_LOCKED / BASELINE_BYTE_VERIFIED / ENFORCEMENT_PARTIALLY_IMPLEMENTED`.

- [ ] **Step 2: Add policy**

Require transitions:

```json
["RED_CONTRACT","IMPLEMENTATION","NEGATIVE_CONTROLS","EXACT_HEAD_CI","ATTESTED_RECEIPT"]
```

Admittable statuses:

```json
["MACHINE_BOUND","EMPIRICAL","EXTERNAL_ESTABLISHED"]
```

Deferred statuses:

```json
["TARGET_OPEN","NOT_ESTABLISHED"]
```

- [ ] **Step 3: Add structural schema**

Require all immutable tuple fields plus `claim_statement`, `bindings`, `required_transitions`, and `admission_decision`.

- [ ] **Step 4: Do not create a real promotion manifest yet**

Framework implementation must not fabricate evidence for any existing claim.

---

### Task 3: Minimal GREEN promotion core

**Files:**
- Create: `scripts/lib/claim-promotion.mjs`

**Interfaces:**
- Produces exactly the exports declared in Task 1.

- [ ] **Step 1: Implement strict JCS**

Use JavaScript default string-key sort, which is lexicographic UTF-16 code-unit order. Reject `undefined`, `bigint`, functions, symbols, sparse/undefined array items, and non-finite numbers.

- [ ] **Step 2: Implement digest helpers**

```js
sha256JCS(value)
computeBundleDigest(repoRoot, paths)
```

Bundle digest is SHA-256 over JCS of sorted `{path,sha256}` entries; individual file SHA-256 is over exact bytes.

- [ ] **Step 3: Implement manifest enforcement**

Return `{ok, decision, errors}`. Never throw for an invalid manifest; all invalid evidence becomes fail-closed errors.

Hard errors include:

```text
BASELINE_DIGEST_MISMATCH
POLICY_DIGEST_MISMATCH
CLAIM_STATEMENT_DIGEST_MISMATCH
RED_CONTRACT_DIGEST_MISMATCH
IMPLEMENTATION_DIGEST_MISMATCH
NEGATIVE_CONTROL_RECEIPT_DIGEST_MISMATCH
VERIFICATION_RECEIPT_DIGEST_MISMATCH
SOURCE_HEAD_INVALID
SOURCE_HEAD_NOT_ANCESTOR
MISSING_REQUIRED_TRANSITION
DUPLICATE_TRANSITION
UNKNOWN_TRANSITION
OPEN_REQUIRED_TRANSITION
AUTHORITY_LEAKAGE
TARGET_STATUS_MUST_DEFER
CI_RUN_IDENTITY_INVALID
```

- [ ] **Step 4: Implement verified-claim mutation detection**

A new `Verified`, a tier transition to `Verified`, or any canonical object change to an already `Verified` claim must be returned as requiring a promotion manifest.

- [ ] **Step 5: Run unit tests**

```bash
node --test test/claim-promotion-admission.test.mjs
```

Expected: PASS.

---

### Task 4: CLI and PR-base admission check

**Files:**
- Create: `scripts/validate-claim-promotion.mjs`

**Interfaces:**
- Consumes policy, baseline, current `docs/claims.json`, optional PR base SHA, and manifests in `docs/claim-promotions/`.
- Produces process exit `0` only when every required promotion is valid.

- [ ] **Step 1: Validate policy/baseline consistency**

The policy baseline digest must equal the baseline descriptor digest.

- [ ] **Step 2: Load PR base claims with git**

```bash
git show <base_sha>:docs/claims.json
```

If a supplied base SHA cannot be resolved, fail closed.

- [ ] **Step 3: Detect required promotions**

Use `findVerifiedClaimMutations`.

- [ ] **Step 4: Require one manifest per changed Verified claim**

Path is exactly:

```text
docs/claim-promotions/<claim_id>.json
```

Missing manifest is a hard error.

- [ ] **Step 5: Validate all supplied manifests**

A manifest for a claim not present in current ledger is rejected.

- [ ] **Step 6: Emit compact receipt-style summary**

Print baseline digest, current HEAD, required promotions, admitted promotions, deferred promotions, and errors.

---

### Task 5: CI GREEN and existing ledger composition

**Files:**
- Modify: `.github/workflows/claim-promotion-admission.yml`
- Modify: `.github/workflows/claims-ledger.yml`

**Interfaces:**
- Existing `scripts/validate-claims.mjs` remains unchanged in authority scope.

- [ ] **Step 1: Add CLI validation to new workflow**

For pull requests:

```bash
node scripts/validate-claim-promotion.mjs --base-sha "${{ github.event.pull_request.base.sha }}"
```

- [ ] **Step 2: Expand path filters**

Include promotion manifests, baseline, policy, schema, validator, tests, and `docs/claims.json`.

- [ ] **Step 3: Cross-wire the existing claims-ledger workflow**

Run the promotion validator after `validate-claims.mjs` when the event is a pull request. This prevents a branch-protection configuration that requires only the old workflow from silently bypassing the new gate once the workflow is selected as required.

- [ ] **Step 4: Re-run hosted CI**

Expected: unit tests PASS; promotion validator PASS when no Verified claim is being promoted by this implementation PR.

---

### Task 6: Exact-head verification and PR evidence

**Files:**
- No source changes unless verification finds a defect.

- [ ] **Step 1: Fetch current PR head SHA**
- [ ] **Step 2: Confirm both claim workflows are terminal GREEN on that exact SHA**
- [ ] **Step 3: Confirm branch diff contains no fabricated promotion manifest**
- [ ] **Step 4: Record RED run, GREEN run, exact head, and authority boundary in PR body/comment**

Final status may be stated only as:

```text
POLICY_LOCKED / BASELINE_BYTE_VERIFIED / MACHINE_ENFORCED_FOR_VERIFIED_LEDGER_PROMOTIONS
```

Do not generalize this to scientific proof, RH closure, PQC integration, or physical measurement admission.
