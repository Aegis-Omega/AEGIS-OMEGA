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
| `five_block_certificate_impossible` | the four-block certificate schema admits no five-block extension with the same constants | `RHFourBlockCertificateLimitV13` |

`RiemannHypothesis` is Mathlib's own definition
(`∀ s, riemannZeta s = 0 → ¬(∃ n : ℕ, s = -2 * (n + 1)) → s ≠ 1 → s.re = 1 / 2`).

Consequences:
- the repository's Millennium gate `MillenniumMomentReachedV10` is **exactly** RH; the restricted
  Weil criterion is closed as an equivalence in both directions;
- the RH-equivalent predicate is **verified unconditionally on the four-translate span
  `{Σ_{k=0}^{3} z_k · T_{k·log 2} g}` of every moment-zero packet `g` of log-support width ≤ 1/64**;
- the method that produced that verification provably stops at four translates (§3c).

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

Phase-sensitive cross-term information (a bound on `Re B`, not `‖B‖`) exists in exactly three
theorems, and each takes the target as hypothesis:
`universal_zero_quadratic_implies_twoPoint_translate_sign_v10` (assumes Universal),
`final_sign_implies_translate_component_bounds_v11` / `…_cross_bounds_v11` (assume FinalSign).
`mixed_translate_B_eq_neg_zero_tsum_v10` identifies every translated cross term with the zero-side
sum — the phase of a cross term *is* zero-side information.

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

### The four-translate family

`RHFourBlockConcreteV3` derives, with **no analytic hypotheses beyond width ≤ 1/64 and the two
moment conditions**:

- diagonal: `32/25 · E ≤ −Re B(T_d g, T_d g)` for each of the four translates
  (`RHNarrowDiagonalUpgradeV2`, from the Archimedean budget on `(1/64, 1/32]`);
- cross terms: `‖B‖ ≤ 51/100 · E` (gap `log 2`), `9/25 · E` (gap `2 log 2`), `13/50 · E`
  (gap `3 log 2`; the `n = 8` dyadic prime term `Λ(8) = log 2`, `RHFourBlockPrimeEightV3`);
- SOS certificate `158/125 · energy4 − cross4 = comparisonSOS ≥ 0` (`RHFourBlockComparisonV2`),
  leaving coercivity margin `32/25 − 158/125 = 2/125`.

## 3c. Where the method stops (kernel-checked + arithmetic)

**Kernel-checked** (`RHFourBlockCertificateLimitV13`, axioms `[propext, Classical.choice, Quot.sound]`):

- `five_block_all_ones_value`: with ceilings `51/100, 9/25, 13/50` and fourth-gap ceiling `0`, the
  five-translate worst case on the all-ones vector is `5·32/25 − 7.28 = −22/25`.
- `five_block_certificate_impossible (r) (hr : 0 ≤ r)`: for **every** nonnegative fourth-gap
  ceiling, `¬ ∀ x, cross5 … r x ≤ 32/25 · energy5 x`. The five-block analogue of
  `actual_four_block_bound_v2` is false as a statement about norm ceilings.
- `interior_row_exceeds_diagonal`: `2·(51/100 + 9/25) > 32/25` — the interior of any chain of
  ≥ 5 translates already violates Gershgorin with the first two ceilings alone.

**Arithmetic** (the repository's own window rule, `mixed_translate_zero_of_width_v28`:
the cross term at gap `k·log 2` sees only integers `m` with `|log m − k·log 2| ≤ 1/32`, and
`mixed_translate_center_v28` gives each such sample weight `≈ 2^{k/2}·E`, so the prime side is
`Σ_{m ∈ window} Λ(m)·2^{-k/2}·E` up to a bump factor ≤ 1):

| gap `k` | integers in window with `Λ ≠ 0` | `Σ Λ(m)·2^{-k/2}` | repo ceiling |
|---|---|---|---|
| 1 | 2 | 0.490 | 0.51 |
| 2 | 4 | 0.347 | 0.36 |
| 3 | 8 | 0.245 | 0.26 |
| 4 | 16 | 0.173 | — |
| 5 | 32 | 0.123 | — |
| 6 | 64 | 0.087 | — |
| 7 | 125, 127, 128, 131 | **1.063** | — |
| 8 | 251, 256, 257, 263 | 1.084 | — |
| 9 | 499, 503, 509, 512, 521, 523 | 1.409 | — |
| 10 | 997 … 1051 | 2.188 | — |
| 12 | 3989 … 4219 | 3.780 | — |
| 15 | 31769 … 33797 | 11.837 | — |

For `k ≤ 6` the window contains a single dyadic sample and the ceiling decays like `2^{-k/2}`;
that is exactly why the four-block lane works. From `k = 7` on, primes enter the window and the
prime mass grows like `2^{k/2}·(1/16)` (prime number theorem in the interval
`[2^k e^{-1/32}, 2^k e^{1/32}]`). **Any norm ceiling on wide-gap cross terms therefore grows
exponentially in the gap.** The true cross term is small only through cancellation of
`ψ(x) − x` over short intervals — and `mixed_translate_B_eq_neg_zero_tsum_v10` says that
cancellation is, term for term, the zero-side sum. This is the precise point where the
repository's method ends, and it is Weil's circularity, not a missing lemma: bounding the wide-gap
cross terms from the arithmetic side requires prime distribution in short intervals of relative
width `1/16`, i.e. zero-free-region input of RH strength.

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
python3 build2.py RHFourBlockCertificateLimitV13        # expect rc=0 sorryAx=0 OK
lean -R aegis_rh aegis_rh/DeepMindAcceptanceCheckV13c.lean   # expect both exact? to fail
```

Pushed blobs are byte-verified against the compiled sources:
`RHRestrictedWeilBridgeV13.lean` = `cda7c59f`, `WeilRHImpliesFinalSignV13.lean` = `7b00e26b`,
`RHFourBlockConcreteV3.lean` = `1dbb003a`, `RHFineMomentPacketV3.lean` = `5b169696`,
`RHFourPacketZeroQuadraticV13.lean` = `d770bc0c`, `WeilLogTransportCanonicalV1.lean` = `75e8f3c9`.

## 5. Honest one-line summary

The Weil-type criterion `RH ↔ UniversalZeroQuadraticNonnegativeV10` is formally closed; the
RH-equivalent quadratic is kernel-verified nonnegative on a 4-parameter family per narrow seed; the
method behind that verification is kernel-proved to stop at four translates, because wide-gap cross
terms are governed by primes in short intervals. RH itself is open; the repository contains no proof
of it, and nothing in it is submitted upstream.
