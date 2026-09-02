# Polyglot Metacognition v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an authority-neutral, fail-closed polyglot metacognitive runtime that discovers verified toolchains, decomposes tasks by reasoning paradigm and isolation role, normalizes heterogeneous evidence into RFC 8785 receipts, joins evidence without truth laundering, updates a bounded self-model/strategy ledger, and exposes first-wave adapter contracts for egg, cvc5, Lean/Rocq, and CUDA-Q.

**Architecture:** Extend the existing AEGIS extension/capability and metacognitive substrate rather than creating a parallel authority plane. Toolchains are catalogued separately from executable capability evidence; dispatch requires exact verified evidence and never silently substitutes or mocks missing backends. Heterogeneous outputs become authority-neutral typed receipts, are joined through explicit conflict semantics, and can update strategy/self-model telemetry but can never directly promote canonical knowledge.

**Tech Stack:** TypeScript 5.5, Vitest 4, existing RFC 8785 canonicalizer, existing SHA-256 `hashValue`, existing `MetacognitiveLoop`, GitHub Actions Node 22 exact-head CI.

**Spec:** User-approved federated Polyglot Metacognition design, PR #377 body, existing `sovereign-omega-v2/src/extensions/*`, `sovereign-omega-v2/src/metacognition/loop.ts`, and Drive document `AEGIS-SOVEREIGN OS Design Roadmap` as historical architectural reference only.

## Global Constraints

- `AUTHORITY_CLASS = NONE` and `AUTHORITY_EFFECT = NONE` for every polyglot backend and receipt in v1.
- No direct Tier 2/Tier 3 state or backend output may promote canonical knowledge.
- No silent mock, purity fallback, wrong-paradigm substitution, or public executor/command-runner injection seam.
- Missing required toolchain evidence fails closed as `TOOLCHAIN_UNAVAILABLE` or a `DEFER` routing result, depending on API boundary.
- Integrity-critical serialization uses the repository RFC 8785 implementation; integrity digests use `hashValue`/SHA-256.
- Builder context policy = `PRESERVE`; Falsifier = `RAW_EVIDENCE_ONLY`; Reviewer = `CLEAN_ROOM`.
- CUDA-Q remains diagnostic `Authority = NONE`; Self-Witness-0 physical quantum advantage remains not established.
- RH remains `NOT_PROVEN`.
- PR remains DRAFT until all new exact-head checks are terminal and reviewed.

---

### Task 1: PolyglotCapabilityFabric GREEN

**Files:**
- Create: `sovereign-omega-v2/src/polyglot/fabric.ts`
- Existing test: `sovereign-omega-v2/test/unit/polyglot-fabric.test.ts`

**Interfaces:**
- Produces: `POLYGLOT_FRONTIER_CATALOG`, `ToolchainCapabilityEvidence`, `routePolyglotTask()`, `buildPolyglotMetacognitiveObservation()`.

- [x] RED: exact-head CI fails because `src/polyglot/fabric.ts` is absent.
- [ ] Implement deterministic catalogue, evidence validation, exact-paradigm routing and digest-bound route receipt.
- [ ] Run exact-head `Polyglot Metacognition` workflow and require tests + typecheck PASS.
- [ ] Record GREEN head/run in PR body.

### Task 2: Toolchain Detection + Fail-Closed Capability Admission

**Files:**
- Create: `sovereign-omega-v2/src/polyglot/detection.ts`
- Test: `sovereign-omega-v2/test/unit/polyglot-detection.test.ts`

**Interfaces:**
- Produces: `ToolchainDetector`, `ToolchainDetectionObservation`, `admitDetectedToolchain()` and `TOOLCHAIN_UNAVAILABLE` error semantics.
- Consumes: `ToolchainCapabilityEvidence` from Task 1.

- [ ] Write tests proving absent executable cannot become verified evidence, malformed version/digest/receipt is rejected, and detector output remains authority-neutral.
- [ ] Verify RED on exact head.
- [ ] Implement pure admission over externally supplied detection observations; no command-runner injection in public runtime API.
- [ ] Verify GREEN and typecheck.

### Task 3: ParadigmDecomposer + Isolated Dispatcher

**Files:**
- Create: `sovereign-omega-v2/src/polyglot/dispatch.ts`
- Test: `sovereign-omega-v2/test/unit/polyglot-dispatch.test.ts`

**Interfaces:**
- Produces: `CognitiveRole`, `ContextInheritancePolicy`, `ParadigmWorkUnit`, `decomposePolyglotTask()`, `buildDispatchPlan()`.
- Consumes: verified routes from Task 1.

- [ ] Write RED tests for Builder=`PRESERVE`, Falsifier=`RAW_EVIDENCE_ONLY`, Reviewer=`CLEAN_ROOM`, deterministic work-unit IDs, backend budget and exact paradigm isolation.
- [ ] Implement deterministic decomposition/dispatch planning only; actual external process execution stays inside adapter-specific runners outside this public planner API.
- [ ] Verify GREEN and typecheck.

### Task 4: Evidence Normalization + Prismatic Join

**Files:**
- Create: `sovereign-omega-v2/src/polyglot/evidence.ts`
- Test: `sovereign-omega-v2/test/unit/polyglot-evidence.test.ts`

**Interfaces:**
- Produces typed `ClaimReceipt`, `CounterexampleReceipt`, `ProofReceipt`, `PosteriorReceipt`, `SimulationReceipt`, `QuantumReceipt`, `PerformanceReceipt`, plus `canonicalReceiptJSON()` and `joinPolyglotEvidence()`.

- [ ] Write RED tests for RFC 8785 byte identity, receipt digest recomputation, authority-neutral schema, conflict detection, counterexample precedence, and `QUARANTINED`/`NOT_ESTABLISHED` outcomes.
- [ ] Implement normalization via existing `canonicalizeJCSString()` and `hashValue()` only.
- [ ] Implement join with explicit conflict set and no majority-vote truth promotion.
- [ ] Verify GREEN and typecheck.

### Task 5: MetacognitiveSelfModel + StrategyPerformanceLedger

**Files:**
- Create: `sovereign-omega-v2/src/polyglot/self-model.ts`
- Test: `sovereign-omega-v2/test/unit/polyglot-self-model.test.ts`

**Interfaces:**
- Produces: immutable `MetacognitiveSelfModel`, `StrategyPerformanceRecord`, `StrategyPerformanceLedger`, Pareto frontier query, and T2 observations consumable by `MetacognitiveLoop.observe()`.

- [ ] Write RED tests for immutable updates, deterministic three-run replay, Pareto dominance, uncertainty tracking, capability-state tracking and prohibition on knowledge-admission fields.
- [ ] Implement self-model projection from routing/evidence/strategy receipts.
- [ ] Verify GREEN and typecheck.

### Task 6: First-Wave Adapter Contracts

**Files:**
- Create: `sovereign-omega-v2/src/polyglot/adapters.ts`
- Test: `sovereign-omega-v2/test/unit/polyglot-adapters.test.ts`

**Interfaces:**
- Produces adapter descriptors for `egg`, `cvc5`, `lean4`, `rocq`, `cudaq`; each declares paradigm, evidence type, required verified capability, context policy compatibility, output receipt kind and authority NONE.

- [ ] Write RED tests proving no adapter executes without verified toolchain evidence and CUDA-Q can emit only `QuantumReceipt`/diagnostic evidence with authority NONE.
- [ ] Bind CUDA-Q descriptor to Self-Witness-0 contract metadata without importing unadmitted branch runtime code.
- [ ] Verify GREEN and typecheck.

### Task 7: Exact-Head CI + Documentation Receipt

**Files:**
- Modify: `.github/workflows/polyglot-metacognition.yml`
- Modify: PR #377 body.

- [ ] Run all polyglot unit suites in one exact-head job.
- [ ] Preserve exact candidate checkout assertion and pinned actions.
- [ ] Record RED→GREEN heads and terminal run IDs.
- [ ] Keep PR DRAFT and authority `NONE` until broader repo checks finish.
