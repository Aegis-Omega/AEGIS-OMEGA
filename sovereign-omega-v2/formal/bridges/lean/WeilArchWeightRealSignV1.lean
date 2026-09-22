import Mathlib.Analysis.Real.Pi.Bounds
import Mathlib.Analysis.SpecialFunctions.Gamma.BohrMollerup
import Mathlib.NumberTheory.Harmonic.GammaDeriv
import Mathlib.Analysis.Convex.Deriv
import Mathlib.Tactic

/-!
AEGIS Ω — the real archimedean weight is negative at the bottom of the range.

`WeilArchTailWeightSignV1` proved that the sign of the weighted Archimedean
Gram integral is carried entirely by the weight hypothesis `hw`, and recorded
the sign of the ACTUAL zeta weight as `ARCH_WEIGHT_SIGN_LOW_RANGE_OPEN`.
This module discharges the real half of that obligation.

WHAT IS PROVED

With `psi = (log Gamma)'` on the positive reals, and the weight written

  archWeightRealV1 x = psi x - log pi,

`arch_weight_real_neg_at_quarter` proves `archWeightRealV1 (1/4) < 0`.

`1/4` is the Gamma argument at spectral parameter `T = 0`, i.e. the bottom of
the archimedean range.  So the weight is NOT nonnegative there, and `hw` of
`weil_arch_weighted_tail_quadratic_nonnegative_v1` cannot be discharged for the
real weight on any window whose Gamma argument reaches `1/4`.

The proof needs no numerical evaluation and no series expansion:

  * `log Gamma` is convex on `Ioi 0` (`Real.convexOn_log_Gamma`), and is
    differentiable there, so `psi` is monotone on `Ioi 0`
    (`ConvexOn.monotoneOn_deriv`).  Hence `psi (1/4) <= psi (1/2)`.
  * `psi (1/2) = -(gamma + 2 log 2)`, computed from Mathlib's real
    `hasDerivAt_Gamma_one_half` and `Gamma (1/2) = sqrt pi`.
  * `gamma > 1/2` and `log 2 > 0`, so `psi (1/2) < 0`; and `log pi > 0`.

WHAT REMAINS

One piece, narrower than what the original marker anticipated:
`ARCH_WEIGHT_DIGAMMA_OFREAL_IDENTIFICATION_OPEN`.  This file works with
`deriv (log ∘ Real.Gamma)` on the reals.  Identifying that with
`Re (Complex.digamma (1/4 + i*T/2))` at `T = 0` needs a real-to-complex
transfer for `logDeriv Gamma`, which Mathlib does not expose at the pinned
commit.  Until that is added, the statement here is about the real
log-derivative of Gamma, not literally about `Complex.digamma`.

Nothing about the full archimedean term, the explicit formula, the global Weil
sign or RH follows.  AUTHORITY_EFFECT = NONE.
-/

open Real Set

set_option autoImplicit false

noncomputable section

/-- The real archimedean spectral weight at `T = 0`, written without any
complex digamma: `psi x - log pi` with `psi = (log Gamma)'`. -/
def archWeightRealV1 (x : ℝ) : ℝ :=
  deriv (Real.log ∘ Real.Gamma) x - Real.log Real.pi

/-- `log ∘ Gamma` is differentiable at every positive real. -/
theorem differentiableAt_log_Gamma_of_pos {x : ℝ} (hx : 0 < x) :
    DifferentiableAt ℝ (Real.log ∘ Real.Gamma) x := by
  have hG : DifferentiableAt ℝ Real.Gamma x :=
    Real.differentiableAt_Gamma (fun m => by
      have : (0:ℝ) ≤ (m : ℝ) := m.cast_nonneg
      nlinarith [hx])
  exact (Real.differentiableAt_log (ne_of_gt (Real.Gamma_pos_of_pos hx))).comp x hG

/-- `psi (1/2) = -(gamma + 2 log 2)`, from Mathlib's real Gamma derivative. -/
theorem deriv_log_Gamma_one_half :
    deriv (Real.log ∘ Real.Gamma) (1/2) =
      -(Real.eulerMascheroniConstant + 2 * Real.log 2) := by
  have hsp : Real.sqrt Real.pi ≠ 0 := by positivity
  have hG : Real.Gamma (1/2) = Real.sqrt Real.pi := Real.Gamma_one_half_eq
  have hd : HasDerivAt Real.Gamma
      (-Real.sqrt Real.pi * (Real.eulerMascheroniConstant + 2 * Real.log 2)) (1/2) :=
    Real.hasDerivAt_Gamma_one_half
  have hne : Real.Gamma (1/2) ≠ 0 := by rw [hG]; exact hsp
  have hlog := hd.log hne
  have hval : deriv (fun y => Real.log (Real.Gamma y)) (1/2)
      = (-Real.sqrt Real.pi *
          (Real.eulerMascheroniConstant + 2 * Real.log 2)) / Real.Gamma (1/2) :=
    hlog.deriv
  rw [Function.comp_def, hval, hG]
  field_simp

/-- `psi (1/2) < 0`. -/
theorem deriv_log_Gamma_one_half_neg :
    deriv (Real.log ∘ Real.Gamma) (1/2) < 0 := by
  rw [deriv_log_Gamma_one_half]
  have hg : 1/2 < Real.eulerMascheroniConstant := Real.one_half_lt_eulerMascheroniConstant
  have hl : 0 < Real.log 2 := Real.log_pos (by norm_num)
  linarith

/-- `psi` is monotone on the positive reals, by convexity of `log Gamma`. -/
theorem monotoneOn_deriv_log_Gamma :
    MonotoneOn (deriv (Real.log ∘ Real.Gamma)) (Ioi (0:ℝ)) :=
  Real.convexOn_log_Gamma.monotoneOn_deriv
    (fun _ hx => differentiableAt_log_Gamma_of_pos hx)

/-- **The real archimedean weight is negative at the bottom of the range.**
Therefore the nonnegative-weight hypothesis of
`weil_arch_weighted_tail_quadratic_nonnegative_v1` is false there, and by
`weil_arch_weighted_tail_quadratic_nonpositive_v1` the conclusion reverses. -/
theorem arch_weight_real_neg_at_quarter : archWeightRealV1 (1/4) < 0 := by
  have h14 : (1/4 : ℝ) ∈ Ioi (0:ℝ) := by norm_num
  have h12 : (1/2 : ℝ) ∈ Ioi (0:ℝ) := by norm_num
  have hle : deriv (Real.log ∘ Real.Gamma) (1/4) ≤ deriv (Real.log ∘ Real.Gamma) (1/2) :=
    monotoneOn_deriv_log_Gamma h14 h12 (by norm_num)
  have hneg := deriv_log_Gamma_one_half_neg
  have hpi : 0 < Real.log Real.pi := Real.log_pos (by linarith [Real.pi_gt_three])
  unfold archWeightRealV1
  linarith

#print axioms archWeightRealV1
#print axioms differentiableAt_log_Gamma_of_pos
#print axioms deriv_log_Gamma_one_half
#print axioms deriv_log_Gamma_one_half_neg
#print axioms monotoneOn_deriv_log_Gamma
#print axioms arch_weight_real_neg_at_quarter
