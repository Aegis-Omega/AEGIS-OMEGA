# Automaton-3 PR-1 Transition Identity and Receipt Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement PR-1 SafeIncompleteness: first-class transition binding plus nominally and serially distinct decision/execution/effect receipt types, while keeping effect observation, complete verification, atomic admission, and valid effect-receipt production unavailable.

**Architecture:** Add a focused transition/receipt module instead of expanding the already-large Automaton-3 authority module. Canonical authority producers will emit a new DecisionReceipt alongside the legacy MutationReceiptV1; the legacy artifact remains compatibility-only and cannot satisfy effect evidence. EffectReceipt is schema/type-defined but has no public generic constructor or producer.

**Tech Stack:** Python 3.12 stdlib dataclasses/hashlib/json, JSON Schema draft 2020-12, existing GitHub Actions Automaton-3 workflow.

**Spec:** Frozen conversation contract: `Authorization success can no longer masquerade as mutation or effect success.`

## Global Constraints

- Exact parent: `main@32b7eb6a37fb69d19dd80189390b6641c5004ef1`.
- `DecisionOutcome ∈ {PERMIT, DENY, DEFER}` and only `PERMIT` satisfies decision authority.
- `DEFER -> WAITING` is allowed; `DEFER -> EXECUTE` is forbidden.
- Receipt discriminators are mandatory and JSON-schema `const`-bound.
- Receipt hash domains are distinct: `AEGIS_DECISION_RECEIPT_V1`, `AEGIS_EXECUTION_RECEIPT_V1`, `AEGIS_EFFECT_RECEIPT_V1`.
- `LegacyMutationReceiptV1` remains format-compatible but is `DECISION_DERIVED / NOT_EFFECT_PROOF`.
- No authorization-derived artifact may satisfy `V_effect`.
- EffectReceipt schema is defined; generic producer is forbidden; adapter-backed production is not implemented.
- Missing EffectReceipt never falls back to legacy success.
- PR-1 must end in `SafeIncompleteness`: TransitionBinding/ReceiptSeparation implemented, EffectObservation/CompleteVerification/AtomicAdmission not implemented.
- No claim that EffectBoundClosure or `C_implementation` is established.

---

### Task 1: Write PR-1 falsification tests first

**Files:**
- Modify: `sovereign-omega-v2/python/tests/test_automaton3.py`

**Interfaces:**
- Consumes future symbols from `harness.sdk.transition_receipts`.
- Produces failing tests for nominal receipt separation, transition anti-splicing, DEFER non-authority, forbidden EffectReceipt construction, and legacy no-fallback.

- [ ] Add tests for: legacy SUCCEEDED is not effect evidence; PERMIT does not imply execution success; execution success does not imply effect success; DEFER never satisfies decision verification; cross-transition splicing fails; wrong action/nonce/fence/verifier-policy/admission-policy binding fails; caller cannot construct EffectReceipt; missing effect evidence has no legacy fallback; legacy receipt remains reproducible.
- [ ] Open draft PR to trigger `aegis / automaton-3` against the tests-only commit.
- [ ] Confirm RED because the new transition/receipt API does not yet exist.

### Task 2: Implement transition binding and receipt types

**Files:**
- Create: `harness/sdk/transition_receipts.py`
- Create: `schemas/transition-identity-envelope.v1.schema.json`
- Create: `schemas/decision-receipt.v1.schema.json`
- Create: `schemas/execution-receipt.v1.schema.json`
- Create: `schemas/effect-receipt.v1.schema.json`

**Interfaces:**
- Produces `TransitionIdentity`, `DecisionReceipt`, `ExecutionReceipt`, `EffectReceipt`, `decision_satisfies_authority`, `verify_transition_binding`, `accept_effect_evidence`, and deterministic policy/fence/delegation/capability commitment helpers.
- `EffectReceipt` must be `init=False` with no public factory in PR-1.

- [ ] Implement exact canonical field validation and `TransitionIdentity.root` under `AEGIS_TRANSITION_ID_V1`.
- [ ] Add nominal discriminators: `DECISION_RECEIPT_V1`, `EXECUTION_RECEIPT_V1`, `EFFECT_RECEIPT_V1`.
- [ ] Domain-separate all receipt roots.
- [ ] Implement DecisionReceipt outcomes `PERMIT|DENY|DEFER`; only PERMIT returns true from `decision_satisfies_authority`.
- [ ] Require ExecutionReceipt execution-instance identity; do not expose any effect-success predicate.
- [ ] Define EffectReceipt fields but make direct construction unavailable.
- [ ] Implement `verify_transition_binding` to recompute τ and reject mixed-transition receipts.
- [ ] Implement `accept_effect_evidence` so legacy/decision/execution artifacts are always false in PR-1.
- [ ] Run Automaton-3 tests until Task 1 turns GREEN.

### Task 3: Separate canonical authority producers without breaking legacy compatibility

**Files:**
- Modify: `harness/sdk/authority_client.py`
- Modify: `scripts/automaton3-authority.py`

**Interfaces:**
- Both paths continue producing the existing legacy MutationReceiptV1 where compatibility requires it.
- Both additionally emit `decision_receipt` and `transition_id` derived from the same policy decision and PR-1 transition binding.
- Neither path produces EffectReceipt or authoritative effect admission.

- [ ] Build transition identity from exact source commit, pre-state commitment, identity root, delegation/capability commitments, action digest, nonce/fence binding, and versioned verifier/admission policy commitments.
- [ ] Map legacy `ADMITTED -> PERMIT`, `DENIED -> DENY`; no implicit execution/effect success conversion.
- [ ] Keep existing `receipt_root` / `mutation_receipt` compatibility output unchanged.
- [ ] Add explicit new `decision_receipt` and `decision_receipt_root` output.
- [ ] Verify legacy output remains reproducible and cannot be passed as effect evidence.

### Task 4: Exact-head conformance metadata and CI witness

**Files:**
- Modify: `scripts/run-automaton3-tests.py`
- Modify: `scripts/validate-automaton3.py`
- Modify: `.github/workflows/automaton-3.yml`

**Interfaces:**
- Candidate manifest includes the new transition module and schemas.
- Test-count expectation matches the enlarged falsification suite.
- Workflow schema validation and attestation include the new receipts.

- [ ] Update expected Automaton-3 test count to the observed new exact count.
- [ ] Add new module/schemas to exact-candidate key-file manifest.
- [ ] Add new schemas to attested subject paths.
- [ ] Run full draft-PR checks and inspect failures.
- [ ] Fix only PR-1 scope failures.
- [ ] Record exact head SHA and CI results; do not promote EffectBoundAdmission.

## Required postcondition

```text
TRANSITION_BINDING = IMPLEMENTED_AND_TESTED   # only if exact-head CI proves it
RECEIPT_SEPARATION = IMPLEMENTED_AND_TESTED   # only if exact-head CI proves it
EFFECT_RECEIPT_SCHEMA = DEFINED
VALID_EFFECT_RECEIPT_PRODUCTION = UNAVAILABLE
EFFECT_OBSERVATION = NOT_IMPLEMENTED
COMPLETE_VERIFICATION = NOT_IMPLEMENTED
ATOMIC_ADMISSION = NOT_IMPLEMENTED
EFFECT_BOUND_ADMISSION = UNAVAILABLE
C_IMPLEMENTATION = FALSE
```

Acceptance sentence: **Authorization success can no longer masquerade as mutation or effect success.**
