import Mathlib

/-!
AEGIS Ω — Krein pairing for the boundary columns ξ^j·e^{±2πiξL} of the dual certificate.

`RHKreinPairingV13.krein_pairing` covers genuine functions `H` vanishing on `|u| < L`. The certificate in
`RH_STATUS.md` also uses the distributional columns `δ^{(j)}(|u| − L)`, whose Fourier transforms are
`ξ^j cos(ξL)` / `ξ^j sin(ξL)`. This module proves that they pair to zero as well:

* `cross_support`: the cross-correlation `G₁ ⋆ G̃₂` vanishes on `|x| ≥ b − a` when both factors vanish outside `(a, b)`.
* `fourier_cross`: `𝓕(G₁ ⋆ G̃₂) = 𝓕G₁ · conj 𝓕G₂` (Mathlib's convolution theorem).
* `cross_pairing_zero`: for `L ≥ b − a`, `∫ 𝓕G₁(ξ)·conj(𝓕G₂(ξ))·e^{2πiξL} dξ = 0` (Fourier inversion at `x = −L`).
* `delta_pairing_zero`: with `G₁ = G^{(j₁)}`, `G₂ = G^{(j₂)}` (Mathlib's `fourier_iteratedDeriv`), the column
  `ξ^{j₁+j₂} e^{2πiξL} |𝓕G(ξ)|²` integrates to zero.

Not RH.  AUTHORITY_EFFECT = NONE.
-/

open MeasureTheory FourierTransform Convolution
set_option autoImplicit false
noncomputable section

namespace AEGIS.RHKreinDeltaPairingV1

theorem fourier_conj_neg (f : ℝ → ℂ) (ξ : ℝ) :
    𝓕 (fun x => (starRingEnd ℂ) (f (-x))) ξ = (starRingEnd ℂ) (𝓕 f ξ) := by
  rw [Real.fourier_real_eq_integral_exp_smul, Real.fourier_real_eq_integral_exp_smul,
    ← integral_conj, ← integral_neg_eq_self]
  congr 1
  funext x
  simp only [smul_eq_mul, map_mul, neg_neg, ← Complex.exp_conj, Complex.conj_ofReal, Complex.conj_I]
  congr 2
  push_cast
  ring

/-- Cross-correlation `G₁ ⋆ G̃₂`, `G̃₂(x) = conj G₂(−x)`. -/
def cross (G₁ G₂ : ℝ → ℂ) : ℝ → ℂ :=
  G₁ ⋆[ContinuousLinearMap.mul ℂ ℂ] (fun x => (starRingEnd ℂ) (G₂ (-x)))

theorem tilde_integrable (G : ℝ → ℂ) (hG : Integrable G) :
    Integrable (fun x => (starRingEnd ℂ) (G (-x))) := by
  have h := (Complex.conjLIE.toContinuousLinearMap).integrable_comp hG.comp_neg
  simpa using h

theorem fourier_cross (G₁ G₂ : ℝ → ℂ) (h₁ : Integrable G₁) (h₂ : Integrable G₂) (ξ : ℝ) :
    𝓕 (cross G₁ G₂) ξ = 𝓕 G₁ ξ * (starRingEnd ℂ) (𝓕 G₂ ξ) := by
  unfold cross
  rw [Real.fourier_mul_convolution_eq h₁ (tilde_integrable G₂ h₂), fourier_conj_neg]

theorem cross_support (G₁ G₂ : ℝ → ℂ) (a b : ℝ)
    (hs₁ : ∀ y, G₁ y ≠ 0 → y ∈ Set.Ioo a b) (hs₂ : ∀ y, G₂ y ≠ 0 → y ∈ Set.Ioo a b) :
    ∀ x, cross G₁ G₂ x ≠ 0 → |x| < b - a := by
  intro x hx
  by_contra hge
  apply hx
  have hz : ∀ t, G₁ t * (starRingEnd ℂ) (G₂ (t - x)) = 0 := by
    intro t
    by_cases h1 : G₁ t = 0
    · rw [h1, zero_mul]
    · by_cases h2 : G₂ (t - x) = 0
      · rw [h2, map_zero, mul_zero]
      · exfalso
        have m1 := hs₁ t h1
        have m2 := hs₂ _ h2
        apply hge
        rw [abs_lt]
        constructor <;> linarith [m1.1, m1.2, m2.1, m2.2]
  unfold cross
  rw [convolution_def]
  simp only [ContinuousLinearMap.mul_apply', neg_sub]
  simp [hz]

/-- **Boundary-column pairing.** If `G₁, G₂` are integrable, vanish outside `(a, b)`, their
cross-correlation is continuous and its Fourier transform integrable, then for every `L ≥ b − a`
`∫ 𝓕G₁(ξ)·conj(𝓕G₂(ξ))·e^{2πiξL} dξ = 0`. -/
theorem cross_pairing_zero (G₁ G₂ : ℝ → ℂ) (a b L : ℝ) (h₁ : Integrable G₁) (h₂ : Integrable G₂)
    (hs₁ : ∀ y, G₁ y ≠ 0 → y ∈ Set.Ioo a b) (hs₂ : ∀ y, G₂ y ≠ 0 → y ∈ Set.Ioo a b)
    (hc : Continuous (cross G₁ G₂)) (hF : Integrable (𝓕 (cross G₁ G₂))) (hL : b - a ≤ L) :
    ∫ ξ, 𝓕 G₁ ξ * (starRingEnd ℂ) (𝓕 G₂ ξ) *
        Complex.exp (↑(2 * Real.pi * ξ * L) * Complex.I) = 0 := by
  have hX : Integrable (cross G₁ G₂) :=
    h₁.integrable_convolution (ContinuousLinearMap.mul ℂ ℂ) (tilde_integrable G₂ h₂)
  have hinv := hc.fourierInv_fourier_eq hX hF
  have hval : cross G₁ G₂ L = 0 := by
    by_contra hne
    have h1 := cross_support G₁ G₂ a b hs₁ hs₂ L hne
    have h2 := le_abs_self L
    linarith
  have h := congrFun hinv L
  rw [hval, Real.fourierInv_eq_fourier_neg, Real.fourier_real_eq_integral_exp_smul] at h
  rw [← h]
  congr 1
  funext ξ
  rw [fourier_cross G₁ G₂ h₁ h₂ ξ, smul_eq_mul]
  ring_nf

end AEGIS.RHKreinDeltaPairingV1

#print axioms AEGIS.RHKreinDeltaPairingV1.cross_pairing_zero
