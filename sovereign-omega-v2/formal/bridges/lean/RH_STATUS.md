# RH formal status — `proof/rh-restricted-weil-final-bridge-v13`

Ledger as of 2026-09-24. Everything below is either a kernel-checked Lean fact on the
pinned toolchain or a mechanical scan result. Nothing here is interpretation.

Toolchain pin: Lean 4.33.1 · Mathlib `0df444a360eaa60ab8c11dca51a86af692955474`.
Axiom target for every theorem: `[propext, Classical.choice, Quot.sound]`. `sorryAx` is 0 everywhere.

## 1. What is proved (kernel-accepted)

| Theorem | Statement | Module |
|---|---|---|
| `final_sign_implies_rh_v13` | `FinalSignResidualV1 → RiemannHypothesis` | `RHRestrictedWeilBridgeV13` |
| `restricted_weil_criterion_kernel_bridge_v13` | `RestrictedWeilCriterionKernelBridgeV10` (= `UniversalZeroQuadraticNonnegativeV10 → RiemannHypothesis`) | `RHRestrictedWeilBridgeV13` |
| `millennium_moment_iff_universal_v13` | `MillenniumMomentReachedV10 ↔ UniversalZeroQuadraticNonnegativeV10` | `RHRestrictedWeilBridgeV13` |
| `rh_implies_final_sign_residual_v13` | `RiemannHypothesis → FinalSignResidualV1` | `WeilRHImpliesFinalSignV13` |
| `rh_iff_final_sign_v13` | `RiemannHypothesis ↔ FinalSignResidualV1` | `WeilRHImpliesFinalSignV13` |
| `rh_iff_universal_v13` | `RiemannHypothesis ↔ UniversalZeroQuadraticNonnegativeV10` | `WeilRHImpliesFinalSignV13` |
| `millennium_moment_iff_rh_v13` | `MillenniumMomentReachedV10 ↔ RiemannHypothesis` | `WeilRHImpliesFinalSignV13` |

`RiemannHypothesis` is Mathlib's own definition
(`∀ s, riemannZeta s = 0 → ¬(∃ n : ℕ, s = -2 * (n + 1)) → s ≠ 1 → s.re = 1 / 2`).

Consequence: the repository's Millennium gate `MillenniumMomentReachedV10` is **exactly** RH.
The restricted Weil criterion is closed as an equivalence in both directions.

## 2. What is NOT proved — the single open target

```
UniversalZeroQuadraticNonnegativeV10 :=
  ∀ g : WeilCompactSmoothGV1, WeilMomentConditionsV1 g →
    0 ≤ (∑' rho : RiemannNontrivialZeroIndexV2,
           WeilZeroIndexSummandV1 (WeilAutocorrelationV1 g) rho).re
```

By §1 this proposition is logically equivalent to RH. Proving it *from the arithmetic side*
(prime sums + Archimedean term, without assuming anything about zeros) is the entire
content of the Riemann Hypothesis under Weil's criterion. No module does this.

Acceptance probe (`DeepMindAcceptanceCheckV13c.lean`):

```
example : RiemannHypothesis := by exact?                          -- fails
example : RiemannHypothesis := by rw [rh_iff_universal_v13]; exact?  -- fails
```

There is no Lean term of type `RiemannHypothesis` in this repository.

## 3. Repository-wide scan (mechanical)

Scope: every `.lean` blob on every remote branch — 133 `proof/*`/`agents/*`/`research/*`/… branches,
211 distinct paths, **246 distinct blobs, 1 600 theorems, 321 definitions**.

Method: parse each theorem signature; take the conclusion after the last depth-0 `:`; follow every
`↔` to collect the RH-equivalent class; list producers of each member and their hypotheses.

RH-equivalent class found:
`RiemannHypothesis`, `FinalSignResidualV1`, `UniversalZeroQuadraticNonnegativeV10`,
`MillenniumMomentReachedV10`, `RHMillenniumCertificateV10`, `RestrictedWeilCriterionKernelBridgeV10`,
`WeilCompactSmoothNegativityV1`, `ZeroShiftComponentDominanceV1`.

Result: **the only unconditional, non-`↔` theorem whose conclusion lies in that class is
`restricted_weil_criterion_kernel_bridge_v13`** — which is itself an implication
(`Universal → RH`). Every other producer either is an `↔` or takes a member of the class as a hypothesis.
No `sorry`, no `axiom` anywhere in the 246 blobs.

Modules that a `*Spec.lean` file `#check`s but that exist on **no** branch (the claims have no source):
`WeilAbjadGramPositivityV1`, `GaussSeriesIntegralReductionV1`, `ZeroCountingOnePlusEpsilonV2`.

### Partial sign results that exist (and what they are not)

| Theorem | Proves | Scope limit (from its own header) |
|---|---|---|
| `canonical_four_packet_sign_v3` (`RHFourBlockConcreteV3`, branch `agents/rh-proof-closure-swarm-v1`) | arithmetic side `≤ 0` for the four-packet family with log-support width ≤ 1/64 | "finite-family statement, not density, globalization, universal Weil sign or RH. Compilation NOT_RUN" |
| `weil_compact_smooth_negativity_iff_all_windows_v1` (`WeilWindowExhaustionV1`) | universality ⇔ nonpositivity on every window `[-L, L]` | reduces the quantifier; each window still open |
| `arch_weight_digamma_neg_at_zero`, `arch_weight_real_neg_at_quarter` | sign of the Archimedean weight at specific points | pointwise, not the quadratic form |
| `weil_arch_weighted_tail_quadratic_nonpositive_v1` | tail quadratic `≤ 0` **given** a nonpositive weight on `[A, B]` | conditional on the weight sign |
| `abstract_bridge_carries_all_of_rh` (`WeilSemanticBridgeObstructionV1`) | any bridge from an *abstract* positivity to RH already carries all of RH | obstruction result — negative, not progress |

None of these produce `UniversalZeroQuadraticNonnegativeV10`.

## 4. Reproduce

```
# sources: aegis_rh/*.lean next to the Mathlib checkout; oleans in aegis_rh_out/
python3 build_target.py WeilRHImpliesFinalSignV13      # expect [118/118] rc=0 sorryAx=0 ALL BUILT
lean -R aegis_rh aegis_rh/DeepMindAcceptanceCheckV13c.lean   # expect both exact? to fail
```

Pushed blobs are byte-verified against the compiled sources:
`RHRestrictedWeilBridgeV13.lean` = `cda7c59f`, `WeilRHImpliesFinalSignV13.lean` = `7b00e26b`.

## 5. Honest one-line summary

The Weil-type criterion `RH ↔ UniversalZeroQuadraticNonnegativeV10` is formally closed.
RH itself is open; the repository contains no proof of it, and nothing in it is submitted upstream.
