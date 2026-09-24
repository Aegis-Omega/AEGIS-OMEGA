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

`RiemannHypothesis` is Mathlib's own definition
(`∀ s, riemannZeta s = 0 → ¬(∃ n : ℕ, s = -2 * (n + 1)) → s ≠ 1 → s.re = 1 / 2`).

## 2. What is NOT proved — the single open target

```
UniversalZeroQuadraticNonnegativeV10 :=
  ∀ g : WeilCompactSmoothGV1, WeilMomentConditionsV1 g →
    0 ≤ (∑' rho : RiemannNontrivialZeroIndexV2,
           WeilZeroIndexSummandV1 (WeilAutocorrelationV1 g) rho).re
```

By §1 this proposition is logically equivalent to RH. §1 proves it on a 4-parameter family per
narrow seed (dyadic, width 1/64) and on a 9-parameter family per narrow seed (ratio 33/16, width
1/256); it is open for general `g`. Proving it for all `g` from the arithmetic side is the entire
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

## 4. Reproduce

```
python3 build2.py RHNinePacket33Over16V13     # expect rc=0 sorryAx=0 for all six V13 engine modules
lean -R aegis_rh_extra aegis_rh_extra/NineFacesAcceptanceCheck.lean  # expect all six exact? to fail
```

Pushed blobs are byte-verified against the compiled sources:
`RHDyadicDiagonalV13` = `d80ebc02`, `RHDyadicWindowV13` = `37c33671`, `RHGramExpansionV13` = `684a7e8b`,
`RHRatioWindowV13` = `18f83dac`, `RHRatio33Over16V13` = `52ddda77`, `RHNinePacket33Over16V13` = `4534a689`,
plus the earlier `cda7c59f`, `7b00e26b`, `1dbb003a`, `5b169696`, `d770bc0c`, `75e8f3c9`, `e028cc83`, `19da141e`.

## 5. Honest one-line summary

The Weil-type criterion `RH ↔ UniversalZeroQuadraticNonnegativeV10` is formally closed in nine forms;
the RH-equivalent quadratic is kernel-verified nonnegative on a 4-parameter dyadic family and on a
9-parameter `33/16` family per narrow seed, via one generic Toeplitz/Gram engine whose reach grows
without bound as the packet narrows. RH itself is open; the repository contains no proof of it.
