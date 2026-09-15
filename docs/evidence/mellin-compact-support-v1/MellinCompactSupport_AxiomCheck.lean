import Mathlib.Analysis.MellinTransform

-- Mirrors the open-context of Mathlib/Analysis/MellinTransform.lean exactly.
open MeasureTheory Set Filter Asymptotics TopologicalSpace
open Real
open Complex hiding exp log
open scoped Topology

variable {E : Type*} [NormedAddCommGroup E]

/-- If `f` is continuous with compact support contained in the open half-line `Ioi 0`, then its
Mellin transform converges for every `s : ℂ`. -/
theorem mellinConvergent_of_hasCompactSupport [NormedSpace ℂ E] {f : ℝ → E}
    (hfc : Continuous f) (hfs : HasCompactSupport f)
    (hf0 : tsupport f ⊆ Ioi 0) (s : ℂ) :
    MellinConvergent f s := by
  have hts :
      tsupport (fun t : ℝ => (t : ℂ) ^ (s - 1) • f t) ⊆ Ioi 0 :=
    (tsupport_smul_subset_right
      (fun t : ℝ => (t : ℂ) ^ (s - 1)) f).trans hf0
  have hcontOn :
      ContinuousOn (fun t : ℝ => (t : ℂ) ^ (s - 1) • f t) (Ioi 0) := by
    intro t ht
    exact
      ((continuousAt_ofReal_cpow_const t (s - 1)
        (Or.inr (ne_of_gt ht))).smul hfc.continuousAt).continuousWithinAt
  have hcont :
      Continuous (fun t : ℝ => (t : ℂ) ^ (s - 1) • f t) :=
    hcontOn.continuous_of_tsupport_subset isOpen_Ioi hts
  have hcompact :
      HasCompactSupport (fun t : ℝ => (t : ℂ) ^ (s - 1) • f t) :=
    hfs.smul_left
  rw [MellinConvergent]
  exact (hcont.integrable_of_hasCompactSupport hcompact).integrableOn

#print axioms mellinConvergent_of_hasCompactSupport
