# RH formal status — `proof/rh-restricted-weil-final-bridge-v13`

Ledger as of 2026-09-24. Everything below is either a kernel-checked Lean fact on the
pinned toolchain or a mechanical scan/compile result. Nothing here is interpretation.

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
| `four_packet_coercive_v3` | width ≤ 1/64 ∧ moments ⇒ `Re RHS(Autocorr(fourPacket g z)) ≤ −(2/125)·E(g)·energy4‖z‖` | `RHFourBlockConcreteV3` |
| `fourPacket_zero_quadratic_nonnegative_v13` | same hypotheses ⇒ `0 ≤ Re Σ_ρ m_ρ M(Autocorr(fourPacket g z))(ρ)` for all `z ∈ ℂ⁴` | `RHFourPacketZeroQuadraticV13` |
| `canonical_zero_quadratic_nonnegative_v13` | the `gFine` instance (nonzero seed, width 1/64) | `RHFourPacketZeroQuadraticV13` |

`RiemannHypothesis` is Mathlib's own definition
(`∀ s, riemannZeta s = 0 → ¬(∃ n : ℕ, s = -2 * (n + 1)) → s ≠ 1 → s.re = 1 / 2`).

Consequences:
- the repository's Millennium gate `MillenniumMomentReachedV10` is **exactly** RH; the restricted
  Weil criterion is closed as an equivalence in both directions;
- the RH-equivalent predicate is **verified unconditionally on the four-translate span
  `{Σ_{k=0}^{3} z_k · T_{k·log 2} g}` of every moment-zero packet `g` of log-support width ≤ 1/64**.

## 2. What is NOT proved — the single open target

```
UniversalZeroQuadraticNonnegativeV10 :=
  ∀ g : WeilCompactSmoothGV1, WeilMomentConditionsV1 g →
    0 ≤ (∑' rho : RiemannNontrivialZeroIndexV2,
           WeilZeroIndexSummandV1 (WeilAutocorrelationV1 g) rho).re
```

By §1 this proposition is logically equivalent to RH. §1 proves it on a 4-parameter family per
narrow seed; it is open for general `g`. Proving it for all `g` from the arithmetic side is the
entire content of the Riemann Hypothesis under Weil's criterion. No module does this.

Acceptance probe (`DeepMindAcceptanceCheckV13c.lean`):

```
example : RiemannHypothesis := by exact?                          -- fails
example : RiemannHypothesis := by rw [rh_iff_universal_v13]; exact?  -- fails
```

There is no Lean term of type `RiemannHypothesis` in this repository.

## 3. Repository-wide scan (signature level)

Scope: every `.lean` blob on every remote branch — 133 branches, 211 distinct paths,
**246 distinct blobs, 1 600 theorems, 321 definitions**.

Method: parse each theorem signature; take the conclusion after the last depth-0 `:`; follow every
`↔` to collect the RH-equivalent class; list producers of each member and their hypotheses.

RH-equivalent class found:
`RiemannHypothesis`, `FinalSignResidualV1`, `UniversalZeroQuadraticNonnegativeV10`,
`MillenniumMomentReachedV10`, `RHMillenniumCertificateV10`, `RestrictedWeilCriterionKernelBridgeV10`,
`WeilCompactSmoothNegativityV1`, `ZeroShiftComponentDominanceV1`.

Result: **the only unconditional, non-`↔` theorem whose conclusion lies in that class is
`restricted_weil_criterion_kernel_bridge_v13`** — itself an implication (`Universal → RH`).
Every other producer either is an `↔` or takes a member of the class as a hypothesis.
No `sorry`, no `axiom` anywhere in the 246 blobs.

Modules that a `*Spec.lean` file `#check`s but that exist on **no** branch (the claims have no source):
`WeilAbjadGramPositivityV1`, `GaussSeriesIntegralReductionV1`, `ZeroCountingOnePlusEpsilonV2`.

## 3b. Blob-level compile audit (every out-of-chain module, at the pin)

The 46 Lean modules that were on some branch but not in this branch's import closure were
all compiled on the pinned toolchain (`Spec`/`AxiomCheck`/`Control`/`NonVacuity` helpers excluded).

**35 build with 0 `sorryAx`.** Among them: `RHFourBlockActualBridgeV2`, `RHFourBlockComparisonV2`,
`RHNarrowDiagonalUpgradeV2`, `RHFourBlockPrimeEightV3`, `RHFourBlockMarginV1`,
`WeilWindowExhaustionV1`, `WeilArchTailWeightSignV1`, `WeilArchWeightRealSignV1`,
`WeilArchWeightDigammaSignV1`, `WeilMixedLogKernelV27`, `WeilSemanticBridgeObstructionV1`,
`ZeroShellFactorizationV1`, `ZetaDivisorExhaustionV1`, `ZetaDivisorLedgerV1`, …

**11 failed**, with cause:

| Module | Cause |
|---|---|
| `RHFourBlockConcreteV3`, `RHFineMomentPacketV3` | dependency `WeilLogTransportCanonicalV1` had its imports after the docstring (parse error) — **repaired in this branch**; both now build |
| `AegisLiCriterionRebindV1`, `Audit` | import `FormalConjectures.*` / `Lc.LiCriterion.*` — external projects, not in this repo |
| `ZeroRadialTruncationV1` | 11 errors |
| `ZetaDivisorSupportBridgeV1`, `EpistemicAuthorityConservationV1` | 4 errors each |
| `ZeroNegativeIntegerClassificationV1` | 2 errors |
| `WeilAutocorrelationPrimeWindowsV1`, `WeilThreeBlockPrimeWindowsV22`, `GravityQuantumPureProductV1` | 1 error each |

### The four-translate family and why it does not globalize by itself

`RHFourBlockConcreteV3` derives, with **no analytic hypotheses beyond width ≤ 1/64 and the two
moment conditions**:

- diagonal: `32/25 · E ≤ −Re B(T_d g, T_d g)` for each of the four translates
  (`RHNarrowDiagonalUpgradeV2`, from the Archimedean budget on `(1/64, 1/32]`);
- cross terms: `‖B‖ ≤ 51/100 · E` (gap `log 2`), `9/25 · E` (gap `2 log 2`), `13/50 · E`
  (gap `3 log 2`; the `n = 8` dyadic prime term `Λ(8) = log 2`, `RHFourBlockPrimeEightV3`);
- SOS certificate `158/125 · energy4 − cross4 = comparisonSOS ≥ 0` (`RHFourBlockComparisonV2`),
  leaving coercivity margin `32/25 − 158/125 = 2/125`.

The margin is `2/125 ≈ 0.016` out of a diagonal `1.28`. The Gershgorin row sum for four blocks is
`0.51 + 0.36 + 0.26 = 1.13 < 1.28`. Adding a fifth translate with any nonnegative cross bound
`c₄` gives interior row sums `≥ 2·0.51 + 2·0.36 + 0.26 = 2.0 > 1.28`; even the SOS route cannot
recover a margin once the interior rows exceed the diagonal. So **this family is a finite-family
verification, not the start of an exhaustion**: the constants themselves rule out extending the same
scheme to `n → ∞` translates, and `WeilWindowExhaustionV1` (which reduces universality to
"all windows `[-L, L]`") needs every window, i.e. arbitrarily many overlapping translates.

Partial sign results that also exist (all compile) and what they are not:

| Theorem | Proves | Scope limit |
|---|---|---|
| `weil_compact_smooth_negativity_iff_all_windows_v1` (`WeilWindowExhaustionV1`) | universality ⇔ nonpositivity on every window `[-L, L]` | quantifier reduction only |
| `arch_weight_digamma_neg_at_zero`, `arch_weight_real_neg_at_quarter` | sign of the Archimedean weight at specific points | pointwise |
| `weil_arch_weighted_tail_quadratic_nonpositive_v1` | tail quadratic `≤ 0` **given** a nonpositive weight on `[A, B]` | conditional |
| `abstract_bridge_carries_all_of_rh` (`WeilSemanticBridgeObstructionV1`) | any bridge from an *abstract* positivity to RH already carries all of RH | obstruction, negative |

None of these produce `UniversalZeroQuadraticNonnegativeV10`.

## 4. Reproduce

```
# sources: aegis_rh/*.lean next to the Mathlib checkout; oleans in aegis_rh_out/
python3 build_target.py WeilRHImpliesFinalSignV13      # expect [118/118] rc=0 sorryAx=0 ALL BUILT
python3 build2.py RHFourPacketZeroQuadraticV13          # expect rc=0 sorryAx=0 OK
lean -R aegis_rh aegis_rh/DeepMindAcceptanceCheckV13c.lean   # expect both exact? to fail
```

Pushed blobs are byte-verified against the compiled sources:
`RHRestrictedWeilBridgeV13.lean` = `cda7c59f`, `WeilRHImpliesFinalSignV13.lean` = `7b00e26b`,
`RHFourBlockConcreteV3.lean` = `1dbb003a`, `RHFineMomentPacketV3.lean` = `5b169696`,
`RHFourPacketZeroQuadraticV13.lean` = `d770bc0c`, `WeilLogTransportCanonicalV1.lean` = `75e8f3c9`.

## 5. Honest one-line summary

The Weil-type criterion `RH ↔ UniversalZeroQuadraticNonnegativeV10` is formally closed, and the
RH-equivalent quadratic is kernel-verified nonnegative on a 4-parameter family per narrow seed.
RH itself is open; the repository contains no proof of it, and nothing in it is submitted upstream.
