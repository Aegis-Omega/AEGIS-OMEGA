# RH formal status — `proof/rh-restricted-weil-final-bridge-v13`

Ledger as of 2026-09-26. Everything below is either a kernel-checked Lean fact on the
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
| `nine_faces_of_rh_v13` | all nine repository RH-equivalent formulations `↔ RiemannHypothesis` in one statement | `RHNineFacesV13` |
| `four_packet_coercive_v3` | width ≤ 1/64 ∧ moments ⇒ `Re RHS(Autocorr(fourPacket g z)) ≤ −(2/125)·E(g)·energy4‖z‖` | `RHFourBlockConcreteV3` |
| `fourPacket_zero_quadratic_nonnegative_v13` | same hypotheses ⇒ `0 ≤ Re Σ_ρ m_ρ M(Autocorr(fourPacket g z))(ρ)` for all `z ∈ ℂ⁴` | `RHFourPacketZeroQuadraticV13` |
| `five_block_certificate_impossible` | the four-block certificate schema admits no five-block extension with the same constants | `RHFourBlockCertificateLimitV13` |
| `diagonal_lower` | `∀ 0 < r ≤ 1/64`: `E·(cothTail(2r) − κ − r·e^{1/64}) ≤ −Re B(g,g)` at log-half-width `r` | `RHDyadicDiagonalV13` |
| `cothTail_ge'`, `cothTail_ge_below_32`, `cothTail_dyadic` | `e^{-c}·log(c/w) + cothTail c ≤ cothTail w`; `e^{-1/32}·log(1/(32w)) + 6 log 2 ≤ cothTail w`; dyadic form | `RHDyadicDiagonalV13` |
| `gap_B_norm_bound_pair` | `d₂ − d₁ = k log 2`, `2r ≤ 2^{-(k+1)}` ⇒ `‖B(T_{d₁}g, T_{d₂}g)‖ ≤ (log 2·2^{-k/2} + 1/100)·E` | `RHDyadicWindowV13` |
| `B_packetSum` | `B(Σ zᵢgᵢ, Σ zⱼgⱼ) = Σᵢⱼ zᵢ z̄ⱼ B(gᵢ,gⱼ)` for every `n` (the gap-kernel form `Q_N`) | `RHGramExpansionV13` |
| `gram_re_le`, `rowSum_le` | Gershgorin: `Re B(Σzg, Σzg) ≤ −(D − S)·E·Σ‖z‖²`; `rowSum ≤ 2Σ_{k=1}^{n} c_k` | `RHGramExpansionV13` |
| `B_norm_le_arch_of_window_pair` | prime-power-free window of radius `2r` at gap `d ≥ log 2` ⇒ `‖B‖ ≤ E/100` | `RHRatioWindowV13` |
| `window_all` | at half-width `1/256` the windows around `(33/16)^k`, `k = 1..8`, are prime-power-free | `RHRatio33Over16V13` |
| `ninePacket_coercive` | `Re RHS(Autocorr(Σ_{k<9} z_k T_{k log(33/16)} g)) ≤ −(D256 − 4/25)·E·Σ‖z_k‖²`, `D256 > 23/10` | `RHNinePacket33Over16V13` |
| `ninePacket_zero_quadratic_nonnegative` | `0 ≤ Re Σ_ρ m_ρ M(Autocorr(ninePacket g z))(ρ)` for all `z ∈ ℂ⁹`, every moment-zero `g` of half-width `1/256` | `RHNinePacket33Over16V13` |
| `narrow_coercive`, `universal_on_narrow_class` | for every moment-zero `g` of half-width `≤ 1/64` (any shape, any dense combination inside the window): `Re RHS ≤ −(103/100)·E`, hence `0 ≤` the zero quadratic — the whole narrow-support class, no lattice | `RHNarrowSupportPositivityV13` |
| `margin_pos`, `tower_coercive` | `m ≥ max 10 (N+2)` ⇒ `Dm m − 2(log 2·2.42 + N/100) ≥ 0`; `Re RHS(Autocorr(Σ_{j≤N} z_j T_{j log 2} g)) ≤ −margin·E·Σ‖z‖²` | `RHDyadicTowerV13` |
| `dyadic_tower` | `∀ N, ∃ m, ∀ g a, HalfWidthAt g 2^{-m} a → moments → ∀ z : Fin (N+1) → ℂ, 0 ≤ Re Σ_ρ m_ρ M(Autocorr(towerPacket N g z))(ρ)` — unbounded tower of dyadic families | `RHDyadicTowerV13` |
| `moment_log_identity` | moments ⇒ `∫₀^∞ e^u·Re A(e^u)·(1 + e^{−u}) du = 0` (the two Mellin endpoint moments folded by the reciprocal symmetry `A(1/x) = x·conj A(x)`) | `RHMomentIdentityV13` |
| `arch_moment_budget` | `r > 0`, half-width `r`, moments ⇒ `Re Arch ≤ E·(cothTail(2r) − 2cothTail(r) + (r/2)e^{r/2} + 4(cosh(r/2) − 1))` | `RHMomentGainV13` |
| `moment_diagonal` | additionally `2r < log 2` ⇒ `Re RHS ≤ momentGain(r)·E`; the diagonal floor rises by `≈ log 4` at every width | `RHMomentGainV13` |
| `momentGain_eighth`, `wide_coercive` | `momentGain(1/8) ≤ −1/5`; every moment-zero `g` of half-width `1/8` has `Re RHS ≤ −(1/5)·E` | `RHMomentNumericsV13`, `RHMomentGainV13` |
| `wide_zero_quadratic_nonnegative`, `universal_on_wide_class` | `0 ≤` the zero quadratic for every moment-zero `g` of log-half-width `≤ 1/8` (log-support length `≤ 1/4`, any shape) — the narrow class widened eightfold | `RHMomentGainV13` |
| `half_cap_logCorrelation` | half-width `r`, shift `u > r` ⇒ `‖logCorrelation g u‖ ≤ E/2` (Cauchy–Schwarz on the two disjoint halves of the support) | `RHHalfCapV13` |
| `arch_half_cap_budget`, `half_cap_diagonal` | moment gain with the half-cap on `(r, 2r]`: `Re RHS ≤ halfGain(r)·E` below `log 2` | `RHHalfCapGainV13` |
| `halfGain_11_64`, `universal_on_half_cap_class` | `halfGain(11/64) ≤ −1/20`; `0 ≤` the zero quadratic for every moment-zero `g` of log-half-width `≤ 11/64` (support length `≤ 11/32`) | `RHHalfCapClassV13` |
| `arch_threshold_budget`, `threshold_diagonal` | the same budget with the kernel threshold `t ≤ r` free (multiplier `lamR t`): `Re RHS ≤ thrGain(t, r)·E` below `log 2` | `RHThresholdGainV13` |
| `thrGain_5_32_one_fifth`, `universal_on_one_fifth_class` | `thrGain(5/32, 1/5) ≤ −1/100`; `0 ≤` the zero quadratic for every moment-zero `g` of log-half-width `≤ 1/5` (support length `≤ 2/5`) | `RHThresholdClassV13` |
| `half_le_bonus`, `bonus_diagonal` | `(e^{u/2} − 1)/sinh u ≥ ½` on `(0, 1]`; kept on the lower-bound pieces: `Re RHS ≤ bonusGain(t, r)·E` | `RHBonusGainV13` |
| `bonusGain_5_32_21_100`, `universal_on_bonus_class` | `bonusGain(5/32, 21/100) ≤ −1/50`; `0 ≤` the zero quadratic for log-half-width `≤ 21/100` | `RHBonusClassV13` |
| `three_cell_logCorrelation` | `2r < 3u` ⇒ `‖logCorrelation g u‖ ≤ (71/100)·E` (three cells of length `u`, weighted AM–GM; the `n = 1` Boas–Kac case) | `RHThreeCellV13` |
| `arch_cell_budget`, `cell_diagonal` | budget split at `2r/3, t, r, 2r` with three-cell cap, half-cap and bonus: `Re RHS ≤ cellGain(t, r)·E` | `RHThreeCellGainV13` |
| `cellGain_5_32_7_32`, `universal_on_cell_class` | `cellGain(5/32, 7/32) ≤ −1/200`; `0 ≤` the zero quadratic for every moment-zero `g` of log-half-width `≤ 7/32` (support length `≤ 7/16`) | `RHThreeCellClassV13` |
| `hat_posdef`, `hat_posdef_Ioi` | for continuous compactly supported `G`, `h ≥ 0`, real `v`: `0 ≤ Σᵢⱼ vᵢvⱼ ∫ Re C(u)·T_h(u − (i−j)h) du` (`T_h(x) = max 0 (h − |x|)`), also folded onto `u > 0` — hat kernels are positive definite against autocorrelations | `RHHatPosDefV13` |
| `hatK_node`, `hatK_affine`, `hatK_run_integral` | `hatK(kh) = h·ρ_k` with `ρ_k = Σⱼ v_{j+k}vⱼ`; `hatK` affine on every cell `[kh,(k+1)h]`; trapezoid rule over runs of cells | `RHHatKernelV13` |
| `hat_arch_budget`, `hat_diagonal` | moment multiplier `λ` + positive-definite hat kernel `σ·hatK` + caps `1, 71/100, 1/2`: if `Q(u) = e^{u/2}/sinh u − 2λcosh(u/2) + σ·hatK(u) ≥ 0` on `(0, 2r]` then `Re RHS ≤ hatGain·E` below `log 2` | `RHHatBudgetV13` |
| `checkF`, `Q_of_checks` | `Q ≥ 0` on `(0, Nh]` follows from one rational inequality per sub-cell `[mh/s, (m+1)h/s]` (node values of `hatK`, monotonicity of `e^{u/2}/sinh u` and `cosh(u/2)`, fourth-order Taylor enclosures) | `RHHatCellsV13` |
| `Q_all`, `gain_bound`, `hat_coercive`, `universal_on_class` | 25 integer weights, `h = 1/24`, 48 sub-cells: `hatGain(1/4) ≤ −1/20`; `Re RHS ≤ −E/20`; `0 ≤` the zero quadratic for every moment-zero `g` of log-half-width `≤ 1/4` (support length `≤ 1/2`) | `RHHatClassV13` |
| `Q_all`, `gain_bound`, `hat_coercive`, `universal_on_class` | 49 integer weights, `h = 1/40`, 192 sub-cells: `hatGain(3/10) ≤ −1/50`; `Re RHS ≤ −E/50`; `0 ≤` the zero quadratic for every moment-zero `g` of log-half-width `≤ 3/10` (support length `≤ 3/5`) | `RHHatClass310V13` |
| `Q_all`, `gain_bound`, `hat_coercive`, `universal_on_class` | 289 integer weights (list `wL`, `ρ_k` by kernel evaluation of integer sums), `h = 1/72`, 192 sub-cells: `hatGain(1/3) ≤ −1/100`; `Re RHS ≤ −E/100`; `0 ≤` the zero quadratic for every moment-zero `g` of log-half-width `≤ 1/3` (support length `≤ 2/3`) | `RHHatClass13V13` |
| `expNeg_sq_lower`, `cell_QW`, `Q_of_checksW` | `e^{−3b/2} ≥ (1 − x + x²/2 − x³/6 + x⁴/24 − x⁵/100)²` at `x = 3b/4`, `b ≤ 4/3`; the sub-cell sweep of `Q_of_checks` with this enclosure, valid up to `Nh ≤ 4/3` (the old one stops at `2/3`) | `RHHatCellsWideV13` |
| `Q_all`, `gain_bound`, `hat_coercive`, `universal_on_class` | 505 integer weights, `h = 23/2800`, 336 sub-cells via `Q_of_checksW`: `hatGain(69/200) ≤ −1/200`; `Re RHS ≤ −E/200`; `0 ≤` the zero quadratic for every moment-zero `g` of log-half-width `≤ 69/200` (support length `≤ 0.69`, `99.5%` of the prime-free range `< log 2 ≈ 0.6931`) | `RHHatClass69200V13` |

`RiemannHypothesis` is Mathlib's own definition
(`∀ s, riemannZeta s = 0 → ¬(∃ n : ℕ, s = -2 * (n + 1)) → s ≠ 1 → s.re = 1 / 2`).

## 2. What is NOT proved — the single open target

```
UniversalZeroQuadraticNonnegativeV10 :=
  ∀ g : WeilCompactSmoothGV1, WeilMomentConditionsV1 g →
    0 ≤ (∑' rho : RiemannNontrivialZeroIndexV2,
           WeilZeroIndexSummandV1 (WeilAutocorrelationV1 g) rho).re
```

By §1 this proposition is logically equivalent to RH. §1 proves it on the whole class of
half-width `≤ 69/200` (any shape; `RHHatClass69200V13.universal_on_class`), on a 9-parameter family per narrow seed (ratio 33/16, width 1/256),
and on an `(N+1)`-parameter dyadic family per seed of width `2^{-max(10,N+2)}` for every `N`
(`dyadic_tower`); it is open for general `g` — in particular for every `g` whose log-support is
wider than `0.69` and is not a lattice combination of narrow seeds. Proving it for all `g` from the arithmetic side is the entire
content of the Riemann Hypothesis under Weil's criterion. No module does this.

Acceptance probes (`DeepMindAcceptanceCheckV13c.lean`, `NineFacesAcceptanceCheck.lean`): with every
equivalence imported, `exact?` fails on `RiemannHypothesis` and on each of its faces, before and
after rewriting around the cycle. There is no Lean term of type `RiemannHypothesis` in this repository.

## 3. Repository-wide scan (signature level)

Scope: every `.lean` blob on every remote branch — 133 branches, 211 distinct paths,
**246 distinct blobs, 1 600 theorems, 321 definitions**.

RH-equivalent class found: `RiemannHypothesis`, `FinalSignResidualV1`,
`UniversalZeroQuadraticNonnegativeV10`, `MillenniumMomentReachedV10`, `RHMillenniumCertificateV10`,
`RestrictedWeilCriterionKernelBridgeV10`, `WeilCompactSmoothNegativityV1`,
`ZeroShiftComponentDominanceV1`, `UniversalArithmeticNonpositiveV1`, the window forms.

Result: **the only unconditional, non-`↔` theorem whose conclusion lies in that class is
`restricted_weil_criterion_kernel_bridge_v13`** — itself an implication. Every other producer is an
`↔` or takes a member of the class as a hypothesis. No `sorry`, no `axiom` anywhere.

Phase-sensitive cross-term information (a bound on `Re B`, not `‖B‖`) exists in exactly three
theorems, each assuming the target. `mixed_translate_B_eq_neg_zero_tsum_v10` identifies every
translated cross term with the zero-side sum — the phase of a cross term *is* zero-side information.

No nine-packet modules (`B_translate_eq_of_gap_nine_v1`, `shift_gap_k_B_norm_v1`, PRs #660/#661/#665)
exist on any branch of this repository.

## 3b. Blob-level compile audit

The 46 out-of-chain Lean modules across all branches were compiled at the pin: 35 build with
0 `sorryAx`; 11 fail (2 import external projects; `RHFourBlockConcreteV3`/`RHFineMomentPacketV3`
failed only through `WeilLogTransportCanonicalV1`'s misplaced imports — repaired here; the rest have
1–11 genuine errors and none touches the RH-equivalent class).

## 3c. Where the width-1/64 constants stop

`five_block_certificate_impossible`: with ceilings `51/100, 9/25, 13/50` and any fourth-gap ceiling,
the five-translate worst case is negative (`5·32/25 − 7.28 = −22/25`). At the fixed window radius
`1/32` the dyadic single-sample regime ends at `k = 6`; from `k = 7` primes enter the window and the
prime mass grows like `2^{k/2}/16`.

## 3d. The width pattern

Diagonal grows like `log(1/r)` (`diagonal_lower` + `cothTail_ge_below_32`); dyadic-gap cross ceilings
form a geometric series (`gap_B_norm_bound_pair`), uniformly in width, and the single-sample regime
widens to `k ≈ m − 1` at half-width `2^{-m}`. So the dyadic lattice certifies `≈ m` translates at
half-width `2^{-m}` once `m ≥ 15` — an unbounded tower of finite verifications.

## 3e. The generic engine and the `33/16` lattice

**Engine** (`RHGramExpansionV13`): one gap kernel + one Gram expansion replace per-pair bounds.
`B_packetSum` is the Toeplitz form `Q_N(z) = Σ zᵢ z̄ⱼ β(j−i)` for every `N`; `gram_re_le` is the
Gershgorin certificate; `rowSum_le` turns a gap series into the row bound. Because
`B_translate_eq_of_gap` makes the kernel depend only on the gap, `N` blocks need `N − 1` gap
producers, not `N(N−1)/2` pair bounds.

**Why a non-integer ratio wins.** The cross term at gap `d` sees the integers in
`[e^{d−2r}, e^{d+2r}]`. On the dyadic lattice `2^k` always sits in the window, so every gap carries
prime mass `log 2·2^{-k/2}` (row sum `≈ 3.35·E`). On the `33/16` lattice at half-width `1/256` the
windows around `(33/16)^k`, `k = 1..8`, contain only `∅, ∅, ∅, {18}, ∅, {77}, {158,159,160},
{325..330}` — no prime power (`window_all`, kernel `decide`). So eight gap producers are
`≤ E/100` each and the row sum is `4/25·E`, against a diagonal `D256 > 2.3·E`:

  `Re RHS(Autocorr(ninePacket g z)) ≤ −(D256 − 4/25)·E·Σ‖z_k‖²`,  margin `> 2.14·E`.

That is nine translates at width `1/256` with a margin sixteen times larger than the dyadic
four-block margin `2/125`, from the same ingredients.

**Signed/Toeplitz-symbol certificates** gain nothing here: in the single-sample regime the prime part
of each `b_k` is a positive real, so the symbol `p(θ) = −D + 2Σ Re(b_k e^{ikθ})` is maximal at
`θ = 0`, where it equals the Gershgorin row sum. The gain comes from choosing a lattice whose windows
carry no prime mass, not from phases.

**What it is not.** `N` translates on a lattice of spacing `log q` with packets of width `2^{-m}` form
a sparse subspace of the test-function class; universality needs spacing `≈ width`, where neighbouring
cross terms reproduce the diagonal singularity and the Gram symbol is the zero-side spectral density.
The tower approaches universality in `N`, not in density. Not RH.

## 3f. Narrow class and the dyadic tower

`RHNarrowSupportPositivityV13`: the diagonal floor alone (no cross terms needed, because a single
packet is its own Gram form) gives `Re RHS ≤ −(103/100)·E` for every moment-zero `g` of half-width
`≤ 1/64`, so the RH-equivalent quadratic is nonnegative on the entire narrow-support class, including
every dense combination inside one window. This is the `N = 0` face of the tower with the seed left
free.

`RHDyadicTowerV13`: for every `N` the `(N+1)` translates `T_{j log 2} g`, `j ≤ N`, of one seed of
half-width `2^{-m}` with `m = max 10 (N+2)` satisfy `2·2^{-m} ≤ 2^{-(k+1)}` for every gap `k ≤ N`
(`hw_single_sample`), so each cross term is one dyadic sample `(log 2·2^{-k/2} + 1/100)·E`
(`gap_B_norm_bound_pair`), the row sum is `≤ 2(log 2·2.42 + N/100)·E` (`sum_dyadicHalf_le`,
geometric series in `2^{-1/2}`), and the diagonal `Dm m ≥ (31/32)(m−6)log 2 + 6 log 2 − κ − 1/60`
grows linearly in `m` (`Dm_ge`, from `cothTail_ge_below_32`). The margin is positive
(`margin_pos`) and `dyadic_tower` follows through `gram_re_le`. Axioms of `dyadic_tower`:
`[propext, Classical.choice, Quot.sound]`.

Still not RH: the width shrinks as `N` grows, so the family never becomes dense at any fixed width.

## 3g. The moment gain and the wide class

`RHMomentIdentityV13` turns the two moment conditions into one log-coordinate identity,
`∫₀^∞ h(u)(1 + e^{−u}) du = 0` with `h(u) = e^u·Re A(e^u)`: the Mellin endpoints `s = 0, 1` are folded
onto `u > 0` by the reciprocal symmetry `A(1/x) = x·conj A(x)`. `RHMomentGainV13` subtracts
`λ·h(u)(1 + e^{−u})` from the Archimedean integrand with `λ = 1/(sinh r·(1 + e^{−r}))`, whose kernel
changes sign exactly at `u = r`, and integrates the resulting majorants on `(0, r]`, `(r, 2r]`,
`(2r, ∞)`. Result: `Re RHS ≤ momentGain(r)·E` whenever `2r < log 2` (no prime term reaches the window),
and `momentGain(1/8) ≤ −1/5` (true value `≈ −0.2806`). So every moment-zero test function of
log-support length `≤ 1/4` is Weil-positive — Yoshida's small-support theorem (1992; reproved by
Bombieri) in kernel-checked form, with an explicit window.

Numerical frontier of this route (support length `L = 2r`, energy units):

| method | provable up to `L` |
|---|---|
| crude pointwise bound (§1, `diagonal_lower`) | `≈ 0.042` (formalized at `1/32`) |
| moment identity, closed form (`momentGain`) | `≈ 0.322` (formalized at `1/4`) |
| moment identity, exact linear program | `≈ 0.354` |
| + Cauchy–Schwarz / Boas–Kac pointwise caps | `≈ 0.48` |
| + positive-definite hat kernel (LP over positive-definite sequences) | `0.69` formalized (505 weights, 336 sub-cells, exact margin `0.0103·E`); `2/3` with 289 weights (`0.0114·E`); `0.6` with 49 weights (`0.0381·E`); `0.5` with 25 weights (`0.0965·E`) |
| true worst case, no prime terms before `log 2` | margin `≈ 0.56·E` at `L = log 2` |

The rest of the prime-free range needs positive-definiteness of the autocorrelation, not pointwise caps;
the hat-kernel certificate below supplies it and converges to the true margin as the grid refines.
Beyond `L = log 2` prime terms enter every window; positivity for every `L` is RH.

**Half-cap (`RHHalfCapV13`, `RHHalfCapGainV13`, `RHHalfCapClassV13`).** For a shift `u` beyond the
half-width the factors `f(v)` and `f(v+u)` live on opposite sides of the centre, so pointwise AM–GM
with the indicators of `(−∞, a]` and `(a, ∞)` halves the correlation cap. Used on `(r, 2r]` it gives
`halfGain(r) = κ + ½·cothTail(2r) − (3/2)·cothTail r + (r/2)e^{r/2} + 2λ(sinh r − 3 sinh(r/2))`, negative up
to `r ≈ 0.195`; formalized at `r = 11/64` with `halfGain ≤ −1/20` (true `≈ −0.1345`). This is the first
positive-definiteness-type input beyond the pointwise cap; the frontier table's `+ Cauchy–Schwarz`
row (`L ≈ 0.41` for the exact linear program) is the ceiling of this ingredient.

**Free threshold (`RHThresholdGainV13`, `RHThresholdClassV13`).** The multiplier `λ` need not change
sign at the half-width: with `λ = lamR t`, `t ≤ r`, the kernel is `≥ 0` on `(0, t]` and `≤ 0` beyond it;
`h` is bounded below by the full cap on `(t, r]` and by the half-cap on `(r, 2r]`. Closed form:
`thrGain(t, r) = κ + (t/2)e^{t/2} + lamR t·(2 sinh r + 2 sinh(r/2) − 8 sinh(t/2)) − 2 cothTail t + ½ cothTail r + ½ cothTail(2r)`,
`thrGain(r, r) = halfGain(r)`, optimal `t ≈ 0.78 r`, negative up to `r ≈ 0.204` (support `≈ 0.409`).
Formalized at `t = 5/32`, `r = 1/5`: `thrGain ≤ −1/100` (true `≈ −0.0237`), so every moment-zero packet
of log-support length `≤ 2/5` is Weil-positive. The three-cell Boas–Kac cap `‖logCorrelation g u‖ ≤ E/√2`
for `2r/3 < u ≤ r` (pointwise weighted AM–GM on cells of length `u`) would add `≈ 0.007` to the
support length; the full Boas–Kac family gives the `≈ 0.48` row of the table.

**Bonus and three-cell cap (`RHBonusGainV13`, `RHBonusClassV13`, `RHThreeCellV13`, `RHThreeCellGainV13`,
`RHThreeCellClassV13`).** On the pieces where `h` is bounded below, the majorants had dropped
`−c·E·(e^{u/2} − 1)/sinh u`; for `0 < u ≤ 1` it is `≤ −c·E/2` (`half_le_bonus`, equivalent to
`(x² − 2x − 1)(x − 1)² ≤ 0` for `x = e^{u/2} ≤ 2`). Keeping it gives `bonusGain(t, r) = thrGain(t, r) − (r − t)/2 − r/4`,
formalized at `r = 21/100` (`≤ −1/50`). The three-cell cap `‖logCorrelation g u‖ ≤ (71/100)·E` for `2r < 3u`
(`three_cell_logCorrelation`: cut the support into cells of length `u` at `a − r + u`, `a − r + 2u`; weights
`50/71` and `71/200` with product `1/4`) is used, relaxed to `3/4`, both as an upper bound on `(2r/3, t]` and as
a lower bound on `(t, r]`; with rational coefficients the four `cothTail` terms combine into
`(1/16)·log(2⁷³·X_r⁴X_{2r}⁸/(X_s³X_t²⁵)) − (73/16)·log 2`. Formalized at `t = 5/32`, `r = 7/32`:
`cellGain ≤ −1/200` (closed form `≈ −0.0182`), so every moment-zero packet of log-support length `≤ 7/16` is
Weil-positive. Closed-form ceiling of this ingredient set `≈ 0.223` in `r`; the remaining Boas–Kac cells
(`cos(π/(n+2))` caps) reach `≈ 0.24`; beyond that the pointwise-cap route ends.

**Positive-definite hat kernel (`RHHatPosDefV13`, `RHHatKernelV13`, `RHHatBudgetV13`, `RHHatCellsV13`,
`RHHatClassV13`, `RHHatClass310V13`, `RHHatClass13V13`, `RHHatCellsWideV13`, `RHHatClass69200V13`).**
Pointwise caps ignore that `c(u) = Re C(u)` is positive definite. For block averages
`aᵢ(s) = ∫_{(0,h]} G(s + ih + t) dt` one has `∫ |Σ vᵢ aᵢ(s)|² ds = Σᵢⱼ vᵢvⱼ ∫ c(u)·T_h(u − (i−j)h) du`
(two Fubini swaps, a translation and the overlap length of two intervals), so every piecewise-linear
interpolant `hatK` of a positive-definite sequence `ρ_k = Σⱼ v_{j+k}vⱼ` pairs nonnegatively with `c`.
Subtracting `σ·c·hatK` together with the moment multiplier leaves the integrand
`−E/sinh u + c(u)·Q(u)`; where `Q ≥ 0`, the caps bound it by
`−(1 − cap)E/sinh u + cap·E·(1/2 + u/8 − 2λcosh(u/2) + σ·hatK(u))` (`w_upper`: `(e^{u/2} − 1)/sinh u ≤ 1/2 + u/8`).
Each certificate comes from a linear program over `(λ, ρ)` with `ρ̂(θ) ≥ 0`, a spectral factor `v` (Fejér–Riesz
roots for 25 and 49 weights, cepstral minimum-phase factor for 289 and 505) rounded to integers (scale `10³`, `σ = 10⁻⁶`), and exact rational checks: `Q ≥ 0` sub-cell by sub-cell
(`Q_of_checks`, one `interval_cases`/`norm_num` sweep), kernel integrals as exact trapezoid sums, and the gain.
`r = 1/4`: `h = 1/24`, 25 weights, `λ = 11511/5000`, 48 sub-cells (minimum `0.018`), margin `0.0965`, stated
as `≤ −1/20`. `r = 3/10`: `h = 1/40`, 49 weights, `λ = 21279/10000`, 192 sub-cells (minimum `0.0166`),
margin `0.0381`, stated as `≤ −1/50`. `r = 1/3`: `h = 1/72`, 289 weights (kernel support `6·2r`), `λ = 833/400`,
192 sub-cells (minimum `0.0141`), margin `0.0114`, stated as `≤ −1/100`; the 49 values `ρ_0 … ρ_48` are checked by
`decide +kernel` on integer sums. `r = 69/200`: `h = 23/2800`, 505 weights, `λ = 4113/2000`, 336 sub-cells through
`Q_of_checksW` (minimum `0.0182`), `cothTail` bounds with exponents up to `12`, margin `0.0103`, stated as `≤ −1/200`.
Numerical reach of the method (formal caps, fine-grid LP, `Q ≥ 0` enforced): margin `+0.19` at `L = 0.5` with 25
weights, `+0.045` at `L = 0.6` with 33, `+0.022` at `L = 2/3` with 289, `+0.0137` at `L = 0.68` with 361, `+0.0104` at
`L = 0.69` with 505 (true margin at `log 2`: `0.56·E`; the gap is grid and cap loss). Two exact losses were removed on the
way to `0.69`: the constant-term lift that makes the LP sequence positive definite (now `|min ρ̂| + 10⁻⁷ρ₀` on a
30 000-point grid instead of `10⁻³ρ₀`) and the `cothTail` bound (exponents up to `12` instead of `5`). The remaining
`0.0031` of the prime-free range is a grid-size question, not a new idea.

**Beyond `log 2` (numerics, not formalized).** The minimum of the Weil form over moment-zero `f` of support
length `L` (sine basis, exact digamma weight, prime terms included), in units of `E`: `0.555` at `log 2`,
`0.24` at `0.8`, `0.014` at `1.0`, `8·10⁻⁵` at `1.2`, `0` to working precision from `1.4` on. The extremal
functions have `f̂` nearly vanishing at the low zeta zeros: past `L ≈ 1.2` finite-window positivity is
numerically the same as knowing where the zeros are. The x-space form used in the formal budget reproduces
these values (`0.5596` at `log 2`).

**Hosted replay.** `tarikskalic33/formal-conjectures` PR #41, run 36146289581 (job 108108162762, real
GitHub runner), replayed the union closure of all seven V13 result targets (114 modules) at AEGIS
`559e2a7f` in the pinned FormalConjectures environment: 31 load-bearing theorems audited
`ALL_STANDARD_AXIOMS_ONLY`; both conditional external-target theorems close Mathlib's
`RiemannHypothesis` under their hypotheses; the unconditional probe stops exactly at
`⊢ UniversalZeroQuadraticNonnegativeV10`. Artifact 10869549523, zip sha256
`a6bf52dd548d46160fc9537d3bc7edb3ee101e501c586f07f2ef6db3b759904c`. (`RHNineFacesV13` needed
`WeilWindowExhaustionV1`, absent from this branch until `559e2a7f`.)

Second hosted replay, same PR, commit `c38e87e7`: AEGIS pinned at `b5d63c23`, eighth target
`RHHalfCapClassV13`, union closure 117 modules, runs 36161489147 (push) and 36161496853 (pull_request) green;
38 theorems audited `ALL_STANDARD_AXIOMS_ONLY` (the 31 above plus the seven half-cap theorems); unconditional
probe again stops at `⊢ UniversalZeroQuadraticNonnegativeV10`. Artifact 10876657852, zip sha256
`28b2469a151b15b697314223b29cd511106775911faa9df0e4fcc760fc76e963`. The runner's source hashes of the
three half-cap modules equal the locally compiled ones. The `1/5` class (`RHThresholdClassV13`, pushed after
this pin) is not yet hosted-replayed.

Third hosted replay, same PR, commit `9abc47e1`: AEGIS pinned at `2dc728bc`, ninth target `RHThresholdClassV13`,
union closure 119 modules, runs 36163799929 (push) and 36163804885 (pull_request) green; 42 theorems audited
`ALL_STANDARD_AXIOMS_ONLY`; unconditional probe stops at `⊢ UniversalZeroQuadraticNonnegativeV10`; runner hashes of
`RHThresholdGainV13`/`RHThresholdClassV13` equal the local ones. Artifact 10877786030, zip sha256
`a728cc5002128067e493bbcdc483613bfc68b84eb3922ffcd7782bd4f026ccab`.

Fourth hosted replay, same PR, commit `e0056214`: AEGIS pinned at `3082f57f`, targets `RHBonusClassV13` and
`RHThreeCellClassV13` added (eleven targets), union closure 124 modules, runs 36170422826 (push) and 36170427472
(pull_request) green; 50 theorems audited `ALL_STANDARD_AXIOMS_ONLY`, 0 `sorryAx`; unconditional probe stops at
`⊢ UniversalZeroQuadraticNonnegativeV10`; runner hashes of the five bonus/three-cell modules equal the local ones.
Artifact 10880947148, zip sha256 `461324760e97308f2adbc231d573966e4e509d8c3a348f4f01b2b71f04039cc7`.

Fifth hosted replay, same PR, commit `c582c30c`: AEGIS pinned at `5509580a`, targets `RHHatClassV13` and
`RHHatClass310V13` added (thirteen targets), union closure 130 modules, runs 36188674571 (push) and 36188680035
(pull_request) green; 63 theorems audited `ALL_STANDARD_AXIOMS_ONLY`, 0 `sorryAx`; unconditional probe stops at
`⊢ UniversalZeroQuadraticNonnegativeV10`; runner hashes of the six hat-kernel modules equal the local ones.
Artifact 10888106932, zip sha256 `5128b9ae055f6d960e0be185af8d9cc69770f2dbe2e38a5242af0450e42186d9`.

Sixth hosted replay, same PR, commit `ba62c035`: AEGIS pinned at `4026b6c8`, target `RHHatClass13V13` added (fourteen
targets), union closure 131 modules, runs 36205050289 (push) and 36205052790 (pull_request) green; 66 theorems audited
`ALL_STANDARD_AXIOMS_ONLY`, 0 `sorryAx`; unconditional probe stops at `⊢ UniversalZeroQuadraticNonnegativeV10`; runner
hashes of the seven hat-kernel modules equal the local ones (`RHHatClass13V13` = `902af511`). Artifact 10894590437, zip
sha256 `9c42305647caa4c5cde76b5b0e070b01a40c97c95b80aa562368dcee58082afb`. Same pin, hardened workflow (`64427279`: no duplicate
push run, `hat_coercive` audited, exactly 67 distinct declarations required, the unconditional probe's only error must be
`unsolved goals` with the single goal `UniversalZeroQuadraticNonnegativeV10`): run 36206490204 green, artifact 10894332351,
zip sha256 `811a08acd1f2c18a7c2d8aa7fa75e84b0f1cd5db152585cc4fe7faa208981222`.

Seventh hosted replay, same PR, commit `141bf5ed` (on top of `64427279`): AEGIS pinned at `514e4493`, target
`RHHatClass69200V13` added (fifteen targets), union closure 133 modules, run 36210491583 green; 72 distinct declarations
audited `ALL_STANDARD_AXIOMS_ONLY` (including `RHHatCellsWideV13.Q_of_checksW` and the four `RHHatClass69200V13`
producers), 0 `sorryAx`; the unconditional probe's only diagnostic is `unsolved goals ⊢ UniversalZeroQuadraticNonnegativeV10`;
runner hashes `RHHatCellsWideV13` = `6b047151`, `RHHatClass69200V13` = `1bea5d5f` equal the local ones. Artifact
10896312115, zip sha256 `e4e77b9cadf1bf5de895253e294337fac410e60a099bef7977660b46e19f0df0`.

**Other lanes (audit of 56 new modules, compiled at the pin).** One genuine extension:
`ten_packet_coercive_v1` (`research/rh-eleven-block-actual-bridge-v1`) — ten translates on the `33/16`
lattice at half-width `1/256`, standard axioms. `proof/rh-window-nine-over-64-globalization-v14`
certifies `momentGain(9/64) ≤ −1/10` on top of `moment_diagonal`. Nothing concludes an RH-equivalent
unconditionally; five modules (restricted-Weil continuation/resolvent/meromorphic/target-sign V13,
`RHSignedFourBlockRealityV1`) fail to compile at the pin; `WeilAbjadGramPositivityV1` exists on no branch.

**Why a density bridge cannot come from these ingredients alone.** Every finite-window proof above
uses only (i) vanishing of the terms at `n ≥ 2` on short windows and (ii) the Archimedean term. The
Davenport–Heilbronn function has an explicit formula of the same shape (a Gamma factor and terms
supported on `n ≥ 2`) and small-window Weil positivity of the same kind, yet zeros off the line. So no
argument that combines narrow-window positivity with continuity or linear algebra can reach
`UniversalZeroQuadraticNonnegativeV10`; it must use the Euler product. (Not formalized.)

**Collision scan (not formalized).** Over all ratios `q ∈ [2, 4]` with denominator `≤ 128`, the longest
run of prime-power-free gap windows `k·log q` is 5, 7, 8, 11, 11 at half-widths `1/64 … 1/1024`;
`33/16` attains the optimum 8 at `1/256`, the dyadic ratio collides at every gap, and unrestricted
shift sets found no larger families (9, 10, 12 packets at `1/256, 1/512, 1/1024`). Collision-free
families grow like `log(1/width)`, never densely at a fixed width.

## 4. Reproduce

```
python3 build2.py RHNinePacket33Over16V13     # expect rc=0 sorryAx=0 for all six V13 engine modules
python3 build2.py RHNarrowSupportPositivityV13 RHDyadicTowerV13   # expect rc=0 sorryAx=0
python3 build2.py RHMomentGainV13   # expect rc=0 sorryAx=0 for RHMomentIdentity/Pieces/Numerics/GainV13
python3 build2.py RHHalfCapClassV13  # expect rc=0 sorryAx=0 for RHHalfCapV13/GainV13/ClassV13
python3 build2.py RHThresholdClassV13  # expect rc=0 sorryAx=0 for RHThresholdGainV13/ClassV13
python3 build2.py RHBonusClassV13 RHThreeCellClassV13  # expect rc=0 sorryAx=0 for the five bonus/three-cell modules
python3 build2.py RHHatClassV13 RHHatClass310V13 RHHatClass13V13 RHHatClass69200V13  # expect rc=0 sorryAx=0 for the nine RHHat* modules
lean -R aegis_rh_extra aegis_rh_extra/NineFacesAcceptanceCheck.lean  # expect all six exact? to fail
```

Pushed blobs are byte-verified against the compiled sources:
`RHDyadicDiagonalV13` = `d80ebc02`, `RHDyadicWindowV13` = `37c33671`, `RHGramExpansionV13` = `684a7e8b`,
`RHRatioWindowV13` = `18f83dac`, `RHRatio33Over16V13` = `52ddda77`, `RHNinePacket33Over16V13` = `4534a689`,
plus the earlier `cda7c59f`, `7b00e26b`, `1dbb003a`, `5b169696`, `d770bc0c`, `75e8f3c9`, `e028cc83`, `19da141e`.
Hat-kernel modules (sha256, commit `68862ad8`): `RHHatPosDefV13` = `5bce3460`, `RHHatKernelV13` = `6bf08c81`,
`RHHatBudgetV13` = `9e407081`, `RHHatCellsV13` = `08d63064`, `RHHatClassV13` = `45e3434e`, `RHHatClass310V13` = `6c841393`;
isolated rebuild of their closure from the pushed sources: 89 modules, 0 `sorryAx`. `RHHatClass13V13` = `902af511`
(commit `023a3e82`; isolated rebuild with it: 90 modules, standard axioms only). `RHHatCellsWideV13` = `6b047151`,
`RHHatClass69200V13` = `1bea5d5f` (commit `6e40dfac`; isolated rebuild of its closure: 89 modules, standard axioms only).

## 5. Honest one-line summary

The Weil-type criterion `RH ↔ UniversalZeroQuadraticNonnegativeV10` is formally closed in nine forms;
the RH-equivalent quadratic is kernel-verified nonnegative on the whole class of log-half-width `≤ 69/200`
(support length `≤ 0.69`, `99.5%` of the prime-free range, via the moment identity, the Cauchy–Schwarz and three-cell caps, and a positive-definite
hat-kernel certificate that goes past the pointwise-cap ceiling `≈ 0.24`; hosted-replayed through FormalConjectures
up to the `≤ 69/200` class), on a 9-parameter `33/16` family per narrow seed, and on `(N+1)`-parameter
dyadic families for every `N` (`dyadic_tower`), via one generic Toeplitz/Gram engine whose reach grows
without bound as the packet narrows. RH itself is open; the repository contains no proof of it.
