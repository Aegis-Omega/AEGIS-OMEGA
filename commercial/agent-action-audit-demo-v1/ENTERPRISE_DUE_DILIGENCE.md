# AEGIS Agent Action Boundary Audit — Enterprise Due-Diligence Pack V1

Status: COMMERCIAL_REVIEW_DRAFT  
Offer scope: one agreed tool-using workflow  
Authority effect: NONE

This document is an evidence-bound technical due-diligence summary for a prospective enterprise pilot. It is not a certification, legal opinion, compliance attestation, penetration-test report, or platform-wide security guarantee.

## 1. Service boundary

The Agent Action Boundary Audit examines one agreed workflow in the buyer's existing stack.

Typical review questions:

- Where can the workflow mutate external state?
- Which action classes require approval before execution?
- Is approval bound to the exact action and parameters?
- What happens when authority is missing, stale, expired, or denied?
- Can a controlled negative case demonstrate fail-closed or fail-open behavior?
- Is the resulting audit evidence bound to the authorized invocation and observed outcome?
- Which claims remain NOT_VERIFIED because evidence is missing?

The audit does not require adoption of AEGIS Ω.

## 2. Initial access model

Production access is not required for initial scoping.

Preferred initial inputs:

- a short workflow description;
- architecture or data-flow diagrams if available;
- representative logs or receipts with sensitive values removed;
- test or staging configuration;
- relevant policy/control descriptions;
- source code or a narrow repository excerpt when needed.

Do not send credentials, API keys, private keys, customer records, access tokens, production secrets, or regulated data during initial scoping.

If a later technical step requires controlled access, the exact access, purpose, duration, environment, and revocation path must be agreed before use.

## 3. Evidence taxonomy

Every reviewed control is classified as one of:

### DEMONSTRATED_FAIL_CLOSED

A controlled test demonstrates that the reviewed action is denied or prevented under the tested unauthorized condition.

### DEMONSTRATED_FAIL_OPEN

A controlled test demonstrates that the reviewed action can proceed under the tested condition where the expected control should have prevented it.

### NOT_VERIFIED

Available evidence is insufficient to establish either fail-closed or fail-open behavior.

NOT_VERIFIED is not automatically treated as a vulnerability.

## 4. Separation of claims

The audit evaluates these separately:

1. Policy intent — what the design or policy says should happen.
2. Pre-execution authorization — whether authorization exists before the action.
3. Action binding — whether authorization applies to the exact target and parameters.
4. Execution behavior — what actually happened.
5. Record integrity — whether evidence can be altered without detection.
6. Outcome correctness — whether the external system reached the intended state.

A hash, signature, receipt, or append-only record can support integrity or lineage claims. It does not by itself prove prior authorization, correct execution, or compliance.

## 5. AEGIS authority model used during the audit

AEGIS distinguishes internal/reversible work from consequential external effects.

Examples of internal/reversible classes:

- RESEARCH_READ
- ANALYZE
- DRAFT
- TEST
- EVAL
- PROPOSE

Examples of consequential classes:

- EXTERNAL_MESSAGE
- REPOSITORY_MUTATION
- MERGE
- DEPLOY
- PRODUCTION_CONFIG
- FINANCIAL
- LEGAL_COMMITMENT
- DELETE_DATA
- IDENTITY_OR_CREDENTIAL

Pipeline state, model output, provider selection, semantic memory, and task assignment do not independently grant consequential authority.

## 6. Credential handling

The audit does not require buyers to place raw credentials in prompts, documentation, receipts, or repository source.

Where a controlled runtime credential is required for a separately agreed test, the preferred design is server-side secret storage with the narrowest feasible scope and a separate presence/status signal rather than secret-value exposure.

AEGIS commercial materials must not request raw customer secrets during initial outreach or scoping.

## 7. Current AEGIS implementation status relevant to a pilot

The following statements are intentionally scoped.

### Implemented in source

- typed company action classes;
- exact consequential-action approval packets;
- evidence-authority handling;
- deterministic work-graph validation;
- lease/fencing logic;
- enterprise opportunity state machine;
- evidence-only mail-ingestion mapping;
- bounded follow-up policy;
- enterprise resource/credit admission policy;
- source-only Scale OS enterprise opportunity/resource persistence.

### Production status boundaries

- new enterprise opportunity/resource Scale OS migrations are SOURCE_ONLY_NOT_APPLIED;
- live OpenAI managed-session execution is NOT_PERFORMED in the current evidence chain;
- current GitHub-hosted exact-head workflow runs have repeatedly created jobs with no executed steps, so HOSTED_PASS is NOT_ESTABLISHED;
- no production deployment, merge, spend, customer credential ingestion, or authority expansion is established by the commercial demo.

These boundaries must be updated if new exact-head evidence supersedes them.

## 8. Buyer data boundary

The preferred pilot minimizes buyer data.

Initial review should use:

- sanitized examples;
- synthetic or test records;
- staging systems;
- narrow technical artifacts;
- metadata/evidence sufficient to test the control.

The pilot should not collect unrelated customer data.

Any additional data category should have a documented purpose before transfer.

## 9. Deliverables

For one agreed workflow, the standard technical output is:

1. Authority surface map.
2. Pre-mutation approval and action-binding review.
3. Controlled negative-test evidence where feasible.
4. Audit-record/receipt binding assessment.
5. Findings table using DEMONSTRATED_FAIL_CLOSED / DEMONSTRATED_FAIL_OPEN / NOT_VERIFIED.
6. Prioritized engineering remediation notes.
7. Evidence appendix identifying source, environment, version, and test scope.

## 10. What the audit does not claim

The audit does not by default establish:

- compliance with the EU AI Act, NIST AI RMF, ISO standards, SOC 2, or another framework;
- platform-wide security;
- correctness outside the reviewed workflow/version/configuration;
- absence of vulnerabilities not tested;
- production enforcement when only source, local, or staging evidence exists;
- legal suitability of the buyer's deployment.

## 11. Pilot acceptance boundary

A pilot finding is accepted only when its supporting evidence is bound to the exact reviewed scope.

The weakest verified transition limits the authority of the final claim.

A successful test of one component cannot be promoted into a system-wide claim.

## 12. Current buyer-side prerequisites

Before technical execution:

- identify one workflow;
- identify its highest-authority action;
- identify a representative non-production or bounded test path;
- identify the evidence the buyer can provide without exposing secrets;
- agree the technical scope and exclusions in writing;
- identify any access that would require separate approval.

Payment and audit start are separate observed events. Payment does not prove delivery has begun.
