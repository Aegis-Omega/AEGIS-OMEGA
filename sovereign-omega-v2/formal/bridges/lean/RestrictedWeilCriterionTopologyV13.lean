import Mathlib.NumberTheory.LSeries.ZetaZeros
import Mathlib.Analysis.Normed.Module.Connected
import Mathlib.Tactic

/-!
AEGIS Omega -- restricted-Weil right-half-plane topology V13.

This module isolates one purely topological obligation in the final
restricted-Weil implication to Mathlib's RiemannHypothesis.

Let P be the centered image of every Mathlib Riemann-zeta zero:
  w in P <-> 1/2 - w in riemannZetaZeros.

The open right half-plane with P removed is path-connected.  We deliberately
remove all zeta zeros, including the trivial ones; the actual zero resolvent
has poles only at a subset, so this stronger puncturing is harmless for the
later identity-theorem step.

No sign theorem and no RH conclusion is asserted here.

AUTHORITY_EFFECT = NONE
RH = NOT_PROVEN
-/

open Set Complex

set_option autoImplicit false
noncomputable section

namespace AEGIS.RestrictedWeilCriterionTopologyV13

def CenteredRiemannZeroSetV13 : Set ℂ :=
  {w : ℂ | (1 / 2 : ℂ) - w ∈ riemannZetaZeros}

def RightHalfMinusCenteredZerosV13 : Set ℂ :=
  {w : ℂ | 0 < w.re} \ CenteredRiemannZeroSetV13

def rightHalfParamV13 (z : ℂ) : ℂ :=
  Complex.ofReal (Real.exp z.re) + Complex.ofReal z.im * I

theorem riemann_zeta_zeros_countable_v13 :
    riemannZetaZeros.Countable :=
  isClosed_riemannZetaZeros.isLindelof.countable_of_isDiscrete
    isDiscrete_riemannZetaZeros

theorem centered_riemann_zero_set_countable_v13 :
    CenteredRiemannZeroSetV13.Countable := by
  change
    ((fun w : ℂ => (1 / 2 : ℂ) - w) ⁻¹' riemannZetaZeros).Countable
  apply riemann_zeta_zeros_countable_v13.preimage
  intro a b h
  linear_combination -h

theorem centered_riemann_zero_set_closed_v13 :
    IsClosed CenteredRiemannZeroSetV13 := by
  change IsClosed ((fun w : ℂ => (1 / 2 : ℂ) - w) ⁻¹' riemannZetaZeros)
  exact isClosed_riemannZetaZeros.preimage (by fun_prop)

theorem right_half_minus_centered_zeros_open_v13 :
    IsOpen RightHalfMinusCenteredZerosV13 := by
  have hhalf : IsOpen {w : ℂ | 0 < w.re} :=
    Complex.continuous_re.isOpen_preimage (Ioi (0 : ℝ)) isOpen_Ioi
  exact hhalf.sdiff centered_riemann_zero_set_closed_v13

theorem rightHalfParam_re_v13 (z : ℂ) :
    (rightHalfParamV13 z).re = Real.exp z.re := by
  simp [rightHalfParamV13, Complex.ofReal_re]

theorem rightHalfParam_im_v13 (z : ℂ) :
    (rightHalfParamV13 z).im = z.im := by
  simp [rightHalfParamV13, Complex.ofReal_im]

theorem rightHalfParam_continuous_v13 :
    Continuous rightHalfParamV13 := by
  unfold rightHalfParamV13
  fun_prop

theorem rightHalfParam_injective_v13 :
    Function.Injective rightHalfParamV13 := by
  intro z w h
  have hre := congrArg Complex.re h
  have him := congrArg Complex.im h
  rw [rightHalfParam_re_v13, rightHalfParam_re_v13] at hre
  rw [rightHalfParam_im_v13, rightHalfParam_im_v13] at him
  have hre' : z.re = w.re := Real.exp_injective hre
  apply Complex.ext
  · exact hre'
  · exact him

theorem rightHalfParam_mem_right_half_v13 (z : ℂ) :
    0 < (rightHalfParamV13 z).re := by
  rw [rightHalfParam_re_v13]
  exact Real.exp_pos _

theorem rightHalfParam_surjective_right_half_v13
    {w : ℂ} (hw : 0 < w.re) :
    ∃ z : ℂ, rightHalfParamV13 z = w := by
  refine ⟨(Real.log w.re : ℂ) + (w.im : ℂ) * I, ?_⟩
  apply Complex.ext
  · simp [rightHalfParamV13, Real.exp_log hw]
  · simp [rightHalfParamV13]

theorem image_param_compl_centered_eq_v13 :
    rightHalfParamV13 ''
        (rightHalfParamV13 ⁻¹' CenteredRiemannZeroSetV13)ᶜ =
      RightHalfMinusCenteredZerosV13 := by
  ext w
  constructor
  · rintro ⟨z, hz, rfl⟩
    constructor
    · exact rightHalfParam_mem_right_half_v13 z
    · intro hbad
      exact hz hbad
  · intro hw
    have hhalf : 0 < w.re := hw.1
    obtain ⟨z, hz⟩ := rightHalfParam_surjective_right_half_v13 hhalf
    refine ⟨z, ?_, hz⟩
    intro hpre
    apply hw.2
    simpa [hz] using hpre

theorem right_half_minus_centered_zeros_pathConnected_v13 :
    IsPathConnected RightHalfMinusCenteredZerosV13 := by
  let S : Set ℂ :=
    rightHalfParamV13 ⁻¹' CenteredRiemannZeroSetV13
  have hS : S.Countable := by
    dsimp [S]
    exact centered_riemann_zero_set_countable_v13.preimage
      rightHalfParam_injective_v13
  have hpc : IsPathConnected Sᶜ :=
    hS.isPathConnected_compl_of_one_lt_rank (by
      simp only [rank_real_complex, Nat.one_lt_ofNat])
  have himg :=
    hpc.image rightHalfParam_continuous_v13
  dsimp [S] at himg
  rw [image_param_compl_centered_eq_v13] at himg
  exact himg

theorem right_half_minus_centered_zeros_preconnected_v13 :
    IsPreconnected RightHalfMinusCenteredZerosV13 :=
  right_half_minus_centered_zeros_pathConnected_v13.isConnected.isPreconnected

end AEGIS.RestrictedWeilCriterionTopologyV13

#print axioms AEGIS.RestrictedWeilCriterionTopologyV13.riemann_zeta_zeros_countable_v13
#print axioms AEGIS.RestrictedWeilCriterionTopologyV13.centered_riemann_zero_set_countable_v13
#print axioms AEGIS.RestrictedWeilCriterionTopologyV13.rightHalfParam_injective_v13
#print axioms AEGIS.RestrictedWeilCriterionTopologyV13.right_half_minus_centered_zeros_pathConnected_v13
#print axioms AEGIS.RestrictedWeilCriterionTopologyV13.right_half_minus_centered_zeros_preconnected_v13
