import Mathlib.Analysis.MellinTransform

open MeasureTheory Set Filter Asymptotics TopologicalSpace
open Real
open Complex hiding exp log
open scoped Topology

variable {E : Type*} [NormedAddCommGroup E]

/-- A continuous compactly-supported function whose topological support is contained in `(0, ∞)`
has an entire Mellin transform. -/
theorem mellin_differentiableAt_of_hasCompactSupport [NormedSpace ℂ E] {f : ℝ → E}
    (hfc : Continuous f) (hfs : HasCompactSupport f)
    (hf0 : tsupport f ⊆ Ioi 0) (s : ℂ) :
    DifferentiableAt ℂ (mellin f) s := by
  have hloc : LocallyIntegrableOn f (Ioi 0) :=
    hfc.locallyIntegrable.locallyIntegrableOn (Ioi 0)

  have htop0 : f =ᶠ[atTop] 0 := by
    have h := hfs
    rw [hasCompactSupport_iff_eventuallyEq, Filter.coclosedCompact_eq_cocompact] at h
    exact h.filter_mono _root_.atTop_le_cocompact
  have htop : f =O[atTop] (fun t : ℝ => t ^ (-(s.re + 1))) :=
    htop0.trans_isBigO (isBigO_zero _ _)

  have hzero : (0 : ℝ) ∉ tsupport f := by
    intro h
    have h' : (0 : ℝ) < 0 := by
      simpa only [mem_Ioi] using hf0 h
    exact (lt_irrefl 0) h'
  have hbot0 : f =ᶠ[𝓝[>] 0] 0 :=
    (notMem_tsupport_iff_eventuallyEq.mp hzero).filter_mono nhdsWithin_le_nhds
  have hbot : f =O[𝓝[>] 0] (fun t : ℝ => t ^ (-(s.re - 1))) :=
    hbot0.trans_isBigO (isBigO_zero _ _)

  exact mellin_differentiableAt_of_isBigO_rpow
    hloc htop (by linarith) hbot (by linarith)
