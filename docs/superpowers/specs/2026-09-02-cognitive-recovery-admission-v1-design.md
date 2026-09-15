# Cognitive Recovery Admission V1 — Design Specification

Date: 2026-09-02
Status: DESIGN_ONLY / NOT_IMPLEMENTED / AUTHORITY_NONE
Stack base: `#387@ca85c76be78bbd880674e01d28d12b3dd8b84430`
Canonical malformed main observed during incident: `d93e75e362e9d51fdf0732f3798e7d9bd34c4d13`

## 1. Problem statement

AEGIS currently has a verified **recovery-evidence** path but no separately trusted **recovery-admission** path.

The ordinary admission automata are intentionally fail-closed when the current canonical cognitive parent is malformed. That behavior must not be weakened. The recovery workflow on #387 proves a bounded counterfactual transition but is candidate-controlled and therefore deliberately has no signer, merge, deployment, or production authority.

The missing capability is a narrow control-plane mechanism that can consume an already-produced, exact-head recovery evidence package and determine whether one exceptional canonical recovery transition is admissible without turning candidate code into its own authority source.

This specification defines that missing boundary. It does **not** authorize a main mutation and does **not** activate repository rulesets, branch protection, billing, deployment, or GCP resources.

## 2. Non-negotiable invariants

1. **Normal admission remains unchanged.** Automaton-2/Automaton-3 continue to reject malformed-parent transitions.
2. **Recovery evidence is not recovery authority.** `RECOVERY_VERIFIED` can be a required input but can never itself authorize mutation.
3. **Candidate-controlled workflow code cannot self-sign.** No recovery candidate may select the verifier implementation, trusted root, source heads, or allowed file set used to admit itself.
4. **Exact-head binding.** All candidate, denied-base, recovery-parent, repair, writer, receipt, artifact, and trusted-root identities are exact cryptographic identifiers.
5. **Single-use scope.** A recovery admission is valid for one exact transition tuple only; it is non-transferable to later candidate SHAs.
6. **No authority widening.** Recovery admission restores the previously admitted cognitive control surface; it cannot add unrelated runtime, provider, deployment, billing, or repository-governance authority.
7. **Fail closed on unavailable platform governance.** Repository-side policy files do not substitute for live GitHub ruleset/branch-protection state.
8. **No merge by verifier.** V1 emits an admission decision/receipt. A separate explicitly authorized mutation step is required to alter `main`.
9. **No GCP coupling.** Recovery admission is independent of GCP. GCP remains disabled and authority `NONE` during this incident.
10. **RH remains outside this mechanism.** Recovery admission grants no mathematical authority and cannot affect the status `RIEMANN_HYPOTHESIS = NOT_PROVEN`.

## 3. Current evidence roots

The design is parameterized, but the current incident has the following observed evidence anchors:

- trusted pre-incident admitted control-plane SHA: `fe7582bf05d7a7242cf8c2f4949b4ac84bf056c9`;
- recovery parent SHA: `1bc8ceff51abe4e8142ef93dde1af316b8bf014d`;
- malformed denied base SHA: `d93e75e362e9d51fdf0732f3798e7d9bd34c4d13`;
- exact zero-parent repair: `#385@495fccdded0d9f5cdef2aac2ac5bbd8465063cf1`;
- retained recovery candidate: `#387@ca85c76be78bbd880674e01d28d12b3dd8b84430`;
- zero-parent validator blob: `3e79b6208e20331d0e379d2bb3f2bb3ab49f1384`;
- zero-parent regression-test blob: `9fab71959b073f485ccf9a74612fbc9ce93f3433`;
- production writer workflow blob verified against clean-room #388: `6f5526671ede8c099cc535a1eebfe94ed6f869ff`;
- reproduced denied Automaton-2 receipt: `64cece801823fe2eab573961ec8cefe4887aecc6a120d0297a0c88d530feb359`;
- counterfactual recovered-anchor Automaton-2 receipt: `596d0742a52f1705bf112daa36e437afe603b8ed5c2b655fbeafc750a0296d06`;
- bounded recovery evidence receipt: `991ec011cf77e268724363a7a0e94e512571dccf306372240712de3c52e00b47`;
- recovery artifact ID: `9841789562`;
- recovery artifact ZIP SHA-256: `fb9f7787607a99f219873f485c6870736094a86a29d29a4664c084a64e1716c6`.

These values are incident evidence, not permanent configuration. A verifier must take them from a base-owned admission request or immutable verifier configuration and must reject any candidate attempt to rewrite them.

## 4. Trust split

### 4.1 Candidate evidence plane

May:
- run deterministic tests;
- produce recovery evidence artifacts;
- prove exact Git ancestry and blob identity;
- reproduce the denied base;
- demonstrate a counterfactual recovered transition;
- emit `AEGIS_COGNITIVE_RECOVERY_RECEIPT_V1` with `production_admission = NONE`.

May not:
- sign its own admission;
- choose its own trusted root;
- mutate main;
- activate rulesets/protection;
- grant itself deployment/provider authority.

### 4.2 Base-owned admission plane

The admission verifier must execute from a verifier definition that the candidate cannot modify for the decision being evaluated. Suitable realizations include, in decreasing preference:

1. a workflow already present on an independently trusted/default-branch control-plane commit and triggered with an exact immutable request;
2. an externally operated verifier whose code digest and identity are pinned in the repository and whose result is imported as a signed receipt;
3. a manual operator-gated offline verification procedure that emits a content-addressed receipt, until a base-owned hosted verifier can be established.

A pull-request workflow whose implementation comes from the recovery candidate is **not** sufficient.

## 5. Recovery admission request

Define `RecoveryAdmissionRequestV1` with at least:

```text
schema_version
request_id
repository_id
trusted_control_plane_sha
recovery_parent_sha
denied_base_sha
candidate_sha
zero_parent_repair_sha
zero_parent_validator_blob
zero_parent_test_blob
writer_workflow_blob
recovery_receipt_hash
denied_receipt_hash
counterfactual_admission_receipt_hash
recovery_artifact_digest
expected_manifest_blob
expected_skill_hashes_blob
expected_recovery_state_hash
allowed_changed_paths[]
requested_transition = COGNITIVE_CANONICAL_RECOVERY
requested_authority = RESTORE_PREVIOUSLY_ADMITTED_COGNITIVE_CONTROL_SURFACE
expires_at
operator_approval_digest
```

The request must be content-addressed. Any field change creates a new request identity and requires a fresh decision.

## 6. Verifier algorithm

The verifier must independently perform all of the following:

### Gate R0 — request integrity

- schema-valid request;
- content digest matches request ID;
- repository identity matches expected repository;
- request not expired;
- no duplicate/replayed successful request ID.

### Gate R1 — trusted-root binding

- trusted control-plane SHA exists;
- its required verifier/workflow/manifest/hash blobs match pinned admitted values;
- recovery parent descends from that trusted root according to the declared incident topology;
- denied base is the exact malformed canonical state named by the request.

### Gate R2 — candidate ancestry

- candidate is an exact descendant of the required zero-parent repair when that repair is declared;
- candidate contains the exact pinned repair blobs;
- candidate contains the exact pinned writer blob when writer restoration is in scope;
- no force-spliced equivalent-looking file may substitute for the pinned ancestry+blob conditions.

### Gate R3 — bounded diff

Compute the full denied-base→candidate changed-path set mechanically.

Reject if any path is outside the base-owned allowlist. The allowlist is part of the admission request/verifier configuration, not candidate prose.

For each allowed path classify it as:
- verifier-generated anchor state;
- pinned semantic repair;
- pinned recovery verifier/test;
- pinned writer hardening;
- explicit open obligation.

Open obligations deny V1 admission.

### Gate R4 — recovery evidence reproduction

The admission plane must reproduce or independently verify:

- malformed denied base produces the expected DENIED receipt;
- candidate anchors validate counterfactually under trusted pre-incident Automaton-2 bytes;
- bounded recovery receipt hash matches;
- recovery artifact digest matches;
- artifact internal hashes match expected constituent receipts.

Reading a candidate-provided string saying `RECOVERY_VERIFIED` is insufficient.

### Gate R5 — authority firewall

Reject if the candidate or request:
- widens execution/deployment/network/secrets authority;
- changes GCP/provider enablement or budgets;
- grants merge authority to the writer;
- alters mathematical claim authority;
- alters unrelated repository governance;
- introduces any signer whose identity is not base-owned and pinned.

### Gate R6 — live platform governance

Immediately before a decision intended for canonical mutation, query live GitHub governance and require the configured recovery governance predicate.

For the current repository, a disabled ruleset or unprotected/unobservable required-check policy is a DENY condition unless the operator explicitly adopts a separately documented emergency recovery policy whose authority is external to this candidate.

A repository file that says enforcement should be enabled does not satisfy this gate.

### Gate R7 — operator approval

The exact request digest and exact candidate SHA require explicit operator approval. Approval for one SHA cannot be transferred to a generated-state child or later commit.

The verifier binds the approval digest into its receipt.

## 7. Output receipt

On success emit `AEGIS_COGNITIVE_RECOVERY_ADMISSION_RECEIPT_V1`:

```text
receipt_kind
schema_version
request_digest
repository_id
candidate_sha
denied_base_sha
trusted_control_plane_sha
recovery_parent_sha
recovery_receipt_hash
writer_workflow_blob
platform_governance_observation
operator_approval_digest
verified_gates[]
violations[]
outcome = RECOVERY_ADMISSION_GRANTED
scope = ONE_EXACT_CANONICAL_RECOVERY_TRANSITION
authority = RECOVERY_ADMISSION_ONLY
mutation_authority = NONE
issued_at
verifier_identity
verifier_code_digest
receipt_hash
```

On failure emit the same bounded structure with:

```text
outcome = DENIED
mutation_authority = NONE
```

The admission receipt itself **still does not mutate main**.

## 8. Separate mutation gate

Canonical mutation is a distinct operation `ApplyCognitiveRecoveryV1` and is not part of the verifier.

It may execute only when all are true at invocation time:

1. exact admission receipt is valid and unexpired;
2. admission receipt candidate SHA equals mutation target SHA;
3. current main equals the receipt denied-base SHA (compare-and-swap semantics);
4. live governance satisfies the recovery mutation policy;
5. explicit operator approval covers the exact mutation;
6. no newer main commit has appeared;
7. mutation method is non-force and preserves the incident/recovery Git history;
8. post-mutation workflows are scheduled against the new exact main head.

If current main differs by even one commit, abort and issue a new request.

V1 must not contain an autonomous merge loop.

## 9. Post-recovery verification

After canonical recovery mutation, the system must establish a fresh ordinary authority chain rather than continuing indefinitely on recovery semantics:

1. regenerate cognitive anchors through the single canonical writer if required;
2. run standard Automaton-2 at the new exact main head;
3. run Automaton-3 and all normal required repository gates;
4. verify live repository enforcement;
5. emit ordinary exact-head admission/evidence receipts;
6. mark recovery mode CLOSED only after the normal chain is healthy.

Recovery authority must not become a permanent alternate admission route.

## 10. Threat model / falsifiers

The implementation is invalid if any of these tests can be made to pass:

1. Candidate changes its recovery verifier and still self-admits.
2. Later candidate SHA reuses an older admission receipt.
3. Same files with different Git ancestry bypass exact repair binding.
4. Repair ancestry is correct but one pinned blob differs and admission still succeeds.
5. An unrelated file is added to the recovery diff and admission succeeds.
6. Artifact ID matches but artifact digest differs and admission succeeds.
7. Repository ruleset is disabled but verifier reports platform governance GREEN.
8. Candidate enables GCP/provider billing/deployment and recovery still succeeds.
9. Writer gains main-target or unrestricted push authority and recovery still succeeds.
10. Operator approval names a different request digest or candidate SHA and recovery succeeds.
11. Main changes after approval but before mutation and mutation proceeds.
12. Recovery receipt is GREEN but the admission verifier cannot reproduce the evidence and still grants admission.
13. Recovery mechanism changes `RIEMANN_HYPOTHESIS = NOT_PROVEN` or any scientific authority classification.

## 11. Proposed implementation layout — not yet authorized

No implementation files are created by this design commit. If approved, the first implementation slice should be RED-only and isolated from canonical mutation:

```text
schemas/cognitive-recovery-admission-request.v1.schema.json
schemas/cognitive-recovery-admission-receipt.v1.schema.json
scripts/validate-cognitive-recovery-admission.py
sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py
```

The initial validator must be offline/deterministic and `mutation_authority = NONE`.

A hosted/base-owned signer is a later slice and must not be implemented until the trust-root execution location is independently established.

`ApplyCognitiveRecoveryV1` is a separate later slice requiring explicit operator approval and live platform-governance support.

## 12. GCP sequencing

Hybrid Sovereign GCP Plane work remains queued behind canonical control-plane recovery.

Allowed before recovery closes:
- read-only audit of existing Vertex/Gemini code;
- design/specification work;
- model/capability research;
- disabled-by-default interface design.

Not allowed before recovery closes:
- deploy Agent Runtime;
- create/relink billable GCP resources;
- enable Gemini provider by default;
- store canonical Tier-4 knowledge in provider memory;
- create cloud identities/secrets as a substitute for repository recovery.

The eventual GCP plane remains provider/execution infrastructure with raw authority `NONE`.

## 13. Current disposition

```text
RECOVERY_EVIDENCE             = VERIFIED_AT_EXACT_HEAD (#387@ca85c76...)
RECOVERY_ADMISSION_DESIGN     = SPECIFIED
RECOVERY_ADMISSION_VALIDATOR  = NOT_IMPLEMENTED
RECOVERY_SIGNER               = NOT_ESTABLISHED
MUTATION_AUTHORITY            = NONE
PLATFORM_ENFORCEMENT          = NOT_ESTABLISHED / previously observed disabled
CANONICAL_MAIN_RECOVERY       = NOT_ADMITTED
GCP_DEPLOYMENT                = DISABLED / NOT_AUTHORIZED
RIEMANN_HYPOTHESIS            = NOT_PROVEN
```
