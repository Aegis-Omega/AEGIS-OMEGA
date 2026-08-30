# Weil Constructive Prime Trig Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Machine-bind the integer-frequency sine/cosine complement phase identities needed by the Weil prime-diagonal proofline using pinned CoRN constructive trigonometry, without widening the claim to O0 trig transport.

**Architecture:** Introduce one focused production Coq module over CoRN `IR`, one RED/GREEN specification, one dedicated exact-head workflow and receipt, then admit the module into the complete formal-attestation inventory. Keep `FinitePrimeDiagonal.v` unchanged because it consumes rational phase values while the present theorem lives on CoRN `IR`; carrier/function transport is a later bridge.

**Tech Stack:** Coq 8.20, `coq-corn.9.0.0`, GitHub Actions, existing AEGIS Coq attestation/receipt infrastructure.

**Spec:** `docs/superpowers/specs/2026-08-31-weil-constructive-prime-trig-design.md`

## Global Constraints

- Base exact head: `proof/weil-prime-diagonal-v1@44015987bee321e0dd722f1c67b909d141f75512`.
- Pin production CoRN dependency exactly to `coq-corn.9.0.0`.
- Coq lane remains exactly `8.20`.
- No `Axiom`, `Axioms`, `Parameter`, `Parameters`, or `Admitted` in the production source.
- Do not import classical `Reals` into the new authority source.
- Preserve `corn_o0_trig_transport_machine_bound = false` and all downstream RH/Weil negative claims.
- Keep the PR stacked and draft; do not merge.

---

### Task 1: Establish the RED theorem contract

**Files:**
- Create: `sovereign-omega-v2/formal/tests/Weil/PrimeTrigConstructiveSpec.v`
- Create: `.github/workflows/weil-constructive-prime-trig.yml`

**Interfaces:**
- Consumes: existing Coq 8.20 formal layout and GitHub exact-head workflow conventions.
- Produces: required theorem symbols `prime_diagonal_constructive_cos_phase_v1` and `prime_source_constructive_sin_phase_v1`.

- [ ] **Step 1: Write the failing specification**

```coq
(* RED: production module intentionally absent at this checkpoint. *)
Require Import PrimeTrigConstructive.

Check prime_diagonal_constructive_cos_phase_v1.
Check prime_source_constructive_sin_phase_v1.
```

- [ ] **Step 2: Add the dedicated exact-head RED/GREEN workflow**

The workflow must:

```text
name: Weil Constructive Prime Trig
checkout github.event.pull_request.head.sha || github.sha
assert git rev-parse HEAD == SOURCE_SHA
reject Axiom/Axioms/Parameter/Parameters/Admitted in PrimeTrigConstructive.v when present
install exactly coq-corn.9.0.0 under Coq 8.20
compile PrimeTrigConstructive.v and PrimeTrigConstructiveSpec.v
Print Assumptions for both theorem names
grep for "Closed under the global context"
fail if an "Axioms:" section appears
emit AEGIS_WEIL_CONSTRUCTIVE_PRIME_TRIG_RECEIPT_V1
upload the evidence directory
```

The receipt must keep these fields false:

```json
{
  "corn_o0_trig_transport_machine_bound": false,
  "prime_source_sine_derivative_machine_bound": false,
  "prime_diagonal_dictionary_formalized": false,
  "analytic_pole_normalization_machine_bound": false,
  "archimedean_entry_identity_proven": false,
  "guinand_weil_explicit_formula_machine_bound": false,
  "formula_to_weil_operator_identity_proven": false,
  "global_weil_positivity_proven": false,
  "rh_proven": false
}
```

- [ ] **Step 3: Commit RED**

Commit message:

```text
test(rh): require constructive prime trig phase theorems
```

- [ ] **Step 4: Verify RED from GitHub Actions**

Expected result: `Weil Constructive Prime Trig` fails because `PrimeTrigConstructive` cannot be resolved. Any earlier infrastructure failure is not an acceptable RED checkpoint.

---

### Task 2: Implement the minimal constructive CoRN phase theorems

**Files:**
- Create: `sovereign-omega-v2/formal/theories/Weil/PrimeTrigConstructive.v`

**Interfaces:**
- Consumes: CoRN `IR`, `Pi`, `Two`, `Cos`, `Sin`, `Cos_periodic_Z`, `Sin_periodic_Z`, `Cos_inv`, `Sin_inv` and constructive ring algebra.
- Produces:
  - `prime_diagonal_constructive_cos_phase_v1 : forall (r : IR) (n : nat), ...`
  - `prime_source_constructive_sin_phase_v1 : forall (r : IR) (n : nat), ...`

- [ ] **Step 1: Write the minimal production source**

Use imports sufficient for the actual proof only, centered on:

```coq
Require Import CoRN.transc.Pi.
Require Import CoRN.tactics.CornTac.
```

State the phase using CoRN operations and the natural-number embedding available in the loaded algebra. Rewrite

```text
Two * n * Pi * (1-r)
```

into

```text
-(Two * n * Pi * r) + zring(Z.of_nat n) * (Two * Pi)
```

with CoRN rational/ring tactics, then apply `Cos_periodic_Z`/`Sin_periodic_Z`, followed by `Cos_inv`/`Sin_inv`.

- [ ] **Step 2: Keep the source assumption-free by construction**

Before relying on CI, inspect the source text and confirm none of:

```text
Axiom
Axioms
Parameter
Parameters
Admitted
```

appear as declarations.

- [ ] **Step 3: Commit GREEN implementation**

Commit message:

```text
proof(rh): bind constructive prime trig phase identities
```

- [ ] **Step 4: Verify the dedicated workflow turns GREEN**

Expected: module compiles, spec compiles, both `Print Assumptions` reports say `Closed under the global context`, receipt generation succeeds.

---

### Task 3: Admit the CoRN theorem module into the complete formal authority inventory

**Files:**
- Modify: `.github/workflows/coq-formal-attestation.yml`

**Interfaces:**
- Consumes: existing all-source census and `REQUIRE_AXIOM_FREE` policy.
- Produces: complete exact-head attestation coverage for `Weil/PrimeTrigConstructive.v`.

- [ ] **Step 1: Pin the production dependency in the formal-attestation lane**

Replace the single dependency install with an exact install containing both required packages:

```bash
opam install -y coq-coquelicot.3.4.2 coq-corn.9.0.0 || exit 1
```

- [ ] **Step 2: Add the module to the compile inventory**

Insert:

```text
'Weil/PrimeTrigConstructive.v'
```

in dependency-safe order before files that may later consume the theorem.

- [ ] **Step 3: Add the module to `REQUIRE_AXIOM_FREE`**

Insert:

```python
'Weil/PrimeTrigConstructive.v',
```

without changing `DIAGNOSTIC_ONLY`.

- [ ] **Step 4: Commit authority wiring**

Commit message:

```text
ci(rh): attest pinned CoRN prime trig authority
```

- [ ] **Step 5: Verify complete Coq formal attestation GREEN**

Expected: every formal source is present in the receipt, `PrimeTrigConstructive.v` is `AUTHORITY_ELIGIBLE`, `COMPILED`, `AXIOM_FREE`, has two closed theorems and no declared assumptions, and the known global assumption counts do not regress.

---

### Task 4: Open the stacked draft and freeze epistemic status

**Files:**
- No additional production code required.

**Interfaces:**
- Consumes: exact-head workflow evidence from Tasks 1–3.
- Produces: one stacked draft PR with exact SHA and bounded claims.

- [ ] **Step 1: Confirm branch diff against the base**

Compare `proof/weil-prime-diagonal-v1` to `proof/weil-constructive-prime-trig-v1`. Expected changed scope is limited to the design/plan, RED/GREEN spec/workflow, production theorem module, and formal-attestation wiring.

- [ ] **Step 2: Open a draft PR**

Base:

```text
proof/weil-prime-diagonal-v1
```

Head:

```text
proof/weil-constructive-prime-trig-v1
```

Title:

```text
proof(rh): bind constructive prime trig phase identities
```

PR body must state that the CoRN `IR` phase identity is machine-bound while O0 trig transport, sine-derivative transport, the concrete finite dictionary, explicit formula, Weil positivity and RH remain unproved.

- [ ] **Step 3: Record exact-head check matrix**

Do not call the slice admitted until both the dedicated `Weil Constructive Prime Trig` workflow and `Coq Formal Attestation` succeed on the final head SHA.

- [ ] **Step 4: Preserve status line**

```text
RH = NOT_PROVEN
```
