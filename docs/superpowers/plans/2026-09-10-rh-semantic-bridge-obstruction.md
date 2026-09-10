# RH Semantic Bridge Obstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Machine-check that the current abstract AEGIS `QuadraticFormV1` positivity statement cannot by itself supply the external Mathlib `RiemannHypothesis` target, then bind that obstruction into exact-head evidence and the fail-closed RH receipt.

**Architecture:** Keep the existing conditional globalization theorem and core Coq attestation inventory unchanged. Put the obstruction theorem in an isolated bridge proof lane under `formal/bridges/coq`, compile it against the exact `AnalyticDefinitions.v` dependency with a dedicated Coq 8.20 workflow, and pin its source digest in the RH manifest. The result is an insufficiency certificate, not a proof or disproof of RH.

**Tech Stack:** Coq 8.20, Python 3 unittest, GitHub Actions.

**Spec:** `sovereign-omega-v2/formal/theories/Weil/AnalyticDefinitions.v`, `sovereign-omega-v2/formal/theories/Weil/WeilCriterion.v`, and `sovereign-omega-v2/formal/bridges/formal_conjectures_rh_target_v1.json`.

## Global Constraints

- Do not modify the semantics of `Globalization.v` or `WeilCriterion.v`.
- Do not manually edit `.claude.json`.
- Do not add `Axiom`, `Parameter`, `Admitted`, or equivalent proof authority.
- Do not add the bridge theorem to the core `formal/theories` inventory.
- `RH_proved=false`, `claim_promotion=BLOCKED`, and `authority_effect=NONE` remain invariant.
- A successful obstruction proof establishes only that the present abstract interface is insufficient; it establishes neither RH nor its negation.

---

### Task 1: Machine-check the abstract-QW obstruction

**Files:**
- Create: `sovereign-omega-v2/formal/bridges/coq/SemanticBridgeObstruction.v`
- Test: `sovereign-omega-v2/formal/tests/test_semantic_bridge_obstruction_v1.py`

**Interfaces:**
- Consumes: `QuadraticFormV1`, `GlobalWeilPositivityV1`, `O0ZeroV1`, `o0_real_order_refl_v1`.
- Produces: `ZeroQuadraticFormV1`, `zero_quadratic_form_global_weil_positivity_v1`, `universal_global_weil_bridge_iff_target_v1`.

- [x] **Step 1: Specify the obstruction structurally before accepting implementation.**
- [x] **Step 2: Add the minimal Coq proof with no assumption escape hatch.**
- [x] **Step 3: Keep the canonical source outside the core theory inventory.**

The load-bearing theorem shape is:

```coq
Theorem universal_global_weil_bridge_iff_target_v1 :
  forall P : Prop,
    (forall QW : QuadraticFormV1, GlobalWeilPositivityV1 QW -> P) <-> P.
```

### Task 2: Bind the theorem to isolated Coq attestation

**Files:**
- Create: `.github/workflows/rh-semantic-bridge-obstruction.yml`

**Interfaces:**
- Consumes: the exact bridge source digest and existing `AnalyticDefinitions.v`.
- Produces: exact-head Coq version, compile logs, `Print Assumptions` logs, and `AEGIS_RH_SEMANTIC_OBSTRUCTION_RECEIPT_V1`.

- [x] **Step 1: Pin the source SHA-256 and exact candidate SHA.**
- [x] **Step 2: Run the structural regression test.**
- [x] **Step 3: Compile `AnalyticDefinitions.v` and a byte-identical build copy of the bridge theorem with Coq 8.20.**
- [x] **Step 4: Require `Closed under the global context` for both obstruction theorems.**
- [x] **Step 5: Confirm hosted workflow succeeds at exact head `9ef75cb9fc7dc3d86044ee5123db499cf518e812`.**

Verified hosted evidence at that head:
- `RH Semantic Bridge Obstruction` run `34504409345`: SUCCESS.
- Coq `8.20.1`.
- both theorem assumption probes: `Closed under the global context`.
- receipt SHA-256: `a027b7be848abd39e9d99889f4dff49fa694f26896313ec8d834af6337a3a082`.
- artifact digest: `sha256:2929dcd407d31a00ea8166d42442fe936456a75edef0ebbed5df67f03b756b14`.

### Task 3: Bind the obstruction into the RH external-target receipt

**Files:**
- Modify: `sovereign-omega-v2/formal/bridges/formal_conjectures_rh_target_v1.json`
- Modify: `sovereign-omega-v2/formal/bridges/verify_formal_conjectures_rh_bridge_v1.py`
- Modify: `sovereign-omega-v2/formal/tests/test_formal_conjectures_rh_bridge_v1.py`

**Interfaces:**
- Consumes: bridge proof source path, SHA-256, theorem names, and bounded claim scope.
- Produces: fail-closed reason code `ABSTRACT_QW_TRIVIAL_POSITIVE_MODEL_PROOF_SOURCE_PINNED` while leaving the semantic mapping and RH implication gates open.

- [x] **Step 1: Extend tests so altered obstruction evidence is rejected.**
- [x] **Step 2: Pin the obstruction source digest and bounded scope in the manifest.**
- [x] **Step 3: Validate the pin and expose the obstruction in the receipt without changing any RH promotion gate to true.**
- [x] **Step 4: Confirm hosted RH bridge tests succeed at exact head `9ef75cb9fc7dc3d86044ee5123db499cf518e812`: 7/7 PASS.**
- [x] **Step 5: Confirm final disposition remains `HOLD_RESEARCH_ONLY`, `RH_proved=false`, `claim_promotion=BLOCKED`, and `authority_effect=NONE`.**

At the same exact head, `Coq Formal Attestation`, `Kernel One`, and `Dependency Review` also completed SUCCESS. This does not close the missing classical Weil/Mathlib semantic identification.
