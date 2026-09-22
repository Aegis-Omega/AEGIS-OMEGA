import WeilArchWeightRealSignV1
import Mathlib.Analysis.SpecialFunctions.Gamma.Digamma
import Mathlib.Analysis.SpecialFunctions.Gamma.Deriv
import Mathlib.Analysis.Complex.RealDeriv

/-!
AEGIS Ω — the ACTUAL zeta archimedean weight is negative at `T = 0`.

`WeilArchWeightRealSignV1` proved negativity for the real surrogate
`deriv (log ∘ Real.Gamma)` and left one obligation,
`ARCH_WEIGHT_DIGAMMA_OFREAL_IDENTIFICATION_OPEN`: identifying that with
`Re (Complex.digamma …)`.  This module closes it, so the statement is now
literally about the weight as written in `WeilArchTailIntegralV1`'s header.

THE BRIDGE

`digamma_re_ofReal`: for real `x > 0`,
`(Complex.digamma x).re = deriv (Real.log ∘ Real.Gamma) x`.

Mathlib's own transfer helper for this is `private`
(`HasDerivAt.complex_of_real`, `Mathlib/NumberTheory/Harmonic/GammaDeriv.lean`),
so the argument is reproduced from its public ingredients:
`Complex.Gamma_ofReal`, `HasDerivAt.comp_ofReal`, `HasDerivAt.ofReal_comp`,
`HasDerivAt.unique`, `HasDerivAt.congr_deriv`.

WHAT IS PROVED

`arch_weight_digamma_neg_at_zero : archWeightDigammaV1 0 < 0`, where
`archWeightDigammaV1 T = Re (digamma (1/4 + i*T/2)) - log pi`.

So `hw` of `weil_arch_weighted_tail_quadratic_nonnegative_v1` is FALSE at
`T = 0` for the real zeta weight, and by
`weil_arch_weighted_tail_quadratic_nonpositive_v1` the conclusion reverses
there.  The weighted tail theorem cannot be extended to a window reaching
`T = 0`.

WHAT THIS DOES NOT DO

Only the single point `T = 0` is covered.  Negativity on a whole low-`T`
interval is not proved here, nor is the identification of the weighted
integral with the complete archimedean term, nor the explicit formula, nor
the global Weil sign, nor RH.  AUTHORITY_EFFECT = NONE.
-/

noncomputable section

/-- Real-to-complex bridge for the log-derivative of Gamma: on the positive
reals, the real part of `Complex.digamma` is the real log-derivative. -/
theorem digamma_re_ofReal {x : ℝ} (hx : 0 < x) :
    (Complex.digamma (x : ℂ)).re = deriv (Real.log ∘ Real.Gamma) x := by
  have hne : ∀ m : ℕ, x ≠ -(m : ℝ) := fun m =>
    ((neg_nonpos.mpr (Nat.cast_nonneg m)).trans_lt hx).ne'
  have hR : HasDerivAt Real.Gamma (deriv Real.Gamma x) x :=
    (Real.differentiableAt_Gamma hne).hasDerivAt
  have hd : DifferentiableAt ℂ Complex.Gamma (x : ℂ) := by
    refine Complex.differentiableAt_Gamma _ fun m => ?_
    simp_rw [← Complex.ofReal_natCast, ← Complex.ofReal_neg, Ne, Complex.ofReal_inj]
    exact hne m
  have hC : HasDerivAt Complex.Gamma ((deriv Real.Gamma x : ℝ) : ℂ) (x : ℂ) := by
    have h1 := hd.hasDerivAt.comp_ofReal
    rw [funext Complex.Gamma_ofReal] at h1
    exact HasDerivAt.congr_deriv hd.hasDerivAt (h1.unique hR.ofReal_comp)
  rw [Complex.digamma_def, logDeriv_apply, hC.deriv, Complex.Gamma_ofReal,
    ← Complex.ofReal_div, Complex.ofReal_re, Function.comp_def]
  exact ((hR.log (Real.Gamma_pos_of_pos hx).ne').deriv).symm

/-- The ACTUAL zeta archimedean spectral weight, as written in the header of
`WeilArchTailIntegralV1`: `Re (digamma (1/4 + i*T/2)) - log pi`. -/
def archWeightDigammaV1 (T : ℝ) : ℝ :=
  (Complex.digamma (1/4 + Complex.I * (T : ℂ) / 2)).re - Real.log Real.pi

/-- **The actual zeta archimedean weight is negative at `T = 0`.**  Hence the
nonnegative-weight hypothesis of
`weil_arch_weighted_tail_quadratic_nonnegative_v1` cannot be discharged on a
window reaching `T = 0`, and by
`weil_arch_weighted_tail_quadratic_nonpositive_v1` the conclusion reverses. -/
theorem arch_weight_digamma_neg_at_zero : archWeightDigammaV1 0 < 0 := by
  have harg : (1/4 + Complex.I * ((0:ℝ) : ℂ) / 2) = (((1/4 : ℝ)) : ℂ) := by
    push_cast
    simp
  have hq : (0:ℝ) < 1/4 := by norm_num
  unfold archWeightDigammaV1
  rw [harg, digamma_re_ofReal hq]
  have := arch_weight_real_neg_at_quarter
  unfold archWeightRealV1 at this
  linarith

#print axioms digamma_re_ofReal
#print axioms archWeightDigammaV1
#print axioms arch_weight_digamma_neg_at_zero
