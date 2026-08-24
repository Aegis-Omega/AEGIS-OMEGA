# UCI-3 Provider Contribution Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add provider-session identity and content-addressed provider contribution evidence to the UCI spine without allowing provider output, lease ownership, contribution existence, or evidence-store membership to become authority.

**Architecture:** UCI-3 stacks on the UCI-1 collective work graph and UCI-2 durable provider claim lease. A provider contribution is accepted only while the exact current lease is held under the lease-store lock, is bound to the exact graph/work node/policy/authority epoch/target/pre-state, is stored content-addressed, and is serialized with a constant `NON_AUTHORITATIVE_EVIDENCE` authority marker. Contribution storage has its own monotonic state root and fail-closed closed-schema boundary. Provider/session identity is identity only and never authorization.

**Tech Stack:** TypeScript, Node.js crypto/fs, existing RFC8785/JCS helper, Vitest, JSON Schema Draft 2020-12, GitHub Actions exact-head witness.

**Spec:** `docs/superpowers/specs/2026-08-19-universal-collective-intelligence-kernel-v1-design.md`

## Global Constraints

- Provider/model output is evidence only and never authority.
- Session bootstrap semantics remain `IDENTITY_ONLY_NOT_AUTHORIZATION`.
- UCI-3 may claim only D0/D1/D2 work already admitted into the graph and currently held by an unexpired UCI-2 scheduling lease.
- D3 remains operator-approval-bound upstream; D4 is never provider-claimable.
- Contribution commit MUST bind exact `graph_id`, `work_node_id`, `intent_digest`, `policy_commitment`, `authority_epoch`, `target_commitment`, `pre_state_commitment`, lease owner, generation, and fencing token.
- Stale lease holders MUST NOT commit even if their contribution bytes are otherwise valid.
- Unknown serialized fields at session, artifact, contribution-record, and store boundaries MUST fail closed.
- Hash domains are versioned and distinct. Hash integrity does not prove proposition truth.
- No provider credential, API call, external mutation, production admission, or AGI claim is introduced in UCI-3.
- Continue on PR #275 integration spine; do not create another persistent feature branch.

---

### Task 1: Lease-locked execution primitive

**Files:**
- Modify: `sovereign-omega-v2/src/collective/provider-claim-lease.ts`
- Modify: `sovereign-omega-v2/test/unit/collective/provider-claim-lease.test.ts`

**Interfaces:**
- Consumes: `CurrentLeaseInputV1`, `DurableProviderClaimLeaseV1`.
- Produces: `withCurrentLease<T>(input: CurrentLeaseInputV1, operation: (lease: DurableProviderClaimLeaseV1) => T): T`.

- [ ] **Step 1: Write failing tests**

Add tests proving: the callback runs for the current lease; expired/wrong-owner/wrong-generation/wrong-fence never run the callback; a lease replacement cannot interleave while the callback holds the lease-store lock.

- [ ] **Step 2: Run focused tests and verify RED**

Run:
`npm test -- --run test/unit/collective/provider-claim-lease.test.ts`

Expected: FAIL because `withCurrentLease` does not exist.

- [ ] **Step 3: Implement minimal lock-held verifier**

Implement `withCurrentLease` by entering the existing `exclusive` critical section, loading current state, checking the same graph/node/time/identity/generation/fence/binding invariants as `assertCurrentLease`, and invoking `operation(current)` before releasing the lock. Refactor shared current-lease checks only where needed to avoid semantic divergence.

- [ ] **Step 4: Verify GREEN**

Run the focused UCI-2 tests, then typecheck.

- [ ] **Step 5: Commit**

Commit message: `feat(uci): add lease-locked provider contribution primitive`.

---

### Task 2: Provider session identity contract

**Files:**
- Create: `sovereign-omega-v2/src/collective/provider-contribution.ts`
- Create: `sovereign-omega-v2/test/unit/collective/provider-contribution.test.ts`

**Interfaces:**
- Produces `ProviderSessionIdentityV1` with: `schema_version`, `session_kind`, `provider`, `model`, `session_id`, `repository`, `head_sha`, `capability_ids`, `policy_commitment`, `authority_epoch`, `skill_catalog_root`, `organism_state_root`, `authority`.
- Constant authority marker: `IDENTITY_ONLY_NOT_AUTHORIZATION`.
- Produces `validateProviderSessionIdentity(session)`.

- [ ] **Step 1: Write failing tests**

Cover exact-key rejection, malformed identities/hashes, unsorted or duplicate capability IDs, stale policy/authority mismatch when checked against a graph, provider not in `allowed_providers`, and injected `permit`, `execute`, `decision_receipt`, or `effect_receipt` fields.

- [ ] **Step 2: Verify RED**

Expected: missing `provider-contribution` module.

- [ ] **Step 3: Implement minimal session validator**

Use bounded identity regexes and lower-case SHA-256/Git hash validation. Keep repository HEAD and roots as identity/provenance bindings only.

- [ ] **Step 4: Verify GREEN**

Run focused tests + typecheck.

- [ ] **Step 5: Commit**

Commit message: `feat(uci): add provider session identity boundary`.

---

### Task 3: Content-addressed evidence store and contribution record

**Files:**
- Modify: `sovereign-omega-v2/src/collective/provider-contribution.ts`
- Modify: `sovereign-omega-v2/test/unit/collective/provider-contribution.test.ts`

**Interfaces:**
- Produces `ProviderContributionArtifactV1` with constant kind, `sha256`, media type, byte length, UTF-8 content, and `authority: NON_AUTHORITATIVE_EVIDENCE`.
- Produces `ProviderContributionRecordV1` bound to graph/work/session/lease/artifact and contribution-store pre-state.
- Produces `FileProviderContributionStoreV1` with `prepareContribution`, `recordTextContribution`, `getArtifact`, `getRecord`, `stateRoot`.
- Maximum UTF-8 text contribution: `262144` bytes.
- Allowed media: `text/plain`, `text/markdown`, `application/json`.

- [ ] **Step 1: Write failing tests**

Cover content addressing, empty/oversize/media rejection, tamper detection, idempotent identical content, exact work-node binding, provider/session mismatch, provider not allowed by node, stale contribution-store root, stale lease, replacement generation/fence, and no status/authority promotion.

- [ ] **Step 2: Verify RED**

Expected: missing store/record APIs.

- [ ] **Step 3: Implement minimal store**

Artifact digest = SHA-256 of raw UTF-8 bytes. Store state uses a separate JCS domain and exact-key validation. `recordTextContribution` MUST execute inside `leaseStore.withCurrentLease(...)`, then inside the contribution-store lock, verify expected contribution-store root, persist artifact + record, and return a record whose authority is only `NON_AUTHORITATIVE_EVIDENCE`.

- [ ] **Step 4: Verify GREEN**

Run UCI-1 regression + UCI-2 lease suite + UCI-3 contribution suite + typecheck + build.

- [ ] **Step 5: Commit**

Commit message: `feat(uci): add content-addressed provider contribution evidence`.

---

### Task 4: Closed JSON schemas and falsification vectors

**Files:**
- Create: `schemas/collective/provider-session-identity-v1.schema.json`
- Create: `schemas/collective/provider-contribution-artifact-v1.schema.json`
- Create: `schemas/collective/provider-contribution-record-v1.schema.json`
- Create: `schemas/collective/provider-contribution-store-v1.schema.json`
- Create: `sovereign-omega-v2/test/unit/collective/provider-contribution-schema.test.ts`
- Create: `test-vectors/collective-intelligence/uci-3-provider-contribution-v1.json`
- Create: `sovereign-omega-v2/test/vectors/uci-3-provider-contribution-vectors.test.ts`

- [ ] **Step 1: Write schema/vector tests first**

Require `additionalProperties: false` at every object boundary. Falsifiers include: authority promotion, unknown receipt injection, stale lease generation, wrong fence, stale store root, wrong work node, wrong provider/session, tampered content digest, malformed policy/root binding, and oversized evidence.

- [ ] **Step 2: Verify RED only because schemas/vector corpus are absent**

- [ ] **Step 3: Add closed Draft 2020-12 schemas and corpus**

- [ ] **Step 4: Run the complete UCI focused suite twice for deterministic replay**

- [ ] **Step 5: Commit**

Commit message: `test(uci): close provider contribution evidence contracts`.

---

### Task 5: Exact-head witness and native UCI-3 admission

**Files:**
- Update `tarikskalic33/info` exact-head witness to run UCI-1/UCI-2/UCI-3, typecheck, build, and dependency audit.
- Rotate `.aegis/experiments/uci-2-provider-claim-lease-v1.json` atomically to `.aegis/experiments/uci-3-provider-contribution-evidence-v1.json` only after the implementation head is GREEN.
- Update PR #275 body with exact SHA, native admission run/artifact digest, external witness run/artifact digest, and explicit non-claims.

- [ ] **Step 1: External exact-head witness**

Prove exact candidate SHA and merge-base before tests. Require UCI-1/UCI-2/UCI-3 tests, strict typecheck, production build, and record npm-audit state.

- [ ] **Step 2: Rotate admission plan**

Keep exactly one experiment-plan diff relative to canonical main. Bind the plan to canonical parent and zero-cost T2 validation authority only.

- [ ] **Step 3: Native verification**

Require Experiment Admission, Constitutional Automaton, Automaton-2, Automaton-3, Kernel One, Scale OS Controls, Integration Ledger, OSV and Hadolint on the same SHA.

- [ ] **Step 4: Update PR checkpoint**

Set current checkpoint to UCI-3 only after both independent and native exact-head evidence are GREEN.

- [ ] **Step 5: Do not merge**

Leave merge as a separate operator decision.
