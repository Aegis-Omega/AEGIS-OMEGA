# AEGIS Ω Weil O₀ Globalization Design

## Subject and lineage

This slice is stacked on exact `#303 / proof/weil-convergence-bridge-v1@6eec4e02a5e46ce8d4dfff49b5f2fd7fbde0de9c`.

It does not modify the finite Weil/Arb/LDLᵀ proof kernel. It adds a separate Coq 8.20 analytic/globalization layer whose purpose is to make the remaining mathematical obligations expressible without pretending they are closed.

## Epistemic contract

The final acceptance target is a kernel-checked theorem with no load-bearing Prop premises:

```coq
Theorem O0_closure : RiemannHypothesis.
```

A theorem of the form

```coq
H_density -> H_continuity -> H_limit -> RiemannHypothesis
```

is not O₀ closure. `Print Assumptions = Closed under the global context` is necessary but not sufficient: the theorem type itself must be exactly the target proposition.

Until a concrete zeta representation, Weil criterion, globalization theorems, and the final theorem are machine-checked, the branch must report:

```text
O_0 = NOT_ESTABLISHED
RH  = NOT_PROVEN
```

No `Axiom`, `Axioms`, `Parameter`, `Parameters`, or `Admitted` is allowed in the O₀ source files.

## First slice

The first slice is deliberately smaller than RH. It establishes an executable analytic vocabulary and a closure guard.

### `AnalyticDefinitions.v`

Defines a concrete v1 carrier for compactly supported continuous real test functions, real-valued quadratic forms on that carrier, finite quadratic-form families, pointwise convergence, vanishing nonnegative error envelopes, and global Weil positivity as a proposition over a supplied concrete quadratic form.

The v1 test-function class is a topology carrier for the globalization proofline. This file does not claim that the v1 class has already been proved extensionally identical to every classical formulation of Weil's admissible test-function class.

### `Globalization.v`

Defines the exact obligations needed to move from finite forms to a limiting form: pointwise convergence, vanishing lower error, finite lower bounds, and the resulting global-positivity target. Intermediate implication lemmas may have explicit premises; only the final O₀ theorem is forbidden from hiding load-bearing premises.

### `WeilCriterion.v`

Carries the criterion boundary. In slice 1 it intentionally does not declare `RiemannHypothesis` or a Weil→RH theorem, because the repository does not yet contain a machine-defined analytically continued Riemann zeta object. The absence is part of the proof state, not a placeholder promoted to authority.

### `O0.v`

Composes the available analytic definitions and exports a machine-readable status value `O0_NOT_ESTABLISHED`. It intentionally does not define `O0_closure`.

## Dependency probe

The existing formal workflow uses bare Coq 8.20. Slice 1 preregisters a Coquelicot import probe before adding any analytic dependency to the runner. This determines whether the current image already contains the library. If it does not, the next GREEN step explicitly pins `coq-coquelicot.3.4.2`, which is part of the Coq 8.20 platform package set.

MathComp-Analysis is not added in slice 1. It becomes a separate dependency decision only if the concrete next theorem requires capabilities that Coq stdlib + Coquelicot cannot express cleanly. This avoids creating a second analysis hierarchy without evidence that it is needed.

## Closure probe

The closure probe imports `O0.v` and requires that `O0_closure` is absent. CI treats that theorem-level RED as the expected state and emits an O₀ receipt with `established=false` and `rh_proven=false`.

If `O0_closure` is later introduced, CI switches from the negative probe to a positive check that must establish all of the following on the exact candidate head:

1. `Check O0_closure : RiemannHypothesis.` succeeds.
2. `Print Assumptions O0_closure` contains `Closed under the global context`.
3. No `Axiom`/`Parameter`/`Admitted` declarations occur in the O₀ source closure.
4. The receipt binds the source commit, source digests, theorem type check, and assumption log.

No receipt may infer RH from the mere presence of a theorem name, from a source hash, or from GREEN CI.

## Non-claims

Slice 1 does not establish the analytic Guinand–Weil identity, positive Archimedean operator tail order, density, continuity, universal coverage, global Weil positivity, the classical Weil equivalence, or RH.
