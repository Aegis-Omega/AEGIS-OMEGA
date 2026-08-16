# AEGIS Ω Authority Control Plane v1 — Design

Date: 2026-08-16
Target branch: `feat/frontier-provider-mesh-v1` (PR #264)
Status: DESIGN APPROVED FOR SPECIFICATION; IMPLEMENTATION NOT YET CLAIMED

## 1. Objective

Turn the existing SOL frontier provider mesh into a product-shaped **Authority Control Plane for Agentic Systems** without creating a second authority evaluator.

The v1 contract is:

> Before an agent can act, AEGIS determines whether this exact execution identity is authorized to perform this exact action, on this exact resource, under this exact state. A successful external effect must then emit a replayable receipt bound to that prior authority decision.

The control plane is about **action/authority correctness**, not model-output correctness.

The following remain non-authoritative inputs:

- model text;
- model confidence;
- provider policy decisions that are not admitted by AEGIS;
- tool availability;
- agent intent;
- provider/model claims that they are authorized.

## 2. Existing load-bearing substrate

This design extends the current PR #264 implementation rather than replacing it.

Existing components that remain authoritative dependencies:

- `platform/sol/frontier/work_order.py`
  - validates proof-carrying work orders;
  - rejects D4;
  - requires evidence for D2/D3;
  - requires explicit operator approval for D3;
  - binds arguments digest, expected parent state, idempotency, cost and token ceilings.
- `sovereign-omega-v2/src/api/frontier-automaton3-verifier.ts`
  - delegates authority evaluation to the existing Automaton-3 path;
  - requires `ADMITTED` plus a valid `authority_receipt_root`;
  - does not create a second authority evaluator.
- `sovereign-omega-v2/src/api/frontier-inference-gateway.ts`
  - fail-closes malformed, stale, unauthorized, over-budget and provider-authority-violating requests;
  - already binds provider execution to a verified work order and authority receipt root.
- `sovereign-omega-v2/src/api/frontier-runtime.ts`
  - composes admitted provider transports and the frontier gateway.

Automaton-3 remains the sole authority root for v1.

## 3. Product boundary

The v1 public product surface consists of two logical operations:

### 3.1 `POST /v1/authority/check`

Purpose: produce an authority decision before any external effect.

Input must bind at minimum:

- execution identity;
- tenant / authority subject;
- action;
- resource / target;
- requested capability;
- requested tool closure;
- consequence class;
- arguments / payload digest;
- expected parent state root;
- topology / observation binding;
- risk policy context;
- cost and token ceilings;
- quota / entitlement context reference;
- operator approval reference when required;
- evidence references;
- idempotency key;
- freshness / expiry information.

Output state is exactly one of:

- `ADMITTED`
- `DENIED`
- `REVIEW_REQUIRED`

The response contains:

- deterministic `decision_digest`;
- `authority_receipt_root` when admitted;
- exact request/work-order digest binding;
- reason codes;
- admitted capability/tool closure;
- exact parent-state/topology binding;
- consequence class;
- expiry / freshness boundary;
- no provider-generated authority field.

`REVIEW_REQUIRED` is not executable authority.

### 3.2 `POST /v1/effects/execute`

Purpose: execute an external effect only under a still-valid admitted authority decision.

The execution path must re-bind and re-check:

- decision digest;
- authority receipt root;
- work-order digest;
- execution identity;
- action;
- resource / target;
- capability;
- arguments digest;
- expected parent state root;
- topology / freshness;
- idempotency key;
- cost / token / quota ceilings;
- consequence class;
- required operator approval.

Any mismatch causes fail-closed denial before provider/tool invocation.

## 4. Authority decision model

The v1 decision predicate is conceptually:

`ADMIT = identity ∩ capability ∩ resource_binding ∩ state_binding ∩ topology_freshness ∩ risk_policy ∩ budget_quota ∩ HITL_required ∩ evidence ∩ work_order_integrity`

This is a conjunction of necessary conditions. No model or provider output may satisfy or bypass a missing authority term.

### 4.1 Consequence classes

- `D0`: read-only / non-mutating; still identity- and scope-bound.
- `D1`: bounded low-risk mutation; must be fully work-order-bound.
- `D2`: requires evidence references.
- `D3`: requires evidence references plus explicit operator approval.
- `D4`: denied in v1.

### 4.2 Tool/capability closure

The authority check must operate on the transitive capability closure of the requested tool set, not only the named top-level tool.

Required invariant:

`Cl(T_requested) ⊆ AllowedCapabilities(authority_envelope)`

If closure cannot be established deterministically, the request is denied or sent to `REVIEW_REQUIRED`; it is never admitted by assumption.

### 4.3 Freshness

An admitted decision is valid only for the state/topology it binds.

The following invalidate execution authority:

- changed expected parent state root;
- stale topology or authority generation;
- changed resource binding;
- changed identity;
- changed action/capability;
- changed payload digest;
- expired decision;
- revoked/advanced lease or generation;
- changed budget/quota state where the budget gate requires fresh observation.

## 5. Decision artifact

Introduce one canonical product-level decision artifact, logically named `AuthorityDecisionV1`.

Minimum fields:

- `schema_version`;
- `decision_id`;
- `outcome`;
- `decision_digest`;
- `authority_receipt_root` when admitted;
- `work_order_digest`;
- `execution_identity_digest`;
- `action_digest`;
- `resource_digest`;
- `capability`;
- `tool_closure_digest`;
- `arguments_digest`;
- `expected_parent_state_root`;
- `topology_digest`;
- `consequence_class`;
- `budget_ceiling`;
- `quota_observation_digest` or explicit bounded equivalent;
- `operator_approval_reference` when applicable;
- `evidence_references`;
- `issued_at` or monotone issuance reference;
- `expires_at` or deterministic freshness boundary;
- `reason_codes`.

The digest is computed over the canonical decision payload excluding any self-referential digest field.

A decision is an authority witness, not proof that the downstream provider result is correct.

## 6. Effect receipt model

Every successful or attempted externally visible effect produces an `EffectReceiptV1`.

Minimum fields:

- `schema_version`;
- `receipt_id`;
- `decision_digest`;
- `authority_receipt_root`;
- `work_order_digest`;
- `execution_identity_digest`;
- `provider_or_tool`;
- `provider_operation_id` when available;
- `action_digest`;
- `resource_digest`;
- `arguments_digest`;
- `pre_state_digest`;
- `post_state_digest` or explicit `POST_STATE_UNAVAILABLE` status;
- `result_digest`;
- `status` (`SUCCEEDED`, `DENIED`, `FAILED`, `COMPENSATED` where supported);
- `cost_observed` / token usage when applicable;
- `parent_receipt_digest`;
- `receipt_digest`.

The receipt chain must make tampering, reordering and parent substitution detectable.

A provider/model response remains evidence only. Receipt creation does not upgrade provider output into authority.

## 7. Execution flow

1. Client/agent constructs a proof-carrying work order.
2. Authority endpoint validates request shape and work-order structure.
3. Identity, state, topology and approval observations are bound into the Automaton-3 envelope.
4. Automaton-3 evaluates the request.
5. Non-`ADMITTED` results produce no executable authority.
6. An admitted result is wrapped as `AuthorityDecisionV1` with deterministic digest and freshness boundary.
7. Effect endpoint receives the exact decision plus execution request.
8. Effect endpoint recomputes all relevant digests and verifies freshness.
9. Budget/quota/concurrency checks run before external invocation.
10. Only then is the admitted provider/tool transport invoked.
11. Result is checked for receipt-bindable metadata and authority escalation attempts.
12. Post-state/result evidence is collected.
13. `EffectReceiptV1` is emitted and chained.

## 8. API semantics and error handling

The control plane uses explicit machine-readable denial codes. Initial required classes:

- `IDENTITY_INVALID`
- `CAPABILITY_DENIED`
- `TOOL_CLOSURE_DENIED`
- `RESOURCE_BINDING_MISMATCH`
- `STATE_STALE`
- `TOPOLOGY_STALE`
- `WORK_ORDER_INVALID`
- `WORK_ORDER_MISMATCH`
- `DECISION_INVALID`
- `DECISION_EXPIRED`
- `DECISION_MISMATCH`
- `HITL_REQUIRED`
- `EVIDENCE_REQUIRED`
- `BUDGET_EXCEEDED`
- `QUOTA_EXCEEDED`
- `CONSEQUENCE_DENIED`
- `ADMISSION_UNAVAILABLE`
- `IDEMPOTENCY_CONFLICT`
- `PROVIDER_FAILURE`
- `PROVIDER_AUTHORITY_VIOLATION`
- `RECEIPT_FAILURE`

Authorization, metering, topology, receipt persistence or authority-evaluator unavailability must fail closed.

No fallback path may call the provider/tool after an authority subsystem failure.

## 9. Idempotency and replay

The idempotency fingerprint must include at minimum:

- identity digest;
- action digest;
- resource digest;
- capability;
- payload/arguments digest;
- expected parent state root;
- topology digest;
- work-order digest;
- decision digest.

Reusing one idempotency key for a different fingerprint is a hard conflict.

Replay verification must be able to establish whether the same bound request would reach the same authority decision under the same observation state.

## 10. Non-goals for v1

This slice does not:

- create a second authority evaluator beside Automaton-3;
- claim general intelligence or autonomous legal authority;
- make provider/model confidence authoritative;
- admit D4 effects;
- automatically grant new IAM permissions;
- provision credentials;
- perform DNS, billing or account mutations;
- guarantee semantic correctness of provider output;
- claim EU AI Act compliance solely from receipt generation;
- merge PR #264 to `main` without exact-head verification and existing admission gates.

## 11. Implementation placement

Preferred placement follows existing #264 boundaries:

- product/API contracts: `sovereign-omega-v2/src/api/`
- TypeScript authority/effect orchestration: `sovereign-omega-v2/src/api/`
- canonical JSON schemas and fixtures: `platform/sol/contracts/`
- Python cross-runtime parity helpers where required: `platform/sol/frontier/`
- tests:
  - `sovereign-omega-v2/test/unit/`
  - `platform/sol/tests/`

The existing `FrontierInferenceGateway` should be reused beneath the effect layer rather than duplicated.

## 12. Test / witness requirements

The implementation is not admissible until tests establish at least the following:

1. Same request + same observation state yields the same decision digest.
2. Changed execution identity invalidates a prior admission.
3. Changed action invalidates a prior admission.
4. Changed resource invalidates a prior admission.
5. Changed arguments/payload digest invalidates a prior admission.
6. Changed expected parent state invalidates a prior admission.
7. Stale topology invalidates a prior admission.
8. Tool closure outside the capability envelope is denied.
9. Unknown/unprovable tool closure is not admitted by assumption.
10. Budget/quota excess is denied before provider invocation.
11. D3 without explicit operator approval is denied.
12. D4 is denied.
13. Provider/model output cannot set or increase AEGIS authority.
14. Effect execution without a valid admitted decision never calls the provider/tool.
15. Expired or mismatched decision never calls the provider/tool.
16. Idempotency-key reuse with a different fingerprint is rejected.
17. Effect receipt binds decision, work order, identity, action, resource, pre-state, post-state and result.
18. Parent-receipt substitution or chain break is detected.
19. Python/TypeScript digest fixtures match for the shared canonical artifacts used in this slice.
20. Existing #264 frontier-provider tests remain non-regressed.

## 13. Admission boundary

Completion of code and local tests is not production admission.

The final ledger for this slice must distinguish:

- `DESIGN_SPECIFIED`
- `IMPLEMENTED`
- `LOCAL_TEST_PASS`
- `CROSS_RUNTIME_PARITY_PASS`
- `EXACT_HEAD_CI_PASS`
- `INDEPENDENT_REVIEW_PASS` where required
- `PRODUCTION_ADMISSION`

No state may be promoted merely because a lower state passed.

Current platform-level GitHub Actions billing lock remains an external blocker to `EXACT_HEAD_CI_PASS`; it is not a code-test verdict.

## 14. Commercial product statement

Product name:

**AEGIS Ω — Authority Control Plane for Agentic Systems**

Supporting line:

**Verified Collective Intelligence with proof-carrying execution.**

Technical product promise:

> Prove authority before an agent acts; bind execution to that authority; emit a replayable receipt after the effect.
