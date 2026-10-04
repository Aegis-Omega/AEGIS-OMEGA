# Weil O₀ Globalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure-Coq analytic/globalization proof layer that exposes the finite→global proof obligations and mechanically refuses to report O₀/RH closure until an assumption-free theorem has exact type `RiemannHypothesis`.

**Architecture:** Keep the existing finite bridge untouched. Add four focused Coq modules plus two probe modules and one exact-head CI workflow. The workflow first establishes dependency availability, then compiles the vocabulary, then records that final closure is absent without converting that expected theorem-level RED into a false global claim.

**Tech Stack:** Coq 8.20.1; Coq standard `Reals`; Coquelicot 3.4.2 only after a recorded dependency RED proves the current image lacks it; GitHub Actions exact-head checkout.

**Spec:** `docs/superpowers/specs/2026-08-24-weil-o0-globalization-design.md`

## Global Constraints

- Exact parent: `#303@6eec4e02a5e46ce8d4dfff49b5f2fd7fbde0de9c`.
- Never modify `FiniteBridge.v` in this slice.
- Forbid `Axiom`, `Axioms`, `Parameter`, `Parameters`, and `Admitted` in O₀ source files.
- Do not define a proposition named `RiemannHypothesis` until a concrete repository zeta representation exists.
- `O0_closure` must be absent in slice 1.
- CI receipt must state `O_0=NOT_ESTABLISHED` and `rh_proven=false`.
- GREEN CI is evidence of the bounded contract only, never evidence of RH.

---

### Task 1: Preregister exact-head dependency and closure probes

**Files:**
- Create: `sovereign-omega-v2/formal/theories/Weil/O0DependencyProbe.v`
- Create: `sovereign-omega-v2/formal/theories/Weil/O0ClosureProbe.v`
- Create: `.github/workflows/weil-o0-globalization.yml`

**Interfaces:**
- Consumes: exact PR head through `github.event.pull_request.head.sha`.
- Produces: a CI RED before production O₀ modules exist; later the same workflow becomes the O₀ attestation surface.

- [ ] **Step 1: Write the dependency probe**

```coq
From Coquelicot Require Import Coquelicot.
Check filterlim.
```

- [ ] **Step 2: Write the closure probe before `O0.v` exists**

```coq
Require Import O0.
Fail Check O0_closure.
Check o0_status.
```

- [ ] **Step 3: Add exact-head workflow without installing Coquelicot**

The workflow must pin checkout, set `EXPECTED_SHA=${{ github.event.pull_request.head.sha || github.sha }}`, assert `git rev-parse HEAD`, reject declared assumptions in all future O₀ source files when present, and invoke Coq 8.20 to compile `O0DependencyProbe.v` then `O0ClosureProbe.v`.

- [ ] **Step 4: Open a DRAFT PR stacked on `proof/weil-convergence-bridge-v1`**

Expected CI: RED. Acceptable RED causes are (a) Coquelicot absent, or (b) `O0.v` absent. Record the exact failure rather than guessing.

### Task 2: Establish dependency boundary and analytic vocabulary

**Files:**
- Create: `sovereign-omega-v2/formal/theories/Weil/AnalyticDefinitions.v`
- Modify: `.github/workflows/weil-o0-globalization.yml`

**Interfaces:**
- Produces: `AdmissibleTestFunctionV1`, `QuadraticFormV1`, `FiniteQuadraticFamilyV1`, `pointwise_converges_v1`, `vanishing_nonnegative_error_v1`, `GlobalWeilPositivityV1`.

- [ ] **Step 1: If RED proves Coquelicot absent, pin it explicitly**

Inside the Coq action environment install exactly `coq-coquelicot.3.4.2`; do not add MathComp-Analysis in this task.

- [ ] **Step 2: Add concrete stdlib-compatible definitions**

```coq
Record AdmissibleTestFunctionV1 := {
  test_function_v1 :> R -> R;
  support_radius_v1 : R;
  support_radius_nonnegative_v1 : 0 <= support_radius_v1;
  compact_support_v1 : forall x, Rabs x > support_radius_v1 -> test_function_v1 x = 0;
  continuous_v1 : continuity test_function_v1
}.

Definition QuadraticFormV1 := AdmissibleTestFunctionV1 -> R.
Definition FiniteQuadraticFamilyV1 := nat -> QuadraticFormV1.
Definition GlobalWeilPositivityV1 (QW : QuadraticFormV1) : Prop :=
  forall f, 0 <= QW f.
```

Define pointwise convergence and vanishing nonnegative error envelopes with epsilon/N quantifiers over `R`/`nat`; no opaque constants.

- [ ] **Step 3: Compile and `Print Assumptions` for every proved helper lemma**

Expected: `Closed under the global context` for any helper theorem introduced here.

### Task 3: Encode globalization obligations without closing them by assumption

**Files:**
- Create: `sovereign-omega-v2/formal/theories/Weil/Globalization.v`

**Interfaces:**
- Consumes: `AnalyticDefinitions.v`.
- Produces: named propositions for finite lower bounds, pointwise limit identification, vanishing error, and the global positivity target.

- [ ] **Step 1: Define obligations as transparent propositions**

```coq
Definition FiniteLowerBoundV1 (QR : FiniteQuadraticFamilyV1) (eps : nat -> R) : Prop :=
  forall n f, - eps n <= QR n f.

Definition GlobalizationReadyV1
    (QR : FiniteQuadraticFamilyV1) (QW : QuadraticFormV1) (eps : nat -> R) : Prop :=
  pointwise_converges_v1 QR QW /\
  vanishing_nonnegative_error_v1 eps /\
  FiniteLowerBoundV1 QR eps.
```

Do not introduce `Parameter QW`, `Axiom density`, or an admitted convergence theorem.

- [ ] **Step 2: Prove only genuinely derivable helper lemmas**

Any intermediate theorem may consume explicit mathematical premises, but it must not be named or counted as O₀ closure.

### Task 4: Make Weil/RH boundary explicit and unforgeable

**Files:**
- Create: `sovereign-omega-v2/formal/theories/Weil/WeilCriterion.v`
- Create: `sovereign-omega-v2/formal/theories/Weil/O0.v`

**Interfaces:**
- Produces: a status value and no final theorem.

- [ ] **Step 1: Keep the criterion file executable but theorem-empty at the RH boundary**

It may import the globalization vocabulary and document the missing concrete zeta/explicit-formula bridge, but it must not declare `RiemannHypothesis` through an opaque constant or premise.

- [ ] **Step 2: Add status type to `O0.v`**

```coq
Inductive O0StatusV1 : Set := O0_NOT_ESTABLISHED.
Definition o0_status : O0StatusV1 := O0_NOT_ESTABLISHED.
```

There must be no `O0_closure` declaration.

- [ ] **Step 3: Run closure probe**

`Require Import O0. Fail Check O0_closure.` must compile. This is an expected theorem-level RED encoded as a successful guard.

### Task 5: Emit a fail-closed O₀ receipt and regress inherited prooflines

**Files:**
- Modify: `.github/workflows/weil-o0-globalization.yml`

**Interfaces:**
- Produces: `AEGIS_WEIL_O0_RECEIPT_V1`.

- [ ] **Step 1: Emit content-addressed receipt**

The JSON receipt must bind candidate SHA plus SHA-256 of `AnalyticDefinitions.v`, `Globalization.v`, `WeilCriterion.v`, `O0.v`, dependency-probe log, compile log, and closure-probe log. Fixed fields:

```json
{
  "receipt_kind": "AEGIS_WEIL_O0_RECEIPT_V1",
  "o0_status": "NOT_ESTABLISHED",
  "rh_proven": false,
  "global_weil_positivity_proven": false,
  "closure_theorem_present": false
}
```

- [ ] **Step 2: Re-run inherited finite/formal gates**

Verify the existing Weil convergence workflow and shared Coq attestation remain GREEN on the new exact head. No result from those inherited gates may flip the O₀ receipt fields.

- [ ] **Step 3: Update DRAFT PR ledger with exact RED/GREEN run IDs and SHAs**

Record only observed results. Do not claim analytic globalization, Weil criterion, or RH closure.
