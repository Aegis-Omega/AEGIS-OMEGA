# RH Semantic Bridge Obstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Machine-check that the current abstract AEGIS `QuadraticFormV1` positivity statement cannot by itself supply the external Mathlib `RiemannHypothesis` target, then bind that obstruction into exact-head attestation and the fail-closed RH receipt.

**Architecture:** Keep the existing conditional globalization theorem unchanged. Add a separate Coq theorem showing that `GlobalWeilPositivityV1` has a trivial zero-form model and that any bridge universally quantified over arbitrary `QW` is logically equivalent to the target proposition itself. Treat this as an insufficiency certificate, not as a proof or disproof of RH. Extend existing CI/receipt metadata so promotion remains blocked until one concrete classical Weil functional is defined and identified.

**Tech Stack:** Coq 8.20, Python 3 unittest, GitHub Actions, existing AEGIS Coq attestation generator.

**Spec:** `sovereign-omega-v2/formal/theories/Weil/AnalyticDefinitions.v`, `sovereign-omega-v2/formal/theories/Weil/WeilCriterion.v`, and `sovereign-omega-v2/formal/bridges/formal_conjectures_rh_target_v1.json`.

## Global Constraints

- Do not modify the semantics of `Globalization.v` or `WeilCriterion.v`.
- Do not manually edit `.claude.json`.
- Do not add `Axiom`, `Parameter`, `Admitted`, or equivalent proof authority.
- `RH_proved=false`, `claim_promotion=BLOCKED`, and `authority_effect=NONE` must remain invariant.
- A successful obstruction proof establishes only that the present abstract interface is insufficient; it does not establish RH or its negation.

---

### Task 1: Machine-check the abstract-QW obstruction

**Files:**
- Create: `sovereign-omega-v2/formal/theories/Weil/SemanticBridgeObstruction.v`
- Test: `sovereign-omega-v2/formal/tests/test_semantic_bridge_obstruction_v1.py`

**Interfaces:**
- Consumes: `QuadraticFormV1`, `GlobalWeilPositivityV1`, `O0ZeroV1`, `o0_real_order_refl_v1`.
- Produces: `ZeroQuadraticFormV1`, `zero_quadratic_form_global_weil_positivity_v1`, `universal_global_weil_bridge_iff_target_v1`.

- [ ] **Step 1: Write the failing structural regression test**

```python
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "theories" / "Weil" / "SemanticBridgeObstruction.v"

class SemanticBridgeObstructionTests(unittest.TestCase):
    def test_required_theorems_and_no_assumption_escape_hatches(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn("Theorem zero_quadratic_form_global_weil_positivity_v1", text)
        self.assertIn("Theorem universal_global_weil_bridge_iff_target_v1", text)
        for forbidden in ("Axiom ", "Parameter ", "Admitted."):
            self.assertNotIn(forbidden, text)
```

- [ ] **Step 2: Run the test and require failure because the Coq source is absent**

Run: `python3 -m unittest formal.tests.test_semantic_bridge_obstruction_v1 -v`
Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 3: Add the minimal Coq proof**

```coq
Require Import AnalyticDefinitions.

Definition ZeroQuadraticFormV1 : QuadraticFormV1 :=
  fun _ => O0ZeroV1.

Theorem zero_quadratic_form_global_weil_positivity_v1 :
  GlobalWeilPositivityV1 ZeroQuadraticFormV1.
Proof.
  intro f.
  unfold ZeroQuadraticFormV1.
  apply o0_real_order_refl_v1.
Qed.

Theorem universal_global_weil_bridge_iff_target_v1 :
  forall P : Prop,
    (forall QW : QuadraticFormV1, GlobalWeilPositivityV1 QW -> P) <-> P.
Proof.
  intro P.
  split.
  - intro Hbridge.
    apply (Hbridge ZeroQuadraticFormV1).
    exact zero_quadratic_form_global_weil_positivity_v1.
  - intros HP QW HQW.
    exact HP.
Qed.
```

- [ ] **Step 4: Re-run the structural regression test**

Run: `python3 -m unittest formal.tests.test_semantic_bridge_obstruction_v1 -v`
Expected: PASS.

### Task 2: Bind the theorem to Coq attestation

**Files:**
- Modify: `.github/workflows/coq-formal-attestation.yml`

**Interfaces:**
- Consumes: the new Coq source and existing attestation inventory.
- Produces: exact-head compile status and `Print Assumptions` evidence for both new theorems.

- [ ] **Step 1: Add `Weil/SemanticBridgeObstruction.v` to the explicit compile inventory immediately after `Weil/AnalyticDefinitions.v`.**
- [ ] **Step 2: Add the same path to `REQUIRE_AXIOM_FREE`.**
- [ ] **Step 3: Run the hosted `Coq Formal Attestation` workflow and require `COMPILED`, `AXIOM_FREE`, zero admitted declarations, and closed assumption output for the new file.**

### Task 3: Bind the obstruction into the RH external-target receipt

**Files:**
- Modify: `sovereign-omega-v2/formal/bridges/formal_conjectures_rh_target_v1.json`
- Modify: `sovereign-omega-v2/formal/bridges/verify_formal_conjectures_rh_bridge_v1.py`
- Modify: `sovereign-omega-v2/formal/tests/test_formal_conjectures_rh_bridge_v1.py`

**Interfaces:**
- Consumes: exact theorem coordinate and source digest of `SemanticBridgeObstruction.v`.
- Produces: a fail-closed receipt reason code `ABSTRACT_QW_TRIVIAL_POSITIVE_MODEL_PROVED` while leaving the semantic mapping and RH implication gates open.

- [ ] **Step 1: Extend tests so a missing or altered obstruction evidence record is rejected.**
- [ ] **Step 2: Pin the obstruction theorem coordinate and source digest in the manifest.**
- [ ] **Step 3: Validate the pin in the verifier and emit the new reason code without changing any promotion gate to true.**
- [ ] **Step 4: Run both Python test modules and require all tests to pass.**
- [ ] **Step 5: Run exact-head hosted RH bridge CI and require `HOLD_RESEARCH_ONLY`, `RH_proved=false`, `claim_promotion=BLOCKED`, and `authority_effect=NONE`.**
