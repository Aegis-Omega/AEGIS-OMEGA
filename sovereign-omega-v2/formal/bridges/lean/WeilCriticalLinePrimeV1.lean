import WeilMellinInversionV1
import WeilAutocorrelationMellinV11
import Mathlib.Tactic

/-!
AEGIS Ω — autocorrelation values on the critical line (prime half of the bridge).

Mellin inversion on the line σ = 1/2 together with the V11 factorization gives,
for every x > 0,

  A_g(x) = (1/2π) ∫ x^{-(1/2+it)} |Mg(1/2+it)|² dt.

Evaluated at x = m and x = 1/m this is the critical-line form of the repository
prime term Λ(m)·(A_g(m) + A_g(1/m)/m), the arithmetic half of the bridge to the
Krein t-form.  No sign, positivity, or RH claim is made.  AUTHORITY_EFFECT = NONE.
-/

open Complex MeasureTheory
open scoped ComplexConjugate

set_option autoImplicit false
noncomputable section

namespace AEGIS.WeilCriticalLinePrimeV1

open AEGIS.WeilAutocorrelationMellinV11

theorem one_sub_conj_critical_v1 (t : ℝ) :
    (1 : ℂ) - conj (((1 / 2 : ℝ) : ℂ) + (t : ℂ) * I) =
      ((1 / 2 : ℝ) : ℂ) + (t : ℂ) * I := by
  apply Complex.ext <;> norm_num

/-- Autocorrelation Mellin transform on the critical line is a squared modulus. -/
theorem autocorrelation_mellin_critical_v1 (g : WeilCompactSmoothGV1) (t : ℝ) :
    mellin (WeilAutocorrelationV1 g) (((1 / 2 : ℝ) : ℂ) + (t : ℂ) * I) =
      (Complex.normSq (mellin g.1 (((1 / 2 : ℝ) : ℂ) + (t : ℂ) * I)) : ℂ) := by
  rw [weil_autocorrelation_mellin_factorization_v11, one_sub_conj_critical_v1,
    Complex.mul_conj]

/-- Critical-line inversion formula for an autocorrelation packet. -/
theorem autocorrelation_critical_line_inversion_v1
    (g : WeilCompactSmoothGV1) {x : ℝ} (hx : 0 < x) :
    WeilAutocorrelationV1 g x =
      (1 / (2 * Real.pi) : ℂ) *
        ∫ t : ℝ, (x : ℂ) ^ (-(((1 / 2 : ℝ) : ℂ) + (t : ℂ) * I)) *
          (Complex.normSq (mellin g.1 (((1 / 2 : ℝ) : ℂ) + (t : ℂ) * I)) : ℂ) := by
  have h := weil_compact_smooth_mellin_inversion_v1
    (WeilAutocorrelationCompactSmoothV1 g) (1 / 2) hx
  change mellinInv (1 / 2) (mellin (WeilAutocorrelationV1 g)) x =
    WeilAutocorrelationV1 g x at h
  rw [← h]
  unfold mellinInv
  simp only [autocorrelation_mellin_critical_v1, smul_eq_mul]
  rw [Complex.real_smul]
  push_cast
  ring

end AEGIS.WeilCriticalLinePrimeV1

#print axioms AEGIS.WeilCriticalLinePrimeV1.autocorrelation_mellin_critical_v1
#print axioms AEGIS.WeilCriticalLinePrimeV1.autocorrelation_critical_line_inversion_v1
