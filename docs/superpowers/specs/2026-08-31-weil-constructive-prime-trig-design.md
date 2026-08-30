# Weil Constructive Prime Trig — Design

## Scope

Stacked production proof slice on `proof/weil-prime-diagonal-v1@44015987bee321e0dd722f1c67b909d141f75512`.

The slice closes only the constructive trigonometric phase identities currently left as an explicit premise by `FinitePrimeDiagonal.v`. It does not claim the AEGIS O0 carrier commutes with CoRN sine/cosine, does not prove the sine derivative transport used by the executable closed-form route, does not complete the finite prime dictionary, and does not prove the Guinand–Weil explicit formula, Weil positivity, or RH.

## Mathematical target

Use pinned `coq-corn.9.0.0` and its constructive `IR` trigonometry to prove, for every `r : IR` and `n : nat`, the two integer-frequency complement identities:

```text
Cos (Two * nring n * Pi * (1 - r)) == Cos (Two * nring n * Pi * r)
Sin (Two * nring n * Pi * (1 - r)) == - Sin (Two * nring n * Pi * r)
```

The proof must reduce the complement phase to a negative direct phase plus an integer multiple of `Two*Pi`, then use CoRN periodicity and parity (`Cos_periodic_Z`, `Sin_periodic_Z`, `Cos_inv`, `Sin_inv`). No new trigonometric axioms or classical `Reals` authority are permitted.

Exact theorem names exposed by the production module:

- `prime_diagonal_constructive_cos_phase_v1`
- `prime_source_constructive_sin_phase_v1`

## Authority boundary

The new module is production `FORMAL_MATH_EVIDENCE_ONLY` and must be included in the complete Coq formal-attestation inventory. `coq-corn.9.0.0` is a new pinned production proof dependency and therefore must be installed in the same exact Coq 8.20 lane as the existing attestation job.

The new theorem slice establishes only the phase identities on the CoRN constructive `IR` carrier. The existing O0 production carrier remains `CRcarrier CRealConstructive`. Existing proof-only morphisms between CoRN fast reals and O0 are not sufficient to claim that sine/cosine commute with the morphism. Therefore the following remain false after this slice:

```text
corn_o0_trig_transport_machine_bound = false
prime_source_sine_derivative_machine_bound = false
prime_diagonal_dictionary_formalized = false
analytic_pole_normalization_machine_bound = false
archimedean_entry_identity_proven = false
guinand_weil_explicit_formula_machine_bound = false
formula_to_weil_operator_identity_proven = false
global_weil_positivity_proven = false
rh_proven = false
```

`prime_diagonal_trig_periodicity_machine_bound` may become true only with the explicit scope `CORN_IR_PHASE_IDENTITY`; it must not be interpreted as an O0 transport theorem.

## TDD and verification

1. Add `formal/tests/Weil/PrimeTrigConstructiveSpec.v` first. It imports `PrimeTrigConstructive` and checks the two theorem names. Before the production module exists, the dedicated workflow must fail at the intended missing-module boundary.
2. Add `formal/theories/Weil/PrimeTrigConstructive.v` with the minimal constructive proofs and no `Axiom`, `Parameter`, or `Admitted`.
3. Add a dedicated exact-head workflow `weil-constructive-prime-trig.yml` that pins Coq 8.20 and `coq-corn.9.0.0`, compiles the module and RED/GREEN specification, runs `Print Assumptions` for both theorems, rejects declared assumptions, and emits a content-addressed receipt.
4. Extend `coq-formal-attestation.yml` to install `coq-corn.9.0.0`, compile `Weil/PrimeTrigConstructive.v`, and require it to be axiom-free.
5. Do not alter `FinitePrimeDiagonal.v` in this slice. Concrete instantiation of its rational phase premise belongs to the later O0/trig transport bridge, because the present theorem carrier is CoRN `IR` rather than the rational value interface consumed by that module.

## Success criteria

The candidate is successful only if the dedicated workflow and the complete Coq formal attestation both pass on the exact same head SHA; both theorem assumption reports must be `Closed under the global context`; all frozen negative claims remain false; and the PR remains a stacked draft on `proof/weil-prime-diagonal-v1`.
