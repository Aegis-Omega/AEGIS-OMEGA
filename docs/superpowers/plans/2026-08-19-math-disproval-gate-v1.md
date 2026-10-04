# Math Disproval Gate v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `MATH_DISPROVAL_GATE_V1` so AEGIS can distinguish kernel-verified proof/disproof from failure-to-prove, while reusing the repository's existing Coq formal substrate and Lean exact-verification harness.

**Architecture:** The gate is a TypeScript orchestration/receipt layer above existing proof assistants. Current Coq sources under `sovereign-omega-v2/formal/theories/` are treated as repo-native formal artifacts; PR #254's exact-commit Lean workflow is the reference execution pattern for Lean. Kernel output is evidence only. A deterministic aggregator maps exact-bound kernel results to `PROVED`, `DISPROVED`, or `UNRESOLVED`; proof-source audits prevent `Axiom`/`Admitted`/`sorry` laundering.

**Tech Stack:** TypeScript/Vitest, SHA-256/JCS conventions already present in `sovereign-omega-v2`, Coq/Rocq `.v` sources, Lean 4 exact-environment verification pattern from PR #254, GitHub Actions, JSON Schema Draft 2020-12.

**Spec:** `docs/superpowers/specs/2026-08-19-math-disproval-gate-v1-design.md`

## Global Constraints

- `FAIL_TO_PROVE(P) != DISPROVE(P)` is a hard invariant.
- Provider/model/search outputs are evidence only and never mathematical authority.
- `DISPROVED` requires kernel-verified `not P` or a kernel-verified formal counterexample theorem/witness.
- `PROVED`/`DISPROVED` and `SINGLE_KERNEL`/`CROSS_KERNEL` are separate axes.
- Lean and Coq/Rocq are verifier diversity, not foundational independence.
- Existing Coq files must be reused/classified, not replaced by duplicate proofs.
- PR #254 Lean harness semantics must be reused: exact source/toolchain binding, placeholder audit, independent checker, immutable receipt.
- `ThreeWay.v` contains an explicit `Axiom`; it must never be promoted to strict kernel-certified proof evidence without a later admitted assumption policy.
- A math receipt is `FORMAL_MATH_EVIDENCE_ONLY`; it cannot authorize execution, effect, or admission.
- Work remains on PR #275 integration spine; no new persistent feature branch.

---

### Task 1: Typed math contracts and strict source classification

**Files:**
- Create: `sovereign-omega-v2/src/math-verification/contracts.ts`
- Create: `sovereign-omega-v2/src/math-verification/source-audit.ts`
- Test: `sovereign-omega-v2/test/unit/math-verification/math-contracts.test.ts`

**Interfaces:**
- Produces `MathClaimEnvelopeV1`, `FormalizationBindingV1`, `KernelVerificationResultV1`, `MathVerificationReceiptV1`.
- Produces `auditFormalSource(kind, source): FormalSourceAuditV1` for `COQ` and `LEAN`.

- [ ] Write RED tests that reject unknown fields/authority injection, malformed digests, invalid timestamps and invalid nominal discriminators.
- [ ] Write RED tests proving Coq `Axiom`/`Admitted` and Lean `sorry`/`admit` are detected, while the current `LockIrreversibility.v`/`LatticeConvergence.v` pattern is strict-proof eligible and `ThreeWay.v` is not.
- [ ] Run focused tests and confirm failure is caused only by missing math-verification modules.
- [ ] Implement the minimal typed validators and source auditor.
- [ ] Re-run focused tests, typecheck and build; commit GREEN.

### Task 2: Deterministic verdict aggregator

**Files:**
- Create: `sovereign-omega-v2/src/math-verification/aggregate.ts`
- Test: `sovereign-omega-v2/test/unit/math-verification/math-aggregate.test.ts`

**Interfaces:**
- Consumes exact-bound `MathClaimEnvelopeV1`, `FormalizationBindingV1`, kernel results and artifact digests.
- Produces deterministic `MathVerificationReceiptV1` plus diagnostics.

- [ ] RED-test `PROVED/SINGLE_KERNEL`, `DISPROVED/SINGLE_KERNEL` by negation, and `DISPROVED/SINGLE_KERNEL` by formal counterexample.
- [ ] RED-test timeout, error, rejected proof and heuristic witness as `UNRESOLVED`.
- [ ] RED-test proof/disproof contradiction as `UNRESOLVED` + `KERNEL_INCONSISTENCY_DETECTED`.
- [ ] RED-test claim/assumptions/binding/policy/epoch mismatch and receipt injection as rejected evidence.
- [ ] RED-test same-binding Lean+Coq as `CROSS_KERNEL` and different bindings as no cross promotion.
- [ ] Implement the minimal deterministic aggregator and domain-separated receipt hash.
- [ ] Re-run focused tests twice and require byte-identical receipt hashes; commit GREEN.

### Task 3: Closed schemas and canonical falsification corpus

**Files:**
- Create: `schemas/math-verification/math-claim-envelope-v1.schema.json`
- Create: `schemas/math-verification/formalization-binding-v1.schema.json`
- Create: `schemas/math-verification/kernel-verification-result-v1.schema.json`
- Create: `schemas/math-verification/math-verification-receipt-v1.schema.json`
- Create: `test-vectors/math-verification/math-disproval-gate-v1.json`
- Test: `sovereign-omega-v2/test/unit/math-verification/math-schema.test.ts`
- Test: `sovereign-omega-v2/test/vectors/math-disproval-gate-vectors.test.ts`

- [ ] Write schema/vector tests first and verify RED via missing files.
- [ ] Add four closed Draft 2020-12 schemas with nominal discriminators and fixed authority constants.
- [ ] Add at least the 20 falsification cases required by the spec, including axiom/sorry laundering and mismatched formalization binding.
- [ ] Run vectors twice and require deterministic output; run typecheck/build; commit GREEN.

### Task 4: Reuse existing Coq and Lean execution surfaces

**Files:**
- Create: `sovereign-omega-v2/scripts/math-verification/audit-coq-source.mjs`
- Create: `sovereign-omega-v2/scripts/math-verification/normalize-kernel-result.mjs`
- Create: `.github/workflows/math-disproval-gate.yml`
- Modify: `sovereign-omega-v2/src/registry/types.ts`
- Modify: `sovereign-omega-v2/src/registry/entries.ts` only as needed to register proof coverage.

**Existing sources to reuse:**
- `sovereign-omega-v2/formal/theories/Core/LockIrreversibility.v`
- `sovereign-omega-v2/formal/theories/Core/LatticeConvergence.v`
- `sovereign-omega-v2/formal/theories/Bisimulation/ThreeWay.v`
- PR #254 `.github/workflows/verify-openai-ten-proofs.yml` pattern (`leanprover/lean-action@v1`, `lake build All`, placeholder audit, leanchecker, Nanoda `allow_sorry:false`).

- [ ] RED-test registry classification so Lean proof coverage and strict-vs-assumption-bearing Coq evidence cannot collapse into one status.
- [ ] Add `LEAN_THEOREM` and strict formal-result coverage without changing existing `COQ_THEOREM` semantics.
- [ ] Add a fail-closed Coq source audit; strict mode rejects `Axiom`, `Admitted`, and `admit` before a result can be `VERIFIED`.
- [ ] Build GitHub workflow that checks current Coq proof sources with `coqc`/Rocq-compatible command when provisioned, and reuses #254's Lean exact-verification pattern rather than inventing a looser Lean path.
- [ ] If a toolchain is unavailable, record `UNRESOLVED/TOOLCHAIN_UNAVAILABLE`; never convert absence/failure into disproof.
- [ ] Upload content-addressed kernel-result artifacts and receipt inputs; commit GREEN only after exact-head execution evidence.

### Task 5: Independent witness, native admission, and PR ledger

**Files:**
- Update: `tarikskalic33/info` UCI witness workflow to execute math-gate tests and available kernel smoke checks against an exact AEGIS SHA.
- Rotate: the single `.aegis/experiments/` plan changed by PR #275 to the math-disproval checkpoint only after previous UCI-3 evidence is preserved by exact SHA/artifact.
- Update: PR #275 body with UCI-3 and math-gate exact evidence.

- [ ] Run independent exact-head witness: prior UCI regression + math contract/aggregate/schema/vector tests + typecheck/build.
- [ ] Re-run the same witness unchanged to establish deterministic replay.
- [ ] Run native Experiment Admission on the same AEGIS SHA and preserve OIDC attestation/artifact digest.
- [ ] Run Constitutional Automaton on the exact same SHA.
- [ ] Record separately which proof assistants actually executed. Do not claim `CROSS_KERNEL` runtime verification unless both strict kernel paths succeeded on the admitted head.
- [ ] Mark the checkpoint complete only after fresh verification-before-completion review; do not merge PR #275 without operator instruction.
